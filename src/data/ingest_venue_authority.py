"""
ingest_venue_authority.py — iteration 3: the editor's venues file becomes
the AUTHORITATIVE home-grounds source (bridge_entity-style).

Source: docs/Franchise_Cricket_Venues.xlsx (the editor's resolution of the
home-grounds review). Two sheets:

  "Common Venues"  — leagues with NO team home grounds: matches rotate
                     across shared venues (columns = league display names,
                     rows = the league's regular grounds). For these
                     leagues EVERY home-ground derivation is rejected:
                     home-advantage prose is never allowed for any team.
                     The listed venues may be referenced as the league's
                     regular grounds (fixture context only: "at one of the
                     league's home venues"), never as a team's advantage.

  "Sheet1"         — the per-team review rows (same schema as
                     docs/home-grounds-review.csv). human_decision, when
                     filled, is AUTHORITATIVE per team:
                         confirm                — derivation stands
                         reject                 — team gets no home ground
                         correct: <venue name>  — the real ground is <venue>
                     Empty human_decision -> the existing HIGH-confidence
                     gate stands (build_l2 home_ground: >=10 matches AND
                     >=30% share). IPL/BBL/CPL etc. remain derived.

Outputs (data/lake/l2/venue_authority/, read by src/content/payload.py):
  league_policy.parquet   league_key, policy ('shared_venues'|'derived')
  shared_venues.parquet   league_key, venue_name (as listed), venue_key
                          (resolved against L1 dim_venue where possible;
                          NULL when the ground has no dim_venue row yet)
  team_overrides.parquet  team_id, team_name, league_key, decision,
                          venue_name, venue_key (empty while the editor's
                          rows carry no human_decision)
  _manifest.json          source file, counts, unresolved names

Entity resolution is bridge_entity-style: names are matched against L1
dims via normalization + fuzzy ratio, never joined raw; every unresolved
name is reported, nothing is silently dropped.

This file is static editorial configuration (like bridge_entity): it has
no as_of_date and is applied identically to every match, so it cannot
leak future match OUTCOMES. tests/test_leakage.py gains a consistency
check that shared-league matches never surface an at_own_ground claim.

Run:
  venv/Scripts/python.exe -m src.data.ingest_venue_authority
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import duckdb
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
XLSX = ROOT / "docs" / "Franchise_Cricket_Venues.xlsx"
L1 = ROOT / "data" / "lake" / "l1"
OUT_DIR = ROOT / "data" / "lake" / "l2" / "venue_authority"

DIM_VENUE = (L1 / "dim_venue" / "dim_venue.parquet").as_posix()
DIM_TEAM = (L1 / "dim_team" / "dim_team.parquet").as_posix()
DIM_TOURNAMENT = (L1 / "dim_tournament" / "dim_tournament.parquet").as_posix()

# League display names in the Common Venues header -> dim_tournament
# league_key. Kept explicit (4 leagues) rather than fuzzy: a wrong league
# mapping would silently change home-advantage policy.
LEAGUE_DISPLAY_TO_KEY = {
    "pakistan super league": "pakistan super league",
    "lanka premier league": "lanka premier league",
    "major league cricket": "major league cricket",
    "bangladesh premier league": "bangladesh premier league",
}

FUZZY_ACCEPT = 0.80          # minimum ratio for a venue-name match


def _norm(s: str) -> str:
    """Lowercase, strip punctuation, collapse spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()


def _resolve_venue(name: str, venues: dict[str, str]) -> tuple[str | None, float]:
    """Best dim_venue venue_key for a listed name. Score = max of fuzzy
    ratio and a token-containment score (one name's tokens all inside the
    other's, e.g. 'Sinhalese Sports Club' inside 'SSC Cricket Ground
    (Sinhalese Sports Club)'). Tries the full name and the name with a
    trailing ', City' dropped."""
    candidates = [name]
    if "," in name:
        candidates.append(name.rsplit(",", 1)[0])
    best_key, best_score = None, 0.0
    for cand in candidates:
        n = _norm(cand)
        n_tok = set(n.split())
        for vkey, vname in venues.items():
            vn = _norm(vname)
            score = SequenceMatcher(None, n, vn).ratio()
            v_tok = set(vn.split())
            if n_tok and v_tok and (n_tok <= v_tok or v_tok <= n_tok):
                jac = len(n_tok & v_tok) / len(n_tok | v_tok)
                score = max(score, 0.85 + 0.15 * jac)
            if score > best_score:
                best_key, best_score = vkey, score
    return ((best_key, best_score) if best_score >= FUZZY_ACCEPT
            else (None, best_score))


def _resolve_team(name: str, teams: dict[int, str]) -> int | None:
    n = _norm(name)
    for tid, tname in teams.items():
        if _norm(tname) == n:
            return tid
    return None


def main() -> None:
    if not XLSX.exists():
        raise FileNotFoundError(f"editor's venues file not found: {XLSX}")

    con = duckdb.connect()
    venues = dict(con.execute(
        f"SELECT venue_key, venue_name FROM read_parquet('{DIM_VENUE}')").fetchall())
    teams = dict(con.execute(
        f"SELECT CAST(team_id AS BIGINT), team_name FROM read_parquet('{DIM_TEAM}')").fetchall())
    league_keys = {r[0] for r in con.execute(
        f"SELECT DISTINCT league_key FROM read_parquet('{DIM_TOURNAMENT}') "
        "WHERE league_key IS NOT NULL").fetchall()}

    wb = openpyxl.load_workbook(XLSX, data_only=True)

    # ---- Common Venues sheet -> shared-venue leagues --------------------
    ws = wb["Common Venues"]
    grid = [[c for c in row] for row in ws.iter_rows(values_only=True)]
    header, body = grid[0], grid[1:]
    shared_rows, unresolved_venues = [], []
    shared_league_keys = []
    for col, display in enumerate(header):
        if display is None:
            continue
        lk = LEAGUE_DISPLAY_TO_KEY.get(_norm(display))
        if lk is None:
            raise ValueError(f"unmapped league in Common Venues header: {display!r}")
        if lk not in league_keys:
            raise ValueError(f"league_key {lk!r} not present in dim_tournament")
        shared_league_keys.append(lk)
        for row in body:
            vname = row[col] if col < len(row) else None
            if not vname:
                continue
            vkey, ratio = _resolve_venue(str(vname), venues)
            if vkey is None:
                unresolved_venues.append((lk, str(vname), round(ratio, 2)))
            shared_rows.append({"league_key": lk, "venue_name": str(vname).strip(),
                                "venue_key": vkey,
                                "resolved_venue_name": venues.get(vkey),
                                "match_ratio": round(ratio, 3)})

    # ---- Sheet1 -> per-team decisions -----------------------------------
    ws1 = wb["Sheet1"]
    rows1 = list(ws1.iter_rows(values_only=True))
    cols = [str(c) for c in rows1[0]]
    idx = {c: i for i, c in enumerate(cols)}
    overrides, unresolved_teams, empty_decisions = [], [], 0
    for row in rows1[1:]:
        team_name = row[idx["team_name"]]
        league_key = row[idx["league_key"]]
        decision_raw = row[idx["human_decision"]]
        if team_name is None:
            continue
        decision_raw = ("" if decision_raw is None else str(decision_raw).strip())
        if not decision_raw:
            empty_decisions += 1        # existing high-confidence gate stands
            continue
        low = decision_raw.lower()
        if low == "confirm":
            decision, vname = "confirm", str(row[idx["proposed_home_venue"]])
        elif low == "reject":
            decision, vname = "reject", None
        elif low.startswith("correct"):
            decision = "correct"
            vname = decision_raw.split(":", 1)[1].strip() if ":" in decision_raw else None
            if not vname:
                raise ValueError(f"'correct' decision without a venue: {team_name}")
        else:
            raise ValueError(f"unknown human_decision {decision_raw!r} for {team_name}")
        team_id = _resolve_team(str(team_name), teams)
        if team_id is None:
            unresolved_teams.append(str(team_name))
        vkey = None
        if vname:
            vkey, _ = _resolve_venue(vname, venues)
        overrides.append({"team_id": team_id, "team_name": str(team_name),
                          "league_key": str(league_key), "decision": decision,
                          "venue_name": vname, "venue_key": vkey})

    # ---- league policy table -------------------------------------------
    policy_rows = [{"league_key": lk, "policy": "shared_venues",
                    "source": "Common Venues sheet"}
                   for lk in shared_league_keys]
    # every other league seen in the review universe stays derived (explicit
    # rows only for leagues the editor's file actually covers)
    sheet1_leagues = sorted({str(r[idx["league_key"]]) for r in rows1[1:]
                             if r[idx["league_key"]] is not None})
    for lk in sheet1_leagues:
        if lk not in shared_league_keys:
            policy_rows.append({"league_key": lk, "policy": "derived",
                                "source": "Sheet1 (empty human_decision -> "
                                          "high-confidence gate stands)"})

    # ---- write ----------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dfs = {
        "league_policy": pd.DataFrame(policy_rows),
        "shared_venues": pd.DataFrame(shared_rows),
        "team_overrides": pd.DataFrame(
            overrides, columns=["team_id", "team_name", "league_key",
                                "decision", "venue_name", "venue_key"]),
    }
    for name, df in dfs.items():
        out = (OUT_DIR / f"{name}.parquet").as_posix()
        con.register("_tmp", df)
        con.execute(f"COPY _tmp TO '{out}' (FORMAT PARQUET);")
        con.unregister("_tmp")
        print(f"wrote {name}: {len(df)} rows -> {out}")

    manifest = {
        "source": str(XLSX.relative_to(ROOT)),
        "ingested_at": datetime.now().isoformat(timespec="seconds"),
        "shared_venue_leagues": shared_league_keys,
        "derived_leagues_in_review": [lk for lk in sheet1_leagues
                                      if lk not in shared_league_keys],
        "sheet1_rows": len(rows1) - 1,
        "sheet1_empty_decisions": empty_decisions,
        "team_overrides": len(overrides),
        "unresolved_venue_names": [
            {"league_key": lk, "venue_name": v, "best_ratio": r}
            for lk, v, r in unresolved_venues],
        "unresolved_team_names": unresolved_teams,
        "policy_semantics": {
            "shared_venues": "reject ALL home-ground derivations; no "
                             "home-advantage prose ever; listed venues are "
                             "the league's regular grounds (fixture context "
                             "only)",
            "derived": "build_l2 home_ground HIGH-confidence gate stands "
                       "(>=10 matches AND >=30% share), unless a team "
                       "override says otherwise",
        },
    }
    (OUT_DIR / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("wrote _manifest.json")

    # ---- console report -------------------------------------------------
    print("\nSHARED-VENUE LEAGUES (no home-advantage prose ever):")
    for lk in shared_league_keys:
        vs = [r for r in shared_rows if r["league_key"] == lk]
        print(f"  {lk}:")
        for r in vs:
            tag = (f"-> {r['resolved_venue_name']}" if r["venue_key"]
                   else f"UNRESOLVED (best ratio {r['match_ratio']})")
            print(f"    {r['venue_name']:55s} {tag}")
    print(f"\nSheet1: {len(rows1) - 1} rows, {empty_decisions} empty "
          f"human_decision (high-confidence gate stands), "
          f"{len(overrides)} authoritative overrides ingested.")
    if unresolved_teams:
        print(f"UNRESOLVED team names: {unresolved_teams}")
    con.close()


if __name__ == "__main__":
    main()
