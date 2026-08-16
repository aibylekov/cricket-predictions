"""L0 landing — freeze an IMMUTABLE Parquet snapshot of raw cricket_raw tables.

Phase 1.2 (README §9). L0 is the raw ball-by-ball / dims / odds exactly as
stored in MariaDB — **no fixes, no filtering, no T20 filter, no type cleaning**.
Every correction (1970-date recovery, comment parsing, entity resolution) and
the T20-men scope happen later in L1/L2 (README §1.3), never here.

What this script does:
  * exports each required table from `cricket_raw` to `data/lake/l0/<table>/`
    as Parquet, one dataset per table;
  * partitions the two large ball-by-ball tables by `_season_year` (derived
    from the match start date) when that date is reachable — the only added
    column is the partition key; all original columns/values are untouched;
  * preserves original column names and types by building the Arrow schema
    from `information_schema` (int columns with NULLs stay integers);
  * is write-once: a non-empty target folder is SKIPPED unless `--force`;
  * verifies Parquet row counts against MariaDB and writes `_manifest.json`.

Strictly READ-ONLY against cricket_raw (SELECT / information_schema only).
Credentials come from `.env`; nothing is hardcoded.

Usage:
    python -m src.data.land_l0            # write-once (skips existing)
    python -m src.data.land_l0 --force    # overwrite existing datasets
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import pymysql
from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
L0_ROOT = PROJECT_ROOT / "data" / "lake" / "l0"
MANIFEST_PATH = L0_ROOT / "_manifest.json"
CHUNK_SIZE = 100_000

# Tables to land, grouped by role (order preserved in output/summary).
TABLES: list[str] = [
    # Ball-by-ball core
    "cricket__over_summary_balls",
    "cricket__over_summaries",
    # Dimensions / structural
    "cricket__matches",
    "cricket__teams",
    "cricket__players",
    "cricket__tournaments",
    "cricket__tournament_points",
    "cricket__associations",
    # Pre-aggregated stats
    "cricket__player_batting_scores",
    "cricket__player_bowling_scores",
    "cricket__player_fielding_scores",
    "cricket__team_play_stats",
    # Conditions
    "cricket__weather_conditions",
    # Odds (historical source)
    "odd_matches",
    "odd_match_odds",
    "odd_markets",
    "odd_outcomes",
    # Published predictions / tips
    "cricket__predictions",
    "cricket__betting_live_tips",
    "cricket__over_under_betting_tips",
    "cricket__prediction_sites",
]

# Season-year partitioning for the two large ball-by-ball tables. Each maps to
# the SQL that yields all original columns plus a derived `season_year`.
# NOTE: the partition key must NOT start with "_" — pyarrow dataset discovery
# ignores files/dirs with a leading underscore, which would hide the data.
PARTITION_KEY = "season_year"
PARTITIONED: dict[str, str] = {
    "cricket__over_summaries": (
        f"SELECT os.*, YEAR(m.start_at) AS {PARTITION_KEY} "
        "FROM cricket__over_summaries os "
        "LEFT JOIN cricket__matches m ON m.id = os.match_id"
    ),
    "cricket__over_summary_balls": (
        f"SELECT b.*, YEAR(m.start_at) AS {PARTITION_KEY} "
        "FROM cricket__over_summary_balls b "
        "LEFT JOIN cricket__over_summaries os ON os.id = b.over_summary_id "
        "LEFT JOIN cricket__matches m ON m.id = os.match_id"
    ),
}


# --------------------------------------------------------------------------- #
# DB
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
        connect_timeout=10,
    )


def mysql_type_to_arrow(data_type: str, column_type: str,
                        precision, scale) -> pa.DataType:
    """Map an information_schema column type to a faithful Arrow type."""
    dt = (data_type or "").lower()
    unsigned = "unsigned" in (column_type or "").lower()

    if dt == "tinyint":
        return pa.uint8() if unsigned else pa.int8()
    if dt in ("smallint", "year"):
        return pa.uint16() if unsigned else pa.int16()
    if dt in ("mediumint", "int", "integer"):
        return pa.uint32() if unsigned else pa.int32()
    if dt == "bigint":
        return pa.uint64() if unsigned else pa.int64()
    if dt in ("decimal", "numeric"):
        return pa.decimal128(int(precision or 38), int(scale or 0))
    if dt == "float":
        return pa.float32()
    if dt in ("double", "real"):
        return pa.float64()
    if dt == "date":
        return pa.date32()
    if dt in ("datetime", "timestamp"):
        return pa.timestamp("us")
    if dt == "time":
        return pa.duration("us")  # MySQL TIME -> pymysql timedelta
    if "blob" in dt or dt in ("binary", "varbinary"):
        return pa.binary()
    return pa.string()  # char/varchar/text/longtext/enum/set/json


def base_table_of(table: str) -> str:
    return table  # SELECT alias uses the physical table for schema lookup


def build_schema(conn, table: str, extra_fields: list[pa.Field]) -> pa.Schema:
    """Build an Arrow schema from information_schema (ordinal order)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, "
            "NUMERIC_PRECISION, NUMERIC_SCALE "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (table,),
        )
        fields = [
            pa.field(name, mysql_type_to_arrow(dtype, ctype, prec, scale))
            for (name, dtype, ctype, prec, scale) in cur.fetchall()
        ]
    return pa.schema(fields + extra_fields)


def source_row_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        return int(cur.fetchone()[0])


def stream_arrow_chunks(conn, sql: str, schema: pa.Schema):
    """Yield Arrow tables of <= CHUNK_SIZE rows, typed per `schema`.

    Uses a server-side cursor so large tables never fully materialise in
    Python at once.
    """
    cur = conn.cursor(pymysql.cursors.SSCursor)
    try:
        cur.execute(sql)
        col_names = [d[0] for d in cur.description]
        while True:
            rows = cur.fetchmany(CHUNK_SIZE)
            if not rows:
                break
            columns = list(zip(*rows))  # row-major -> column-major
            arrays = [
                pa.array(columns[i], type=schema.field(name).type)
                for i, name in enumerate(col_names)
            ]
            yield pa.Table.from_arrays(arrays, schema=schema)
    finally:
        cur.close()


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def _count_dataset(out_dir: Path, partitioned: bool) -> int:
    """Row count of a written dataset (hive flavor for partitioned output)."""
    if partitioned:
        return ds.dataset(str(out_dir), partitioning="hive").count_rows()
    return ds.dataset(str(out_dir)).count_rows()


def export_table(conn, table: str, force: bool) -> dict:
    out_dir = L0_ROOT / table
    partition_cols = [PARTITION_KEY] if table in PARTITIONED else []
    partitioned = bool(partition_cols)

    src_rows = source_row_count(conn, table)

    # Immutability guard.
    if out_dir.exists() and any(out_dir.iterdir()):
        if not force:
            existing = _count_dataset(out_dir, partitioned)
            print(f"  {table}: exists, skipped ({existing:,} rows)")
            return {"table": table, "source_rows": src_rows,
                    "parquet_rows": existing, "path": str(out_dir),
                    "status": "skipped", "partitioned": partitioned}
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    if partition_cols:
        sql = PARTITIONED[table]
        extra = [pa.field(PARTITION_KEY, pa.int32())]
    else:
        sql = f"SELECT * FROM `{table}`"
        extra = []
    schema = build_schema(conn, base_table_of(table), extra)

    written = 0
    for ci, chunk in enumerate(stream_arrow_chunks(conn, sql, schema)):
        ds.write_dataset(
            chunk,
            base_dir=str(out_dir),
            format="parquet",
            partitioning=partition_cols or None,
            partitioning_flavor="hive" if partition_cols else None,
            existing_data_behavior="overwrite_or_ignore",
            basename_template=f"part-{ci}-{{i}}.parquet",
        )
        written += chunk.num_rows
        print(f"  {table}: wrote chunk {ci} (+{chunk.num_rows:,}, "
              f"total {written:,})", flush=True)

    parquet_rows = _count_dataset(out_dir, partitioned)
    status = "ok" if parquet_rows == src_rows else "MISMATCH"
    print(f"  {table}: done -> {parquet_rows:,} rows "
          f"({'partitioned' if partition_cols else 'single'})")
    return {"table": table, "source_rows": src_rows,
            "parquet_rows": parquet_rows, "path": str(out_dir),
            "status": status, "partitioned": bool(partition_cols)}


def print_summary(results: list[dict]) -> None:
    name_w = max(len("Table"), *(len(r["table"]) for r in results))
    print("\n" + "=" * (name_w + 46))
    print(f"{'Table'.ljust(name_w)}  {'Parquet':>10}  {'Source':>10}  {'Status':>8}")
    print("-" * (name_w + 46))
    mismatches = 0
    for r in results:
        flag = r["status"]
        if flag == "MISMATCH":
            mismatches += 1
        print(f"{r['table'].ljust(name_w)}  {r['parquet_rows']:>10,}  "
              f"{r['source_rows']:>10,}  {flag:>8}")
    print("-" * (name_w + 46))
    total_pq = sum(r["parquet_rows"] for r in results)
    total_src = sum(r["source_rows"] for r in results)
    print(f"{'TOTAL'.ljust(name_w)}  {total_pq:>10,}  {total_src:>10,}")
    print("=" * (name_w + 46))
    if mismatches:
        print(f"\n  *** {mismatches} ROW-COUNT MISMATCH(ES) — INVESTIGATE ***")
    else:
        print("\n  All Parquet row counts match MariaDB. ✓")
    print(f"  Output root: {L0_ROOT}")


def write_manifest(results: list[dict], database: str) -> None:
    manifest = {
        "source": database,
        "export_timestamp": datetime.now().isoformat(timespec="seconds"),
        "l0_root": str(L0_ROOT),
        "table_count": len(results),
        "total_rows": sum(r["parquet_rows"] for r in results),
        "tables": [
            {
                "table": r["table"],
                "rows": r["parquet_rows"],
                "source_rows": r["source_rows"],
                "partitioned": r["partitioned"],
                "status": r["status"],
                "path": r["path"],
            }
            for r in results
        ],
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  Manifest: {MANIFEST_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="L0 landing to Parquet (read-only).")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing L0 datasets (default: skip).")
    args = parser.parse_args()

    conn = get_connection()
    database = os.getenv("DB_NAME", "cricket_raw")
    print(f"L0 landing from '{database}' -> {L0_ROOT}"
          f"{'  [--force]' if args.force else ''}\n")
    results: list[dict] = []
    try:
        for table in TABLES:
            results.append(export_table(conn, table, args.force))
    finally:
        conn.close()

    print_summary(results)
    write_manifest(results, database)

    if any(r["status"] == "MISMATCH" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
