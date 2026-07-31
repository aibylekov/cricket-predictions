"""L1 build — Part 1 of 2: clean transformations (NOT bridge_entity).

Phase 1.3 (README §9, §1.3). Reads the immutable L0 Parquet at
``data/lake/l0/`` and writes cleaned, T20-men-scoped L1 datasets to
``data/lake/l1/``. L0 and cricket_raw are never touched.

Pipeline (in order):
  1. T20-MEN FILTER — cricket__matches where ``format='t20' AND gender='male'``
     (both explicit columns; 4,763 matches). Everything below is scoped to
     this match set by match id. Match ``status`` is carried through and a
     boolean ``is_completed = (status == 'completed')`` is derived; NO
     status/play_status filtering happens here (README: completed-only is a
     Phase-2 training-set concern).
  2. DIMENSIONS — dim_match, dim_team, dim_player, dim_tournament, dim_venue.
     Venue is parsed from the JSON in ``cricket__matches.venue``.
  3. DATE-1970 FIX — ball rows whose ``updated`` date is 1970-01-01 get a
     recovered date from the match ``start_at`` (over_summary_id ->
     over_summaries.match_id -> cricket__matches.start_at). ``entry_time`` is
     the primary clean timestamp.
  4. COMMENT PARSING — split ``comment`` ("Bowler to Batter: outcome.") into
     ``bowler_name`` / ``batter_name`` and resolve to player keys via a
     match-scoped, UNAMBIGUOUS (match_id, name) -> key map (rows with a name
     collision or no match stay NULL — never dropped, never guessed).
  5. MANIFEST — data/lake/l1/_manifest.json.

Bridge_entity / odds resolution is Part 2 (separate script). Read-only inputs.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
L0_ROOT = (PROJECT_ROOT / "data" / "lake" / "l0")
L1_ROOT = (PROJECT_ROOT / "data" / "lake" / "l1")
MANIFEST_PATH = L1_ROOT / "_manifest.json"

BAD_DATE_CUTOFF = "2000-01-01"  # anything older is an epoch/uninitialised date


def l0(name: str, partitioned: bool = False) -> str:
    """Return a DuckDB read_parquet() expression for an L0 dataset."""
    path = (L0_ROOT / name).as_posix()
    hp = ", hive_partitioning=true" if partitioned else ""
    return f"read_parquet('{path}/**/*.parquet'{hp})"


def create_views(con: duckdb.DuckDBPyConnection) -> None:
    """Register L0 sources and the core T20-men scoping views."""
    con.execute(f"CREATE VIEW l0_matches AS SELECT * FROM {l0('cricket__matches')}")
    con.execute(f"CREATE VIEW l0_teams AS SELECT * FROM {l0('cricket__teams')}")
    con.execute(f"CREATE VIEW l0_players AS SELECT * FROM {l0('cricket__players')}")
    con.execute(f"CREATE VIEW l0_tournaments AS SELECT * FROM {l0('cricket__tournaments')}")
    con.execute(f"CREATE VIEW l0_over_summaries AS SELECT * FROM {l0('cricket__over_summaries')}")
    con.execute(
        f"CREATE VIEW l0_balls AS SELECT * FROM {l0('cricket__over_summary_balls', True)}"
    )

    # T20-men scope (the one filter that defines L1).
    con.execute(
        "CREATE VIEW m20 AS SELECT * FROM l0_matches "
        "WHERE format = 't20' AND gender = 'male'"
    )

    # Unambiguous match-scoped name -> player key map (one key per name/match).
    # Names with a within-match collision are excluded so ball rows never
    # inflate and no id is guessed.
    con.execute(
        """
        CREATE VIEW name_key AS
        SELECT match_id, name, ANY_VALUE(key) AS player_key
        FROM (SELECT DISTINCT match_id, name, key FROM l0_players)
        GROUP BY match_id, name
        HAVING COUNT(*) = 1
        """
    )


# --------------------------------------------------------------------------- #
# Dataset definitions (name -> SELECT). Order matters only for readability.
# --------------------------------------------------------------------------- #
def dataset_sql() -> dict[str, str]:
    return {
        # --- dim_match -----------------------------------------------------
        "dim_match": """
            SELECT
                id                       AS match_id,
                key                      AS match_key,
                tournament_id,
                name                     AS match_name,
                short_name,
                sub_title,
                team_a                   AS team_a_id,
                team_b                   AS team_b_id,
                start_at,
                start_at_local,
                format,
                gender,
                status,
                (status = 'completed')   AS is_completed,
                play_status,
                winner,
                result,
                result_type,
                target_runs,
                target_balls,
                target_dl_applied,
                json_extract_string(venue, '$.key')  AS venue_key,
                weather
            FROM m20
        """,
        # --- dim_team (scoped to teams appearing in T20-men matches) -------
        "dim_team": """
            WITH team_ids AS (
                SELECT team_a_id AS team_id FROM (SELECT team_a AS team_a_id FROM m20)
                UNION
                SELECT team_b AS team_id FROM m20
            )
            SELECT
                t.id            AS team_id,
                t.key           AS team_key,
                t.code          AS team_code,
                t.name          AS team_name,
                t.short_name,
                t.country_code,
                t.is_national
            FROM l0_teams t
            JOIN (SELECT DISTINCT team_id FROM team_ids) ti ON ti.team_id = t.id
        """,
        # --- dim_player (scoped to players in T20-men matches) -------------
        # A player key can carry slightly different names/roles across matches;
        # take the most frequent (mode) as the representative.
        "dim_player": """
            SELECT
                key                       AS player_key,
                mode(name)                AS player_name,
                any_value(gender)         AS gender,
                mode(seasonal_role)       AS seasonal_role,
                COUNT(DISTINCT match_id)  AS t20m_matches
            FROM l0_players
            WHERE match_id IN (SELECT id FROM m20)
            GROUP BY key
        """,
        # --- dim_tournament (scoped to tournaments of T20-men matches) -----
        "dim_tournament": """
            SELECT
                tr.id           AS tournament_id,
                tr.key          AS tournament_key,
                tr.name         AS tournament_name,
                tr.short_name,
                tr.slug,
                tr.gender,
                tr.start_date,
                tr.metric_group
            FROM l0_tournaments tr
            WHERE tr.id IN (SELECT DISTINCT tournament_id FROM m20)
        """,
        # --- dim_venue (parsed from cricket__matches.venue JSON) -----------
        "dim_venue": """
            SELECT DISTINCT
                json_extract_string(venue, '$.key')            AS venue_key,
                json_extract_string(venue, '$.name')           AS venue_name,
                json_extract_string(venue, '$.city')           AS city,
                json_extract_string(venue, '$.country.code')   AS country_code,
                json_extract_string(venue, '$.country.name')   AS country_name
            FROM m20
            WHERE venue IS NOT NULL AND venue <> '' AND json_valid(venue)
              AND json_extract_string(venue, '$.key') IS NOT NULL
        """,
        # --- fact_ball_by_ball (date fix + comment parse + resolution) -----
        "fact_ball_by_ball": r"""
            WITH scoped AS (
                SELECT
                    b.id                AS ball_id,
                    b.over_summary_id,
                    os.match_id,
                    os.inning_key,
                    os.over            AS over_number,
                    os.team            AS batting_team,
                    b.key              AS ball_key,
                    b.innings          AS ball_innings,
                    b.ball             AS ball_in_over,
                    b.ball_type,
                    b.wicket,
                    b.runs,
                    b.comment,
                    b.entry_time,
                    b.updated,
                    m.start_at         AS match_start_at,
                    -- comment parse: "Bowler to Batter: outcome."
                    NULLIF(regexp_extract(b.comment, '^(.*?) to (.*?): (.*)$', 1), '') AS bowler_name,
                    NULLIF(regexp_extract(b.comment, '^(.*?) to (.*?): (.*)$', 2), '') AS batter_name,
                    NULLIF(regexp_extract(b.comment, '^(.*?) to (.*?): (.*)$', 3), '') AS outcome_text
                FROM l0_balls b
                JOIN l0_over_summaries os ON os.id = b.over_summary_id
                JOIN m20 m ON m.id = os.match_id
            )
            SELECT
                s.ball_id,
                s.over_summary_id,
                s.match_id,
                s.inning_key,
                s.over_number,
                s.batting_team,
                s.ball_key,
                s.ball_innings,
                s.ball_in_over,
                s.ball_type,
                s.wicket,
                s.runs,
                s.comment,
                s.outcome_text,
                s.bowler_name,
                s.batter_name,
                pw.player_key AS bowler_id,
                pb.player_key AS batter_id,
                (s.bowler_name IS NOT NULL AND s.batter_name IS NOT NULL) AS comment_parsed,
                -- entry_time is the primary clean timestamp
                s.entry_time AS ts_primary,
                s.updated,
                -- date-1970 fix: recover bad `updated` from the match start_at
                CASE WHEN CAST(s.updated AS DATE) < DATE '{cutoff}'
                     THEN s.match_start_at ELSE s.updated END AS updated_recovered,
                (CAST(s.updated AS DATE) < DATE '{cutoff}')   AS date_was_corrected
            FROM scoped s
            LEFT JOIN name_key pb ON pb.match_id = s.match_id AND pb.name = s.batter_name
            LEFT JOIN name_key pw ON pw.match_id = s.match_id AND pw.name = s.bowler_name
        """.replace("{cutoff}", BAD_DATE_CUTOFF),
    }


def write_dataset(con, name: str, sql: str) -> int:
    """Write one L1 dataset to its own folder and return its row count."""
    out_dir = L1_ROOT / name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = (out_dir / f"{name}.parquet").as_posix()
    con.execute(f"COPY ({sql}) TO '{out_file}' (FORMAT PARQUET)")
    return con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_file}')").fetchone()[0]


def main() -> None:
    con = duckdb.connect()
    create_views(con)

    # --- Scope metrics --------------------------------------------------- #
    t20m_total = con.execute("SELECT COUNT(*) FROM m20").fetchone()[0]
    status_rows = con.execute(
        "SELECT status, COUNT(*) c FROM m20 GROUP BY status ORDER BY c DESC"
    ).fetchall()
    completed = con.execute(
        "SELECT COUNT(*) FROM m20 WHERE status = 'completed'"
    ).fetchone()[0]
    not_completed = t20m_total - completed

    print(f"T20-men matches: {t20m_total} "
          f"(completed={completed}, not_completed/other={not_completed})")
    print("  is_completed derivation: (status == 'completed').")
    print("  status breakdown: " + ", ".join(f"{s}={c}" for s, c in status_rows))

    # --- Write datasets -------------------------------------------------- #
    print("\nWriting L1 datasets ->", L1_ROOT)
    counts: dict[str, int] = {}
    for name, sql in dataset_sql().items():
        counts[name] = write_dataset(con, name, sql)
        print(f"  {name}: {counts[name]:,} rows")

    # --- Step 3 & 4 metrics (from the written fact) ---------------------- #
    fact = (L1_ROOT / "fact_ball_by_ball" / "fact_ball_by_ball.parquet").as_posix()
    total_balls = counts["fact_ball_by_ball"]
    corrected = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{fact}') WHERE date_was_corrected"
    ).fetchone()[0]
    parse_ok = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{fact}') WHERE comment_parsed"
    ).fetchone()[0]
    both_resolved = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{fact}') "
        f"WHERE bowler_id IS NOT NULL AND batter_id IS NOT NULL"
    ).fetchone()[0]
    bowler_res = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{fact}') WHERE bowler_id IS NOT NULL"
    ).fetchone()[0]
    batter_res = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{fact}') WHERE batter_id IS NOT NULL"
    ).fetchone()[0]

    print(f"\nStep 3 — date-1970 fix: {corrected} ball rows corrected "
          f"(in T20-men scope) via match start_at.")
    print(f"Step 4 — comment parse: {parse_ok:,}/{total_balls:,} "
          f"({parse_ok/total_balls*100:.2f}%) parsed (both names).")
    print(f"          resolution: bowler {bowler_res/total_balls*100:.2f}%, "
          f"batter {batter_res/total_balls*100:.2f}%, "
          f"both {both_resolved/total_balls*100:.2f}% (match-scoped, unambiguous).")

    print("\nSample of 10 parsed rows:")
    sample = con.execute(
        f"SELECT match_id, over_number, ball_in_over, bowler_name, bowler_id, "
        f"batter_name, batter_id, runs "
        f"FROM read_parquet('{fact}') WHERE comment_parsed LIMIT 10"
    ).fetchall()
    for r in sample:
        print(f"   m={r[0]} ov={r[1]}.{r[2]} | {r[3]} ({r[4]}) -> "
              f"{r[5]} ({r[6]}) | {r[7]} run(s)")

    unparsed = total_balls - parse_ok
    print(f"\nUnparsed balls kept with NULL names: {unparsed:,} "
          f"({unparsed/total_balls*100:.2f}%) — none dropped.")

    # --- Manifest -------------------------------------------------------- #
    manifest = {
        "layer": "L1",
        "part": "1 of 2 (clean transformations; bridge_entity is Part 2)",
        "source": "data/lake/l0 (immutable)",
        "build_timestamp": datetime.now().isoformat(timespec="seconds"),
        "l1_root": str(L1_ROOT),
        "t20_men_scope": {"filter": "format='t20' AND gender='male'",
                          "match_count": t20m_total,
                          "completed": completed,
                          "not_completed_or_other": not_completed,
                          "status_breakdown": {s: c for s, c in status_rows}},
        "date_1970_fix": {"rows_corrected": corrected,
                          "method": "over_summary_id -> over_summaries.match_id "
                                    "-> cricket__matches.start_at; entry_time is "
                                    "primary clean timestamp"},
        "comment_parse": {"total_balls": total_balls,
                          "parsed_both_names": parse_ok,
                          "parse_rate": round(parse_ok / total_balls, 4),
                          "bowler_resolved": bowler_res,
                          "batter_resolved": batter_res,
                          "both_resolved": both_resolved,
                          "both_resolved_rate": round(both_resolved / total_balls, 4),
                          "unparsed_kept_null": unparsed},
        "tables": {name: cnt for name, cnt in counts.items()},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest written: {MANIFEST_PATH}")
    con.close()


if __name__ == "__main__":
    main()
