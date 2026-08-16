"""
export_home_grounds_review.py — editorial review file for derived home grounds.

Writes docs/home-grounds-review.csv: one row per (team, league_key) with the
team's PROPOSED home venue = the venue holding the largest share of its
completed matches in that league. The editor reviews the top leagues and
fills `human_decision` with one of:

    confirm                  — derivation is right
    reject                   — team has no usable home ground signal
    correct: <venue name>    — derivation is wrong; this is the real ground

CONFIDENCE (aligned with build_l2.HOME_GROUND_MIN_*):
    high    >= 10 matches at the venue AND >= 30% share  (this is the gate
            that already sets is_home_ground in L2 — home-advantage prose
            is allowed ONLY for these until the review comes back)
    medium  5-9 matches at >= 30% share (candidate; needs confirmation)
    low     below both bars (listed for completeness; no home claims)

SCOPE NOTE: unlike the L2 home_ground aggregate (point-in-time per target
match), this file uses ALL completed matches to date. It is an editorial
review artifact, not a model or content input, so the anti-leakage rule
does not apply to it.

INGESTION (next step, after the editor returns the file): human_decision
becomes AUTHORITATIVE, overriding the derivation bridge_entity-style —
confirmed/corrected grounds feed the content layer regardless of
confidence; rejected teams never get home-advantage prose.

Run:
  venv/Scripts/python.exe -m src.data.export_home_grounds_review
"""
from __future__ import annotations

import csv
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
L1 = ROOT / "data" / "lake" / "l1"
OUT = ROOT / "docs" / "home-grounds-review.csv"

DIM_MATCH = (L1 / "dim_match" / "dim_match.parquet").as_posix()
DIM_TOURNAMENT = (L1 / "dim_tournament" / "dim_tournament.parquet").as_posix()
DIM_TEAM = (L1 / "dim_team" / "dim_team.parquet").as_posix()
DIM_VENUE = (L1 / "dim_venue" / "dim_venue.parquet").as_posix()

# League prominence for the editor's review order (everything else after,
# alphabetically). Keys are exact league_key values from dim_tournament.
LEAGUE_PRIORITY = [
    "indian premier league",        # IPL
    "big bash league",              # BBL
    "pakistan super league",        # PSL
    "major league cricket",         # MLC
    "sa league",                    # SA20
    "caribbean premier league",     # CPL
    "bangladesh premier league",    # BPL
]

# Same bars as build_l2.HOME_GROUND_MIN_MATCHES / _SHARE (high) and the
# medium candidate band awaiting human confirmation.
HIGH_MIN_MATCHES, MEDIUM_MIN_MATCHES, MIN_SHARE = 10, 5, 0.30


def confidence(at_venue: int, share: float) -> str:
    if at_venue >= HIGH_MIN_MATCHES and share >= MIN_SHARE:
        return "high"
    if at_venue >= MEDIUM_MIN_MATCHES and share >= MIN_SHARE:
        return "medium"
    return "low"


def main() -> None:
    con = duckdb.connect()
    rows = con.execute(f"""
        WITH decided AS (
            SELECT CAST(m.match_id AS BIGINT) AS match_id,
                   CAST(m.team_a_id AS BIGINT) AS team_a_id,
                   CAST(m.team_b_id AS BIGINT) AS team_b_id,
                   m.venue_key, t.league_key
            FROM read_parquet('{DIM_MATCH}') m
            LEFT JOIN read_parquet('{DIM_TOURNAMENT}') t
                   ON CAST(t.tournament_id AS BIGINT) = CAST(m.tournament_id AS BIGINT)
            WHERE m.winner IS NOT NULL AND m.venue_key IS NOT NULL
        ),
        sided AS (
            SELECT team_a_id AS team_id, league_key, venue_key FROM decided
            UNION ALL
            SELECT team_b_id, league_key, venue_key FROM decided
        ),
        per_venue AS (
            SELECT team_id, league_key, venue_key, COUNT(*) AS at_venue
            FROM sided GROUP BY team_id, league_key, venue_key
        ),
        totals AS (
            SELECT team_id, league_key, SUM(at_venue) AS total_matches
            FROM per_venue GROUP BY team_id, league_key
        ),
        top_venue AS (
            SELECT pv.*, ROW_NUMBER() OVER (
                       PARTITION BY pv.team_id, pv.league_key
                       ORDER BY pv.at_venue DESC, pv.venue_key
                   ) AS rn
            FROM per_venue pv
        )
        SELECT tm.team_name, tv.league_key, v.venue_name,
               tv.at_venue, tt.total_matches,
               tv.at_venue / tt.total_matches::DOUBLE AS share
        FROM top_venue tv
        JOIN totals tt ON tt.team_id = tv.team_id
                      AND tt.league_key IS NOT DISTINCT FROM tv.league_key
        LEFT JOIN read_parquet('{DIM_TEAM}') tm
               ON CAST(tm.team_id AS BIGINT) = tv.team_id
        LEFT JOIN read_parquet('{DIM_VENUE}') v
               ON v.venue_key = tv.venue_key
        WHERE tv.rn = 1
        ORDER BY tv.league_key, share DESC
    """).fetchall()
    con.close()

    prio = {lk: i for i, lk in enumerate(LEAGUE_PRIORITY)}
    rows.sort(key=lambda r: (prio.get(r[1], len(LEAGUE_PRIORITY)),
                             r[1] or "~", -r[5]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["team_name", "league_key", "proposed_home_venue",
                    "matches_at_venue", "total_matches", "share_pct",
                    "confidence", "human_decision"])
        for name, league, venue, at_v, total, share in rows:
            w.writerow([name, league, venue, int(at_v), int(total),
                        round(100.0 * share, 1),
                        confidence(int(at_v), share), ""])

    n_high = sum(1 for r in rows if confidence(int(r[3]), r[5]) == "high")
    n_med = sum(1 for r in rows if confidence(int(r[3]), r[5]) == "medium")
    print(f"wrote {OUT} ({len(rows)} rows: {n_high} high, {n_med} medium, "
          f"{len(rows) - n_high - n_med} low)")


if __name__ == "__main__":
    main()
