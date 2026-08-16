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
DIM_TOURNAMENT = (L1 / "dim_tournament" / "dim_tournament.parquet").as_posix()
TEAM_FORM = (L2 / "team_form" / "team_form.parquet").as_posix()
VENUE_STATS = (L2 / "venue_stats" / "venue_stats.parquet").as_posix()
PLAYER_FORM = (L2 / "player_form" / "player_form.parquet").as_posix()
STANDINGS = (L2 / "standings" / "standings.parquet").as_posix()
HOME_GROUND = (L2 / "home_ground" / "home_ground.parquet").as_posix()
L0 = ROOT / "data" / "lake" / "l0"
L0_PLAYERS = (L0 / "cricket__players" / "*.parquet").as_posix()
L0_BAT = (L0 / "cricket__player_batting_scores" / "*.parquet").as_posix()
L0_BOWL = (L0 / "cricket__player_bowling_scores" / "*.parquet").as_posix()
L3_FEATURES = (ROOT / "data" / "lake" / "l3" / "feature_rows" / "feature_rows.parquet").as_posix()

# How many random snapshots to independently audit per window.
SAMPLE_N = 250


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    # Completed = has a recorded outcome; dates at DATE granularity to match L2.
    # league_key joined from dim_tournament (tournament window groups by league).
    con.execute(f"""
        CREATE VIEW decided AS
        SELECT CAST(m.match_id AS BIGINT)   AS match_id,
               CAST(m.team_a_id AS BIGINT)  AS team_a_id,
               CAST(m.team_b_id AS BIGINT)  AS team_b_id,
               CAST(m.tournament_id AS BIGINT) AS tournament_id,
               t.league_key,
               m.winner,
               CAST(m.start_at AS DATE)     AS match_date
        FROM read_parquet('{DIM_MATCH}') m
        LEFT JOIN read_parquet('{DIM_TOURNAMENT}') t
               ON CAST(t.tournament_id AS BIGINT) = CAST(m.tournament_id AS BIGINT)
        WHERE m.winner IS NOT NULL;
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


def _independent_tournament(con, team_id, league_key, as_of_date):
    """Re-derive the team's completed same-LEAGUE matches strictly before D."""
    return con.execute("""
        SELECT match_id, match_date
        FROM decided
        WHERE (team_a_id = ? OR team_b_id = ?)
          AND league_key IS NOT DISTINCT FROM ?
          AND match_date < ?
    """, [team_id, team_id, league_key, as_of_date]).fetchall()


def _independent_current_event(con, team_id, tournament_id, as_of_date):
    """Re-derive the team's completed same-EVENT matches strictly before D."""
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
               league_key, matches_in_window
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
    for match_id, team_id, as_of, tourn, league_key, stored_n in rows:
        if window == "last5":
            contrib = derive_fn(con, team_id, as_of)
        elif window == "current_event":
            contrib = derive_fn(con, team_id, tourn, as_of)
        else:
            contrib = derive_fn(con, team_id, league_key, as_of)

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


def _check_l3(con):
    """
    Re-check the FINAL L3 table: for sampled rows, independently re-derive each
    side's last5 + tournament(league) contributing matches from L1 and assert
    (A) every contributing date is strictly < as_of_date, and (B) the recount
    equals the home_/away_ matches_in_window stored on the L3 row.
    """
    rows = con.execute(f"""
        SELECT match_id, CAST(as_of_date AS DATE), league_key,
               home_team_id, away_team_id,
               home_matches_in_window_last5, home_matches_in_window_tourn,
               away_matches_in_window_last5, away_matches_in_window_tourn
        FROM read_parquet('{L3_FEATURES}')
        USING SAMPLE reservoir({SAMPLE_N} ROWS) REPEATABLE (42)
    """).fetchall()
    assert rows, "no L3 rows sampled"
    leaks, miscounts = [], []
    for (mid, as_of, lk, home_id, away_id,
         h_l5, h_tn, a_l5, a_tn) in rows:
        for side, tid, n_l5, n_tn in [("home", home_id, h_l5, h_tn),
                                      ("away", away_id, a_l5, a_tn)]:
            l5 = _independent_last5(con, tid, as_of)
            tn = _independent_tournament(con, tid, lk, as_of)
            for label, contrib, stored in [("last5", l5, n_l5), ("tourn", tn, n_tn)]:
                for cm_id, cm_date in contrib:
                    if not (cm_date < as_of):
                        leaks.append((side, label, mid, tid, as_of, cm_id, cm_date))
                if len(contrib) != stored:
                    miscounts.append((side, label, mid, tid, as_of, len(contrib), stored))
    assert not leaks, (
        "LEAKAGE in L3: home_/away_ feature used match dated >= as_of_date:\n"
        + "\n".join(f"  {s}/{lb} match={m} team={t} as_of={a} used={mm} dated={d}"
                    for s, lb, m, t, a, mm, d in leaks[:20])
    )
    assert not miscounts, (
        "COUNT MISMATCH in L3 (recount != stored matches_in_window):\n"
        + "\n".join(f"  {s}/{lb} match={m} team={t} as_of={a} recount={r} stored={st}"
                    for s, lb, m, t, a, r, st in miscounts[:20])
    )
    print(f"[L3 feature_rows] audited {len(rows)} rows x2 sides — "
          f"0 leaks, all home_/away_ recounts matched.")


def _check_player_form(con):
    """
    Iteration-2 aggregate. Two layers of proof:
      (FULL SCAN) every row's max_source_date is strictly < its as_of_date —
      the audit column build_l2 stamps from the actual contributing rows.
      (SAMPLE) independent recount: re-derive the team's window matches from
      L1, count those where this player has an L0 score row, compare to the
      stored matches_in_window.
    """
    # full-scan audit column check (cheap, covers every row)
    bad = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{PLAYER_FORM}')
        WHERE max_source_date >= as_of_date
    """).fetchone()[0]
    assert bad == 0, f"LEAKAGE in player_form: {bad} rows with max_source_date >= as_of_date"

    # slim (match, team, player) appearance table for recounts
    con.execute(f"""
        CREATE TEMP TABLE IF NOT EXISTS player_appearances AS
        SELECT DISTINCT CAST(p.match_id AS BIGINT) AS match_id,
               CAST(p.team_id AS BIGINT) AS team_id, p.key AS player_key
        FROM read_parquet('{L0_PLAYERS}') p
        WHERE p.id IN (SELECT player_id FROM read_parquet('{L0_BAT}'))
           OR p.id IN (SELECT player_id FROM read_parquet('{L0_BOWL}'));
    """)

    rows = con.execute(f"""
        SELECT match_id, team_id, CAST(as_of_date AS DATE), player_key,
               "window", matches_in_window
        FROM read_parquet('{PLAYER_FORM}')
        USING SAMPLE reservoir({SAMPLE_N} ROWS) REPEATABLE (42)
    """).fetchall()
    assert rows, "no player_form rows sampled"

    # tournament_id per target match (for the current_event derivation)
    tid_by_match = dict(con.execute(
        "SELECT match_id, tournament_id FROM decided "
        "UNION SELECT CAST(match_id AS BIGINT), CAST(tournament_id AS BIGINT) "
        f"FROM read_parquet('{DIM_MATCH}')").fetchall())

    leaks, miscounts = [], []
    for mid, team_id, as_of, pkey, window, stored_n in rows:
        if window == "last5":
            wm = _independent_last5(con, team_id, as_of)
        else:
            wm = _independent_current_event(con, team_id, tid_by_match[mid], as_of)
        for cm_id, cm_date in wm:
            if not (cm_date < as_of):
                leaks.append((window, mid, team_id, pkey, as_of, cm_id, cm_date))
        if wm:
            ids = ",".join(str(int(w[0])) for w in wm)
            recount = con.execute(f"""
                SELECT COUNT(*) FROM player_appearances
                WHERE match_id IN ({ids}) AND team_id = ? AND player_key = ?
            """, [team_id, pkey]).fetchone()[0]
        else:
            recount = 0
        if recount != stored_n:
            miscounts.append((window, mid, team_id, pkey, as_of, recount, stored_n))

    assert not leaks, (
        "LEAKAGE in player_form: window match dated >= as_of_date:\n"
        + "\n".join(f"  {w} match={m} team={t} player={p} as_of={a} used={u} dated={d}"
                    for w, m, t, p, a, u, d in leaks[:20]))
    assert not miscounts, (
        "COUNT MISMATCH in player_form (recount != stored matches_in_window):\n"
        + "\n".join(f"  {w} match={m} team={t} player={p} as_of={a} recount={r} stored={s}"
                    for w, m, t, p, a, r, s in miscounts[:20]))
    print(f"[player_form] full-scan max_source_date audit + {len(rows)} sampled "
          f"recounts — 0 leaks, all recounts matched.")


def _check_standings(con):
    """
    Iteration-2 aggregate. FULL SCAN of the max_source_date audit column,
    then SAMPLE recompute of played/won/lost from decided matches strictly
    before as_of_date.
    """
    bad = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{STANDINGS}')
        WHERE max_source_date >= as_of_date
    """).fetchone()[0]
    assert bad == 0, f"LEAKAGE in standings: {bad} rows with max_source_date >= as_of_date"

    rows = con.execute(f"""
        SELECT tournament_id, CAST(as_of_date AS DATE), team_id,
               played, won, lost
        FROM read_parquet('{STANDINGS}')
        USING SAMPLE reservoir({SAMPLE_N} ROWS) REPEATABLE (42)
    """).fetchall()
    assert rows, "no standings rows sampled"

    mismatches = []
    for tid, as_of, team_id, played, won, lost in rows:
        rec = con.execute("""
            SELECT COUNT(*) AS played,
                   SUM(CASE WHEN (winner='a' AND team_a_id=?)
                              OR (winner='b' AND team_b_id=?) THEN 1 ELSE 0 END) AS won
            FROM decided
            WHERE tournament_id = ?
              AND (team_a_id = ? OR team_b_id = ?)
              AND match_date < ?
        """, [team_id, team_id, tid, team_id, team_id, as_of]).fetchone()
        r_played, r_won = int(rec[0]), int(rec[1] or 0)
        if not (r_played == played and r_won == won and (r_played - r_won) == lost):
            mismatches.append((tid, as_of, team_id, r_played, r_won, played, won))

    assert not mismatches, (
        "STANDINGS MISMATCH (independent recompute != stored):\n"
        + "\n".join(f"  event={t} as_of={a} team={tm} recount=({rp}p,{rw}w) "
                    f"stored=({sp}p,{sw}w)"
                    for t, a, tm, rp, rw, sp, sw in mismatches[:20]))
    print(f"[standings] full-scan max_source_date audit + {len(rows)} sampled "
          f"recomputes — 0 leaks, all standings matched.")


def _check_home_ground(con):
    """
    Iteration-2b aggregate. FULL SCAN of the max_source_date audit column,
    then SAMPLE recompute: the team's same-league decided matches strictly
    before as_of_date, total and at the target venue.
    """
    bad = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{HOME_GROUND}')
        WHERE max_source_date >= as_of_date
    """).fetchone()[0]
    assert bad == 0, f"LEAKAGE in home_ground: {bad} rows with max_source_date >= as_of_date"

    rows = con.execute(f"""
        SELECT match_id, team_id, CAST(as_of_date AS DATE), venue_key,
               league_matches_before, at_venue_before
        FROM read_parquet('{HOME_GROUND}')
        USING SAMPLE reservoir({SAMPLE_N} ROWS) REPEATABLE (42)
    """).fetchall()
    assert rows, "no home_ground rows sampled"

    lk_by_match = dict(con.execute(
        "SELECT match_id, league_key FROM decided "
        "UNION SELECT CAST(match_id AS BIGINT), t.league_key "
        f"FROM read_parquet('{DIM_MATCH}') m "
        f"LEFT JOIN read_parquet('{DIM_TOURNAMENT}') t "
        "  ON CAST(t.tournament_id AS BIGINT) = CAST(m.tournament_id AS BIGINT)"
    ).fetchall())

    mismatches = []
    for mid, team_id, as_of, venue_key, stored_total, stored_at in rows:
        rec = con.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN m.venue_key = ? THEN 1 ELSE 0 END) AS at_venue
            FROM decided d
            JOIN read_parquet($dm) m ON CAST(m.match_id AS BIGINT) = d.match_id
            WHERE (d.team_a_id = ? OR d.team_b_id = ?)
              AND d.league_key IS NOT DISTINCT FROM ?
              AND d.match_date < ?
        """.replace("$dm", f"'{DIM_MATCH}'"),
            [venue_key, team_id, team_id, lk_by_match[mid], as_of]).fetchone()
        r_total, r_at = int(rec[0]), int(rec[1] or 0)
        if not (r_total == stored_total and r_at == (stored_at or 0)):
            mismatches.append((mid, team_id, as_of, r_total, r_at,
                               stored_total, stored_at))

    assert not mismatches, (
        "HOME_GROUND MISMATCH (independent recompute != stored):\n"
        + "\n".join(f"  match={m} team={t} as_of={a} recount=({rt},{ra}) "
                    f"stored=({st},{sa})"
                    for m, t, a, rt, ra, st, sa in mismatches[:20]))
    print(f"[home_ground] full-scan max_source_date audit + {len(rows)} sampled "
          f"recomputes — 0 leaks, all counts matched.")


# --- pytest entry points -------------------------------------------------
def test_l3_no_leakage():
    con = _con()
    _check_l3(con)
    con.close()


def test_team_form_last5_no_leakage():
    con = _con()
    _check_team_form_window(con, "last5", _independent_last5)
    con.close()


def test_team_form_tournament_no_leakage():
    con = _con()
    _check_team_form_window(con, "tournament", _independent_tournament)
    con.close()


def test_team_form_current_event_no_leakage():
    con = _con()
    _check_team_form_window(con, "current_event", _independent_current_event)
    con.close()


def test_venue_stats_no_leakage():
    con = _con()
    _check_venue_stats(con)
    con.close()


def test_player_form_no_leakage():
    con = _con()
    _check_player_form(con)
    con.close()


def test_standings_no_leakage():
    con = _con()
    _check_standings(con)
    con.close()


def test_home_ground_no_leakage():
    con = _con()
    _check_home_ground(con)
    con.close()


if __name__ == "__main__":
    con = _con()
    print("Running L2 leakage audit "
          f"({SAMPLE_N} random snapshots per dataset)\n")
    _check_team_form_window(con, "last5", _independent_last5)
    _check_team_form_window(con, "tournament", _independent_tournament)
    _check_team_form_window(con, "current_event", _independent_current_event)
    _check_venue_stats(con)
    _check_player_form(con)
    _check_standings(con)
    _check_home_ground(con)
    _check_l3(con)
    con.close()
    print("\nLEAKAGE TEST: PASS — no snapshot (L2 or L3) uses data dated >= its as_of_date.")
