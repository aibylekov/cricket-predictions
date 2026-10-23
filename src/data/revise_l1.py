"""
revise_l1.py — L1 revision for two data-quality fixes found by the
consistency check. Reads L1, writes updated L1. NEVER touches L0.

Originals are backed up to data/lake/l1/_backup_pre_l2revision/ first, so the
revision is fully reversible.

FIX 1 — dim_venue dedupe (mirrors the dim_team dedupe convention: dim_match
        carries CANONICAL keys; a *_id_map keeps old -> canonical for external
        reference resolution).
   Two layers:
     (0) within-key collapse: dim_venue is 388 rows / 289 distinct venue_keys
         because 70 keys have duplicate rows differing only by city spelling
         (incl. junk like "Northern Ireland"). Collapse each key to one row.
     (1) cross-key merge: different venue_keys for the SAME physical ground.
         Match on normalized NAME; use city only as a light confirm/conflict
         signal (city data is unreliable). When name matches but cities
         conflict -> DO NOT merge; FLAG for review. Never merge known generic
         collisions (e.g. the "County Ground" family).

FIX 2 — league_key on dim_tournament: base name with season/year/format
        stripped, so IPL's 4 season ids share one league_key. tournament_id is
        left intact. Genuine same-season-same-start duplicates are FLAGGED, not
        merged.

Run:
  venv/Scripts/python.exe -m src.data.revise_l1
"""
from __future__ import annotations

import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
L1 = ROOT / "data" / "lake" / "l1"
BACKUP = L1 / "_backup_pre_l2revision"

DIM_VENUE = (L1 / "dim_venue" / "dim_venue.parquet")
DIM_MATCH = (L1 / "dim_match" / "dim_match.parquet")
DIM_TOURN = (L1 / "dim_tournament" / "dim_tournament.parquet")
VENUE_MAP = (L1 / "venue_id_map" / "venue_id_map.parquet")

# ---- generic ground names that legitimately repeat across different grounds:
# never auto-merge these on name alone.
GENERIC_NAMES = {"county ground", "tbc"}

# ---- user-approved manual merges the automatic pass (deliberately) flags but
# does NOT perform, because the name matches while the city differs. Format:
# canonical_key -> [member keys to fold into it].
#   Headingley: "Headingley" is a suburb of Leeds -> same ground (approved).
#   (Rajiv Gandhi Dehradun vs Hyderabad is confirmed as TWO grounds -> NOT here.)
MANUAL_MERGES = {
    "a-rz--headinv6wlv9": ["c__stadium__headingley_cricket_ground__a801e"],
    #   Junction Oval, St Kilda (women's T20s; approved 2026-10-23): three keys
    #   for one ground, cities compatible (St Kilda / St Kilda / country-level
    #   "Australia"). Canonical = the key carrying the ground's proper name
    #   (9 matches; "Cricket Victoria" has 10 but is the body, not the ground).
    "c__stadium__citipower_centre_junction_oval__d7b85": [
        "jjunctic4rv4v", "a-rz--joskm-3qwP"],
    #   Albert Park, Suva (women's T20s; approved 2026-10-23): "Albert Park" +
    #   "Albert Park 2, Suva", same city, 10 matches each.
    "a-rz--apalberty7vud5": ["a-rz--ap-nZO1"],
}

# ---- name-match pairs the editor asked to see as a CITY CONFLICT (not merged):
#   men's "Junction Oval" key carries city=Melbourne vs St Kilda on the women's
#   canonical key — same ground geographically, but the rule is: city conflict
#   -> flag, never auto-merge.
REVIEW_FLAGS = [
    ("junction oval (men's key, city=Melbourne vs St Kilda)",
     ["c__stadium__citipower_centre_junction_oval__d7b85",
      "c__stadium__junction_oval__cfc6a"]),
]

# ---- human-approved LEAGUE_KEY ALIASES (bridge_entity style): the same league
# under two spellings of its name across editions, which the year/format strip
# in base_league() cannot unify (apostrophe artifacts "women s" vs "womens",
# word order). member_key -> canonical_key, applied after base_league().
# Canonical = the apostrophe-free spelling, because payload._league_label
# builds labels from the key's initials and a stray "s" token breaks them
# ("women s caribbean premier league" -> "WSCPL"); for a word-order rename,
# the current edition's name. Mechanically checked at build time: every id
# under the merged key must carry ONE gender (abort otherwise), and an alias
# may not chain. Found by the 2026-10-23 league_key audit (men AND women;
# bilateral "X tour of Y" keys excluded - the host side differs). Approved
# 2026-10-23 (user: "consolidate the fragmented league_keys").
LEAGUE_KEY_ALIASES: dict[str, str] = {
    "women s vitality blast": "vitality blast women",
    "women s caribbean premier league": "womens caribbean premier league",
    "icc men s world cup warm up matches": "icc mens world cup warm up matches",
    "icc women s under world cup": "icc under womens world cup",
}
LEAGUE_KEY_ALIAS_EVIDENCE: dict[str, str] = {
    "women s vitality blast":
        "1093 'Women's Vitality Blast T20, 2025' (59 mt) = 1579 'Vitality Blast "
        "Women 2026' (57 mt): England women's tier 1; all 9 teams of 2025 play in "
        "2026 (+ Yorkshire Women). NOT 1582 'Vitality Blast Women League 2, 2026': "
        "0 shared teams (lower tier, own key 'vitality blast women league').",
    "women s caribbean premier league":
        "675/1220 'Women's Caribbean Premier League, 2024/2025' (7+7 mt) = 227 "
        "'Womens Caribbean Premier League 2023' (21 mt): same 3 franchises.",
    "icc men s world cup warm up matches":
        "1447 'ICC Men's T20 World Cup Warm-up Matches, 2026' (16 mt) = 588 'ICC "
        "Mens T20 World Cup Warm-up Matches 2024' (15 mt): consecutive editions.",
    "icc women s under world cup":
        "911 'ICC Women's Under 19 T20 World Cup, 2025' (41 mt) = 912 'ICC Under 19 "
        "Womens T20 World Cup, 2025' (42 mt): SAME edition. The 41 fixtures are "
        "duplicated (same date, teams, venue) -> flagged below as a same-season "
        "duplicate for a separate drop decision; the key merge itself is safe.",
}


def apply_league_aliases(tf: pd.DataFrame) -> list[dict]:
    """Fold alias member keys into their canonical key (in place). Aborts on
    a chained alias or a merged key spanning two genders. Returns records."""
    chained = set(LEAGUE_KEY_ALIASES) & set(LEAGUE_KEY_ALIASES.values())
    if chained:
        raise SystemExit(f"LEAGUE_KEY_ALIASES chain: {sorted(chained)}")
    records = []
    for member, canon in LEAGUE_KEY_ALIASES.items():
        m_ids = tf.loc[tf["league_key"] == member, "tournament_id"].astype(int).tolist()
        c_ids = tf.loc[tf["league_key"] == canon, "tournament_id"].astype(int).tolist()
        gens = set(tf.loc[tf["league_key"].isin([member, canon]), "gender"].dropna())
        if len(gens) > 1:
            raise SystemExit(f"LEAGUE_KEY_ALIASES {member!r} -> {canon!r}: "
                             f"genders {sorted(gens)} - refusing a cross-gender merge")
        tf.loc[tf["league_key"] == member, "league_key"] = canon
        records.append({"member": member, "canonical": canon, "member_ids": m_ids,
                        "canonical_ids": c_ids, "gender": next(iter(gens), None),
                        "status": "applied" if m_ids and c_ids else "not_present",
                        "evidence": LEAGUE_KEY_ALIAS_EVIDENCE.get(member, "")})
    return records


# ---- confirmed duplicate tournament_ids to drop from L1 (matches + dim row).
#   956 = "Asian Legends League, 2025": a never-started schedule snapshot whose
#   early-round fixtures duplicate id 963 (the actually-played, completed copy).
#   All 15 rows are status=not_started / winner NULL (already inert for
#   aggregates); dropped to remove duplicate snapshot targets. 963 is kept.
DROP_TOURNAMENT_IDS = {956}

# ---- city values that carry no locational evidence (country/region-level or junk)
JUNK_CITY = {
    "", "none", "nan", "tbc",
    "northern ireland", "united kingdom", "uk", "england", "scotland", "wales",
    "india", "australia", "pakistan", "new zealand", "south africa", "sri lanka",
    "bangladesh", "west indies", "united arab emirates", "guyana",
}


def norm(s) -> str:
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def base_league(s) -> str:
    """Tournament base name: strip years, year-ranges, and t20/t20i tokens."""
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r"\b20\d{2}(\s*-\s*\d{2,4})?\b", " ", s)
    s = re.sub(r"\bt20i?\b", " ", s)
    s = re.sub(r"[^a-z ]+", " ", s)
    return " ".join(s.split())


def city_compat(a, b) -> bool:
    a, b = norm(a), norm(b)
    if a == b:
        return True
    if a in JUNK_CITY or b in JUNK_CITY:
        return True
    if a and b and (a in b or b in a):
        return True
    if a and b and SequenceMatcher(None, a, b).ratio() >= 0.85:
        return True
    return False


class UF:
    def __init__(self, items):
        self.p = {x: x for x in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


# --------------------------------------------------------------------------
def backup_originals():
    BACKUP.mkdir(parents=True, exist_ok=True)
    for p in [DIM_VENUE, DIM_MATCH, DIM_TOURN]:
        dst = BACKUP / p.name
        if not dst.exists():          # keep the FIRST (pre-revision) backup only
            shutil.copy2(p, dst)
    print(f"Backed up originals -> {BACKUP} (first-run snapshot kept)")


# --------------------------------------------------------------------------
# FIX 1 — venues
# --------------------------------------------------------------------------
def fix_venues(con):
    raw = con.execute(f"""
        SELECT venue_key, venue_name, city, country_code, country_name
        FROM read_parquet('{DIM_VENUE.as_posix()}')
    """).df()
    vcounts = dict(con.execute(f"""
        SELECT venue_key, COUNT(*) FROM read_parquet('{DIM_MATCH.as_posix()}')
        WHERE venue_key IS NOT NULL GROUP BY 1
    """).fetchall())

    # (0) within-key collapse: one representative row per venue_key
    by_key = defaultdict(list)
    for r in raw.itertuples():
        by_key[r.venue_key].append(r)

    def pick_city(vals):
        vals = [v for v in vals if v is not None and str(v) != ""]
        if not vals:
            return None
        real = [v for v in vals if norm(v) not in JUNK_CITY]
        pool = real if real else vals
        cnt = Counter(pool)               # most common, tiebreak shortest, alpha
        return sorted(cnt.items(),
                      key=lambda kv: (-kv[1], len(str(kv[0])), str(kv[0])))[0][0]

    def pick_name(vals):
        # Prefer the most SPECIFIC representative: drop ", <city>"-suffixed
        # variants when a comma-free form exists, then most-common, then LONGEST
        # (keeps discriminating words like "Cricket"), then alpha. This avoids a
        # key drifting into the wrong name-group on a spelling variant.
        vals = [v for v in vals if v is not None and str(v) != ""]
        if not vals:
            return None
        nocomma = [v for v in vals if "," not in str(v)]
        pool = nocomma if nocomma else vals
        cnt = Counter(pool)
        return sorted(cnt.items(),
                      key=lambda kv: (-kv[1], -len(str(kv[0])), str(kv[0])))[0][0]

    def pick_plain(vals):
        vals = [v for v in vals if v is not None and str(v) != ""]
        if not vals:
            return None
        cnt = Counter(vals)
        return sorted(cnt.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0]

    keys = {}          # venue_key -> dict(name, city, cc, country_name, mt)
    for k, rows in by_key.items():
        keys[k] = {
            "name": pick_name([r.venue_name for r in rows]),
            "city": pick_city([r.city for r in rows]),
            "cc": pick_plain([r.country_code for r in rows]),
            "country_name": pick_plain([r.country_name for r in rows]),
            "mt": vcounts.get(k, 0),
        }

    # (1) cross-key merge. Group keys by ANY shared normalized name-variant
    # (each key carries several spellings), so grouping does not depend on the
    # arbitrary choice of a single representative name.
    variants = {k: {norm(r.venue_name) for r in rows if norm(r.venue_name)}
                for k, rows in by_key.items()}
    uf_all = UF(list(keys))
    var_to_keys = defaultdict(list)
    for k, vs in variants.items():
        for v in vs:
            var_to_keys[v].append(k)
    for v, ks_ in var_to_keys.items():
        for other in ks_[1:]:
            uf_all.union(ks_[0], other)
    groups = defaultdict(list)
    for k in keys:
        groups[uf_all.find(k)].append(k)

    id_map = {}                       # old_key -> canonical_key
    merges = []                       # (canonical, [members]) auto-merged
    flagged = []                      # name-match-city-conflict (NOT merged)
    generic_skipped = []              # generic-name groups left distinct

    for _root, ks in groups.items():
        if len(ks) == 1:
            id_map[ks[0]] = ks[0]
            continue
        # representative name = picked name of the highest-match-count key
        rep_key = sorted(ks, key=lambda k: (-keys[k]["mt"], k))[0]
        nname = norm(keys[rep_key]["name"])
        group_variants = set().union(*(variants[k] for k in ks))
        if group_variants & GENERIC_NAMES:
            generic_skipped.append((nname, ks))
            for k in ks:
                id_map[k] = k
            continue

        # cluster keys by city compatibility
        uf = UF(ks)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                if city_compat(keys[ks[i]]["city"], keys[ks[j]]["city"]):
                    uf.union(ks[i], ks[j])
        clusters = defaultdict(list)
        for k in ks:
            clusters[uf.find(k)].append(k)

        if len(clusters) >= 3:
            # many distinct-city same-name grounds -> treat as generic/distinct
            generic_skipped.append((nname, ks))
            for k in ks:
                id_map[k] = k
            continue

        # merge within each cluster; flag across clusters (city conflict)
        canon_reps = []
        for members in clusters.values():
            canon = sorted(members, key=lambda k: (-keys[k]["mt"], k))[0]
            canon_reps.append(canon)
            for k in members:
                id_map[k] = canon
            if len(members) > 1:
                merges.append((canon, members))
        if len(clusters) >= 2:
            flagged.append((nname, canon_reps))

    # ---- apply user-approved MANUAL merges (override the city-conflict flag) ----
    manual = []
    for canon, members in MANUAL_MERGES.items():
        involved = set(members) | {canon}
        for m in members:
            # re-point m and anything currently pointing at m onto canon
            for k in list(id_map):
                if id_map[k] == m:
                    id_map[k] = canon
            id_map[m] = canon
        id_map[canon] = canon
        manual.append((canon, list(members)))
        # drop any flag that is now fully resolved to a single canonical
        flagged = [(nn, reps) for (nn, reps) in flagged
                   if not (set(reps) <= involved)]
    # editor-requested conflict flags (keys that still exist after the merges)
    for nname, ks in REVIEW_FLAGS:
        ks = [id_map.get(k, k) for k in ks if k in keys]
        if len(set(ks)) > 1:
            flagged.append((nname, sorted(set(ks))))

    # ---- build new dim_venue (one row per canonical key) ----
    canonical_keys = sorted(set(id_map.values()))
    new_rows = []
    merged_mt = defaultdict(int)
    for old, canon in id_map.items():
        merged_mt[canon] += keys[old]["mt"]
    for ck in canonical_keys:
        v = keys[ck]
        new_rows.append({
            "venue_key": ck, "venue_name": v["name"], "city": v["city"],
            "country_code": v["cc"], "country_name": v["country_name"],
        })
    new_venue = pd.DataFrame(new_rows)

    map_df = pd.DataFrame([
        {"old_key": o, "canonical_key": c, "is_remapped": o != c}
        for o, c in sorted(id_map.items())
    ])

    return new_venue, map_df, merges, manual, flagged, generic_skipped, keys, merged_mt


# --------------------------------------------------------------------------
# FIX 2 — league_key
# --------------------------------------------------------------------------
def fix_tournaments(con):
    tf = con.execute(f"""
        SELECT * FROM read_parquet('{DIM_TOURN.as_posix()}')
    """).df()
    tf["league_key"] = tf["tournament_name"].map(base_league)
    alias_records = apply_league_aliases(tf)

    tcounts = dict(con.execute(f"""
        SELECT CAST(tournament_id AS BIGINT), COUNT(*)
        FROM read_parquet('{DIM_MATCH.as_posix()}') GROUP BY 1
    """).fetchall())

    # same-season-same-start duplicates within a league (potential true dupes)
    dupes = []
    for lk, g in tf.groupby("league_key"):
        by_start = defaultdict(list)
        for r in g.itertuples():
            sd = None if pd.isna(r.start_date) else pd.Timestamp(r.start_date).date()
            by_start[sd].append(int(r.tournament_id))
        for sd, ids in by_start.items():
            if sd is not None and len(ids) > 1:
                dupes.append((lk, sd, ids))
    return tf, tcounts, dupes, alias_records


# --------------------------------------------------------------------------
def write_parquet(con, df, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con.register("_w", df)
    con.execute(f"COPY _w TO '{path.as_posix()}' (FORMAT PARQUET)")
    con.unregister("_w")


def main():
    con = duckdb.connect()
    backup_originals()

    # ---------- FIX 1 ----------
    (new_venue, map_df, merges, manual, flagged,
     generic, keys, merged_mt) = fix_venues(con)
    before_rows = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{DIM_VENUE.as_posix()}')").fetchone()[0]
    before_keys = con.execute(
        f"SELECT COUNT(DISTINCT venue_key) FROM read_parquet('{DIM_VENUE.as_posix()}')"
    ).fetchone()[0]

    # remap dim_match.venue_key -> canonical
    remap = {o: c for o, c in zip(map_df.old_key, map_df.canonical_key)}
    dm = con.execute(f"SELECT * FROM read_parquet('{DIM_MATCH.as_posix()}')").df()
    dm_before_keys = dm["venue_key"].nunique(dropna=True)
    dm["venue_key"] = dm["venue_key"].map(lambda k: remap.get(k, k) if pd.notna(k) else k)
    dm_after_keys = dm["venue_key"].nunique(dropna=True)

    # ---------- FIX 2 ----------
    tf, tcounts, dupes, alias_records = fix_tournaments(con)

    # ---------- FIX 3 — drop confirmed duplicate tournament(s) ----------
    dm_rows_before = len(dm)
    dm = dm[~dm["tournament_id"].astype("int64").isin(DROP_TOURNAMENT_IDS)].copy()
    dropped_matches = dm_rows_before - len(dm)
    tf = tf[~tf["tournament_id"].astype("int64").isin(DROP_TOURNAMENT_IDS)].copy()

    # ---------- WRITE updated L1 ----------
    write_parquet(con, new_venue, DIM_VENUE)
    write_parquet(con, map_df, VENUE_MAP)
    write_parquet(con, dm, DIM_MATCH)
    write_parquet(con, tf, DIM_TOURN)

    # ================= REPORT =================
    print("\n" + "=" * 74)
    print("FIX 1 — dim_venue dedupe")
    print("=" * 74)
    print(f"  dim_venue BEFORE : {before_rows} rows / {before_keys} distinct keys")
    print(f"  dim_venue AFTER  : {len(new_venue)} rows (one per canonical key)")
    print(f"    within-key row collapse : {before_rows} -> {before_keys}")
    print(f"    cross-key ground merges : {before_keys} -> {len(new_venue)} "
          f"({before_keys - len(new_venue)} keys merged away)")
    print(f"  dim_match venue_key distinct: {dm_before_keys} -> {dm_after_keys}")
    print(f"  venue_id_map rows: {len(map_df)} "
          f"({int(map_df.is_remapped.sum())} remapped)")

    print(f"\n  AUTO-MERGED grounds ({len(merges)}):")
    for canon, members in sorted(merges, key=lambda m: -merged_mt[m[0]]):
        others = [m for m in members if m != canon]
        print(f"    '{keys[canon]['name']}' (city={keys[canon]['city']}, "
              f"{merged_mt[canon]} mt)  canonical={canon}")
        for o in others:
            print(f"        + {o}  (city={keys[o]['city']}, {keys[o]['mt']} mt)")

    if manual:
        print(f"\n  MANUAL merges (user-approved; overrides city-conflict flag) "
              f"({len(manual)}):")
        for canon, members in manual:
            print(f"    '{keys[canon]['name']}' (city={keys[canon]['city']}, "
                  f"{merged_mt[canon]} mt)  canonical={canon}")
            for o in members:
                print(f"        + {o}  (city={keys[o]['city']}, {keys[o]['mt']} mt)")

    print(f"\n  >>> FLAGGED for YOUR review — name matches but CITY CONFLICTS "
          f"(NOT merged) ({len(flagged)}):")
    if not flagged:
        print("      (none)")
    for nname, reps in flagged:
        print(f"    '{nname}':")
        for k in reps:
            print(f"        key={k}  city={keys[k]['city']}  {keys[k]['mt']} mt")

    print(f"\n  Known-distinct / generic names left UNMERGED ({len(generic)}):")
    for nname, ks in generic:
        cities = ", ".join(sorted({str(keys[k]['city']) for k in ks}))
        print(f"    '{nname}' — {len(ks)} keys  [{cities}]")

    print("\n" + "=" * 74)
    print("FIX 2 — league_key on dim_tournament")
    print("=" * 74)
    n_ids = tf["tournament_id"].nunique()
    n_leagues = tf["league_key"].nunique()
    print(f"  {n_ids} tournament_ids  ->  {n_leagues} league_keys")
    multi = (tf.groupby("league_key")["tournament_id"].nunique()
               .loc[lambda s: s > 1])
    print(f"  {len(multi)} league_keys span >1 season/id.")
    print(f"\n  APPROVED league_key aliases ({len(alias_records)}):")
    for a in alias_records:
        print(f"    [{a['status']}] '{a['member']}' {a['member_ids']} -> "
              f"'{a['canonical']}' {a['canonical_ids']} ({a['gender']})")
        print(f"        evidence: {a['evidence']}")

    ipl = tf[tf.league_key == "indian premier league"]
    ipl_matches = int(sum(tcounts.get(int(i), 0) for i in ipl.tournament_id))
    print(f"\n  IPL check: league_key='indian premier league' groups "
          f"{ipl.tournament_id.nunique()} ids, {ipl_matches} T20-men matches")
    for r in ipl.sort_values("start_date").itertuples():
        print(f"    id={int(r.tournament_id):5d}  {r.tournament_name:32s} "
              f"{tcounts.get(int(r.tournament_id),0)} mt")

    print(f"\n  >>> FLAGGED same-season-same-start duplicate tournament_ids "
          f"(NOT merged) ({len(dupes)}):")
    if not dupes:
        print("      (none)")
    for lk, sd, ids in dupes:
        names = con.execute(f"""
            SELECT tournament_id, tournament_name FROM read_parquet('{DIM_TOURN.as_posix()}')
            WHERE tournament_id IN ({','.join(map(str, ids))})
        """).fetchall()
        print(f"    league='{lk}' start={sd}: {ids}")
        for tid, nm in names:
            print(f"        id={tid}  {nm}")

    print("\n" + "=" * 74)
    print("FIX 3 — drop confirmed duplicate tournament(s)")
    print("=" * 74)
    print(f"  dropped tournament_ids: {sorted(DROP_TOURNAMENT_IDS)}")
    print(f"  dim_match rows dropped : {dropped_matches} "
          f"({dm_rows_before} -> {len(dm)})")
    print(f"  dim_tournament rows    : removed {len(DROP_TOURNAMENT_IDS)} "
          f"(956 = Asian Legends never-started dup of 963; 963 kept)")

    con.close()
    print("\n(Updated L1 written. Remaining flagged items NOT finalized — awaiting review.)")


if __name__ == "__main__":
    main()
