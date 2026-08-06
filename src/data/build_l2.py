"""
build_l2.py — L2 point-in-time team aggregates (MVP, winner model).

Reads L1 (data/lake/l1/) + a little L0 (odds prices, raw toss JSON). NEVER
modifies L0 or L1. Writes L2 Parquet to data/lake/l2/.

CORE RULE (anti-leakage): every aggregate row carries an `as_of_date` and is
computed using ONLY completed matches STRICTLY BEFORE that date. A "completed"
match here means one with a recorded outcome (winner in {'a','b'}); this also
cleanly excludes the handful of future-dated rows that are flagged
is_completed=True but have no winner yet.

SNAPSHOT GRAIN: for EVERY T20-men match M (played or not-yet-played), with
D = date(M.start_at), we emit a pre-match snapshot for each of the two
participating teams, as_of_date = D. Future matches are valid targets; their
snapshot simply uses only past completed data.

Datasets produced (MVP, team-level only — no player/matchup aggregates):
  1) team_form       grain (match_id, team_id, window)   [as_of_date carried]
  2) venue_stats     grain (venue_key, as_of_date)
  3) match_conditions grain (match_id)
  4) match_odds_devig grain (match_id)  — bridge-linked priced T20-men only

Run:
  venv/Scripts/python.exe -m src.data.build_l2
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
L1 = ROOT / "data" / "lake" / "l1"
L0 = ROOT / "data" / "lake" / "l0"
L2 = ROOT / "data" / "lake" / "l2"

L1_DIM_MATCH = (L1 / "dim_match" / "dim_match.parquet").as_posix()
L1_FACT = (L1 / "fact_ball_by_ball" / "fact_ball_by_ball.parquet").as_posix()
L1_VENUE = (L1 / "dim_venue" / "dim_venue.parquet").as_posix()
L1_MATCH_BRIDGE = (L1 / "bridge" / "match_bridge.parquet").as_posix()
L0_ODDS = (L0 / "odd_match_odds" / "*.parquet").as_posix()
L0_MATCHES = (L0 / "cricket__matches" / "*.parquet").as_posix()

# Phase boundaries (over_number is 1..20 in this data)
#   powerplay = overs 1-6, middle = overs 7-15, death = overs 16-20
# A "legal" delivery excludes wides and no-balls (they don't advance the over);
# byes/leg-byes ARE legal deliveries. Run rate / economy = runs / (legal_balls/6).


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    # Register base relations as views (cast ids to BIGINT to avoid the
    # uint64/int64 mismatch between dim_match and fact_ball_by_ball).
    con.execute(f"""
        CREATE VIEW dim_match AS
        SELECT
            CAST(match_id   AS BIGINT) AS match_id,
            CAST(tournament_id AS BIGINT) AS tournament_id,
            CAST(team_a_id  AS BIGINT) AS team_a_id,
            CAST(team_b_id  AS BIGINT) AS team_b_id,
            start_at,
            start_at_local,
            CAST(start_at AS DATE)     AS match_date,
            winner,
            result_type,
            venue_key
        FROM read_parquet('{L1_DIM_MATCH}');
    """)
    con.execute(f"""
        CREATE VIEW fact AS
        SELECT
            CAST(match_id AS BIGINT) AS match_id,
            inning_key,
            batting_team AS side,          -- 'a' / 'b'
            over_number,
            ball_type,
            runs,
            ts_primary
        FROM read_parquet('{L1_FACT}')
        WHERE inning_key IN ('a_1','b_1');  -- main innings only (drop super-overs)
    """)
    return con


# --------------------------------------------------------------------------
# Per-match building blocks (from ball-by-ball)
# --------------------------------------------------------------------------
def build_ball_features(con: duckdb.DuckDBPyConnection) -> None:
    """Per (match_id, side) phase run/ball tallies + innings order + totals."""
    # phase tallies per (match, side)
    con.execute("""
        CREATE TEMP TABLE side_phase AS
        WITH tagged AS (
            SELECT
                match_id, side, inning_key, runs, ts_primary,
                CASE
                    WHEN over_number BETWEEN 1  AND 6  THEN 'pp'
                    WHEN over_number BETWEEN 7  AND 15 THEN 'mid'
                    ELSE 'death'
                END AS phase,
                CASE WHEN ball_type NOT IN ('wide','no_ball') THEN 1 ELSE 0 END AS legal
            FROM fact
        )
        SELECT
            match_id, side,
            SUM(runs)                                              AS total_runs,
            MIN(ts_primary)                                        AS innings_start_ts,
            SUM(CASE WHEN phase='pp'    THEN runs  END)            AS pp_runs,
            SUM(CASE WHEN phase='pp'    THEN legal END)            AS pp_balls,
            SUM(CASE WHEN phase='mid'   THEN runs  END)            AS mid_runs,
            SUM(CASE WHEN phase='mid'   THEN legal END)            AS mid_balls,
            SUM(CASE WHEN phase='death' THEN runs  END)            AS death_runs,
            SUM(CASE WHEN phase='death' THEN legal END)            AS death_balls
        FROM tagged
        GROUP BY match_id, side;
    """)

    # First-innings total per match: the side whose innings started earliest.
    con.execute("""
        CREATE TEMP TABLE first_innings AS
        SELECT match_id, total_runs AS first_innings_runs
        FROM (
            SELECT match_id, total_runs,
                   ROW_NUMBER() OVER (PARTITION BY match_id
                                      ORDER BY innings_start_ts ASC) AS rn
            FROM side_phase
        )
        WHERE rn = 1;
    """)


def build_team_match_history(con: duckdb.DuckDBPyConnection) -> None:
    """
    One row per (completed match, participating team) = the historical pool
    that windows draw from. Bat features = the team's own innings; bowl
    features = what the team CONCEDED (the opponent's innings).
    """
    con.execute("""
        CREATE TEMP TABLE team_match_history AS
        WITH decided AS (
            SELECT * FROM dim_match WHERE winner IS NOT NULL
        ),
        -- long form: one row per (match, side) with that team's identity + outcome
        sided AS (
            SELECT match_id, match_date, tournament_id,
                   team_a_id AS team_id, team_b_id AS opp_id, 'a' AS side, 'b' AS opp_side,
                   CASE WHEN winner='a' THEN 1 ELSE 0 END AS won
            FROM decided
            UNION ALL
            SELECT match_id, match_date, tournament_id,
                   team_b_id AS team_id, team_a_id AS opp_id, 'b' AS side, 'a' AS opp_side,
                   CASE WHEN winner='b' THEN 1 ELSE 0 END AS won
            FROM decided
        )
        SELECT
            s.match_id, s.team_id, s.opp_id, s.match_date, s.tournament_id, s.won,
            bat.total_runs  AS team_runs,
            bwl.total_runs  AS opp_runs,
            (bat.match_id IS NOT NULL) AS has_balls,
            -- batting (team's own innings)
            bat.pp_runs  AS bat_pp_runs,  bat.pp_balls  AS bat_pp_balls,
            bat.mid_runs AS bat_mid_runs, bat.mid_balls AS bat_mid_balls,
            bat.death_runs AS bat_death_runs, bat.death_balls AS bat_death_balls,
            -- bowling (runs conceded = opponent's innings)
            bwl.pp_runs  AS bowl_pp_runs,  bwl.pp_balls  AS bowl_pp_balls,
            bwl.mid_runs AS bowl_mid_runs, bwl.mid_balls AS bowl_mid_balls,
            bwl.death_runs AS bowl_death_runs, bwl.death_balls AS bowl_death_balls
        FROM sided s
        LEFT JOIN side_phase bat ON bat.match_id=s.match_id AND bat.side=s.side
        LEFT JOIN side_phase bwl ON bwl.match_id=s.match_id AND bwl.side=s.opp_side;
    """)


def build_targets(con: duckdb.DuckDBPyConnection) -> None:
    """Every T20-men match (played or not) x its two teams = snapshot targets."""
    con.execute("""
        CREATE TEMP TABLE targets AS
        SELECT match_id, team_a_id AS team_id, match_date AS as_of_date,
               tournament_id, venue_key
        FROM dim_match
        UNION ALL
        SELECT match_id, team_b_id AS team_id, match_date AS as_of_date,
               tournament_id, venue_key
        FROM dim_match;
    """)


# --------------------------------------------------------------------------
# 1) team_form
# --------------------------------------------------------------------------
# Aggregation expression shared by both windows. Aggregate-then-divide (weights
# by volume) is the stable choice for phase rates.
_AGG_COLS = """
    COUNT(h.match_id)                                             AS matches_in_window,
    SUM(h.bat_pp_runs)    / NULLIF(SUM(h.bat_pp_balls)/6.0,0)     AS rr_powerplay,
    SUM(h.bat_mid_runs)   / NULLIF(SUM(h.bat_mid_balls)/6.0,0)    AS rr_middle,
    SUM(h.bat_death_runs) / NULLIF(SUM(h.bat_death_balls)/6.0,0)  AS rr_death,
    SUM(h.bowl_pp_runs)   / NULLIF(SUM(h.bowl_pp_balls)/6.0,0)    AS econ_powerplay,
    SUM(h.bowl_mid_runs)  / NULLIF(SUM(h.bowl_mid_balls)/6.0,0)   AS econ_middle,
    SUM(h.bowl_death_runs)/ NULLIF(SUM(h.bowl_death_balls)/6.0,0) AS econ_death,
    AVG(CAST(h.won AS DOUBLE))                                    AS win_pct,
    AVG(h.team_runs - h.opp_runs)                                AS avg_margin
"""


def build_team_form(con: duckdb.DuckDBPyConnection):
    # window='last5' — team's last 5 completed matches strictly before D.
    # Target keys are renamed tgt_* so h.* (history) keeps its own match_id.
    con.execute(f"""
        CREATE TEMP TABLE tf_last5 AS
        WITH ranked AS (
            SELECT t.match_id AS tgt_match_id, t.team_id AS tgt_team_id,
                   t.as_of_date, t.tournament_id AS tgt_tournament_id, h.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY t.match_id, t.team_id
                       ORDER BY h.match_date DESC, h.match_id DESC
                   ) AS rn
            FROM targets t
            LEFT JOIN team_match_history h
                   ON h.team_id = t.team_id
                  AND h.match_date < t.as_of_date          -- STRICTLY before
        )
        SELECT tgt_match_id AS match_id, tgt_team_id AS team_id, as_of_date,
               tgt_tournament_id AS tournament_id, 'last5' AS "window",
               {_AGG_COLS}
        FROM ranked h
        WHERE h.match_id IS NULL OR h.rn <= 5              -- keep empty targets
        GROUP BY tgt_match_id, tgt_team_id, as_of_date, tgt_tournament_id;
    """)

    # window='tournament' — team's completed matches in the SAME tournament before D.
    con.execute(f"""
        CREATE TEMP TABLE tf_tourn AS
        SELECT t.match_id, t.team_id, t.as_of_date, t.tournament_id,
               'tournament' AS "window",
               {_AGG_COLS}
        FROM targets t
        LEFT JOIN team_match_history h
               ON h.team_id = t.team_id
              AND h.tournament_id = t.tournament_id
              AND h.match_date < t.as_of_date              -- STRICTLY before
        GROUP BY t.match_id, t.team_id, t.as_of_date, t.tournament_id;
    """)

    return con.execute("""
        SELECT match_id, team_id, as_of_date, tournament_id, "window",
               matches_in_window,
               rr_powerplay, rr_middle, rr_death,
               econ_powerplay, econ_middle, econ_death,
               win_pct, avg_margin
        FROM tf_last5
        UNION ALL
        SELECT match_id, team_id, as_of_date, tournament_id, "window",
               matches_in_window,
               rr_powerplay, rr_middle, rr_death,
               econ_powerplay, econ_middle, econ_death,
               win_pct, avg_margin
        FROM tf_tourn
        ORDER BY match_id, team_id, "window";
    """).df()


# --------------------------------------------------------------------------
# 2) venue_stats
# --------------------------------------------------------------------------
def build_venue_stats(con: duckdb.DuckDBPyConnection):
    # completed matches at a venue, with first-innings score + win-type
    con.execute("""
        CREATE TEMP TABLE venue_history AS
        SELECT d.match_id, d.venue_key, d.match_date, d.result_type,
               fi.first_innings_runs
        FROM dim_match d
        LEFT JOIN first_innings fi ON fi.match_id = d.match_id
        WHERE d.winner IS NOT NULL AND d.venue_key IS NOT NULL;
    """)
    # snapshot targets: every distinct (venue_key, as_of_date) on the schedule
    con.execute("""
        CREATE TEMP TABLE venue_targets AS
        SELECT DISTINCT venue_key, match_date AS as_of_date
        FROM dim_match
        WHERE venue_key IS NOT NULL;
    """)
    return con.execute("""
        SELECT
            t.venue_key,
            t.as_of_date,
            COUNT(h.match_id)                                   AS matches_at_venue,
            AVG(h.first_innings_runs)                           AS avg_first_innings_score,
            -- decisive matches only for win-split (exclude ties / no-result / DL 'draw')
            SUM(CASE WHEN h.result_type='runs'    THEN 1 ELSE 0 END)
                / NULLIF(SUM(CASE WHEN h.result_type IN ('runs','wickets') THEN 1 ELSE 0 END),0)::DOUBLE
                                                               AS batfirst_win_pct,
            SUM(CASE WHEN h.result_type='wickets' THEN 1 ELSE 0 END)
                / NULLIF(SUM(CASE WHEN h.result_type IN ('runs','wickets') THEN 1 ELSE 0 END),0)::DOUBLE
                                                               AS chase_win_pct
        FROM venue_targets t
        LEFT JOIN venue_history h
               ON h.venue_key = t.venue_key
              AND h.match_date < t.as_of_date                  -- STRICTLY before
        GROUP BY t.venue_key, t.as_of_date
        ORDER BY t.venue_key, t.as_of_date;
    """).df()


# --------------------------------------------------------------------------
# 3) match_conditions
# --------------------------------------------------------------------------
def build_match_conditions(con: duckdb.DuckDBPyConnection):
    """
    Per T20-men match: toss + day/night + dew flag.

    - toss_winner / toss_decision: parsed from L0 cricket__matches.toss JSON
      ({"winner":"a|b","elected":"bat|bowl"}). NULL for not-yet-played matches
      (lifecycle: live-sourced at prediction time; present here for backtest).
    - day_night: heuristic from local start hour (>=15:00 local -> day/night
      session that runs under lights, else a day match). Source has no explicit
      flag.
    - dew_flag: heuristic proxy = 1 for night sessions (dew forms after dark),
      else 0. The raw data carries NO explicit dew measurement, so this is a
      derived signal, not ground truth — flagged as such for the model owner.
    """
    return con.execute(f"""
        WITH toss AS (
            SELECT
                CAST(id AS BIGINT) AS match_id,
                NULLIF(json_extract_string(toss, '$.winner'), '')  AS toss_side,
                NULLIF(json_extract_string(toss, '$.elected'), '') AS toss_decision
            FROM read_parquet('{L0_MATCHES}')
        )
        SELECT
            m.match_id,
            CASE t.toss_side WHEN 'a' THEN m.team_a_id
                             WHEN 'b' THEN m.team_b_id END          AS toss_winner,
            t.toss_side,
            t.toss_decision,
            CASE WHEN m.start_at_local IS NULL THEN NULL
                 WHEN EXTRACT(hour FROM m.start_at_local) >= 15 THEN 'day_night'
                 ELSE 'day' END                                    AS day_night,
            CASE WHEN m.start_at_local IS NULL THEN NULL
                 WHEN EXTRACT(hour FROM m.start_at_local) >= 15 THEN 1
                 ELSE 0 END                                        AS dew_flag
        FROM dim_match m
        LEFT JOIN toss t ON t.match_id = m.match_id
        ORDER BY m.match_id;
    """).df()


# --------------------------------------------------------------------------
# 4) match_odds_devig
# --------------------------------------------------------------------------
def build_match_odds_devig(con: duckdb.DuckDBPyConnection):
    """
    Devigged home/away win probabilities for bridge-linked priced T20-men
    matches. odd_match_odds can carry several vendor rows (and a match can be
    linked to >1 odds fixture), so we take the mean decimal price per
    (internal match, home/away) as the consensus line, then de-vig.
    """
    return con.execute(f"""
        WITH priced AS (
            SELECT
                CAST(match_id AS BIGINT) AS odds_match_id,
                generic_name,
                CAST(value AS DOUBLE)    AS odds
            FROM read_parquet('{L0_ODDS}')
            WHERE market = 'Winner 2 Ways'
              AND generic_name IN ('team_home_name','team_away_name')
        ),
        linked AS (
            SELECT DISTINCT
                CAST(b.odds_match_id AS BIGINT)     AS odds_match_id,
                CAST(b.internal_match_id AS BIGINT) AS match_id
            FROM read_parquet('{L1_MATCH_BRIDGE}') b
            JOIN dim_match m ON m.match_id = CAST(b.internal_match_id AS BIGINT)
        ),
        per_match AS (
            SELECT
                l.match_id,
                AVG(CASE WHEN p.generic_name='team_home_name' THEN p.odds END) AS home_odds,
                AVG(CASE WHEN p.generic_name='team_away_name' THEN p.odds END) AS away_odds
            FROM linked l
            JOIN priced p ON p.odds_match_id = l.odds_match_id
            GROUP BY l.match_id
        )
        SELECT
            match_id,
            home_odds,
            away_odds,
            (1.0/home_odds) / ((1.0/home_odds)+(1.0/away_odds)) AS home_devig,
            (1.0/away_odds) / ((1.0/home_odds)+(1.0/away_odds)) AS away_devig
        FROM per_match
        WHERE home_odds IS NOT NULL AND away_odds IS NOT NULL
        ORDER BY match_id;
    """).df()


# --------------------------------------------------------------------------
# Write helpers + main
# --------------------------------------------------------------------------
def write_parquet(con: duckdb.DuckDBPyConnection, df, name: str) -> str:
    out_dir = L2 / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = (out_dir / f"{name}.parquet").as_posix()
    con.register("_tmp_df", df)
    con.execute(f"COPY _tmp_df TO '{out}' (FORMAT PARQUET);")
    con.unregister("_tmp_df")
    return out


def main() -> None:
    L2.mkdir(parents=True, exist_ok=True)
    con = connect()

    print("Building per-match ball features ...")
    build_ball_features(con)
    build_team_match_history(con)
    build_targets(con)

    print("Building team_form ...")
    team_form = build_team_form(con)
    print("Building venue_stats ...")
    venue_stats = build_venue_stats(con)
    print("Building match_conditions ...")
    match_conditions = build_match_conditions(con)
    print("Building match_odds_devig ...")
    match_odds_devig = build_match_odds_devig(con)

    datasets = {
        "team_form": team_form,
        "venue_stats": venue_stats,
        "match_conditions": match_conditions,
        "match_odds_devig": match_odds_devig,
    }
    for name, df in datasets.items():
        path = write_parquet(con, df, name)
        print(f"  wrote {name}: {len(df):,} rows -> {path}")

    # ---- manifest ----
    manifest = {
        "layer": "L2",
        "purpose": "point-in-time team aggregates (MVP winner model)",
        "source": "data/lake/l1 (+ L0 odds prices & raw toss JSON, read-only)",
        "build_timestamp": datetime.now().isoformat(timespec="seconds"),
        "anti_leakage_rule": "every row uses only completed (winner-not-null) "
                             "matches with date STRICTLY < as_of_date",
        "completed_definition": "winner IN ('a','b')",
        "phase_overs": {"powerplay": "1-6", "middle": "7-15", "death": "16-20"},
        "notes": {
            "avg_margin": "signed run differential (team_runs - opp_runs) averaged "
                          "over window matches with ball data; uniform unit = runs, "
                          "sign encodes win/loss magnitude.",
            "avg_first_innings_score": "from ball-by-ball; innings order by ts_primary "
                                       "(target_runs is empty in source).",
            "ball_data_coverage": "only ~2218/4036 completed matches carry ball-by-ball; "
                                  "phase rates are NULL where the window has no ball data.",
            "dew_flag": "HEURISTIC (night session -> 1). No explicit dew field in source.",
            "day_night": "HEURISTIC from local start hour (>=15:00 -> day_night).",
            "odds": "mean vendor decimal price per match; bridge-linked priced T20-men only.",
        },
        "row_counts": {name: int(len(df)) for name, df in datasets.items()},
    }
    (L2 / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"  wrote _manifest.json")

    _console_summary(con, datasets)
    con.close()


def _console_summary(con, datasets) -> None:
    import pandas as pd
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 60)

    print("\n" + "=" * 70)
    print("L2 BUILD SUMMARY")
    print("=" * 70)
    print("\nRow counts per L2 dataset:")
    for name, df in datasets.items():
        print(f"  {name:20s} {len(df):>8,} rows")

    tf = datasets["team_form"]
    print("\nteam_form coverage:")
    print(f"  snapshots total          : {len(tf):,}")
    print(f"  rows w/ >=1 match         : {(tf['matches_in_window']>0).sum():,}")
    print(f"  rows w/ powerplay rr avail: {tf['rr_powerplay'].notna().sum():,}")

    # ---- hand-checkable sample: one well-known team, one date ----
    # Pick an India men's snapshot if present, else the team with most snapshots.
    dm = con.execute("""
        SELECT team_id, team_name FROM read_parquet($p)
    """.replace("$p", f"'{(L1/'dim_team'/'dim_team.parquet').as_posix()}'")).df()
    name_by_id = dict(zip(dm.team_id.astype("int64"), dm.team_name))

    sample_team = None
    for tid, nm in name_by_id.items():
        if isinstance(nm, str) and nm.strip().lower() == "india":
            sample_team = tid
            break
    if sample_team is None:
        sample_team = int(tf.groupby("team_id").size().idxmax())

    sub = tf[tf.team_id == sample_team]
    # Prefer a snapshot where BOTH windows carry history (richer hand-check):
    # rank match_ids by the tournament-window match count, tie-break on recency.
    tourn = sub[(sub["window"] == "tournament") & (sub.matches_in_window > 0)]
    if len(tourn):
        pick_match = int(tourn.sort_values(
            ["matches_in_window", "as_of_date"]).iloc[-1]["match_id"])
    else:
        cand = sub[sub.matches_in_window > 0]
        pick_match = int(cand.sort_values("as_of_date").iloc[-1]["match_id"]) if len(cand) else int(sub.iloc[0]["match_id"])

    print("\n" + "-" * 70)
    print(f"SAMPLE team_form  team_id={sample_team} "
          f"({name_by_id.get(sample_team,'?')})  match_id={pick_match}")
    print("-" * 70)
    show = tf[(tf.team_id == sample_team) & (tf.match_id == pick_match)]
    with pd.option_context("display.float_format", lambda v: f"{v:,.3f}"):
        print(show.to_string(index=False))

    print("\nSee tests/test_leakage.py for the mandatory leakage assertions.")


if __name__ == "__main__":
    main()
