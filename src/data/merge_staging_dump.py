"""merge_staging_dump.py — stage per-table SQL dumps and merge NEW rows into
cricket_raw (id-keyed, additive, never destructive).

The site exports phpMyAdmin per-table dumps (CREATE TABLE under an ALIAS name
such as `m` / `bat` / `p`, ALTER TABLE for keys, INSERT rows). They must NEVER
be sourced into cricket_raw directly: the CREATE/ALTER statements would land
junk alias tables next to the real ones, and a future export could carry DROP.

Flow (every step reported, nothing silent):
  1. INSPECT  — each .sql is scanned; any DROP / TRUNCATE / DELETE / UPDATE /
                REPLACE / RENAME / USE / CREATE DATABASE aborts the run.
  2. LOAD     — `--load`: the dump is sourced into a disposable STAGING
                database (default `cricket_sc`) with the MariaDB client; the
                alias table is (re)created there. cricket_raw is untouched.
  3. COMPARE  — per table: column drift (dump vs cricket_raw), staged rows,
                id overlap with cricket_raw (same site DB => same id space),
                overlap split into IDENTICAL rows and CHANGED rows (same id,
                different content; which columns differ).
  4. MERGE    — `--apply`: rows whose id is NOT in cricket_raw are inserted
                (common columns only). Identical rows are skipped. CHANGED
                rows are NEVER overwritten (L0 is immutable; they are listed
                for a human decision).
  5. REPORT   — Markdown + JSON (default docs/ingest/<dump-dir-name>_merge_report.*).

Usage:
  python -m src.data.merge_staging_dump --dump-dir data/raw/spring_challenge_2026 --load
  python -m src.data.merge_staging_dump --dump-dir data/raw/spring_challenge_2026 --apply
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pymysql
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN = re.compile(
    r"^\s*(DROP|TRUNCATE|DELETE|UPDATE|REPLACE|RENAME|USE|GRANT|REVOKE|"
    r"CREATE\s+(DATABASE|SCHEMA|USER)|LOAD\s+DATA)\b",
    re.IGNORECASE | re.MULTILINE,
)
CREATE_RE = re.compile(r"^CREATE TABLE `([^`]+)`", re.MULTILINE)
INSERT_RE = re.compile(r"^INSERT INTO `([^`]+)`", re.MULTILINE)
ALTER_RE = re.compile(r"^ALTER TABLE `([^`]+)`", re.MULTILINE)
PROTECTED_DBS = {"cricket_raw", "mysql", "information_schema",
                 "performance_schema", "sys"}


# --------------------------------------------------------------------------- #
def db_params() -> dict:
    load_dotenv(PROJECT_ROOT / ".env")
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "") or "",
    }


def connect(database: str | None = None):
    p = db_params()
    return pymysql.connect(host=p["host"], port=p["port"], user=p["user"],
                           password=p["password"], database=database,
                           charset="utf8mb4", connect_timeout=10,
                           autocommit=False)


def find_client() -> str:
    env = os.getenv("MARIADB_CLIENT")
    if env and Path(env).exists():
        return env
    for name in ("mariadb", "mysql"):
        found = shutil.which(name)
        if found:
            return found
    for pat in (r"C:\Program Files\MariaDB*\bin\mariadb.exe",
                r"C:\Program Files\MariaDB*\bin\mysql.exe",
                r"C:\Program Files\MySQL\*\bin\mysql.exe"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    sys.exit("No MariaDB/MySQL client found (set MARIADB_CLIENT in .env).")


# --------------------------------------------------------------------------- #
def inspect_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    forbidden = [m.group(0).strip() for m in FORBIDDEN.finditer(text)]
    creates = CREATE_RE.findall(text)
    inserts = INSERT_RE.findall(text)
    alters = ALTER_RE.findall(text)
    if len(set(creates)) != 1:
        sys.exit(f"{path.name}: expected exactly one CREATE TABLE, found {creates}")
    alias = creates[0]
    if set(inserts) - {alias} or set(alters) - {alias}:
        sys.exit(f"{path.name}: INSERT/ALTER target differs from CREATE alias "
                 f"({set(inserts) | set(alters)} vs {alias})")
    # value tuples: phpMyAdmin writes one row per line, each starting with "("
    tuple_lines = sum(1 for ln in text.splitlines() if ln.startswith("("))
    return {"file": path.name, "target_table": path.stem, "alias": alias,
            "create": len(creates), "insert_stmts": len(inserts),
            "alter": len(alters), "tuple_lines": tuple_lines,
            "forbidden": forbidden, "bytes": path.stat().st_size}


def load_into_staging(client: str, staging: str, path: Path, alias: str) -> None:
    p = db_params()
    if staging.lower() in PROTECTED_DBS:
        sys.exit(f"refusing to use '{staging}' as a staging database")
    con = connect()
    try:
        with con.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{staging}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            # staging is disposable: recreate the alias table from the dump
            cur.execute(f"DROP TABLE IF EXISTS `{staging}`.`{alias}`")
        con.commit()
    finally:
        con.close()
    env = dict(os.environ, MYSQL_PWD=p["password"])
    cmd = [client, f"--host={p['host']}", f"--port={p['port']}",
           f"--user={p['user']}", "--default-character-set=utf8mb4",
           f"--database={staging}"]
    with path.open("rb") as fh:
        res = subprocess.run(cmd, stdin=fh, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"client failed on {path.name}:\n{res.stderr}")


# --------------------------------------------------------------------------- #
def columns(cur, schema: str, table: str) -> list[str]:
    cur.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
                (schema, table))
    return [r[0] for r in cur.fetchall()]


def compare_table(cur, staging: str, alias: str, target: str) -> dict:
    s_cols = columns(cur, staging, alias)
    r_cols = columns(cur, "cricket_raw", target)
    if not s_cols:
        sys.exit(f"staging table {staging}.{alias} not found — run with --load first")
    if not r_cols:
        sys.exit(f"cricket_raw.{target} does not exist")
    common = [c for c in r_cols if c in s_cols]
    only_dump = [c for c in s_cols if c not in r_cols]
    only_raw = [c for c in r_cols if c not in s_cols]
    if "id" not in common:
        sys.exit(f"{target}: no `id` column in common — cannot merge by id")

    S, R = f"`{staging}`.`{alias}`", f"`cricket_raw`.`{target}`"
    cur.execute(f"SELECT COUNT(*), MIN(id), MAX(id) FROM {S}")
    staged, s_min, s_max = cur.fetchone()
    cur.execute(f"SELECT COUNT(*), MAX(id) FROM {R}")
    raw_rows, raw_max = cur.fetchone()
    cur.execute(f"SELECT COUNT(*) FROM {S} s JOIN {R} r ON r.id = s.id")
    overlap = cur.fetchone()[0]

    identical, changed_ids, changed_cols = 0, [], {}
    if overlap:
        same = " AND ".join(f"(s.`{c}` <=> r.`{c}`)" for c in common)
        cur.execute(f"SELECT COUNT(*) FROM {S} s JOIN {R} r ON r.id = s.id WHERE {same}")
        identical = cur.fetchone()[0]
        cur.execute(f"SELECT s.id FROM {S} s JOIN {R} r ON r.id = s.id "
                    f"WHERE NOT ({same}) ORDER BY s.id LIMIT 50")
        changed_ids = [r[0] for r in cur.fetchall()]
        if changed_ids:
            for c in common:
                cur.execute(f"SELECT COUNT(*) FROM {S} s JOIN {R} r ON r.id = s.id "
                            f"WHERE NOT (s.`{c}` <=> r.`{c}`)")
                n = cur.fetchone()[0]
                if n:
                    changed_cols[c] = n
    return {
        "table": target, "alias": alias, "staged": staged,
        "staged_id_min": s_min, "staged_id_max": s_max,
        "raw_rows_before": raw_rows, "raw_id_max_before": raw_max,
        "overlap": overlap, "identical": identical,
        "changed": overlap - identical, "changed_ids_sample": changed_ids,
        "changed_columns": changed_cols,
        "new": staged - overlap, "common_columns": len(common),
        "columns_only_in_dump": only_dump, "columns_only_in_raw": only_raw,
        "_common": common,
    }


def apply_insert(cur, staging: str, info: dict) -> int:
    S, R = f"`{staging}`.`{info['alias']}`", f"`cricket_raw`.`{info['table']}`"
    cols = ", ".join(f"`{c}`" for c in info["_common"])
    scols = ", ".join(f"s.`{c}`" for c in info["_common"])
    cur.execute(f"INSERT INTO {R} ({cols}) SELECT {scols} FROM {S} s "
                f"LEFT JOIN {R} r ON r.id = s.id WHERE r.id IS NULL")
    return cur.rowcount


# --------------------------------------------------------------------------- #
def write_report(out_md: Path, out_json: Path, dump_dir: Path, staging: str,
                 inspections: list[dict], results: list[dict], applied: bool) -> None:
    mode = ("APPLIED (new rows inserted into cricket_raw)" if applied
            else "DRY RUN (nothing written to cricket_raw)")
    lines = [f"# Merge report — {dump_dir.name}", "",
             f"- generated: {datetime.now().isoformat(timespec='seconds')}",
             f"- dump dir: `{dump_dir}`", f"- staging db: `{staging}`",
             f"- mode: **{mode}**",
             "", "## 1. Dump inspection", "",
             "| file | alias | CREATE | ALTER | INSERT stmts | row tuples | forbidden statements |",
             "|---|---|---|---|---|---|---|"]
    for i in inspections:
        lines.append(f"| {i['file']} | `{i['alias']}` | {i['create']} | {i['alter']} | "
                     f"{i['insert_stmts']} | {i['tuple_lines']} | "
                     f"{', '.join(i['forbidden']) or 'none'} |")
    lines += ["",
              "Dumps are CREATE TABLE (alias name) + ALTER TABLE (PK/indexes/"
              "AUTO_INCREMENT) + INSERT. No DROP/TRUNCATE. Sourcing them into "
              "cricket_raw directly would have created junk alias tables; they "
              "were loaded into the staging db instead.",
              "", "## 2. Merge per table", "",
              "| table | staged | raw rows before | raw max id before | staged id range | "
              "already present (identical) | present but CHANGED (kept existing) | "
              f"{'inserted' if applied else 'to insert'} | raw rows after |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['table']} | {r['staged']} | {r['raw_rows_before']:,} | "
                     f"{r['raw_id_max_before']} | {r['staged_id_min']}–{r['staged_id_max']} | "
                     f"{r['identical']} | {r['changed']} | {r.get('inserted', r['new'])} | "
                     f"{r.get('raw_rows_after', '-')} |")
    lines += ["", "## 3. Column drift (dump vs cricket_raw)", ""]
    any_drift = False
    for r in results:
        if r["columns_only_in_dump"] or r["columns_only_in_raw"]:
            any_drift = True
            lines.append(f"- **{r['table']}**: only in dump = {r['columns_only_in_dump'] or '—'}; "
                         f"only in cricket_raw (left NULL/default on insert) = "
                         f"{r['columns_only_in_raw'] or '—'}")
    if not any_drift:
        lines.append("None — every dump column exists in cricket_raw and vice versa.")
    lines += ["", "## 4. Changed rows (same id, different content — NOT overwritten)", ""]
    any_changed = False
    for r in results:
        if r["changed"]:
            any_changed = True
            lines.append(f"- **{r['table']}**: {r['changed']} row(s); differing columns "
                         f"{{col: rows}} = {r['changed_columns']}; ids (first 50) = "
                         f"{r['changed_ids_sample']}")
    if not any_changed:
        lines.append("None — every overlapping id is a byte-identical duplicate.")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    slim = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    out_json.write_text(json.dumps({"dump_dir": str(dump_dir), "staging": staging,
                                    "applied": applied, "inspections": inspections,
                                    "tables": slim}, indent=2, default=str),
                        encoding="utf-8")
    print("\n".join(lines))
    print(f"\nReport: {out_md}\n        {out_json}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage SQL dumps and merge new rows into cricket_raw.")
    ap.add_argument("--dump-dir", required=True)
    ap.add_argument("--staging", default="cricket_sc")
    ap.add_argument("--load", action="store_true", help="source dumps into staging first")
    ap.add_argument("--apply", action="store_true", help="insert NEW rows into cricket_raw")
    ap.add_argument("--report", default=None, help="markdown report path")
    args = ap.parse_args()

    dump_dir = Path(args.dump_dir).resolve()
    files = sorted(dump_dir.glob("*.sql"))
    if not files:
        sys.exit(f"no .sql files in {dump_dir}")

    # 1. inspect (abort on anything destructive)
    inspections = [inspect_file(f) for f in files]
    bad = [i for i in inspections if i["forbidden"]]
    if bad:
        for i in bad:
            print(f"FORBIDDEN in {i['file']}: {i['forbidden']}")
        sys.exit("aborting — dump contains destructive statements")
    print("Inspection: no DROP/TRUNCATE/DELETE; CREATE+ALTER+INSERT only.")
    for i in inspections:
        print(f"  {i['file']:40s} alias=`{i['alias']}` tuples~{i['tuple_lines']}")

    # 2. load
    if args.load:
        client = find_client()
        print(f"\nLoading into staging `{args.staging}` with {client}")
        for f, i in zip(files, inspections):
            load_into_staging(client, args.staging, f, i["alias"])
            print(f"  loaded {f.name} -> {args.staging}.{i['alias']}")

    # 3. compare (+ 4. apply)
    con = connect()
    results = []
    try:
        with con.cursor() as cur:
            for i in inspections:
                info = compare_table(cur, args.staging, i["alias"], i["target_table"])
                if args.apply:
                    info["inserted"] = apply_insert(cur, args.staging, info)
                    cur.execute(f"SELECT COUNT(*) FROM `cricket_raw`.`{info['table']}`")
                    info["raw_rows_after"] = cur.fetchone()[0]
                    expected = info["raw_rows_before"] + info["new"]
                    if info["inserted"] != info["new"] or info["raw_rows_after"] != expected:
                        con.rollback()
                        sys.exit(f"{info['table']}: inserted {info['inserted']} != new "
                                 f"{info['new']} or after {info['raw_rows_after']} != "
                                 f"{expected} — ROLLED BACK")
                results.append(info)
            if args.apply:
                con.commit()
                print("\nAll inserts committed.")
    finally:
        con.close()

    out_md = Path(args.report) if args.report else \
        PROJECT_ROOT / "docs" / "ingest" / f"{dump_dir.name}_merge_report.md"
    out_json = out_md.with_suffix(".json")
    write_report(out_md, out_json, dump_dir, args.staging, inspections, results, args.apply)


if __name__ == "__main__":
    main()
