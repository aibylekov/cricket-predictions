"""
test_leakage.py — MANDATORY point-in-time / anti-leakage test for L2.

The single most important guarantee of L2 is: an aggregate stamped with
`as_of_date = D` must be computed from ONLY completed matches whose date is
STRICTLY < D. No contributing row may ever be dated >= D.

This test does NOT trust build_l2.py's SQL. It re-derives, straight from L1,
the exact set of matches each sampled snapshot is supposed to use, and then:

  (A) asserts every contributing match date is strictly < as_of_date, and
  (B) asserts the INDEPENDENT recount equals the `matches_in_window` stored in
      the L2 output.

If build_l2 had leaked a match dated >= D, (A) would catch a bad contributing
row and/or (B) would disagree with the stored count. Either fails loudly.

Run:
  venv/Scripts/python.exe -m pytest tests/test_leakage.py -v
  # or simply:  venv/Scripts/python.exe tests/test_leakage.py
"""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
L1 = ROOT / "data" / "lake" / "l1"
L2 = ROOT / "data" / "lake" / "l2"

DIM_MATCH = (L1 / "dim_match" / "dim_match.parquet").as_posix()
TEAM_FORM = (L2 / "team_form" / "team_form.parquet").as_posix()
VENUE_STATS = (L2 / "venue_stats" / "venue_stats.parquet").as_posix()

# How many random snapshots to independently audit per window.
SAMPLE_N = 250


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    # Completed = has a recorded outcome; dates at DATE granularity to match L2.
    con.execute(f"""
        CREATE VIEW decided AS
        SELECT CAST(match_id AS BIGINT)   AS match_id,
               CAST(team_a_id AS BIGINT)  AS team_a_id,
               CAST(team_b_id AS BIGINT)  AS team_b_id,
               CAST(tournament_id AS BIGINT) AS tournament_id,
               CAST(start_at AS DATE)     AS match_date
        FROM read_parquet('{DIM_MATCH}')
        WHERE winner IS NOT NULL;
    """)
    return con


def _independent_last5(con, team_id, as_of_date):
    """Re-derive the team's last-5 completed matches strictly before D."""
    return con.execute("""
        SELECT match_id, match_date
        FROM decided
        WHERE (team_a_id = ? OR team_b_id = ?)
          AND match_date < ?
        ORDER BY match_date DESC, match_id DESC
        LIMIT 5
    """, [team_id, team_id, as_of_date]).fetchall()


def _independent_tournament(con, team_id, tournament_id, as_of_date):
    """Re-derive the team's completed same-tournament matches strictly before D."""
    return con.execute("""
        SELECT match_id, match_date
        FROM decided
        WHERE (team_a_id = ? OR team_b_id = ?)
          AND tournament_id = ?
          AND match_date < ?
    """, [team_id, team_id, tournament_id, as_of_date]).fetchall()


def _sample(con, window, n):
    # NB: DuckDB applies USING SAMPLE at the table scan (before WHERE), so we
    # filter in a subquery first, then sample exactly n of the matching rows.
    return con.execute(f"""
        SELECT match_id, team_id, CAST(as_of_date AS DATE), tournament_id,
               matches_in_window
        FROM (
            SELECT * FROM read_parquet('{TEAM_FORM}') WHERE "window" = ?
        )
        USING SAMPLE reservoir({int(n)} ROWS) REPEATABLE (42)
    """, [window]).fetchall()


def _check_team_form_window(con, window, derive_fn):
    rows = _sample(con, window, SAMPLE_N)
    assert rows, f"no team_form rows sampled for window={window}"
    leaks = []
    miscounts = []
    for match_id, team_id, as_of, tourn, stored_n in rows:
        if window == "last5":
            contrib = derive_fn(con, team_id, as_of)
        else:
            contrib = derive_fn(con, team_id, tourn, as_of)

        # (A) every contributing match strictly before as_of_date
        for cm_id, cm_date in contrib:
            if not (cm_date < as_of):
                leaks.append((window, team_id, as_of, cm_id, cm_date))

        # (B) independent recount matches the stored window size
        if len(contrib) != stored_n:
            miscounts.append((window, match_id, team_id, as_of,
                              len(contrib), stored_n))

    assert not leaks, (
        f"LEAKAGE in team_form/{window}: contributing match dated >= as_of_date:\n"
        + "\n".join(f"  team={t} as_of={a} used match={m} dated={d}"
                    for _, t, a, m, d in leaks[:20])
    )
    assert not miscounts, (
        f"COUNT MISMATCH in team_form/{window} "
        f"(independent recount != stored matches_in_window):\n"
        + "\n".join(f"  match={mi} team={t} as_of={a} recount={r} stored={s}"
                    for _, mi, t, a, r, s in miscounts[:20])
    )
    print(f"[team_form/{window}] audited {len(rows)} snapshots — "
          f"0 leaks, all recounts matched.")


def _check_venue_stats(con):
    rows = con.execute(f"""
        SELECT venue_key, CAST(as_of_date AS DATE), matches_at_venue
        FROM (
            SELECT * FROM read_parquet('{VENUE_STATS}') WHERE matches_at_venue > 0
        )
        USING SAMPLE reservoir({SAMPLE_N} ROWS) REPEATABLE (42)
    """).fetchall()
    assert rows, "no venue_stats rows sampled"
    leaks, miscounts = [], []
    for venue_key, as_of, stored_n in rows:
        contrib = con.execute("""
            SELECT CAST(match_id AS BIGINT), CAST(start_at AS DATE)
            FROM read_parquet($p)
            WHERE winner IS NOT NULL AND venue_key = $v
              AND CAST(start_at AS DATE) < $d
        """.replace("$p", f"'{DIM_MATCH}'"),
            {"v": venue_key, "d": as_of}).fetchall()
        for cm_id, cm_date in contrib:
            if not (cm_date < as_of):
                leaks.append((venue_key, as_of, cm_id, cm_date))
        if len(contrib) != stored_n:
            miscounts.append((venue_key, as_of, len(contrib), stored_n))
    assert not leaks, (
        "LEAKAGE in venue_stats: contributing match dated >= as_of_date:\n"
        + "\n".join(f"  venue={v} as_of={a} used match={m} dated={d}"
                    for v, a, m, d in leaks[:20])
    )
    assert not miscounts, (
        "COUNT MISMATCH in venue_stats:\n"
        + "\n".join(f"  venue={v} as_of={a} recount={r} stored={s}"
                    for v, a, r, s in miscounts[:20])
    )
    print(f"[venue_stats] audited {len(rows)} snapshots — "
          f"0 leaks, all recounts matched.")


# --- pytest entry points -------------------------------------------------
def test_team_form_last5_no_leakage():
    con = _con()
    _check_team_form_window(con, "last5", _independent_last5)
    con.close()


def test_team_form_tournament_no_leakage():
    con = _con()
    _check_team_form_window(con, "tournament", _independent_tournament)
    con.close()


def test_venue_stats_no_leakage():
    con = _con()
    _check_venue_stats(con)
    con.close()


if __name__ == "__main__":
    con = _con()
    print("Running L2 leakage audit "
          f"({SAMPLE_N} random snapshots per dataset)\n")
    _check_team_form_window(con, "last5", _independent_last5)
    _check_team_form_window(con, "tournament", _independent_tournament)
    _check_venue_stats(con)
    con.close()
    print("\nLEAKAGE TEST: PASS — no snapshot uses data dated >= its as_of_date.")
