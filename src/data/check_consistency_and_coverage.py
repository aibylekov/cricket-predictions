"""
check_consistency_and_coverage.py — READ-ONLY analysis of L1 + L2.

Detection only. Writes nothing, commits nothing, auto-merges nothing.

PART A — internal name consistency (our Roanuz-derived dims). The odds bridge
assumed OUR side was canonical, so we verify our own names are actually clean:
  A1 TEAMS       — fuzzy near-duplicate team names under different team_ids
  A2 VENUES      — same for grounds
  A3 TOURNAMENTS — fuzzy pairs AND (critically) per-season fragmentation:
                   is IPL one coherent group or split across season rows?

PART B — ball-by-ball coverage by tournament. Phase-rate features are NULL for
~half of L2 snapshots; this shows WHERE the rich ball-by-ball signal lives, so
we can confirm the top tournaments (IPL etc.) are well covered and only minor
leagues are sparse.

Run:
  venv/Scripts/python.exe -m src.data.check_consistency_and_coverage
"""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from pathlib import Path

import duckdb


def _s(v) -> str:
    """Safe string: None / NaN -> '' (pandas NaN is truthy, so `v or ''` fails)."""
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v)

ROOT = Path(__file__).resolve().parents[2]
L1 = ROOT / "data" / "lake" / "l1"

DIM_TEAM = (L1 / "dim_team" / "dim_team.parquet").as_posix()
DIM_VENUE = (L1 / "dim_venue" / "dim_venue.parquet").as_posix()
DIM_TOURNAMENT = (L1 / "dim_tournament" / "dim_tournament.parquet").as_posix()
DIM_MATCH = (L1 / "dim_match" / "dim_match.parquet").as_posix()
FACT = (L1 / "fact_ball_by_ball" / "fact_ball_by_ball.parquet").as_posix()

SIM_THRESHOLD = 0.80          # report pairs at or above this
LIKELY_SAME = 0.90            # >= this -> flagged "LIKELY SAME", else "REVIEW"


# --------------------------------------------------------------------------
# normalization helpers
# --------------------------------------------------------------------------
def norm_name(s) -> str:
    """lowercase, drop punctuation, collapse whitespace."""
    s = _s(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def base_tournament(s) -> str:
    """
    League 'base name' with season/format noise removed, so that
    'Indian Premier League 2023', 'Indian Premier League, 2024', ... all map
    to 'indian premier league'. Years, year-ranges (2024-25) and t20/t20i
    format tokens are stripped.
    """
    s = _s(s).lower()
    s = re.sub(r"\b20\d{2}(\s*-\s*\d{2,4})?\b", " ", s)   # 2024 / 2024-25
    s = re.sub(r"\bt20i?\b", " ", s)                       # t20 / t20i
    s = re.sub(r"[^a-z ]+", " ", s)                        # digits + punct
    return " ".join(s.split())


def similar(a: str, b: str) -> float:
    sm = SequenceMatcher(None, a, b)
    if sm.quick_ratio() < SIM_THRESHOLD:        # cheap upper-bound gate
        return 0.0
    return sm.ratio()


def fuzzy_pairs(items, threshold=SIM_THRESHOLD, block_key=None):
    """
    items: list of (id, display_name, norm_name, extra_dict)
    Returns pairs [(sim, a, b)] with norm-name similarity >= threshold and
    different ids. If block_key is given, only compare items whose block_key
    differs is allowed but we skip pairs sharing the SAME block value (used to
    suppress same-league season pairs for tournaments).
    """
    out = []
    n = len(items)
    for i in range(n):
        id_i, name_i, norm_i, extra_i = items[i]
        if not norm_i:
            continue
        for j in range(i + 1, n):
            id_j, name_j, norm_j, extra_j = items[j]
            if not norm_j or id_i == id_j:
                continue
            if block_key is not None and extra_i.get(block_key) == extra_j.get(block_key) \
                    and extra_i.get(block_key) != "":
                continue
            s = similar(norm_i, norm_j)
            if s >= threshold:
                out.append((s, items[i], items[j]))
    out.sort(key=lambda x: -x[0])
    return out


# --------------------------------------------------------------------------
# load reference counts
# --------------------------------------------------------------------------
def load(con):
    teams = con.execute(f"""
        SELECT CAST(team_id AS BIGINT) team_id, team_name, short_name, country_code
        FROM read_parquet('{DIM_TEAM}')
    """).df()
    venues = con.execute(f"""
        SELECT venue_key, venue_name, city, country_code
        FROM read_parquet('{DIM_VENUE}')
    """).df()
    tours = con.execute(f"""
        SELECT CAST(tournament_id AS BIGINT) tournament_id, tournament_name,
               short_name, slug, CAST(start_date AS DATE) start_date
        FROM read_parquet('{DIM_TOURNAMENT}')
    """).df()

    # T20-men match counts (dim_match is already the T20-men scope)
    team_counts = dict(con.execute(f"""
        WITH long AS (
            SELECT CAST(team_a_id AS BIGINT) tid FROM read_parquet('{DIM_MATCH}')
            UNION ALL
            SELECT CAST(team_b_id AS BIGINT) tid FROM read_parquet('{DIM_MATCH}')
        )
        SELECT tid, COUNT(*) FROM long GROUP BY tid
    """).fetchall())
    venue_counts = dict(con.execute(f"""
        SELECT venue_key, COUNT(*) FROM read_parquet('{DIM_MATCH}')
        WHERE venue_key IS NOT NULL GROUP BY venue_key
    """).fetchall())
    tour_counts = dict(con.execute(f"""
        SELECT CAST(tournament_id AS BIGINT), COUNT(*)
        FROM read_parquet('{DIM_MATCH}') GROUP BY 1
    """).fetchall())
    return teams, venues, tours, team_counts, venue_counts, tour_counts


# --------------------------------------------------------------------------
# PART A printers
# --------------------------------------------------------------------------
def part_a_teams(teams, team_counts):
    print("\n" + "=" * 78)
    print("PART A1 — TEAMS: fuzzy near-duplicate names under different team_ids")
    print("=" * 78)
    items = [
        (int(r.team_id), _s(r.team_name), norm_name(r.team_name),
         {"cc": _s(r.country_code)})
        for r in teams.itertuples()
    ]
    pairs = fuzzy_pairs(items)
    if not pairs:
        print("  none above %.2f" % SIM_THRESHOLD)
    print(f"  {len(pairs)} suspicious pair(s) >= {SIM_THRESHOLD:.2f}:\n")
    for s, a, b in pairs:
        ca = team_counts.get(a[0], 0)
        cb = team_counts.get(b[0], 0)
        same_cc = a[3]["cc"] == b[3]["cc"] and a[3]["cc"] != ""
        label = "LIKELY SAME" if (s >= LIKELY_SAME and same_cc) else "REVIEW"
        print(f"  [{label:11s} sim={s:.3f}] "
              f"'{a[1]}' (id={a[0]}, cc={a[3]['cc']}, {ca} mt)  <->  "
              f"'{b[1]}' (id={b[0]}, cc={b[3]['cc']}, {cb} mt)")


def part_a_venues(venues, venue_counts):
    print("\n" + "=" * 78)
    print("PART A2 — VENUES: fuzzy near-duplicate ground names under different keys")
    print("=" * 78)
    items = [
        (r.venue_key, _s(r.venue_name), norm_name(r.venue_name),
         {"city": _s(r.city)})
        for r in venues.itertuples()
    ]
    pairs = fuzzy_pairs(items)
    print(f"  {len(pairs)} suspicious pair(s) >= {SIM_THRESHOLD:.2f}:\n")
    for s, a, b in pairs:
        ca = venue_counts.get(a[0], 0)
        cb = venue_counts.get(b[0], 0)
        same_city = a[3]["city"].lower() == b[3]["city"].lower() and a[3]["city"] != ""
        label = "LIKELY SAME" if (s >= LIKELY_SAME and same_city) else "REVIEW"
        print(f"  [{label:11s} sim={s:.3f}] "
              f"'{a[1]}' (city={a[3]['city']}, {ca} mt)  <->  "
              f"'{b[1]}' (city={b[3]['city']}, {cb} mt)")
        print(f"                 keys: {a[0]}  |  {b[0]}")


def part_a_tournaments(tours, tour_counts):
    print("\n" + "=" * 78)
    print("PART A3 — TOURNAMENTS: per-season fragmentation + fuzzy variants")
    print("=" * 78)

    # ---- fragmentation: group by year/format-stripped base name ----
    groups = {}
    for r in tours.itertuples():
        base = base_tournament(r.tournament_name)
        groups.setdefault(base, []).append(r)
    frag = {b: rs for b, rs in groups.items() if len({x.tournament_id for x in rs}) > 1}

    print(f"\n  {len(frag)} league(s) span MULTIPLE tournament_ids "
          f"(per-season / duplicate rows).")
    print("  NOTE: L2 team_form 'tournament' window keys on tournament_id, so it")
    print("        currently groups WITHIN a single season only, not league-wide.\n")

    # sort groups by total T20-men match count desc; highlight IPL first
    def gcount(rs):
        return sum(tour_counts.get(int(x.tournament_id), 0) for x in rs)

    ordered = sorted(frag.items(), key=lambda kv: -gcount(kv[1]))
    for base, rs in ordered:
        rs_sorted = sorted(rs, key=lambda x: (x.start_date is None, x.start_date))
        tag = "  <<< IPL" if base == "indian premier league" else ""
        print(f"  '{base}'  — {len(rs_sorted)} ids, {gcount(rs)} T20-men matches{tag}")
        for x in rs_sorted:
            sd = x.start_date.isoformat() if x.start_date is not None else "?"
            print(f"       id={int(x.tournament_id):5d}  "
                  f"{str(x.tournament_name):42s} start={sd}  "
                  f"{tour_counts.get(int(x.tournament_id),0)} mt")
        print()

    # ---- fuzzy variants ACROSS different base names (real spelling drift) ----
    items = [
        (int(r.tournament_id), _s(r.tournament_name), norm_name(r.tournament_name),
         {"base": base_tournament(r.tournament_name)})
        for r in tours.itertuples()
    ]
    pairs = fuzzy_pairs(items, block_key="base")   # suppress same-league pairs
    print("  Fuzzy name pairs ACROSS different base leagues "
          f"(possible spelling drift), >= {SIM_THRESHOLD:.2f}: {len(pairs)}")
    for s, a, b in pairs[:40]:
        print(f"    [sim={s:.3f}] '{a[1]}' (id={a[0]})  <->  '{b[1]}' (id={b[0]})")


# --------------------------------------------------------------------------
# PART B — coverage
# --------------------------------------------------------------------------
def part_b_coverage(con):
    print("\n" + "=" * 78)
    print("PART B — ball-by-ball coverage by tournament (completed T20-men matches)")
    print("=" * 78)

    df = con.execute(f"""
        WITH balls AS (SELECT DISTINCT CAST(match_id AS BIGINT) match_id
                       FROM read_parquet('{FACT}')),
        m AS (
            SELECT CAST(m.match_id AS BIGINT) match_id,
                   CAST(m.tournament_id AS BIGINT) tournament_id,
                   (b.match_id IS NOT NULL) AS has_balls
            FROM read_parquet('{DIM_MATCH}') m
            LEFT JOIN balls b ON b.match_id = CAST(m.match_id AS BIGINT)
            WHERE m.winner IS NOT NULL          -- completed
        )
        SELECT t.tournament_id,
               t.tournament_name,
               COUNT(*)                                    AS completed,
               SUM(CASE WHEN m.has_balls THEN 1 ELSE 0 END) AS with_balls,
               ROUND(100.0*SUM(CASE WHEN m.has_balls THEN 1 ELSE 0 END)/COUNT(*),1) AS cov_pct
        FROM m
        JOIN read_parquet('{DIM_TOURNAMENT}') t
             ON CAST(t.tournament_id AS BIGINT) = m.tournament_id
        GROUP BY 1,2
        ORDER BY completed DESC, cov_pct DESC
    """).df()

    tot = int(df["completed"].sum())
    totb = int(df["with_balls"].sum())
    print(f"\n  {len(df)} tournaments · {tot:,} completed matches · "
          f"{totb:,} with ball-by-ball ({100*totb/tot:.1f}% overall)\n")
    print(f"  {'tournament':44s} {'compl':>6s} {'balls':>6s} {'cov%':>6s}")
    print("  " + "-" * 66)
    for r in df.head(40).itertuples():
        nm = (r.tournament_name or "")[:43]
        print(f"  {nm:44s} {int(r.completed):6d} {int(r.with_balls):6d} {r.cov_pct:6.1f}")

    # league-group rollup (year-stripped) for the fragmented leagues
    df2 = df.copy()
    df2["base"] = df2["tournament_name"].map(base_tournament)
    roll = (df2.groupby("base")
                .agg(ids=("tournament_id", "nunique"),
                     completed=("completed", "sum"),
                     with_balls=("with_balls", "sum"))
                .reset_index())
    roll["cov_pct"] = (100.0 * roll["with_balls"] / roll["completed"]).round(1)
    roll = roll.sort_values("completed", ascending=False)
    print("\n  --- league-group rollup (season ids merged by base name), top 20 ---")
    print(f"  {'league':40s} {'ids':>4s} {'compl':>6s} {'balls':>6s} {'cov%':>6s}")
    print("  " + "-" * 66)
    for r in roll.head(20).itertuples():
        nm = (r.base or "")[:39]
        print(f"  {nm:40s} {int(r.ids):4d} {int(r.completed):6d} "
              f"{int(r.with_balls):6d} {r.cov_pct:6.1f}")


# --------------------------------------------------------------------------
def main():
    con = duckdb.connect()
    teams, venues, tours, tc, vc, toc = load(con)
    print("Loaded L1 dims:", f"{len(teams)} teams,", f"{len(venues)} venues,",
          f"{len(tours)} tournaments.")
    part_a_teams(teams, tc)
    part_a_venues(venues, vc)
    part_a_tournaments(tours, toc)
    part_b_coverage(con)
    con.close()
    print("\n(Detection only — nothing was written or merged.)")


if __name__ == "__main__":
    main()
