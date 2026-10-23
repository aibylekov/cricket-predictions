"""L1 build — Part 1 of 2: clean transformations (NOT bridge_entity).

Phase 1.3 (README §9, §1.3). Reads the immutable L0 Parquet at
``data/lake/l0/`` and writes cleaned, T20-scoped (men + women) L1 datasets to
``data/lake/l1/``. L0 and cricket_raw are never touched.

Pipeline (in order):
  1. T20 SCOPE FILTER — cricket__matches where ``format='t20' AND gender IN
     (<genders>)``; default genders = male + female (``--genders`` overrides;
     men-only was the v1 scope). ``gender`` is carried through dim_match so
     every downstream layer (L2/L3, model, reports) can split. Everything
     below is scoped to
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

# Scope: T20 only; genders parameterized (v1 = men only; v2 adds women for WBBL).
SCOPE_FORMAT = "t20"
DEFAULT_GENDERS = ("male", "female")

# Human-approved CROSS-SEASON team aliases (bridge_entity style): the same side
# under two different names/ids in different editions. old_id -> canonical_id
# (the id with more in-scope matches). Applied on top of the exact-name
# collapse. Mechanically checked at build time: both ids must carry the same
# match gender, otherwise the build aborts. Evidence is one line per alias and
# is written to the L1 manifest.
APPROVED_TEAM_ALIASES: dict[int, int] = {353: 738}
APPROVED_TEAM_ALIAS_EVIDENCE: dict[int, str] = {
    353: "353 'Australian Capital Territory' (code ACT-W, AUS, female; Spring "
         "Challenge 2024 only, 4 matches) = 738 'ACT Meteors Women' (code ACT-W, "
         "AUS, female; Spring Challenge 2025-26, 8 matches). ACT = Australian "
         "Capital Territory; the men's ACT side is a separate id (671, code ACOM, "
         "Top End T20). Approved 2026-10-23.",
}


def l0(name: str, partitioned: bool = False) -> str:
    """Return a DuckDB read_parquet() expression for an L0 dataset."""
    path = (L0_ROOT / name).as_posix()
    hp = ", hive_partitioning=true" if partitioned else ""
    return f"read_parquet('{path}/**/*.parquet'{hp})"


def create_views(con: duckdb.DuckDBPyConnection,
                 genders: tuple[str, ...] = DEFAULT_GENDERS) -> None:
    """Register L0 sources and the core T20 scoping views (format + genders)."""
    con.execute(f"CREATE VIEW l0_matches AS SELECT * FROM {l0('cricket__matches')}")
    con.execute(f"CREATE VIEW l0_teams AS SELECT * FROM {l0('cricket__teams')}")
    con.execute(f"CREATE VIEW l0_players AS SELECT * FROM {l0('cricket__players')}")
    con.execute(f"CREATE VIEW l0_tournaments AS SELECT * FROM {l0('cricket__tournaments')}")
    con.execute(f"CREATE VIEW l0_over_summaries AS SELECT * FROM {l0('cricket__over_summaries')}")
    con.execute(
        f"CREATE VIEW l0_balls AS SELECT * FROM {l0('cricket__over_summary_balls', True)}"
    )

    # T20 scope (the one filter that defines L1): format + gender list.
    gender_list = ", ".join(f"'{g}'" for g in genders)
    con.execute(
        f"CREATE VIEW m20 AS SELECT * FROM l0_matches "
        f"WHERE format = '{SCOPE_FORMAT}' AND gender IN ({gender_list})"
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

    # Team canonicalization: cricket__teams holds the SAME real team under two
    # Roanuz key schemes (e.g. IPL 'mi' vs 'a-rz--cricket--mmindianlkksck'),
    # producing duplicate ids with identical name+short_name. Collapse each
    # exact-name group WITHIN A GENDER to ONE canonical id = the id used in the
    # MOST in-scope T20 matches (ties -> lowest id). The gender of a team id is
    # the gender of the matches it plays (from cricket__matches, never from the
    # name): the source reuses club names across genders WITHOUT a "Women"
    # suffix (CPL "Barbados Royals" men id 119 vs women ids 132/316, Super
    # Smash "Northern Brave", "Australian Capital Territory"), so an exact-name
    # collapse that ignores gender would fold a women's side into the men's id.
    # A full old_id -> canonical_id map is kept so anything still referencing
    # an old id resolves. (Same spirit as the dim_player key-dedupe.)
    con.execute(
        """
        CREATE VIEW team_gender AS
        SELECT team_id, string_agg(gender, '/' ORDER BY gender) AS team_gender
        FROM (SELECT DISTINCT team_id, gender FROM (
                  SELECT team_a AS team_id, gender FROM m20
                  UNION ALL SELECT team_b AS team_id, gender FROM m20))
        GROUP BY team_id
        """
    )
    con.execute(
        """
        CREATE VIEW team_scoped AS
        SELECT DISTINCT t.id AS team_id, t.name AS team_name, g.team_gender
        FROM l0_teams t
        JOIN team_gender g ON g.team_id = t.id
        """
    )
    con.execute(
        """
        CREATE VIEW team_refs AS
        SELECT team_id, COUNT(*) AS refs FROM (
            SELECT team_a AS team_id FROM m20
            UNION ALL SELECT team_b AS team_id FROM m20
        ) GROUP BY team_id
        """
    )
    con.execute(
        """
        CREATE VIEW team_canon AS
        SELECT ts.team_id, ts.team_name, ts.team_gender,
               FIRST_VALUE(ts.team_id) OVER (
                   PARTITION BY ts.team_name, ts.team_gender
                   ORDER BY COALESCE(tr.refs, 0) DESC, ts.team_id ASC
               ) AS canonical_id
        FROM team_scoped ts
        LEFT JOIN team_refs tr ON tr.team_id = ts.team_id
        """
    )
    # Approved cross-season aliases on top of the exact-name collapse.
    alias_rows = ", ".join(f"({o}, {c})" for o, c in APPROVED_TEAM_ALIASES.items())
    con.execute(
        f"CREATE VIEW team_alias AS SELECT * FROM (VALUES {alias_rows or '(NULL, NULL)'}) "
        f"v(old_id, new_id) WHERE old_id IS NOT NULL"
    )
    con.execute(
        """
        CREATE VIEW team_canon_final AS
        SELECT tc.team_id, tc.team_name, tc.team_gender,
               COALESCE(a.new_id, tc.canonical_id) AS canonical_id
        FROM team_canon tc
        LEFT JOIN team_alias a ON a.old_id = tc.canonical_id
        """
    )
    con.execute(
        "CREATE VIEW team_id_map AS "
        "SELECT team_id AS old_id, canonical_id, (team_id <> canonical_id) AS is_remapped "
        "FROM team_canon_final"
    )


# --------------------------------------------------------------------------- #
# Dataset definitions (name -> SELECT). Order matters only for readability.
# --------------------------------------------------------------------------- #
def dataset_sql() -> dict[str, str]:
    return {
        # --- dim_match (team ids canonicalized via team_id_map) ------------
        "dim_match": """
            SELECT
                m.id                     AS match_id,
                m.key                    AS match_key,
                m.tournament_id,
                m.name                   AS match_name,
                m.short_name,
                m.sub_title,
                COALESCE(ma.canonical_id, m.team_a) AS team_a_id,
                COALESCE(mb.canonical_id, m.team_b) AS team_b_id,
                m.start_at,
                m.start_at_local,
                m.format,
                m.gender,
                m.status,
                (m.status = 'completed')  AS is_completed,
                m.play_status,
                m.winner,
                m.result,
                m.result_type,
                m.target_runs,
                m.target_balls,
                m.target_dl_applied,
                json_extract_string(m.venue, '$.key')  AS venue_key,
                m.weather
            FROM m20 m
            LEFT JOIN team_id_map ma ON ma.old_id = m.team_a
            LEFT JOIN team_id_map mb ON mb.old_id = m.team_b
        """,
        # --- team_id_map (old duplicate id -> canonical id) ----------------
        "team_id_map": """
            SELECT old_id, canonical_id, is_remapped
            FROM team_id_map
            ORDER BY old_id
        """,
        # --- dim_team (deduped: one row per canonical team id) -------------
        # team_gender = gender of the matches the team plays ('male' |
        # 'female'; 'female/male' only if the source reuses one id).
        "dim_team": """
            SELECT
                t.id            AS team_id,
                t.key           AS team_key,
                t.code          AS team_code,
                t.name          AS team_name,
                t.short_name,
                t.country_code,
                t.is_national,
                c.team_gender
            FROM l0_teams t
            JOIN (SELECT DISTINCT canonical_id, team_gender FROM team_canon_final) c
              ON c.canonical_id = t.id
        """,
        # --- dim_player (scoped to players in in-scope T20 matches) --------
        # A player key can carry slightly different names/roles across matches;
        # take the most frequent (mode) as the representative.
        "dim_player": """
            SELECT
                key                       AS player_key,
                mode(name)                AS player_name,
                any_value(gender)         AS gender,
                mode(seasonal_role)       AS seasonal_role,
                COUNT(DISTINCT match_id)  AS t20_matches
            FROM l0_players
            WHERE match_id IN (SELECT id FROM m20)
            GROUP BY key
        """,
        # --- dim_tournament (scoped to tournaments of in-scope T20 matches) -
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
    import argparse
    ap = argparse.ArgumentParser(description="L1 build (clean transformations).")
    ap.add_argument("--genders", default=",".join(DEFAULT_GENDERS),
                    help="comma-separated genders in scope (default: male,female)")
    args = ap.parse_args()
    genders = tuple(g.strip() for g in args.genders.split(",") if g.strip())

    con = duckdb.connect()
    create_views(con, genders)

    # --- Scope metrics --------------------------------------------------- #
    t20m_total = con.execute("SELECT COUNT(*) FROM m20").fetchone()[0]
    by_gender = con.execute(
        "SELECT gender, COUNT(*), SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) "
        "FROM m20 GROUP BY gender ORDER BY gender"
    ).fetchall()
    # tournaments referenced by in-scope matches but absent from the source
    # cricket__tournaments table (league_key will be NULL for them downstream)
    missing_tourn = con.execute(
        "SELECT tournament_id, COUNT(*) FROM m20 "
        "WHERE tournament_id NOT IN (SELECT id FROM l0_tournaments) "
        "GROUP BY tournament_id ORDER BY tournament_id"
    ).fetchall()
    status_rows = con.execute(
        "SELECT status, COUNT(*) c FROM m20 GROUP BY status ORDER BY c DESC"
    ).fetchall()
    completed = con.execute(
        "SELECT COUNT(*) FROM m20 WHERE status = 'completed'"
    ).fetchone()[0]
    not_completed = t20m_total - completed

    print(f"T20 matches (genders={','.join(genders)}): {t20m_total} "
          f"(completed={completed}, not_completed/other={not_completed})")
    for g, n, c in by_gender:
        print(f"  {g}: {n} matches, {c} completed")
    if missing_tourn:
        print(f"  WARNING: {len(missing_tourn)} tournament_id(s) referenced by in-scope "
              f"matches are MISSING from cricket__tournaments -> no dim_tournament row, "
              f"league_key NULL: "
              + ", ".join(f"{tid} ({n} matches)" for tid, n in missing_tourn))
    print("  is_completed derivation: (status == 'completed').")
    print("  status breakdown: " + ", ".join(f"{s}={c}" for s, c in status_rows))

    # --- dim_team dedupe summary ---------------------------------------- #
    n_scoped = con.execute("SELECT COUNT(*) FROM team_scoped").fetchone()[0]
    n_canon = con.execute("SELECT COUNT(DISTINCT canonical_id) FROM team_canon_final").fetchone()[0]
    n_remapped = con.execute("SELECT COUNT(*) FROM team_id_map WHERE is_remapped").fetchone()[0]
    print(f"\ndim_team dedupe: {n_scoped} scoped team ids -> {n_canon} canonical "
          f"({n_remapped} duplicate ids remapped to a canonical id; exact name "
          f"WITHIN gender).")
    # --- approved cross-season aliases: same-gender check + evidence -------- #
    alias_records = []
    for old_id, new_id in APPROVED_TEAM_ALIASES.items():
        rows = {r[0]: r for r in con.execute(
            "SELECT ts.team_id, ts.team_name, ts.team_gender, COALESCE(tr.refs, 0) "
            "FROM team_scoped ts LEFT JOIN team_refs tr ON tr.team_id = ts.team_id "
            "WHERE ts.team_id IN (?, ?)", [old_id, new_id]).fetchall()}
        if old_id not in rows or new_id not in rows:
            raise SystemExit(f"approved alias {old_id}->{new_id}: id not in scope {rows}")
        if rows[old_id][2] != rows[new_id][2]:
            raise SystemExit(f"approved alias {old_id}->{new_id}: GENDER MISMATCH "
                             f"{rows[old_id][2]} vs {rows[new_id][2]} — refusing")
        if rows[new_id][3] < rows[old_id][3]:
            raise SystemExit(f"approved alias {old_id}->{new_id}: canonical must be "
                             f"the id with MORE matches ({rows[new_id][3]} < {rows[old_id][3]})")
        alias_records.append({
            "old_id": old_id, "old_name": rows[old_id][1], "old_matches": rows[old_id][3],
            "canonical_id": new_id, "canonical_name": rows[new_id][1],
            "canonical_matches": rows[new_id][3], "gender": rows[new_id][2],
            "evidence": APPROVED_TEAM_ALIAS_EVIDENCE.get(old_id, "")})
        print(f"  approved alias: {old_id} '{rows[old_id][1]}' ({rows[old_id][2]}, "
              f"{rows[old_id][3]} mt) -> {new_id} '{rows[new_id][1]}' ({rows[new_id][2]}, "
              f"{rows[new_id][3]} mt)")
    mixed = con.execute(
        "SELECT team_id, team_name, team_gender FROM team_scoped "
        "WHERE team_gender LIKE '%/%' ORDER BY team_id").fetchall()
    if mixed:
        print(f"  NOTE: {len(mixed)} team id(s) play BOTH genders in the source "
              f"(kept as one id, not split): "
              + ", ".join(f"{i} {n}" for i, n, _ in mixed))

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
          f"(in T20 scope) via match start_at.")
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
        "t20_scope": {"filter": f"format='{SCOPE_FORMAT}' AND gender IN "
                                f"({', '.join(genders)})",
                      "format": SCOPE_FORMAT,
                      "genders": list(genders),
                      "match_count": t20m_total,
                      "completed": completed,
                      "not_completed_or_other": not_completed,
                      "by_gender": {g: {"matches": int(n), "completed": int(c)}
                                    for g, n, c in by_gender},
                      "status_breakdown": {s: c for s, c in status_rows},
                      "tournament_ids_missing_from_source": [
                          {"tournament_id": int(tid), "matches": int(n)}
                          for tid, n in missing_tourn]},
        "dim_team_dedupe": {"scoped_team_ids": n_scoped,
                            "canonical_teams": n_canon,
                            "duplicate_ids_remapped": n_remapped,
                            "approved_cross_season_aliases": alias_records,
                            "method": "collapse exact-name duplicates WITHIN the "
                                      "same match gender to the id used in the "
                                      "most in-scope T20 matches; "
                                      "team_id_map keeps old_id -> canonical_id"},
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
