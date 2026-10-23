"""
build_l2.py — L2 point-in-time team aggregates (MVP, winner model).

Reads L1 (data/lake/l1/) + a little L0 (odds prices, raw toss JSON). NEVER
modifies L0 or L1. Writes L2 Parquet to data/lake/l2/.

CORE RULE (anti-leakage): every aggregate row carries an `as_of_date` and is
computed using ONLY completed matches STRICTLY BEFORE that date. A "completed"
match here means one with a recorded outcome (winner in {'a','b'}); this also
cleanly excludes the handful of future-dated rows that are flagged
is_completed=True but have no winner yet.

SNAPSHOT GRAIN: for EVERY in-scope T20 match M (men + women; dim_match.gender) (played or not-yet-played), with
D = date(M.start_at), we emit a pre-match snapshot for each of the two
participating teams, as_of_date = D. Future matches are valid targets; their
snapshot simply uses only past completed data.

Datasets produced:
  1) team_form       grain (match_id, team_id, window)   [as_of_date carried]
                     windows: last5 | tournament (league_key-scoped, model
                     feature) | current_event (tournament_id-scoped, content
                     layer: "this season/tour so far"; L3 ignores it)
  2) venue_stats     grain (venue_key, as_of_date)
  3) match_conditions grain (match_id)
  4) match_odds_devig grain (match_id)  — bridge-linked priced in-scope T20 only
  5) player_form     grain (match_id, team_id, player_key, window)
                     [iteration 2, content layer] windows: last5 (the TEAM's
                     last 5 completed matches) | current_event.
                     SOURCE CHOICE (documented): L0 player_batting_scores /
                     player_bowling_scores joined via the cricket__players
                     per-match roster (score.player_id -> players.id, 100%
                     join coverage, real ids). NOT the L1 ball-by-ball
                     comment parse: that covers only ~2218/4036 completed
                     matches and rests on name-string parsing. The score
                     tables are the cleaner source by both coverage and
                     linkage. Note cricket__players.playing_xi is NOT read
                     here (leakage rule README §1.3): only realized score
                     rows of completed past matches contribute.
  6) standings       grain (tournament_id, as_of_date, team_id)
                     [iteration 2, content layer] DERIVED from dim_match
                     decided results, point-in-time. The raw
                     cricket__tournament_points table is a CURRENT-STATE
                     snapshot updated in place (verified: exactly 1 row per
                     (tournament_id, team_code), rolling updated_at) and is
                     therefore unusable for as-of-date standings. Derivation
                     convention: points = 2 * wins, decided matches only
                     (ties/no-results excluded — rare in T20); position
                     ranks by points, wins, then ball-data run differential
                     (NRR proxy; official NRR is not derivable for matches
                     without ball coverage). Positions are therefore
                     approximate around NRR-decided ties.

  7) home_ground     grain (match_id, team_id)
                     [iteration 2b, content layer] Is the TARGET match's
                     venue this team's own ground? Derived point-in-time
                     from the team's completed same-league matches strictly
                     before as_of_date: is_home_ground = the team has
                     played >= 10 prior league matches AT this venue AND
                     that venue holds >= 30% of its prior league matches
                     (HIGH-confidence gate; thresholds at
                     HOME_GROUND_MIN_*; a team may qualify at more than
                     one venue, e.g. after a ground move).
                     NOTE: the task brief said "derive in L1", but a static
                     L1 table would leak (an early-season signal would see
                     future matches). Same derivation, made point-in-time,
                     lives here instead. International sides rotating
                     grounds rarely reach 30% at one venue and fall to
                     is_home_ground = false with counts shown - the signal
                     targets franchise-league grounds specifically.

player_form, standings and home_ground carry a max_source_date audit
column so the leakage test can mechanically assert max_source_date <
as_of_date per row.

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
L1_TOURNAMENT = (L1 / "dim_tournament" / "dim_tournament.parquet").as_posix()
L1_MATCH_BRIDGE = (L1 / "bridge" / "match_bridge.parquet").as_posix()
L0_ODDS = (L0 / "odd_match_odds" / "*.parquet").as_posix()
L0_MATCHES = (L0 / "cricket__matches" / "*.parquet").as_posix()
L0_PLAYERS = (L0 / "cricket__players" / "*.parquet").as_posix()
L0_BAT_SCORES = (L0 / "cricket__player_batting_scores" / "*.parquet").as_posix()
L0_BOWL_SCORES = (L0 / "cricket__player_bowling_scores" / "*.parquet").as_posix()

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
            CAST(m.match_id   AS BIGINT) AS match_id,
            CAST(m.tournament_id AS BIGINT) AS tournament_id,
            t.league_key,
            m.gender,                    -- male | female (scope widened for WBBL)
            CAST(m.team_a_id  AS BIGINT) AS team_a_id,
            CAST(m.team_b_id  AS BIGINT) AS team_b_id,
            m.start_at,
            m.start_at_local,
            CAST(m.start_at AS DATE)     AS match_date,
            m.winner,
            m.result_type,
            m.venue_key
        FROM read_parquet('{L1_DIM_MATCH}') m
        LEFT JOIN read_parquet('{L1_TOURNAMENT}') t
               ON CAST(t.tournament_id AS BIGINT) = CAST(m.tournament_id AS BIGINT);
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
            batter_id,                     -- comment-parsed roster keys
            bowler_id,                     -- (iteration 3: player_phase)
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
            SELECT match_id, match_date, tournament_id, league_key,
                   team_a_id AS team_id, team_b_id AS opp_id, 'a' AS side, 'b' AS opp_side,
                   CASE WHEN winner='a' THEN 1 ELSE 0 END AS won
            FROM decided
            UNION ALL
            SELECT match_id, match_date, tournament_id, league_key,
                   team_b_id AS team_id, team_a_id AS opp_id, 'b' AS side, 'a' AS opp_side,
                   CASE WHEN winner='b' THEN 1 ELSE 0 END AS won
            FROM decided
        )
        SELECT
            s.match_id, s.team_id, s.opp_id, s.match_date, s.tournament_id,
            s.league_key, s.won,
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
    """Every in-scope T20 match (played or not) x its two teams = snapshot targets."""
    con.execute("""
        CREATE TEMP TABLE targets AS
        SELECT match_id, team_a_id AS team_id, match_date AS as_of_date,
               tournament_id, league_key, venue_key
        FROM dim_match
        UNION ALL
        SELECT match_id, team_b_id AS team_id, match_date AS as_of_date,
               tournament_id, league_key, venue_key
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
                   t.as_of_date, t.tournament_id AS tgt_tournament_id,
                   t.league_key AS tgt_league_key, h.*,
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
               tgt_tournament_id AS tournament_id, tgt_league_key AS league_key,
               'last5' AS "window",
               {_AGG_COLS}
        FROM ranked h
        WHERE h.match_id IS NULL OR h.rn <= 5              -- keep empty targets
        GROUP BY tgt_match_id, tgt_team_id, as_of_date, tgt_tournament_id,
                 tgt_league_key;
    """)

    # window='tournament' — team's completed matches in the SAME LEAGUE before D.
    # Keyed on league_key (year-stripped), so IPL's 4 season ids form one
    # coherent group (e.g. IPL-2025 form draws on all prior IPL seasons).
    con.execute(f"""
        CREATE TEMP TABLE tf_tourn AS
        SELECT t.match_id, t.team_id, t.as_of_date, t.tournament_id, t.league_key,
               'tournament' AS "window",
               {_AGG_COLS}
        FROM targets t
        LEFT JOIN team_match_history h
               ON h.team_id = t.team_id
              AND h.league_key = t.league_key
              AND h.match_date < t.as_of_date              -- STRICTLY before
        GROUP BY t.match_id, t.team_id, t.as_of_date, t.tournament_id, t.league_key;
    """)

    # window='current_event' — completed matches in the SAME tournament_id
    # (the single current season/tour) strictly before D. Content-layer
    # window ("this tour so far"); the model keeps the league_key window,
    # and build_l3 pivots only last5/tournament so L3 is unaffected.
    con.execute(f"""
        CREATE TEMP TABLE tf_event AS
        SELECT t.match_id, t.team_id, t.as_of_date, t.tournament_id, t.league_key,
               'current_event' AS "window",
               {_AGG_COLS}
        FROM targets t
        LEFT JOIN team_match_history h
               ON h.team_id = t.team_id
              AND h.tournament_id = t.tournament_id
              AND h.match_date < t.as_of_date              -- STRICTLY before
        GROUP BY t.match_id, t.team_id, t.as_of_date, t.tournament_id, t.league_key;
    """)

    return con.execute("""
        SELECT match_id, team_id, as_of_date, tournament_id, league_key, "window",
               matches_in_window,
               rr_powerplay, rr_middle, rr_death,
               econ_powerplay, econ_middle, econ_death,
               win_pct, avg_margin
        FROM tf_last5
        UNION ALL
        SELECT match_id, team_id, as_of_date, tournament_id, league_key, "window",
               matches_in_window,
               rr_powerplay, rr_middle, rr_death,
               econ_powerplay, econ_middle, econ_death,
               win_pct, avg_margin
        FROM tf_tourn
        UNION ALL
        SELECT match_id, team_id, as_of_date, tournament_id, league_key, "window",
               matches_in_window,
               rr_powerplay, rr_middle, rr_death,
               econ_powerplay, econ_middle, econ_death,
               win_pct, avg_margin
        FROM tf_event
        ORDER BY match_id, team_id, "window";
    """).df()


# --------------------------------------------------------------------------
# 2) venue_stats
# --------------------------------------------------------------------------
def build_venue_stats(con: duckdb.DuckDBPyConnection):
    """Venue split per (venue_key, GENDER, as_of_date).

    GENDER-SCOPED: men's and women's T20s share grounds (WBBL plays at the
    BBL venues) but have different scoring levels, so the venue sample behind
    a match is same-gender only. Men's venue numbers are therefore unchanged
    by the scope widening; women's matches get their own venue history.
    """
    # completed matches at a venue, with first-innings score + win-type
    con.execute("""
        CREATE TEMP TABLE venue_history AS
        SELECT d.match_id, d.venue_key, d.gender, d.match_date, d.result_type,
               fi.first_innings_runs
        FROM dim_match d
        LEFT JOIN first_innings fi ON fi.match_id = d.match_id
        WHERE d.winner IS NOT NULL AND d.venue_key IS NOT NULL;
    """)
    # snapshot targets: every distinct (venue_key, gender, as_of_date) on the schedule
    con.execute("""
        CREATE TEMP TABLE venue_targets AS
        SELECT DISTINCT venue_key, gender, match_date AS as_of_date
        FROM dim_match
        WHERE venue_key IS NOT NULL;
    """)
    return con.execute("""
        SELECT
            t.venue_key,
            t.gender,
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
              AND h.gender = t.gender                          -- same-gender sample
              AND h.match_date < t.as_of_date                  -- STRICTLY before
        GROUP BY t.venue_key, t.gender, t.as_of_date
        ORDER BY t.venue_key, t.gender, t.as_of_date;
    """).df()


# --------------------------------------------------------------------------
# 3) match_conditions
# --------------------------------------------------------------------------
def build_match_conditions(con: duckdb.DuckDBPyConnection):
    """
    Per in-scope T20 match: toss + day/night + dew flag.

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
# 5) player_form  (iteration 2, content layer)
# --------------------------------------------------------------------------
def build_player_form(con: duckdb.DuckDBPyConnection):
    """
    Point-in-time per-player form, per (target match, team, window).

    Source: L0 pre-aggregated score tables joined through the
    cricket__players per-match roster (see module docstring for why this
    beats the ball-by-ball comment parse). Player identity = the roster
    `key` (stable across matches, matches dim_player.player_key).

    Batting: runs, balls, innings, strike_rate (100*runs/balls).
    Bowling: wickets, overs (balls/6, decimal overs), economy
    (runs per 6 legal-ball over as recorded by the source).
    """
    # one row per (match, team, player) with that match's realized scores
    con.execute(f"""
        CREATE TEMP TABLE player_match_scores AS
        WITH bat AS (
            SELECT player_id, SUM(runs) AS runs, SUM(balls) AS balls,
                   COUNT(*) AS innings
            FROM read_parquet('{L0_BAT_SCORES}') GROUP BY player_id
        ),
        bowl AS (
            SELECT player_id, SUM(wickets) AS wickets, SUM(balls) AS balls,
                   SUM(runs) AS runs, COUNT(*) AS innings
            FROM read_parquet('{L0_BOWL_SCORES}') GROUP BY player_id
        )
        SELECT
            CAST(p.match_id AS BIGINT) AS match_id,
            CAST(p.team_id  AS BIGINT) AS team_id,
            p.key                      AS player_key,
            MAX(p.name)                AS player_name,
            SUM(b.runs)                AS bat_runs,
            SUM(b.balls)               AS bat_balls,
            SUM(b.innings)             AS bat_innings,
            SUM(w.wickets)             AS wickets,
            SUM(w.balls)               AS bowl_balls,
            SUM(w.runs)                AS bowl_runs,
            SUM(w.innings)             AS bowl_innings
        FROM read_parquet('{L0_PLAYERS}') p
        LEFT JOIN bat  b ON b.player_id = p.id
        LEFT JOIN bowl w ON w.player_id = p.id
        WHERE b.player_id IS NOT NULL OR w.player_id IS NOT NULL
        GROUP BY 1, 2, 3;
    """)

    _pf_aggs = """
            COUNT(*)                                              AS matches_in_window,
            SUM(s.bat_runs)                                       AS bat_runs,
            SUM(s.bat_balls)                                      AS bat_balls,
            SUM(s.bat_innings)                                    AS bat_innings,
            100.0 * SUM(s.bat_runs) / NULLIF(SUM(s.bat_balls),0)  AS strike_rate,
            SUM(s.wickets)                                        AS wickets,
            SUM(s.bowl_balls) / 6.0                               AS overs,
            SUM(s.bowl_runs) / NULLIF(SUM(s.bowl_balls)/6.0, 0)   AS economy,
            SUM(s.bowl_innings)                                   AS bowl_innings
    """

    # window='last5': the TEAM's last 5 completed matches strictly before D
    con.execute(f"""
        CREATE TEMP TABLE pf_last5 AS
        WITH ranked AS (
            SELECT t.match_id AS tgt_match_id, t.team_id AS tgt_team_id,
                   t.as_of_date,
                   h.match_id AS hist_match_id, h.match_date AS hist_date,
                   ROW_NUMBER() OVER (
                       PARTITION BY t.match_id, t.team_id
                       ORDER BY h.match_date DESC, h.match_id DESC
                   ) AS rn
            FROM targets t
            JOIN team_match_history h
              ON h.team_id = t.team_id
             AND h.match_date < t.as_of_date               -- STRICTLY before
        )
        SELECT r.tgt_match_id AS match_id, r.tgt_team_id AS team_id,
               r.as_of_date, s.player_key,
               MAX(s.player_name) AS player_name,
               'last5' AS "window",
               {_pf_aggs},
               MAX(r.hist_date) AS max_source_date
        FROM ranked r
        JOIN player_match_scores s
          ON s.match_id = r.hist_match_id AND s.team_id = r.tgt_team_id
        WHERE r.rn <= 5
        GROUP BY r.tgt_match_id, r.tgt_team_id, r.as_of_date, s.player_key;
    """)

    # window='current_event': same tournament_id, strictly before D
    con.execute(f"""
        CREATE TEMP TABLE pf_event AS
        SELECT t.match_id, t.team_id, t.as_of_date, s.player_key,
               MAX(s.player_name) AS player_name,
               'current_event' AS "window",
               {_pf_aggs},
               MAX(h.match_date) AS max_source_date
        FROM targets t
        JOIN team_match_history h
          ON h.team_id = t.team_id
         AND h.tournament_id = t.tournament_id
         AND h.match_date < t.as_of_date                   -- STRICTLY before
        JOIN player_match_scores s
          ON s.match_id = h.match_id AND s.team_id = t.team_id
        GROUP BY t.match_id, t.team_id, t.as_of_date, s.player_key;
    """)

    return con.execute("""
        SELECT * FROM pf_last5
        UNION ALL
        SELECT * FROM pf_event
        ORDER BY match_id, team_id, "window", player_key;
    """).df()


# --------------------------------------------------------------------------
# 5b) player_phase  (iteration 3, content layer)
# --------------------------------------------------------------------------
def build_player_phase(con: duckdb.DuckDBPyConnection):
    """
    Point-in-time per-player PHASE splits, per (target match, team, window),
    from L1 ball-by-ball (fact.batter_id / bowler_id — the comment-parsed
    ids, which match the roster `key` 1:1 on the covered matches).

    Batting (the player's own deliveries faced):
        balls faced = deliveries excluding wides; runs = the `runs` column
        (off-the-bat; extras rows carry runs=0 in this source, no_ball rows
        include the single penalty — an accepted approximation).
    Bowling (deliveries the player bowled):
        legal balls = excluding wides/no-balls (same convention as the
        team-level phase econ); runs = the `runs` column.

    COVERAGE: only ~55% of completed matches carry ball data, so a window's
    phase split may rest on FEWER matches than the player_form window it
    accompanies (phase_matches counts them). Rows exist only where at least
    one covered delivery exists; the content layer omits the block silently
    otherwise (NULL-safe by absence). Windows mirror player_form: last5
    (the TEAM's last 5 completed matches) | current_event. max_source_date
    audit column as usual.
    """
    # per (match, team, player, phase) tallies, batting and bowling
    con.execute("""
        CREATE TEMP TABLE player_ball_phase AS
        WITH tagged AS (
            SELECT f.match_id, f.side, f.ball_type, f.runs,
                   f.batter_id, f.bowler_id,
                   CASE
                       WHEN f.over_number BETWEEN 1  AND 6  THEN 'pp'
                       WHEN f.over_number BETWEEN 7  AND 15 THEN 'mid'
                       ELSE 'death'
                   END AS phase,
                   d.team_a_id, d.team_b_id
            FROM fact f
            JOIN dim_match d ON d.match_id = f.match_id
            WHERE f.batter_id IS NOT NULL OR f.bowler_id IS NOT NULL
        ),
        bat AS (
            SELECT match_id,
                   CASE side WHEN 'a' THEN team_a_id ELSE team_b_id END AS team_id,
                   batter_id AS player_key, phase,
                   SUM(CASE WHEN ball_type != 'wide' THEN 1 ELSE 0 END) AS bat_balls,
                   SUM(runs) AS bat_runs
            FROM tagged WHERE batter_id IS NOT NULL
            GROUP BY 1, 2, 3, 4
        ),
        bowl AS (
            SELECT match_id,
                   CASE side WHEN 'a' THEN team_b_id ELSE team_a_id END AS team_id,
                   bowler_id AS player_key, phase,
                   SUM(CASE WHEN ball_type NOT IN ('wide','no_ball')
                            THEN 1 ELSE 0 END) AS bowl_balls,
                   SUM(runs) AS bowl_runs
            FROM tagged WHERE bowler_id IS NOT NULL
            GROUP BY 1, 2, 3, 4
        )
        SELECT COALESCE(b.match_id, w.match_id)     AS match_id,
               COALESCE(b.team_id, w.team_id)       AS team_id,
               COALESCE(b.player_key, w.player_key) AS player_key,
               COALESCE(b.phase, w.phase)           AS phase,
               b.bat_balls, b.bat_runs, w.bowl_balls, w.bowl_runs
        FROM bat b
        FULL OUTER JOIN bowl w
          ON w.match_id = b.match_id AND w.team_id = b.team_id
         AND w.player_key = b.player_key AND w.phase = b.phase;
    """)

    _phase_aggs = """
            COUNT(DISTINCT s.match_id)                              AS phase_matches,
            SUM(CASE WHEN s.phase='pp'    THEN s.bat_runs  END)     AS bat_pp_runs,
            SUM(CASE WHEN s.phase='pp'    THEN s.bat_balls END)     AS bat_pp_balls,
            SUM(CASE WHEN s.phase='mid'   THEN s.bat_runs  END)     AS bat_mid_runs,
            SUM(CASE WHEN s.phase='mid'   THEN s.bat_balls END)     AS bat_mid_balls,
            SUM(CASE WHEN s.phase='death' THEN s.bat_runs  END)     AS bat_death_runs,
            SUM(CASE WHEN s.phase='death' THEN s.bat_balls END)     AS bat_death_balls,
            SUM(CASE WHEN s.phase='pp'    THEN s.bowl_runs  END)    AS bowl_pp_runs,
            SUM(CASE WHEN s.phase='pp'    THEN s.bowl_balls END)    AS bowl_pp_balls,
            SUM(CASE WHEN s.phase='mid'   THEN s.bowl_runs  END)    AS bowl_mid_runs,
            SUM(CASE WHEN s.phase='mid'   THEN s.bowl_balls END)    AS bowl_mid_balls,
            SUM(CASE WHEN s.phase='death' THEN s.bowl_runs  END)    AS bowl_death_runs,
            SUM(CASE WHEN s.phase='death' THEN s.bowl_balls END)    AS bowl_death_balls
    """

    # window='last5': the TEAM's last 5 completed matches strictly before D
    con.execute(f"""
        CREATE TEMP TABLE pp_last5 AS
        WITH ranked AS (
            SELECT t.match_id AS tgt_match_id, t.team_id AS tgt_team_id,
                   t.as_of_date,
                   h.match_id AS hist_match_id, h.match_date AS hist_date,
                   ROW_NUMBER() OVER (
                       PARTITION BY t.match_id, t.team_id
                       ORDER BY h.match_date DESC, h.match_id DESC
                   ) AS rn
            FROM targets t
            JOIN team_match_history h
              ON h.team_id = t.team_id
             AND h.match_date < t.as_of_date               -- STRICTLY before
        )
        SELECT r.tgt_match_id AS match_id, r.tgt_team_id AS team_id,
               r.as_of_date, s.player_key,
               'last5' AS "window",
               {_phase_aggs},
               MAX(r.hist_date) AS max_source_date
        FROM ranked r
        JOIN player_ball_phase s
          ON s.match_id = r.hist_match_id AND s.team_id = r.tgt_team_id
        WHERE r.rn <= 5
        GROUP BY r.tgt_match_id, r.tgt_team_id, r.as_of_date, s.player_key;
    """)

    # window='current_event': same tournament_id, strictly before D
    con.execute(f"""
        CREATE TEMP TABLE pp_event AS
        SELECT t.match_id, t.team_id, t.as_of_date, s.player_key,
               'current_event' AS "window",
               {_phase_aggs},
               MAX(h.match_date) AS max_source_date
        FROM targets t
        JOIN team_match_history h
          ON h.team_id = t.team_id
         AND h.tournament_id = t.tournament_id
         AND h.match_date < t.as_of_date                   -- STRICTLY before
        JOIN player_ball_phase s
          ON s.match_id = h.match_id AND s.team_id = t.team_id
        GROUP BY t.match_id, t.team_id, t.as_of_date, s.player_key;
    """)

    return con.execute("""
        SELECT * FROM pp_last5
        UNION ALL
        SELECT * FROM pp_event
        ORDER BY match_id, team_id, "window", player_key;
    """).df()


# --------------------------------------------------------------------------
# 6) standings  (iteration 2, content layer)
# --------------------------------------------------------------------------
def build_standings(con: duckdb.DuckDBPyConnection):
    """
    Point-in-time standings per (tournament_id, as_of_date, team_id),
    DERIVED from dim_match decided results (see module docstring for why
    the raw tournament_points table cannot be used). Standings as of the
    day before: strictly-before match_date = everything through D-1.

    Convention: points = 2 * wins over DECIDED matches only (ties and
    no-results excluded; standard T20 league scoring, minus the rare
    1-point NR which the source cannot attribute cleanly). position ranks
    points desc, wins desc, run_diff desc (ball-data NRR proxy; NULL where
    no ball coverage) then team_id for determinism. n_teams_in_event comes
    from the full schedule, so it's stable across as_of dates.
    """
    return con.execute("""
        WITH tgt AS (
            SELECT DISTINCT tournament_id, match_date AS as_of_date
            FROM dim_match
        ),
        event_teams AS (
            SELECT tournament_id, COUNT(DISTINCT team_id) AS n_teams_in_event
            FROM (
                SELECT tournament_id, team_a_id AS team_id FROM dim_match
                UNION
                SELECT tournament_id, team_b_id FROM dim_match
            )
            GROUP BY tournament_id
        ),
        agg AS (
            SELECT t.tournament_id, t.as_of_date, h.team_id,
                   COUNT(*)                      AS played,
                   SUM(h.won)                    AS won,
                   COUNT(*) - SUM(h.won)         AS lost,
                   2 * SUM(h.won)                AS points,
                   SUM(h.team_runs - h.opp_runs) AS run_diff,
                   MAX(h.match_date)             AS max_source_date
            FROM tgt t
            JOIN team_match_history h
              ON h.tournament_id = t.tournament_id
             AND h.match_date < t.as_of_date               -- STRICTLY before
            GROUP BY t.tournament_id, t.as_of_date, h.team_id
        )
        SELECT a.*,
               ROW_NUMBER() OVER (
                   PARTITION BY a.tournament_id, a.as_of_date
                   ORDER BY a.points DESC, a.won DESC,
                            a.run_diff DESC NULLS LAST, a.team_id
               ) AS position,
               e.n_teams_in_event
        FROM agg a
        JOIN event_teams e ON e.tournament_id = a.tournament_id
        ORDER BY a.tournament_id, a.as_of_date, position;
    """).df()


# --------------------------------------------------------------------------
# 7) home_ground  (iteration 2b, content layer)
# --------------------------------------------------------------------------
# HIGH-confidence gate: home-advantage prose is allowed only for teams that
# clear this bar (or are later human-confirmed via docs/home-grounds-review
# .csv - see src/data/export_home_grounds_review.py). Medium-confidence
# derivations (5-9 matches at >=30%) appear in that review file but do NOT
# set is_home_ground until the editor confirms them.
HOME_GROUND_MIN_MATCHES = 10     # >= this many prior league matches AT venue
HOME_GROUND_MIN_SHARE = 0.30     # AND >= this share of prior league matches


def build_home_ground(con: duckdb.DuckDBPyConnection):
    """
    Per (target match, team): is the target venue this team's own ground,
    judged ONLY on completed same-league matches strictly before as_of_date
    (thresholds above; rationale in the module docstring).
    """
    return con.execute(f"""
        WITH hist AS (
            SELECT h.team_id, h.league_key, h.match_date, d.venue_key
            FROM team_match_history h
            JOIN dim_match d ON d.match_id = h.match_id
        )
        SELECT
            t.match_id, t.team_id, t.as_of_date, t.venue_key,
            COUNT(h.match_date)                            AS league_matches_before,
            SUM(CASE WHEN h.venue_key = t.venue_key
                     THEN 1 ELSE 0 END)                    AS at_venue_before,
            SUM(CASE WHEN h.venue_key = t.venue_key THEN 1 ELSE 0 END)
                / NULLIF(COUNT(h.match_date), 0)::DOUBLE   AS venue_share,
            (SUM(CASE WHEN h.venue_key = t.venue_key THEN 1 ELSE 0 END)
                 >= {HOME_GROUND_MIN_MATCHES}
             AND SUM(CASE WHEN h.venue_key = t.venue_key THEN 1 ELSE 0 END)
                 >= {HOME_GROUND_MIN_SHARE} * COUNT(h.match_date))
                                                           AS is_home_ground,
            MAX(h.match_date)                              AS max_source_date
        FROM targets t
        LEFT JOIN hist h
               ON h.team_id = t.team_id
              AND h.league_key IS NOT DISTINCT FROM t.league_key
              AND h.match_date < t.as_of_date              -- STRICTLY before
        GROUP BY t.match_id, t.team_id, t.as_of_date, t.venue_key
        ORDER BY t.match_id, t.team_id;
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
    print("Building player_form ...")
    player_form = build_player_form(con)
    print("Building player_phase ...")
    player_phase = build_player_phase(con)
    print("Building standings ...")
    standings = build_standings(con)
    print("Building home_ground ...")
    home_ground = build_home_ground(con)

    datasets = {
        "team_form": team_form,
        "venue_stats": venue_stats,
        "match_conditions": match_conditions,
        "match_odds_devig": match_odds_devig,
        "player_form": player_form,
        "player_phase": player_phase,
        "standings": standings,
        "home_ground": home_ground,
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
            "odds": "mean vendor decimal price per match; bridge-linked priced in-scope T20 only.",
            "gender_scope": "L1 scope = T20 men + women (dim_match.gender). "
                            "venue_stats is keyed by (venue_key, gender, as_of_date): "
                            "same-gender venue sample only, so men's venue numbers "
                            "are unchanged by the widening. team/player/standings/"
                            "home_ground aggregates are keyed by team/player/"
                            "tournament ids, which are gender-specific already.",
            "tournament_window": "team_form 'tournament' window groups by league_key "
                                 "(year-stripped), so IPL's 4 season ids form one "
                                 "coherent league group; league_key also carried as a column.",
            "venue_dedupe": "reads revised L1 dim_venue (deduped) + remapped "
                            "dim_match.venue_key; see venue_id_map.",
            "current_event_window": "team_form/player_form window scoped to "
                                    "tournament_id (this season/tour only); "
                                    "content layer, ignored by build_l3.",
            "player_form_source": "L0 player_batting/bowling_scores via "
                                  "cricket__players roster join (100% id "
                                  "linkage); NOT the ball-by-ball comment "
                                  "parse (~55% match coverage). playing_xi "
                                  "never read (leakage rule).",
            "standings": "DERIVED from dim_match decided results; raw "
                         "cricket__tournament_points is current-state-only "
                         "(1 row per tournament+team, updated in place) and "
                         "cannot give as-of-date tables. points=2*wins, "
                         "decided only; position tie-break uses ball-data "
                         "run_diff as NRR proxy -> approximate around "
                         "NRR-decided ties.",
            "home_ground": "point-in-time: venue is a team's own ground when "
                           f">= {HOME_GROUND_MIN_MATCHES} prior same-league "
                           f"matches there AND >= {HOME_GROUND_MIN_SHARE:.0%} "
                           "of prior league matches; content layer.",
            "player_phase": "iteration 3, content layer: per-player phase "
                            "splits from ball-by-ball (batter_id/bowler_id "
                            "= roster keys). Only ball-covered matches "
                            "contribute (phase_matches may be < the "
                            "player_form window count); rows exist only "
                            "where covered deliveries exist (NULL-safe by "
                            "absence). bat runs = off-the-bat `runs` col; "
                            "bowl legal balls exclude wides/no-balls (same "
                            "convention as team phase econ).",
            "venue_authority": "editorial authority from docs/"
                               "Franchise_Cricket_Venues.xlsx via "
                               "src/data/ingest_venue_authority.py "
                               "(separate build; static config, no "
                               "as_of_date). Shared-venue leagues reject "
                               "ALL home-ground derivations at the "
                               "content layer.",
            "max_source_date": "audit column on player_form/player_phase/"
                               "standings/home_ground rows; leakage test "
                               "asserts it < as_of_date.",
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
