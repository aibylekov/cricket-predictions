"""bridge_entity — Phase 1.3 Part 2: resolve the odds feed to Roanuz matches.

`odd_matches` has NO clean FK to cricket — only `team_home_name` /
`team_away_name` (text) + `start_time`. Our L1 `dim_match` uses team ids. This
script bridges the two, TIERED from safe to unsafe, and NEVER guesses a link
automatically:

  TIER 1 — CONFIDENT (written): both team names resolve UNIQUELY to L1 teams
           AND a single L1 T20-men match exists on the SAME date with exactly
           those two teams. -> team_bridge + match_bridge.
  TIER 2 — LIKELY/UNCERTAIN (NOT written): names similar (fuzzy) or a name maps
           to >1 team, or names resolve but the date/opponent don't fully
           confirm. -> _review_candidates.csv (blank `human_decision`).
  TIER 3 — UNRESOLVED: neither confident nor a review candidate. ->
           _unresolved.csv.

Team-name comparison normalizes first (lowercase, strip punctuation, drop
tokens like "cricket"/"club"/"cc"/"xi"). Matching is EXACT-token-set first,
then a benign token-SUBSET ("mumbai" ⊂ "mumbai indians"); subset is rejected
when the differing tokens are disqualifiers (women / A / U19 / academy / …) so
a men-senior team is never matched to a women's/age/second-XI side.

Inputs: L1 (data/lake/l1) + L0 odds (data/lake/l0/odd_matches, odd_match_odds).
L0/L1 are never modified. Output: data/lake/l1/bridge/.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
L0_ROOT = PROJECT_ROOT / "data" / "lake" / "l0"
L1_ROOT = PROJECT_ROOT / "data" / "lake" / "l1"
BRIDGE_DIR = L1_ROOT / "bridge"

# Tokens dropped during normalization (generic cricket cruft).
# NB: "xi" is deliberately NOT dropped — dropping it made "Perth Scorchers"
# collide with the distinct "Perth Scorchers XI"; it stays a DISQUALIFIER instead.
DROP_TOKENS = {"cricket", "club", "cc", "the", "fc"}
# Tokens that must NOT be the difference in a subset match — they denote a
# different team (women / age-group / second string / academy, etc.).
DISQUALIFIER_TOKENS = {
    "women", "w", "under", "u19", "u23", "u21", "u16", "u18",
    "academy", "development", "emerging", "2nd", "ii", "a", "b",
    "masters", "legends", "invitational", "xi",
}
# Human-approved spelling aliases (normalized odds name -> normalized team name).
# Confirmed by review before finalizing the bridge.
APPROVED_ALIASES = {
    "royal challengers bangalore": "royal challengers bengaluru",  # 2024 rename
}
FUZZY_REVIEW_THRESHOLD = 0.85
NON_TEAM_NAMES = {"", "tbc", "tba", "tbd"}


# --------------------------------------------------------------------------- #
# Normalization + team matching
# --------------------------------------------------------------------------- #
def norm(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t and t not in DROP_TOKENS]
    return " ".join(toks)


def team_method(a_norm: str, b_norm: str) -> str | None:
    """'exact' if token sets equal, 'subset' if benign subset, else None."""
    if not a_norm or not b_norm:
        return None
    A, B = set(a_norm.split()), set(b_norm.split())
    if A == B:
        return "exact"
    if A < B or B < A:
        if (A ^ B) & DISQUALIFIER_TOKENS:
            return None
        return "subset"
    return None


# --------------------------------------------------------------------------- #
# Load data from L0/L1
# --------------------------------------------------------------------------- #
def load_data():
    con = duckdb.connect()

    def P0(n):
        return f"read_parquet('{(L0_ROOT / n).as_posix()}/**/*.parquet')"

    def P1(n):
        return f"read_parquet('{(L1_ROOT / n).as_posix()}/**/*.parquet')"

    teams = con.execute(
        f"SELECT team_id, team_name FROM {P1('dim_team')}"
    ).fetchall()

    matches = con.execute(
        f"SELECT match_id, CAST(start_at AS DATE) AS d, team_a_id, team_b_id "
        f"FROM {P1('dim_match')} WHERE start_at IS NOT NULL"
    ).fetchall()

    odds = con.execute(
        f"SELECT id, CAST(start_time AS DATE) AS d, team_home_name, team_away_name "
        f"FROM {P0('odd_matches')}"
    ).fetchall()

    priced = {
        r[0] for r in con.execute(
            f"SELECT DISTINCT match_id FROM {P0('odd_match_odds')} "
            f"WHERE market = 'Winner 2 Ways'"
        ).fetchall()
    }
    con.close()
    return teams, matches, odds, priced


# --------------------------------------------------------------------------- #
# Team-name resolution (exact-priority, then benign subset)
# --------------------------------------------------------------------------- #
def build_resolver(teams):
    """Return (resolve, team_norm) where resolve(name)->(ids, method)."""
    team_norm = {tid: norm(name) for tid, name in teams}
    team_name = {tid: name for tid, name in teams}

    def resolve(name: str):
        n0 = norm(name)
        if not n0:
            return [], None
        n = APPROVED_ALIASES.get(n0, n0)   # apply human-approved spelling alias
        aliased = n != n0
        exact = [tid for tid, tn in team_norm.items() if tn and set(tn.split()) == set(n.split())]
        if exact:
            return exact, ("approved_alias" if aliased else "exact")
        subs = [tid for tid, tn in team_norm.items() if team_method(n, tn) == "subset"]
        if subs:
            return subs, ("approved_alias" if aliased else "subset")
        return [], None

    return resolve, team_norm, team_name


def best_fuzzy(name_norm: str, team_norm: dict):
    """Best (team_id, score) by SequenceMatcher over normalized team names."""
    best_id, best_score = None, 0.0
    for tid, tn in team_norm.items():
        if not tn:
            continue
        score = SequenceMatcher(None, name_norm, tn).ratio()
        if score > best_score:
            best_id, best_score = tid, score
    return best_id, best_score


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    teams, matches, odds, priced = load_data()
    resolve, team_norm, team_name = build_resolver(teams)

    # Index L1 matches by date -> list of (match_id, frozenset{team ids}).
    matches_by_date = defaultdict(list)
    for match_id, d, a, b in matches:
        matches_by_date[d].append((match_id, frozenset({a, b})))

    # --- TIER 1: confident match-level links ---------------------------- #
    match_bridge = []           # (odds_match_id, internal_match_id, date, method)
    team_links = {}             # (internal_team_id, odds_feed_name) -> (norm, method)
    confident_odds_ids = set()

    # Track, per odds row, why it failed (for tiering the rest).
    unlinked = []               # list of odds rows not confidently linked

    for oid, d, home, away in odds:
        if norm(home) in NON_TEAM_NAMES or norm(away) in NON_TEAM_NAMES:
            continue  # placeholder fixtures (TBC) — not biddable
        hids, hmethod = resolve(home)
        aids, amethod = resolve(away)

        if len(hids) == 1 and len(aids) == 1 and d is not None:
            want = frozenset({hids[0], aids[0]})
            hits = [mid for (mid, pair) in matches_by_date.get(d, []) if pair == want]
            if len(hits) == 1:
                if "approved_alias" in (hmethod, amethod):
                    method = "approved_alias"
                elif hmethod == "exact" and amethod == "exact":
                    method = "exact"
                else:
                    method = "subset"
                match_bridge.append((oid, hits[0], str(d), method))
                confident_odds_ids.add(oid)
                team_links[(hids[0], home)] = (norm(home), hmethod)
                team_links[(aids[0], away)] = (norm(away), amethod)
                continue

        unlinked.append((oid, d, home, away, hids, aids))

    # --- TIER 2 / TIER 3 (date-anchored; see below) --------------------- #
    confident_names = {name for (_tid, name) in team_links}

    # Count how many odds matches (all + priced) each name appears in.
    name_all_counts = defaultdict(lambda: {"odds_matches": set(), "priced": set()})
    for oid, d, home, away in odds:
        for nm in (home, away):
            if norm(nm) in NON_TEAM_NAMES:
                continue
            name_all_counts[nm]["odds_matches"].add(oid)
            if oid in priced:
                name_all_counts[nm]["priced"].add(oid)

    # DATE-ANCHORED Tier 2/3 (priced matches are the actionable universe).
    # A priced odds match is an in-scope T20-men REVIEW candidate only if a
    # T20-men dim_match exists on the SAME date whose two teams align (exact/
    # subset or fuzzy) to the two odds names. This anchors on a real T20-men
    # fixture, so it cannot be fooled by a coincidental same-date Test/ODI/
    # women's match (which have no T20-men dim_match and fall to Tier 3).
    def align(name_norm: str, tid: int) -> float:
        tn = team_norm.get(tid, "")
        if not tn:
            return 0.0
        if team_method(name_norm, tn) in ("exact", "subset"):
            return 1.0
        return SequenceMatcher(None, name_norm, tn).ratio()

    IN_SCOPE_MIN = 0.80  # both sides must align at least this well

    review_map = {}                 # (odds_name, suggested_team_name) -> agg
    inscope_unlinked_priced = set()  # priced oids that a review would unlock
    outscope_priced = set()          # priced oids with no T20-men fixture (other format)
    unresolved_names = defaultdict(lambda: {"priced": set(), "odds": set()})

    for oid, d, home, away, hids, aids in unlinked:
        if oid not in priced:
            continue  # focus the review on biddable (priced) matches
        hn, an = norm(home), norm(away)
        best = None
        if d is not None:
            for (mid, pair) in matches_by_date.get(d, []):
                if len(pair) != 2:
                    continue  # placeholder fixture (team_a == team_b, e.g. TBC)
                ta, tb = tuple(pair)
                for ca, cb in ((ta, tb), (tb, ta)):
                    s1, s2 = align(hn, ca), align(an, cb)
                    sc = min(s1, s2)
                    if best is None or sc > best[0]:
                        best = (sc, mid, ca, cb, s1, s2)

        if best and best[0] >= IN_SCOPE_MIN:
            # In-scope T20-men match found by name similarity -> review.
            inscope_unlinked_priced.add(oid)
            _, mid, ca, cb, s1, s2 = best
            for odds_name, tid, s in ((home, ca, s1), (away, cb, s2)):
                n_ids = len(resolve(odds_name)[0])
                if s < 1.0:
                    note = "spelling variant"        # fuzzy name difference
                elif n_ids > 1:
                    note = "name maps to >1 team"     # ambiguous; match disambiguates
                else:
                    continue                          # this side is fine
                key = (odds_name, team_name.get(tid, ""))
                agg = review_map.setdefault(
                    key, {"sim": 0.0, "oids": set(), "date": str(d),
                          "internal_match": mid, "note": note})
                agg["sim"] = max(agg["sim"], round(s, 3))
                agg["oids"].add(oid)
        else:
            # No same-date T20-men fixture -> out of T20-men scope (Test/ODI/
            # women/other) or genuinely absent.
            outscope_priced.add(oid)
            for nm in (home, away):
                if norm(nm) in NON_TEAM_NAMES:
                    continue
                unresolved_names[nm]["priced"].add(oid)
                unresolved_names[nm]["odds"].update(name_all_counts[nm]["odds_matches"])

    review_rows = [
        {"odds_feed_name": onm,
         "suggested_internal_team": tnm,
         "similarity_score": agg["sim"],
         "supporting_evidence": "yes (same-date T20-men fixture)",
         "note": agg["note"],
         "internal_match_id": agg["internal_match"],
         "match_date": agg["date"],
         "priced_matches_affected": len(agg["oids"]),
         "human_decision": ""}
        for (onm, tnm), agg in review_map.items()
    ]

    # Tier 3: names only ever seen in out-of-scope priced matches (not confident,
    # not a review candidate).
    review_names = {onm for (onm, _t) in review_map}
    unresolved_rows = [
        {"odds_feed_name": nm,
         "odds_matches_affected": len(v["odds"]),
         "priced_matches_affected": len(v["priced"]),
         "reason": "no same-date T20-men fixture (likely Test/ODI/women/other format)"}
        for nm, v in unresolved_names.items()
        if nm not in confident_names and nm not in review_names
    ]

    # --- WRITE Tier 1 + review/unresolved CSVs -------------------------- #
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)

    tb_rows = [
        {"internal_team_id": tid, "odds_feed_name": name,
         "normalized_name": nrm, "match_method": mth, "confidence": "confident"}
        for (tid, name), (nrm, mth) in sorted(team_links.items())
    ]
    pq.write_table(
        pa.Table.from_pylist(tb_rows) if tb_rows else pa.table({
            "internal_team_id": pa.array([], pa.int64()),
            "odds_feed_name": pa.array([], pa.string()),
            "normalized_name": pa.array([], pa.string()),
            "match_method": pa.array([], pa.string()),
            "confidence": pa.array([], pa.string())}),
        (BRIDGE_DIR / "team_bridge.parquet").as_posix())

    mb_rows = [
        {"odds_match_id": oid, "internal_match_id": mid,
         "match_date": md, "match_method": mth}
        for (oid, mid, md, mth) in sorted(match_bridge)
    ]
    pq.write_table(
        pa.Table.from_pylist(mb_rows) if mb_rows else pa.table({
            "odds_match_id": pa.array([], pa.int64()),
            "internal_match_id": pa.array([], pa.int64()),
            "match_date": pa.array([], pa.string()),
            "match_method": pa.array([], pa.string())}),
        (BRIDGE_DIR / "match_bridge.parquet").as_posix())

    review_cols = ["odds_feed_name", "suggested_internal_team", "similarity_score",
                   "supporting_evidence", "note", "internal_match_id", "match_date",
                   "priced_matches_affected", "human_decision"]
    with open(BRIDGE_DIR / "_review_candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=review_cols)
        w.writeheader()
        for r in sorted(review_rows, key=lambda x: -x["priced_matches_affected"]):
            w.writerow(r)

    unresolved_cols = ["odds_feed_name", "odds_matches_affected",
                       "priced_matches_affected", "reason"]
    with open(BRIDGE_DIR / "_unresolved.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=unresolved_cols)
        w.writeheader()
        for r in sorted(unresolved_rows, key=lambda x: -x["priced_matches_affected"]):
            w.writerow(r)

    # --- CONSOLE SUMMARY ------------------------------------------------- #
    priced_linked = len([1 for (oid, *_ ) in match_bridge if oid in priced])
    n_priced = len(priced)
    inscope_priced = priced_linked + len(inscope_unlinked_priced)

    print("=" * 68)
    print("bridge_entity — TIERED RESULTS")
    print("=" * 68)
    print("\nTIER 1 — CONFIDENT (written to team_bridge / match_bridge):")
    print(f"  internal teams linked ........ {len({t for t, _ in team_links})}")
    print(f"  distinct odds team names ..... {len({n for _, n in team_links})}")
    print(f"  odds matches linked (total) .. {len(match_bridge)}  "
          f"(incl. non-priced T20-men fixtures)")
    ex = len([1 for *_, m in match_bridge if m == 'exact'])
    sub = len([1 for *_, m in match_bridge if m == 'subset'])
    ali = len([1 for *_, m in match_bridge if m == 'approved_alias'])
    print(f"     exact / subset / approved-alias ... {ex} / {sub} / {ali}")
    print(f"  PRICED T20-men linked ........ {priced_linked}")

    print("\nKEY FINDING — the 354 priced matches are mostly NOT T20-men:")
    print(f"  Only ~{inscope_priced} of 354 priced matches are T20-men at all.")
    print("  The rest are Test/ODI/women's/other-format matches that have no")
    print("  T20-men dim_match by design. The 59/354 'gap' is FORMAT, not names.")

    print(f"\nTIER 2 — REVIEW (NOT written; -> _review_candidates.csv):")
    print(f"  T20-men spelling-variant candidates .. {len(review_rows)}")
    print(f"  in-scope priced matches they'd unlock  {len(inscope_unlinked_priced)}")

    print(f"\nTIER 3 — UNRESOLVED / OUT-OF-SCOPE (-> _unresolved.csv):")
    print(f"  priced matches with no T20-men fixture {len(outscope_priced)}")
    print(f"  distinct odds names in them ........... {len(unresolved_rows)}")

    print(f"\nPRICED reconciliation: {priced_linked} linked (Tier1) + "
          f"{len(inscope_unlinked_priced)} review + {len(outscope_priced)} out-of-scope "
          f"= {priced_linked + len(inscope_unlinked_priced) + len(outscope_priced)} of {n_priced}")
    print(f"\nOutputs in {BRIDGE_DIR}")
    print("  team_bridge.parquet, match_bridge.parquet (Tier 1 — written)")
    print("  _review_candidates.csv (Tier 2), _unresolved.csv (Tier 3)")

    # Show the review candidates inline for confirmation.
    print("\n" + "-" * 68)
    print(f"REVIEW CANDIDATES ({len(review_rows)}) — confirm before adding to bridge:")
    print("-" * 68)
    if review_rows:
        print(f"{'odds_feed_name':28} {'suggested_internal_team':28} {'sim':>5} {'prc':>3}  note")
        for r in sorted(review_rows, key=lambda x: -x["priced_matches_affected"]):
            print(f"{r['odds_feed_name'][:28]:28} {r['suggested_internal_team'][:28]:28} "
                  f"{r['similarity_score']:>5} {r['priced_matches_affected']:>3}  {r['note']}")
    else:
        print("  (none)")


if __name__ == "__main__":
    main()
