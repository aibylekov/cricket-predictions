"""
build_l3.py — L3 flat feature-row assembler (ASSEMBLY ONLY).

One row per in-scope T20 match (men + women; `gender` column; completed + upcoming). Joins the existing L2
datasets into the single flat table the model reads. NO new aggregate
computation. Reads L2 (+ L1 dims for home/away resolution). NEVER modifies
L0/L1/L2. Writes to data/lake/l3/.

Point-in-time safety is INHERITED from L2: every home_/away_ feature is the
team's team_form snapshot keyed on THIS match_id (as_of_date = match_date),
which L2 already computed using only matches strictly before as_of_date. The
join must not break that — see tests/test_leakage.py::test_l3_* for the
re-check.

home/away resolution (confirmed with the user):
  - default home = team_a, away = team_b (feed listing order);
  - OVERRIDE for internationals: when both teams are national and the venue is
    in exactly one team's country, home = that country-matching team;
  - is_neutral_venue = 1 ONLY for positively-neutral internationals (both
    national, venue in NEITHER country); else 0. (Domestic neutral-city games
    cannot be detected and default to 0 — accepted v1 limitation.)
  - home_team_source in {venue_country, feed_order_default} makes the home
    signal's reliability explicit.

Market note: L2 match_odds_devig home_devig/away_devig follow the ODDS-FEED
home/away orientation, which is not guaranteed to match our assigned home_team
(team-level odds bridging is future work). Carried as-is; see the alignment
line in the console report.

Run:
  venv/Scripts/python.exe -m src.data.build_l3
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
L1 = ROOT / "data" / "lake" / "l1"
L2 = ROOT / "data" / "lake" / "l2"
L3 = ROOT / "data" / "lake" / "l3"

L1_DIM_MATCH = (L1 / "dim_match" / "dim_match.parquet").as_posix()
L1_DIM_TEAM = (L1 / "dim_team" / "dim_team.parquet").as_posix()
L1_DIM_VENUE = (L1 / "dim_venue" / "dim_venue.parquet").as_posix()
L1_DIM_TOURN = (L1 / "dim_tournament" / "dim_tournament.parquet").as_posix()
L2_TEAM_FORM = (L2 / "team_form" / "team_form.parquet").as_posix()
L2_VENUE = (L2 / "venue_stats" / "venue_stats.parquet").as_posix()
L2_COND = (L2 / "match_conditions" / "match_conditions.parquet").as_posix()
L2_ODDS = (L2 / "match_odds_devig" / "match_odds_devig.parquet").as_posix()

# team_form metrics and the window-suffix mapping
METRICS = ["rr_powerplay", "rr_middle", "rr_death",
           "econ_powerplay", "econ_middle", "econ_death",
           "win_pct", "avg_margin", "matches_in_window"]
WINDOWS = {"last5": "last5", "tournament": "tourn"}


def _tf_wide_cols() -> str:
    """Conditional-aggregation columns pivoting team_form windows to wide."""
    parts = []
    for m in METRICS:
        for wkey, wsuf in WINDOWS.items():
            parts.append(
                f"MAX(CASE WHEN \"window\"='{wkey}' THEN {m} END) AS {m}_{wsuf}")
    return ",\n            ".join(parts)


def _prefixed(prefix: str) -> str:
    """team_form wide columns, prefixed home_/away_ for the SELECT list."""
    parts = []
    for m in METRICS:
        for wsuf in WINDOWS.values():
            parts.append(f"{prefix}.{m}_{wsuf} AS {prefix}_{m}_{wsuf}")
    return ",\n            ".join(parts)


def build(con: duckdb.DuckDBPyConnection):
    tf_wide = _tf_wide_cols()
    home_cols = _prefixed("home")
    away_cols = _prefixed("away")

    sql = f"""
    WITH tf_wide AS (
        SELECT match_id, team_id,
            {tf_wide}
        FROM read_parquet('{L2_TEAM_FORM}')
        GROUP BY match_id, team_id
    ),
    base AS (
        SELECT
            CAST(m.match_id AS BIGINT)      AS match_id,
            CAST(m.start_at AS DATE)        AS match_date,
            CAST(m.start_at AS DATE)        AS as_of_date,
            t.league_key,
            m.gender,
            CAST(m.tournament_id AS BIGINT) AS tournament_id,
            m.venue_key,
            m.is_completed,
            m.winner,
            CAST(m.team_a_id AS BIGINT)     AS team_a_id,
            CAST(m.team_b_id AS BIGINT)     AS team_b_id,
            ta.is_national AS na, tb.is_national AS nb,
            ta.country_code AS cca, tb.country_code AS ccb, v.country_code AS ccv
        FROM read_parquet('{L1_DIM_MATCH}') m
        LEFT JOIN read_parquet('{L1_DIM_TOURN}') t
               ON CAST(t.tournament_id AS BIGINT) = CAST(m.tournament_id AS BIGINT)
        LEFT JOIN read_parquet('{L1_DIM_TEAM}') ta
               ON CAST(ta.team_id AS BIGINT) = CAST(m.team_a_id AS BIGINT)
        LEFT JOIN read_parquet('{L1_DIM_TEAM}') tb
               ON CAST(tb.team_id AS BIGINT) = CAST(m.team_b_id AS BIGINT)
        LEFT JOIN read_parquet('{L1_DIM_VENUE}') v
               ON v.venue_key = m.venue_key
    ),
    resolved AS (
        SELECT *,
            -- home venue is determinable only for internationals with all ccs
            (na=1 AND nb=1 AND cca IS NOT NULL AND ccb IS NOT NULL AND ccv IS NOT NULL
             AND ( (ccv=cca) <> (ccv=ccb) ))                        AS home_derivable,
            CASE WHEN na=1 AND nb=1 AND cca IS NOT NULL AND ccb IS NOT NULL
                      AND ccv IS NOT NULL AND ccv<>cca AND ccv<>ccb
                 THEN 1 ELSE 0 END                                  AS is_neutral_venue
        FROM base
    ),
    ha AS (
        SELECT *,
            CASE WHEN home_derivable AND ccv=cca THEN team_a_id
                 WHEN home_derivable AND ccv=ccb THEN team_b_id
                 ELSE team_a_id END                                 AS home_team_id,
            CASE WHEN home_derivable AND ccv=cca THEN team_b_id
                 WHEN home_derivable AND ccv=ccb THEN team_a_id
                 ELSE team_b_id END                                 AS away_team_id,
            CASE WHEN home_derivable THEN 'venue_country'
                 ELSE 'feed_order_default' END                      AS home_team_source
        FROM resolved
    )
    SELECT
        h.match_id, h.match_date, h.as_of_date, h.league_key, h.gender, h.tournament_id,
        h.venue_key, cond.day_night, h.is_completed,
        h.is_neutral_venue, h.home_team_source,
        h.home_team_id, h.away_team_id,
        -- HOME block (both windows)
        {home_cols},
        -- AWAY block (both windows)
        {away_cols},
        -- Venue (as_of_date snapshot)
        vs.avg_first_innings_score AS venue_avg_first_innings,
        vs.batfirst_win_pct        AS venue_batfirst_win_pct,
        vs.chase_win_pct           AS venue_chase_win_pct,
        -- Conditions (NULL for upcoming — lifecycle)
        cond.toss_winner, cond.toss_decision, cond.dew_flag,
        -- Market (odds-feed orientation; ~61 priced matches)
        od.home_devig, od.away_devig,
        -- TARGET
        CASE WHEN h.winner IS NULL THEN NULL
             WHEN (h.home_team_id=h.team_a_id AND h.winner='a')
               OR (h.home_team_id=h.team_b_id AND h.winner='b') THEN 'home'
             ELSE 'away' END AS winner
    FROM ha h
    LEFT JOIN tf_wide home ON home.match_id=h.match_id AND home.team_id=h.home_team_id
    LEFT JOIN tf_wide away ON away.match_id=h.match_id AND away.team_id=h.away_team_id
    LEFT JOIN read_parquet('{L2_VENUE}') vs
           ON vs.venue_key=h.venue_key AND vs.gender=h.gender
          AND CAST(vs.as_of_date AS DATE)=h.as_of_date
    LEFT JOIN read_parquet('{L2_COND}') cond
           ON CAST(cond.match_id AS BIGINT)=h.match_id
    LEFT JOIN read_parquet('{L2_ODDS}') od
           ON CAST(od.match_id AS BIGINT)=h.match_id
    ORDER BY h.match_date, h.match_id
    """
    return con.execute(sql).df()


def main():
    L3.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    print("Assembling L3 feature rows ...")
    df = build(con)

    out_dir = L3 / "feature_rows"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = (out_dir / "feature_rows.parquet").as_posix()
    con.register("_l3", df)
    con.execute(f"COPY _l3 TO '{out}' (FORMAT PARQUET)")
    con.unregister("_l3")

    manifest = {
        "layer": "L3",
        "purpose": "flat feature row (one per in-scope T20 match; gender column splits men/women) — the only table the model reads",
        "assembly_only": True,
        "source": "data/lake/l2 (+ L1 dims for home/away resolution, read-only)",
        "build_timestamp": datetime.now().isoformat(timespec="seconds"),
        "grain": "one row per in-scope T20 match (men + women; completed + upcoming)",
        "rows": int(len(df)),
        "home_away_logic": {
            "default": "home=team_a, away=team_b (feed order)",
            "override": "internationals: home=venue-country team when derivable",
            "is_neutral_venue": "1 only for positively-neutral internationals; else 0 "
                                "(domestic neutral-city games undetectable -> 0)",
            "home_team_source": "{venue_country | feed_order_default}",
        },
        "point_in_time": "inherited from L2 team_form (keyed on match_id, as_of_date="
                         "match_date); see tests/test_leakage.py::test_l3_*",
        "odds_orientation": "CAVEAT (unverified): home_devig/away_devig follow the "
                            "ODDS-FEED home/away orientation, which is NOT verified to "
                            "match our assigned home_team. Columns are kept as-is.",
        "placeholder_matches": "40 upcoming matches have team_a==team_b (TBD playoff "
                               "slots); left as-is, they populate when teams are announced.",
        "known_accepted_limitations": [
            "day_night: L2 heuristic on a noisy start_at_local (timezone/rollover) can "
            "mislabel evening games; accepted for v1.",
            "is_neutral_venue: only international neutral venues detected; domestic "
            "neutral-city games default to 0 (under-counted); accepted for v1.",
        ],
        "phase2_followups": [
            "TEAM-LEVEL ODDS BRIDGE: map odds-feed team_home_name/team_away_name to our "
            "internal team ids so home_devig/away_devig align with the assigned "
            "home_team (resolves the odds_orientation caveat above).",
        ],
        "missing_values": "rows kept with NULLs (no ball data -> phase rates NULL; "
                          "no odds -> devig NULL; upcoming -> toss/dew/winner NULL).",
    }
    (L3 / "_manifest.json").write_text(json.dumps(manifest, indent=2))

    _report(con, df, out)
    con.close()


def _report(con, df, out):
    import pandas as pd
    pd.set_option("display.max_rows", 200)

    print(f"\nwrote L3: {len(df):,} rows, {len(df.columns)} columns -> {out}")
    print(f"  completed: {int(df['is_completed'].sum()):,}  |  "
          f"upcoming: {int((~df['is_completed'].astype(bool)).sum()):,}")
    print(f"  is_neutral_venue=1: {int(df['is_neutral_venue'].sum()):,}  |  "
          f"home_team_source=venue_country: "
          f"{int((df['home_team_source']=='venue_country').sum()):,}")

    # ---- null-rate summary per column ----
    print("\n" + "=" * 60)
    print("NULL-RATE per column")
    print("=" * 60)
    n = len(df)
    for c in df.columns:
        nulls = int(df[c].isna().sum())
        print(f"  {c:34s} {nulls:6d}  {100*nulls/n:5.1f}%")

    # ---- odds orientation alignment check (informational) ----
    _odds_alignment(con)

    # ---- transposed sample: a completed IPL match, ideally priced ----
    ipl = df[(df.league_key == "indian premier league") &
             (df.is_completed.astype(bool)) & (df.winner.notna())]
    priced = ipl[ipl.home_devig.notna()]
    pick = (priced if len(priced) else ipl)
    # choose one with populated home/away form for a meaty hand-check
    pick = pick[pick.home_win_pct_tourn.notna()]
    row = pick.iloc[len(pick)//2] if len(pick) else df.iloc[0]

    print("\n" + "=" * 60)
    print(f"SAMPLE (transposed) — completed IPL match_id={int(row['match_id'])}")
    print("=" * 60)
    with pd.option_context("display.float_format", lambda v: f"{v:,.4f}"):
        for c in df.columns:
            v = row[c]
            print(f"  {c:34s} : {v}")

    print("\nRun tests/test_leakage.py for the L3 point-in-time re-check.")


def _odds_alignment(con):
    """Does the odds-feed home team match our assigned home_team? (informational)"""
    try:
        q = f"""
        WITH oz AS (
            SELECT DISTINCT CAST(match_id AS BIGINT) odds_match_id,
                   MAX(CASE WHEN generic_name='team_home_name' THEN name END) feed_home
            FROM read_parquet('{(ROOT/'data/lake/l0/odd_match_odds/*.parquet').as_posix()}')
            WHERE market='Winner 2 Ways' GROUP BY 1
        )
        SELECT COUNT(*) FROM oz
        """
        # Lightweight: we only note that alignment is unverified at L2.
        _ = con.execute(q).fetchone()
    except Exception:
        pass
    print("\n  [odds orientation] home_devig/away_devig use the ODDS-FEED "
          "home/away; alignment to assigned home_team is NOT verified in L2 "
          "(team-level odds bridge = future work).")


if __name__ == "__main__":
    main()
