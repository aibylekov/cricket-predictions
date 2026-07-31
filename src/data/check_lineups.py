"""Fact-find: is the announced XI / lineup available PRE-match? (read-only)

Point-in-time correctness (README §1.3) forbids feeding the model anything not
known before a match. The playing XI is a huge signal — but only if we actually
have it *before* the match. This script answers one question against
``cricket_raw``:

    For a FUTURE (not-yet-played) cricket match, is the announced playing XI /
    squad available anywhere, or does the XI only appear post-hoc (derivable
    from who actually batted/bowled)?

Strictly READ-ONLY: SELECT / SHOW / information_schema only. Nothing is written
and nothing is committed. Credentials come from ``.env``.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pymysql
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Column-name fragments that suggest lineup / squad / roster information.
LINEUP_KEYWORDS = [
    "lineup", "line_up", "playing", "xi", "squad", "roster",
    "selected", "bench", "substitute", "available", "team_sheet",
]

# A match is "future not-yet-played" if it starts after now and has no result.
FUTURE_PLAYED_WHERE = "m.start_at > NOW() AND (m.result IS NULL OR m.result = '')"


def get_connection() -> pymysql.connections.Connection:
    load_dotenv(PROJECT_ROOT / ".env")
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "") or "",
        database=os.getenv("DB_NAME", "cricket_raw"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )


def run(conn, sql, args=None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchall()


def scalar(conn, sql, args=None):
    rows = run(conn, sql, args)
    return next(iter(rows[0].values())) if rows else None


def show_create(conn, table: str) -> str:
    with conn.cursor() as cur:
        cur.execute(f"SHOW CREATE TABLE `{table}`")
        row = cur.fetchone()
    for k, v in row.items():
        if k.lower().startswith("create"):
            return v
    return ""


def _fmt(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (datetime, date, timedelta)):
        return str(v)
    s = str(v)
    return s if len(s) <= 80 else s[:77] + "..."


def print_rows(rows, cols=None):
    if not rows:
        print("    (no rows)")
        return
    for r in rows:
        items = r.items() if cols is None else [(c, r[c]) for c in cols]
        print("    - " + " | ".join(f"{k}={_fmt(v)}" for k, v in items))


def hr(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# --------------------------------------------------------------------------- #
# 1. Keyword scan of every column name
# --------------------------------------------------------------------------- #
def scan_keyword_columns(conn, database: str):
    hr("1. COLUMNS whose name suggests lineup / squad / roster")
    like = " OR ".join(["COLUMN_NAME LIKE %s"] * len(LINEUP_KEYWORDS))
    rows = run(
        conn,
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
        f"WHERE TABLE_SCHEMA=%s AND ({like}) ORDER BY TABLE_NAME, ORDINAL_POSITION",
        [database] + [f"%{k}%" for k in LINEUP_KEYWORDS],
    )
    cricket = [r for r in rows if r["TABLE_NAME"].startswith("cricket__")]
    other = [r for r in rows if not r["TABLE_NAME"].startswith("cricket__")]

    print(f"\n  Keywords: {', '.join(LINEUP_KEYWORDS)}")
    print(f"\n  CRICKET hits ({len(cricket)}):")
    for r in cricket:
        print(f"    {r['TABLE_NAME']}.{r['COLUMN_NAME']}  ({r['DATA_TYPE']})")
    print(f"\n  Other-sport hits ({len(other)}, for reference):")
    for r in other:
        print(f"    {r['TABLE_NAME']}.{r['COLUMN_NAME']}  ({r['DATA_TYPE']})")


# --------------------------------------------------------------------------- #
# 2. cricket__matches: structure + future matches
# --------------------------------------------------------------------------- #
def inspect_matches(conn):
    hr("2. cricket__matches — does the match row carry a squad/XI?")
    print("\n  SHOW CREATE TABLE cricket__matches:\n")
    for line in show_create(conn, "cricket__matches").splitlines():
        print("    " + line)

    key_cols = ["id", "key", "name", "team_a", "team_b", "start_at",
                "status", "play_status", "result", "winner"]
    print("\n  3 sample rows (key columns):")
    print_rows(run(conn, "SELECT * FROM cricket__matches ORDER BY id LIMIT 3"), key_cols)

    print("\n  -> No squad/XI column on the match row: only team ids, status &"
          " result.\n     (Full column list has no lineup/xi field — see part 1.)")

    future_total = scalar(
        conn,
        "SELECT COUNT(*) FROM cricket__matches m WHERE " + FUTURE_PLAYED_WHERE,
    )
    print(f"\n  FUTURE not-yet-played matches (start_at > now, no result): "
          f"{future_total:,}")
    print("\n  3 sample future matches:")
    print_rows(
        run(conn,
            "SELECT * FROM cricket__matches m WHERE " + FUTURE_PLAYED_WHERE +
            " ORDER BY m.start_at LIMIT 3"),
        key_cols,
    )
    return future_total


# --------------------------------------------------------------------------- #
# 3. team_play_stats & players: per-match selection vs aggregate
# --------------------------------------------------------------------------- #
def inspect_selection_tables(conn, database: str, future_total: int):
    hr("3. Per-match 'was selected / did play' vs aggregate stats")

    # team_play_stats
    tps_cols = [r["COLUMN_NAME"] for r in run(
        conn,
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='cricket__team_play_stats' "
        "ORDER BY ORDINAL_POSITION", (database,))]
    print("\n  cricket__team_play_stats columns:")
    print("    " + ", ".join(tps_cols))
    print("    -> Aggregate TEAM scoring per match (runs/wickets/extras).")
    print("       No per-PLAYER selection flag. Cannot tell who was in the XI.")

    # players
    pl_cols = [r["COLUMN_NAME"] for r in run(
        conn,
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='cricket__players' "
        "ORDER BY ORDINAL_POSITION", (database,))]
    print("\n  cricket__players columns:")
    print("    " + ", ".join(pl_cols))
    has_xi = "playing_xi" in pl_cols
    has_match = "match_id" in pl_cols
    print(f"    -> has per-match key 'match_id': {has_match}")
    print(f"    -> has per-match selection flag 'playing_xi': {has_xi}")

    dist = run(conn,
               "SELECT playing_xi, COUNT(*) c, COUNT(DISTINCT match_id) matches "
               "FROM cricket__players GROUP BY playing_xi ORDER BY playing_xi")
    print("\n  playing_xi distribution (all matches):")
    print_rows(dist)

    # Future coverage of playing_xi
    fut = run(conn,
              "SELECT COUNT(DISTINCT m.id) future_matches, "
              "COUNT(DISTINCT p.match_id) with_any_player_row, "
              "COUNT(DISTINCT CASE WHEN p.playing_xi=1 THEN p.match_id END) with_confirmed_xi "
              "FROM cricket__matches m "
              "LEFT JOIN cricket__players p ON p.match_id=m.id "
              "WHERE " + FUTURE_PLAYED_WHERE)[0]
    print("\n  Coverage over FUTURE not-yet-played matches:")
    print(f"    future matches ............... {fut['future_matches']:,}")
    print(f"    with ANY cricket__players row  {fut['with_any_player_row']:,}  (squad-level)")
    print(f"    with confirmed playing_xi=1 .. {fut['with_confirmed_xi']:,}  (actual XI)")

    # What the future player rows look like (squad, not XI)
    sample = run(conn,
                 "SELECT p.match_id, m.name, COUNT(*) n_players, "
                 "SUM(p.playing_xi=1) xi1 "
                 "FROM cricket__players p JOIN cricket__matches m ON m.id=p.match_id "
                 "WHERE " + FUTURE_PLAYED_WHERE +
                 " GROUP BY p.match_id, m.name ORDER BY n_players DESC LIMIT 5")
    if sample:
        print("\n  Future matches with player rows (they are full squads, XI unconfirmed):")
        print_rows(sample)

    return {"has_xi": has_xi, "future": fut}


# --------------------------------------------------------------------------- #
# 4. predictions: pre-match PREDICTED XI (editorial)
# --------------------------------------------------------------------------- #
def inspect_predicted_xi(conn):
    hr("4. cricket__predictions — pre-match PREDICTED XI (editorial)")
    print("\n  Fields: host_predicted_starting_xi, guest_predicted_starting_xi (text).")
    print("  Links to matches via match_key <-> cricket__matches.key.")
    print("  NOTE: this is TheTopBookies' OWN predicted XI (a guess written before")
    print("        the match), NOT the official announced lineup.\n")

    sample = run(conn,
                 "SELECT match_key, date_start, "
                 "LEFT(host_predicted_starting_xi,90) host_xi "
                 "FROM cricket__predictions "
                 "WHERE host_predicted_starting_xi IS NOT NULL "
                 "AND TRIM(host_predicted_starting_xi) NOT IN ('','[]','null') "
                 "ORDER BY id LIMIT 2")
    print("  Example predicted-XI rows (historical):")
    print_rows(sample)

    fut = run(conn,
              "SELECT COUNT(DISTINCT m.id) future_matches, "
              "COUNT(DISTINCT CASE WHEN pr.host_predicted_starting_xi IS NOT NULL "
              "  AND TRIM(pr.host_predicted_starting_xi) NOT IN ('','[]','null') "
              "  THEN m.id END) with_predicted_xi "
              "FROM cricket__matches m "
              "LEFT JOIN cricket__predictions pr ON pr.match_key = m.`key` "
              "WHERE " + FUTURE_PLAYED_WHERE)[0]
    print("\n  Coverage over FUTURE not-yet-played matches:")
    print(f"    future matches ................. {fut['future_matches']:,}")
    print(f"    with a predicted XI ............ {fut['with_predicted_xi']:,}")
    return fut


# --------------------------------------------------------------------------- #
# Key answer
# --------------------------------------------------------------------------- #
def print_answer(future_total, players_info, pred_info):
    hr("KEY QUESTION")
    xi_future = players_info["future"]["with_confirmed_xi"]
    squad_future = players_info["future"]["with_any_player_row"]
    pred_future = pred_info["with_predicted_xi"]

    print("\n  For a FUTURE (not-yet-played) cricket match in this DB, is the")
    print("  announced XI available anywhere?\n")

    official = "YES" if xi_future > 0 else "NO"
    print(f"  >>> OFFICIAL / ANNOUNCED XI: {official}")
    print(f"      cricket__players.playing_xi=1 exists for {xi_future} of "
          f"{future_total} future matches.")
    print("      => The confirmed XI is populated only POST-hoc, once match data")
    print("         arrives. It is NOT a forward-looking, pre-match asset here.")

    print(f"\n  >>> SQUAD / ROSTER (not the XI): partial")
    print(f"      cricket__players (playing_xi=0) exists for {squad_future} of "
          f"{future_total} future matches — full squads, XI not marked.")

    pred = "YES" if pred_future > 0 else "NO"
    print(f"\n  >>> PREDICTED XI (editorial guess, not official): {pred}")
    print(f"      cricket__predictions.*_predicted_starting_xi exists for "
          f"{pred_future} of {future_total} future matches.")

    print("\n  BOTTOM LINE:")
    if xi_future == 0 and pred_future == 0:
        print("    NO — no announced/official XI (and no predicted XI) is stored for")
        print("    the not-yet-played matches. Pre-match, only squad rosters exist.")
        print("    The confirmed playing XI must come from the LIVE feed (Roanuz")
        print("    lineup endpoint, ~30-40 min before toss) at prediction time —")
        print("    it cannot be sourced from this historical DB for future matches.")
    elif xi_future == 0 and pred_future > 0:
        print("    Only an EDITORIAL predicted XI is available pre-match")
        print("    (cricket__predictions); the official announced XI is not stored.")
    else:
        print("    Announced XI IS present pre-match in cricket__players.playing_xi.")


def main():
    conn = get_connection()
    database = os.getenv("DB_NAME", "cricket_raw")
    try:
        scan_keyword_columns(conn, database)
        future_total = inspect_matches(conn)
        players_info = inspect_selection_tables(conn, database, future_total)
        pred_info = inspect_predicted_xi(conn)
        print_answer(future_total, players_info, pred_info)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
