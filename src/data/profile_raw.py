"""Profile the raw cricket DB (read-only).

Phase 1.1 of the build plan (see README §9): inventory every relevant table in
the local `cricket_raw` MySQL/MariaDB database before we land it as immutable
Parquet.

For every table whose name starts with ``cricket__``, ``odd_`` or ``odds__`` we
collect:
  * exact row count
  * column list with data types (from information_schema)
  * MIN / MAX for every date/datetime-looking column
  * null count per column

Results are written to ``logs/raw_profile_report.md`` (one section per table)
and a short summary (table + rows + date range) is printed to the console.

This script is strictly READ-ONLY. It issues only SELECT / SHOW / information_
schema queries and never modifies ``cricket_raw``.

Credentials come from ``.env`` (see ``.env.example``); nothing is hardcoded.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

import pymysql
from dotenv import load_dotenv

# --- Paths ------------------------------------------------------------------
# src/data/profile_raw.py -> project root is two parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "logs" / "raw_profile_report.md"

# Table-name prefixes we care about (README §1.1 scope: cricket + odds).
TABLE_PREFIXES = ("cricket__", "odd_", "odds__")

# DATA_TYPE values (from information_schema) that are inherently temporal.
TEMPORAL_TYPES = {"date", "datetime", "timestamp", "time", "year"}

# Name substrings that suggest a temporal column even when stored as text/int.
TEMPORAL_NAME_HINTS = ("date", "time", "_at", "timestamp", "start", "end")


def get_connection() -> pymysql.connections.Connection:
    """Open a read-only DB connection using credentials from .env."""
    load_dotenv(PROJECT_ROOT / ".env")

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "") or ""
    database = os.getenv("DB_NAME", "cricket_raw")

    try:
        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
            connect_timeout=10,
        )
    except pymysql.err.OperationalError as exc:
        code = exc.args[0] if exc.args else None
        print(f"\n[ERROR] Could not connect to '{database}' at {host}:{port} as '{user}'.")
        if code == 1045:
            print("        Access denied — set DB_PASSWORD in your .env file.")
        elif code == 2059:
            print("        The server requested an auth plugin (gssapi). This happens on a")
            print("        passwordless attempt — set the real DB_PASSWORD in .env.")
        print(f"        Driver said: {exc}")
        sys.exit(1)


def list_target_tables(conn, database: str) -> list[str]:
    """Return, sorted, all tables in `database` matching our prefixes."""
    like_clauses = " OR ".join("TABLE_NAME LIKE %s" for _ in TABLE_PREFIXES)
    params = [database] + [f"{p}%" for p in TABLE_PREFIXES]
    sql = (
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s AND (" + like_clauses + ") "
        "ORDER BY TABLE_NAME"
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [row[0] for row in cur.fetchall()]


def get_columns(conn, database: str, table: str) -> list[dict]:
    """Return column metadata (name, type, nullability) for a table."""
    sql = (
        "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
        "ORDER BY ORDINAL_POSITION"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (database, table))
        return [
            {
                "name": name,
                "data_type": data_type,
                "column_type": column_type,
                "nullable": is_nullable == "YES",
            }
            for (name, data_type, column_type, is_nullable) in cur.fetchall()
        ]


def is_temporal(col: dict) -> bool:
    """Decide whether a column looks like a date/datetime worth MIN/MAX-ing."""
    if col["data_type"] in TEMPORAL_TYPES:
        return True
    name = col["name"].lower()
    return any(hint in name for hint in TEMPORAL_NAME_HINTS)


def profile_table(conn, database: str, table: str) -> dict:
    """Collect row count, null counts and date ranges for a single table.

    All aggregates are gathered in one pass over the table for efficiency.
    """
    columns = get_columns(conn, database, table)
    temporal_cols = [c for c in columns if is_temporal(c)]

    # Build a single aggregate query: COUNT(*), per-column null counts, and
    # MIN/MAX for temporal columns.
    select_parts = ["COUNT(*) AS `__row_count`"]
    for c in columns:
        col = c["name"]
        select_parts.append(
            f"SUM(CASE WHEN `{col}` IS NULL THEN 1 ELSE 0 END) AS `null__{col}`"
        )
    for c in temporal_cols:
        col = c["name"]
        select_parts.append(f"MIN(`{col}`) AS `min__{col}`")
        select_parts.append(f"MAX(`{col}`) AS `max__{col}`")

    sql = f"SELECT {', '.join(select_parts)} FROM `{database}`.`{table}`"

    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(sql)
        row = cur.fetchone() or {}

    row_count = int(row.get("__row_count", 0) or 0)

    null_counts = {c["name"]: int(row.get(f"null__{c['name']}", 0) or 0) for c in columns}

    date_ranges = {}
    for c in temporal_cols:
        col = c["name"]
        date_ranges[col] = {
            "min": row.get(f"min__{col}"),
            "max": row.get(f"max__{col}"),
        }

    return {
        "table": table,
        "row_count": row_count,
        "columns": columns,
        "null_counts": null_counts,
        "date_ranges": date_ranges,
    }


def _fmt(value) -> str:
    """Format a scalar value for the report/console."""
    if value is None:
        return "—"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _sort_key(value):
    """Return a comparable datetime for chronological values, else None.

    Temporal columns can be a mix of real datetimes, plain dates, and even
    text/int columns caught by the name heuristic. Only fold genuinely
    chronological values into the representative range, normalizing `date`
    to `datetime` so the two can be compared.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return None


def overall_date_range(profile: dict) -> tuple[str, str]:
    """Compute a representative (min, max) across all temporal columns."""
    lows, highs = [], []
    for rng in profile["date_ranges"].values():
        lo_key = _sort_key(rng["min"])
        if lo_key is not None:
            lows.append((lo_key, rng["min"]))
        hi_key = _sort_key(rng["max"])
        if hi_key is not None:
            highs.append((hi_key, rng["max"]))
    lo = min(lows, key=lambda x: x[0])[1] if lows else None
    hi = max(highs, key=lambda x: x[0])[1] if highs else None
    return _fmt(lo), _fmt(hi)


def write_report(profiles: list[dict], database: str, server_version: str) -> None:
    """Write the full markdown report, one section per table."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# Raw DB profile — `{database}`")
    lines.append("")
    lines.append(f"- Server: `{server_version}`")
    lines.append(f"- Tables profiled: **{len(profiles)}** "
                 f"(prefixes: {', '.join('`' + p + '`' for p in TABLE_PREFIXES)})")
    lines.append(f"- Total rows: **{sum(p['row_count'] for p in profiles):,}**")
    lines.append("- Read-only profile (Phase 1.1). `cricket_raw` was not modified.")
    lines.append("")

    # Table of contents / summary table.
    lines.append("## Summary")
    lines.append("")
    lines.append("| Table | Rows | Date range |")
    lines.append("|---|---:|---|")
    for p in profiles:
        lo, hi = overall_date_range(p)
        rng = "—" if lo == "—" and hi == "—" else f"{lo} → {hi}"
        lines.append(f"| `{p['table']}` | {p['row_count']:,} | {rng} |")
    lines.append("")

    # Per-table detail.
    for p in profiles:
        lines.append(f"## `{p['table']}`")
        lines.append("")
        lines.append(f"- Rows: **{p['row_count']:,}**")
        lines.append(f"- Columns: **{len(p['columns'])}**")
        lines.append("")

        # Columns + types + null counts.
        lines.append("| Column | Type | Nullable | Nulls | Null % |")
        lines.append("|---|---|:--:|---:|---:|")
        for c in p["columns"]:
            nulls = p["null_counts"].get(c["name"], 0)
            pct = (nulls / p["row_count"] * 100) if p["row_count"] else 0.0
            lines.append(
                f"| `{c['name']}` | {c['column_type']} | "
                f"{'yes' if c['nullable'] else 'no'} | {nulls:,} | {pct:.1f}% |"
            )
        lines.append("")

        # Date/datetime ranges.
        if p["date_ranges"]:
            lines.append("**Date / datetime ranges**")
            lines.append("")
            lines.append("| Column | Min | Max |")
            lines.append("|---|---|---|")
            for col, rng in p["date_ranges"].items():
                lines.append(f"| `{col}` | {_fmt(rng['min'])} | {_fmt(rng['max'])} |")
            lines.append("")
        else:
            lines.append("_No date/datetime-looking columns detected._")
            lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def print_console_summary(profiles: list[dict]) -> None:
    """Print a short summary table to stdout."""
    name_w = max([len("Table")] + [len(p["table"]) for p in profiles])
    rows_w = max([len("Rows")] + [len(f"{p['row_count']:,}") for p in profiles])

    header = f"{'Table'.ljust(name_w)}  {'Rows'.rjust(rows_w)}  Date range"
    print("\n" + header)
    print("-" * len(header))
    for p in profiles:
        lo, hi = overall_date_range(p)
        rng = "—" if lo == "—" and hi == "—" else f"{lo} → {hi}"
        rows_str = f"{p['row_count']:,}".rjust(rows_w)
        print(f"{p['table'].ljust(name_w)}  {rows_str}  {rng}")
    total = sum(p["row_count"] for p in profiles)
    print("-" * len(header))
    print(f"{len(profiles)} tables, {total:,} total rows")


def main() -> None:
    database = os.getenv("DB_NAME", "cricket_raw")
    conn = get_connection()
    # load_dotenv already ran inside get_connection; re-read DB_NAME in case
    # the default differed.
    database = os.getenv("DB_NAME", "cricket_raw")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION()")
            server_version = cur.fetchone()[0]

        tables = list_target_tables(conn, database)
        if not tables:
            print(f"No tables matching {TABLE_PREFIXES} found in '{database}'.")
            return

        print(f"Profiling {len(tables)} tables in '{database}' (read-only)...")
        profiles: list[dict] = []
        for i, table in enumerate(tables, 1):
            print(f"  [{i}/{len(tables)}] {table}", flush=True)
            try:
                profiles.append(profile_table(conn, database, table))
            except Exception as exc:  # noqa: BLE001 - keep going on one bad table
                print(f"      ! failed to profile {table}: {exc}")

        write_report(profiles, database, server_version)
        print_console_summary(profiles)
        print(f"\nReport written to {REPORT_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
