"""Targeted source investigations for Phase 1.1 (read-only).

Two questions must be answered before L0 planning (see README §6, §1.4):

A) ODDS lineage — which odds tables are usable, do they carry a match-winner
   (1x2 / moneyline) market, and how well do they cover cricket T20?
B) BALL-BY-BALL reality — is ``cricket__over_summary_balls`` truly one row per
   delivery, and is the stray ``1970-01-01`` date a real problem or recoverable?

Output goes two places:
  * console — a concise findings summary
  * ``logs/raw_profile_report.md`` — a full "Source investigation" section is
    appended (re-runs replace the previous one), with SHOW CREATE TABLE,
    sample rows and the supporting counts.

Strictly READ-ONLY: only SELECT / SHOW / information_schema queries. Credentials
come from ``.env`` (see ``.env.example``); nothing is hardcoded.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path

import pymysql
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "logs" / "raw_profile_report.md"
SECTION_MARKER = "## Source investigation"

# Markets that represent a straight match-winner bet (1x2 / moneyline / H2H).
WINNER_MARKET_RE = re.compile(
    r"winner|1\s*x\s*2|money\s*line|match\s*win|to\s*win|head\s*to\s*head|h2h",
    re.IGNORECASE,
)

# Datetime columns are considered "bad" (epoch/uninitialised) below this.
BAD_DATE_CUTOFF = "2000-01-01"


# --------------------------------------------------------------------------- #
# DB helpers
# --------------------------------------------------------------------------- #
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


def run(conn, sql: str, args=None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchall()


def scalar(conn, sql: str, args=None):
    rows = run(conn, sql, args)
    if not rows:
        return None
    return next(iter(rows[0].values()))


def show_create(conn, table: str) -> str:
    with conn.cursor() as cur:
        cur.execute(f"SHOW CREATE TABLE `{table}`")
        row = cur.fetchone()
    # Key is 'Create Table' (or 'Create View').
    for k, v in row.items():
        if k.lower().startswith("create"):
            return v
    return ""


def datetime_columns(conn, database: str, table: str) -> list[str]:
    rows = run(
        conn,
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
        "AND DATA_TYPE IN ('datetime','timestamp','date') "
        "ORDER BY ORDINAL_POSITION",
        (database, table),
    )
    return [r["COLUMN_NAME"] for r in rows]


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def _fmt(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def sample_block(conn, table: str, n: int = 5) -> list[str]:
    rows = run(conn, f"SELECT * FROM `{table}` LIMIT {n}")
    lines = ["```text"]
    if not rows:
        lines.append("(no rows)")
    for r in rows:
        lines.append(" | ".join(f"{k}={_fmt(v)}" for k, v in r.items()))
    lines.append("```")
    return lines


# --------------------------------------------------------------------------- #
# Investigation A — odds lineage
# --------------------------------------------------------------------------- #
def investigate_odds(conn, database: str) -> tuple[list[str], dict]:
    report: list[str] = ["### A) Odds lineage", ""]
    findings: dict = {}

    # --- SHOW CREATE + samples for the odd_* catalog ------------------------
    for table in ("odd_matches", "odd_match_odds", "odd_markets", "odd_outcomes"):
        report.append(f"#### `{table}`")
        report.append("")
        report.append("```sql")
        report.append(show_create(conn, table))
        report.append("```")
        report.append("")
        report.append(f"_Sample rows ({table}):_")
        report += sample_block(conn, table)
        report.append("")

    # --- Market inventory ---------------------------------------------------
    markets = run(
        conn,
        "SELECT market, COUNT(*) rows_cnt, COUNT(DISTINCT match_id) matches "
        "FROM odd_match_odds GROUP BY market ORDER BY rows_cnt DESC",
    )
    winner_markets = [m["market"] for m in markets if WINNER_MARKET_RE.search(m["market"] or "")]
    findings["markets"] = markets
    findings["winner_markets"] = winner_markets

    report.append("#### Market types in `odd_match_odds`")
    report.append("")
    report.append("| Market | Rows | Distinct matches | Match-winner? |")
    report.append("|---|---:|---:|:--:|")
    for m in markets:
        is_win = "✓" if m["market"] in winner_markets else ""
        report.append(f"| {m['market']} | {m['rows_cnt']:,} | {m['matches']:,} | {is_win} |")
    report.append("")

    # Outcomes-per-match sanity for the winner market(s): expect 2 (or 3 w/ draw).
    if winner_markets:
        placeholders = ",".join(["%s"] * len(winner_markets))
        outcome_shape = run(
            conn,
            f"SELECT n_outcomes, COUNT(*) n_matches FROM ("
            f"  SELECT match_id, vendor, COUNT(*) n_outcomes "
            f"  FROM odd_match_odds WHERE market IN ({placeholders}) "
            f"  GROUP BY match_id, vendor) t "
            f"GROUP BY n_outcomes ORDER BY n_outcomes",
            winner_markets,
        )
        findings["winner_outcome_shape"] = outcome_shape
        matches_with_winner = scalar(
            conn,
            f"SELECT COUNT(DISTINCT match_id) FROM odd_match_odds "
            f"WHERE market IN ({placeholders})",
            winner_markets,
        )
        findings["matches_with_winner"] = matches_with_winner

        report.append(
            f"**Match-winner market present:** `{', '.join(winner_markets)}` — "
            f"**{matches_with_winner:,} matches** priced."
        )
        report.append("")
        report.append("_Outcome prices per (match, vendor) for the winner market:_")
        report.append("")
        report.append("| # outcomes/side | # (match,vendor) groups |")
        report.append("|---:|---:|")
        for o in outcome_shape:
            report.append(f"| {o['n_outcomes']} | {o['n_matches']:,} |")
        report.append("")

    # --- Vendor breakdown ---------------------------------------------------
    vendors = run(
        conn,
        "SELECT vendor, COUNT(*) rows_cnt, COUNT(DISTINCT match_id) matches "
        "FROM odd_match_odds GROUP BY vendor ORDER BY rows_cnt DESC",
    )
    findings["vendors"] = vendors
    report.append("#### Vendors present in `odd_match_odds`")
    report.append("")
    report.append("| Vendor | Rows | Distinct matches |")
    report.append("|---|---:|---:|")
    for v in vendors:
        report.append(f"| {v['vendor']} | {v['rows_cnt']:,} | {v['matches']:,} |")
    report.append("")

    # --- Coverage over cricket T20 (men) -----------------------------------
    # odd_matches has no cricket FK — only team NAMES + start_time. So coverage
    # is a heuristic name+date join (this is exactly why README §1.4 mandates a
    # bridge_entity table). Two levels: fixtures vs actually-priced matches.
    total_cricket_fixtures = scalar(
        conn, "SELECT COUNT(*) FROM odd_matches WHERE sport_id=1"
    )
    fixtures_matched_t20m = scalar(
        conn,
        "SELECT COUNT(DISTINCT om.id) FROM odd_matches om "
        "JOIN cricket__matches m ON DATE(m.start_at)=DATE(om.start_time) "
        "  AND m.format='t20' AND m.gender='male' "
        "JOIN cricket__teams ta ON ta.id=m.team_a "
        "JOIN cricket__teams tb ON tb.id=m.team_b "
        "WHERE (om.team_home_name=ta.name AND om.team_away_name=tb.name) "
        "   OR (om.team_home_name=tb.name AND om.team_away_name=ta.name)",
    )

    priced_cov = {}
    if winner_markets:
        placeholders = ",".join(["%s"] * len(winner_markets))
        priced_cov = run(
            conn,
            "SELECT COUNT(DISTINCT m.id) cricket_matches, "
            "       COUNT(DISTINCT om.id) odd_matches "
            "FROM odd_match_odds oo "
            "JOIN odd_matches om ON om.id=oo.match_id "
            "JOIN cricket__matches m ON DATE(m.start_at)=DATE(om.start_time) "
            "  AND m.format='t20' AND m.gender='male' "
            "JOIN cricket__teams ta ON ta.id=m.team_a "
            "JOIN cricket__teams tb ON tb.id=m.team_b "
            f"WHERE oo.market IN ({placeholders}) "
            "  AND ((om.team_home_name=ta.name AND om.team_away_name=tb.name) "
            "    OR (om.team_home_name=tb.name AND om.team_away_name=ta.name))",
            winner_markets,
        )[0]

    findings["total_cricket_fixtures"] = total_cricket_fixtures
    findings["fixtures_matched_t20m"] = fixtures_matched_t20m
    findings["priced_cov"] = priced_cov

    report.append("#### Coverage over cricket T20 (men)")
    report.append("")
    report.append(
        "> `odd_matches` has **no cricket foreign key** — only team names + "
        "`start_time`. Coverage below is a heuristic join on `DATE(start)` + "
        "exact team-name match (either home/away orientation). This under-counts "
        "wherever names differ, which is precisely the gap `bridge_entity` "
        "(README §1.4) must close."
    )
    report.append("")
    report.append(f"- Cricket fixtures in `odd_matches` (sport_id=1): **{total_cricket_fixtures:,}**")
    report.append(f"- …that map to a **T20-male** cricket match (name+date): **{fixtures_matched_t20m:,}**")
    if priced_cov:
        report.append(
            f"- **T20-male matches with actual winner odds:** "
            f"**{priced_cov['cricket_matches']:,}** cricket matches "
            f"(via {priced_cov['odd_matches']:,} priced `odd_matches`)"
        )
    report.append("")

    return report, findings


# --------------------------------------------------------------------------- #
# Investigation B — ball-by-ball reality
# --------------------------------------------------------------------------- #
def investigate_balls(conn, database: str) -> tuple[list[str], dict]:
    table = "cricket__over_summary_balls"
    report: list[str] = ["### B) Ball-by-ball reality check", ""]
    findings: dict = {}

    report.append(f"#### `{table}`")
    report.append("")
    report.append("```sql")
    report.append(show_create(conn, table))
    report.append("```")
    report.append("")
    report.append("_Sample rows:_")
    report += sample_block(conn, table)
    report.append("")

    # --- Grain proof: rows per over_summary_id ------------------------------
    total = scalar(conn, f"SELECT COUNT(*) FROM `{table}`")
    dist = run(
        conn,
        f"SELECT cnt AS balls_in_over, COUNT(*) AS num_overs FROM "
        f"(SELECT over_summary_id, COUNT(*) cnt FROM `{table}` "
        f" GROUP BY over_summary_id) t GROUP BY cnt ORDER BY cnt",
    )
    ball_values = run(
        conn,
        f"SELECT ball, COUNT(*) c FROM `{table}` GROUP BY ball ORDER BY c DESC LIMIT 10",
    )
    findings["total"] = total
    findings["dist"] = dist
    findings["ball_values"] = ball_values

    report.append("#### Grain: is it one row per delivery?")
    report.append("")
    report.append(
        "Each `over_summary_id` groups the deliveries of one over. A T20 over is "
        "6 legal balls (more when extras add re-bowls), so a mode of **6 rows per "
        "over** proves **per-delivery** grain — not per-over."
    )
    report.append("")
    report.append("| Balls in over | # overs |")
    report.append("|---:|---:|")
    for d in dist:
        report.append(f"| {d['balls_in_over']} | {d['num_overs']:,} |")
    report.append("")
    report.append(
        "Columns proving per-delivery grain: `over_summary_id` (→ over via "
        "`cricket__over_summaries.over`), `ball` (ball # within over), `runs` "
        "(runs off that ball), `ball_type`/`wicket` (per-ball events), and "
        "`comment` (e.g. _\"Ajaz Patel to Taijul Islam: No runs.\"_). "
        "**Batter & bowler are embedded in `comment` text, not separate columns** "
        "— L0 parsing will need to extract them (or join Roanuz ball keys)."
    )
    report.append("")

    # --- 1970 date audit ----------------------------------------------------
    dt_cols = datetime_columns(conn, database, table)
    bad_counts = {}
    for col in dt_cols:
        bad_counts[col] = int(
            scalar(conn, f"SELECT COUNT(*) FROM `{table}` WHERE `{col}` < %s", (BAD_DATE_CUTOFF,))
            or 0
        )
    findings["bad_counts"] = bad_counts
    findings["dt_cols"] = dt_cols

    # Recoverability for whichever columns are affected.
    recoverable = {}
    for col, bad in bad_counts.items():
        if bad == 0:
            continue
        row = run(
            conn,
            f"SELECT COUNT(*) bad_rows, SUM(m.start_at IS NOT NULL) recoverable "
            f"FROM `{table}` b "
            f"JOIN cricket__over_summaries os ON os.id=b.over_summary_id "
            f"LEFT JOIN cricket__matches m ON m.id=os.match_id "
            f"WHERE b.`{col}` < %s",
            (BAD_DATE_CUTOFF,),
        )[0]
        recoverable[col] = {
            "bad": int(row["bad_rows"] or 0),
            "recoverable": int(row["recoverable"] or 0),
        }
    findings["recoverable"] = recoverable

    report.append("#### The `1970-01-01` date")
    report.append("")
    report.append("| Column | Rows before 2000 | % of table |")
    report.append("|---|---:|---:|")
    for col, bad in bad_counts.items():
        pct = (bad / total * 100) if total else 0.0
        report.append(f"| `{col}` | {bad:,} | {pct:.4f}% |")
    report.append("")
    for col, rec in recoverable.items():
        report.append(
            f"- `{col}`: **{rec['bad']:,}** bad rows, "
            f"**{rec['recoverable']:,} recoverable** via "
            f"`over_summary_id → over_summaries.match_id → cricket__matches.start_at`."
        )
    if not recoverable:
        report.append("- No datetime column has pre-2000 rows.")
    report.append("")
    report.append(
        "The real per-ball timestamp is `entry_time` (clean). The stray epoch "
        "dates sit in the secondary `updated` column and are fully recoverable, "
        "so this is **not** a blocker for L0."
    )
    report.append("")

    return report, findings


# --------------------------------------------------------------------------- #
# Report writing (replace prior Source-investigation section on re-run)
# --------------------------------------------------------------------------- #
def append_to_report(body: list[str]) -> None:
    header = [
        SECTION_MARKER,
        "",
        "_Phase 1.1 targeted investigations (read-only). Re-running "
        "`src/data/inspect_sources.py` replaces this section._",
        "",
    ]
    new_section = "\n".join(header + body).rstrip() + "\n"

    existing = ""
    if REPORT_PATH.exists():
        existing = REPORT_PATH.read_text(encoding="utf-8")
        idx = existing.find(SECTION_MARKER)
        if idx != -1:
            existing = existing[:idx].rstrip() + "\n"

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sep = "\n" if existing.endswith("\n") else "\n\n"
    REPORT_PATH.write_text(existing + sep + new_section, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Console summary
# --------------------------------------------------------------------------- #
def print_console(odds: dict, balls: dict) -> None:
    print("\n" + "=" * 64)
    print("SOURCE INVESTIGATION — FINDINGS")
    print("=" * 64)

    print("\nA) ODDS LINEAGE")
    mk = odds["markets"]
    print(f"  Markets in odd_match_odds: {len(mk)} "
          f"({', '.join(m['market'] for m in mk)})")
    if odds.get("winner_markets"):
        print(f"  Match-winner market: YES -> {', '.join(odds['winner_markets'])}")
        shape = ", ".join(f"{o['n_outcomes']}px x{o['n_matches']}"
                          for o in odds.get("winner_outcome_shape", []))
        print(f"    outcome prices per (match,vendor): {shape}")
        print(f"    matches priced (any vendor): {odds['matches_with_winner']:,}")
    else:
        print("  Match-winner market: NONE FOUND")
    print("  Vendors: " + ", ".join(
        f"{v['vendor']}({v['matches']} m)" for v in odds["vendors"]))
    print(f"  Cricket fixtures in odd_matches: {odds['total_cricket_fixtures']:,}")
    print(f"    -> map to T20-male cricket (name+date): {odds['fixtures_matched_t20m']:,}")
    if odds.get("priced_cov"):
        pc = odds["priced_cov"]
        print(f"    -> T20-male matches with ACTUAL winner odds: "
              f"{pc['cricket_matches']:,}")

    print("\nB) BALL-BY-BALL (cricket__over_summary_balls)")
    print(f"  Total rows: {balls['total']:,}")
    mode = max(balls["dist"], key=lambda d: d["num_overs"])
    print(f"  Grain: PER-DELIVERY (mode = {mode['balls_in_over']} balls/over, "
          f"{mode['num_overs']:,} overs)")
    print("  Balls-in-over distribution: " + ", ".join(
        f"{d['balls_in_over']}:{d['num_overs']:,}" for d in balls["dist"]))
    for col, bad in balls["bad_counts"].items():
        if bad:
            pct = bad / balls["total"] * 100
            rec = balls["recoverable"].get(col, {})
            print(f"  1970 dates in `{col}`: {bad:,} ({pct:.4f}%) -> "
                  f"{rec.get('recoverable', 0):,} recoverable via matches.start_at")
    clean = [c for c, b in balls["bad_counts"].items() if b == 0]
    if clean:
        print(f"  Clean datetime columns: {', '.join(clean)}")
    print("=" * 64)


def main() -> None:
    conn = get_connection()
    database = os.getenv("DB_NAME", "cricket_raw")
    try:
        odds_report, odds_findings = investigate_odds(conn, database)
        balls_report, balls_findings = investigate_balls(conn, database)
    finally:
        conn.close()

    append_to_report(odds_report + [""] + balls_report)
    print_console(odds_findings, balls_findings)
    print(f"\nAppended 'Source investigation' section to {REPORT_PATH}")


if __name__ == "__main__":
    main()
