"""entity_watch.py — bridge-style review of entities ENTERING L1 after a
rebuild (new teams / venues / tournaments), for human review before commit.

Compares a snapshot of the previous L1 dims (copied before the rebuild) with
the current data/lake/l1 and reports, in bridge_entity spirit (nothing merged
or dropped automatically; every candidate is listed with evidence):

  * new teams          — id, name, key, gender (from their matches), national
                         flag, in-scope matches, dedupe status (canonical /
                         duplicates remapped into it), and POSSIBLE duplicates:
                         other L1 teams whose normalized name matches once
                         "women/w" and the club prefix are stripped
                         (e.g. "Scorchers Women" vs "Perth Scorchers Women").
  * new venues         — key, name, city, country, matches, revise_l1 merge
                         status (remapped into / canonical).
  * new tournaments    — id, name, league_key, gender, dates, matches,
                         completed; plus tournament ids present in dim_match
                         but ABSENT from dim_tournament (missing source row).
  * league_key groups  — every league_key whose members' names mention the
                         watched leagues (WBBL / Big Bash / Spring Challenge)
                         so season grouping can be eyeballed.
  * match deltas       — by gender and status.

Usage:
  python -m src.data.entity_watch --before <dir with previous dim_*.parquet> \
        [--out docs/ingest/entity_watch.md] [--watch "Big Bash,Spring Challenge"]
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
L1 = ROOT / "data" / "lake" / "l1"

DROP_TOKENS = {"cricket", "club", "cc", "the", "fc", "women", "womens", "w", "xi"}


def norm(s) -> str:
    if s is None:
        return ""
    s = re.sub(r"[^a-z0-9 ]", " ", str(s).lower())
    return " ".join(t for t in s.split() if t and t not in DROP_TOKENS)


def rp(path: Path) -> str:
    return f"read_parquet('{path.as_posix()}')"


def load(con, before: Path) -> dict:
    cur = {n: con.execute(f"SELECT * FROM {rp(L1 / n / f'{n}.parquet')}").df()
           for n in ("dim_team", "dim_venue", "dim_tournament", "dim_match",
                     "team_id_map", "venue_id_map")}
    prev = {}
    for n in ("dim_team", "dim_venue", "dim_tournament", "dim_match",
              "team_id_map", "venue_id_map"):
        f = before / f"{n}.parquet"
        prev[n] = con.execute(f"SELECT * FROM {rp(f)}").df() if f.exists() else None
    return {"cur": cur, "prev": prev}


def md_table(df: pd.DataFrame, cols: list[str] | None = None, limit: int = 400) -> list[str]:
    if df is None or df.empty:
        return ["(none)"]
    cols = cols or list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.head(limit).iterrows():
        out.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]).replace("|", "/")
                                     for c in cols) + " |")
    if len(df) > limit:
        out.append(f"| … {len(df) - limit} more rows … |" + " |" * (len(cols) - 1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="dir holding the previous dim_*.parquet")
    ap.add_argument("--out", default=str(ROOT / "docs" / "ingest" / "entity_watch.md"))
    ap.add_argument("--watch", default="Big Bash,Spring Challenge,WBBL")
    args = ap.parse_args()
    before = Path(args.before)
    watch = [w.strip().lower() for w in args.watch.split(",") if w.strip()]

    con = duckdb.connect()
    d = load(con, before)
    cur, prev = d["cur"], d["prev"]
    dm, dt, dv, dtr = cur["dim_match"], cur["dim_team"], cur["dim_venue"], cur["dim_tournament"]
    for df in (dm,):
        for c in ("match_id", "team_a_id", "team_b_id", "tournament_id"):
            df[c] = df[c].astype("int64")
    dt["team_id"] = dt["team_id"].astype("int64")
    dtr["tournament_id"] = dtr["tournament_id"].astype("int64")
    dm["match_date"] = pd.to_datetime(dm["start_at"]).dt.date

    lines = [f"# Entity watch — L1 rebuild ({datetime.now().isoformat(timespec='seconds')})",
             "", f"- previous dims: `{before}`", f"- current L1: `{L1}`",
             "- rule: nothing below was merged or dropped automatically; "
             "candidates are listed for a human decision (bridge_entity style).", ""]

    # ---------------- match deltas ----------------
    lines += ["## 0. Match deltas (dim_match)", ""]
    g_cur = dm.groupby("gender").agg(matches=("match_id", "size"),
                                     completed=("is_completed", "sum")).reset_index()
    if prev["dim_match"] is not None:
        pm = prev["dim_match"]
        g_prev = pm.groupby("gender").agg(matches_before=("match_id", "size"),
                                          completed_before=("is_completed", "sum")).reset_index()
        g_cur = g_cur.merge(g_prev, on="gender", how="left").fillna(0)
        for c in ("matches_before", "completed_before"):
            g_cur[c] = g_cur[c].astype(int)
        removed = set(pm["match_id"].astype("int64")) - set(dm["match_id"])
        lines += md_table(g_cur) + ["", f"- matches REMOVED vs before: {len(removed)}"
                                     + (f" -> {sorted(removed)[:30]}" if removed else "")]
    else:
        lines += md_table(g_cur)
    st = dm.groupby(["gender", "status"]).size().reset_index(name="n")
    lines += ["", "status by gender:", ""] + md_table(st) + [""]

    # ---------------- teams ----------------
    team_gender = pd.concat([
        dm[["team_a_id", "gender"]].rename(columns={"team_a_id": "team_id"}),
        dm[["team_b_id", "gender"]].rename(columns={"team_b_id": "team_id"})])
    tg = (team_gender.groupby("team_id")["gender"]
          .agg(lambda s: "/".join(sorted(set(s)))).rename("gender"))
    tn = team_gender.groupby("team_id").size().rename("matches")
    teams = dt.set_index("team_id").join(tg).join(tn).reset_index()
    tim = cur["team_id_map"].copy()
    tim["old_id"] = tim["old_id"].astype("int64")
    tim["canonical_id"] = tim["canonical_id"].astype("int64")
    dup_into = (tim[tim["is_remapped"]].groupby("canonical_id")["old_id"]
                .agg(lambda s: ",".join(map(str, sorted(s)))).rename("duplicate_ids_remapped_in"))
    teams = teams.set_index("team_id").join(dup_into).reset_index()
    teams["dedupe_status"] = teams["duplicate_ids_remapped_in"].map(
        lambda v: "canonical (absorbed duplicates)" if isinstance(v, str) else "canonical (single id)")

    prev_ids = set(prev["dim_team"]["team_id"].astype("int64")) if prev["dim_team"] is not None else set()
    new_teams = teams[~teams["team_id"].isin(prev_ids)].copy()

    # possible duplicates: same normalized name (women/w/club cruft stripped)
    teams["_n"] = teams["team_name"].map(norm)
    cand = []
    for _, r in new_teams.iterrows():
        n = norm(r["team_name"])
        toks = set(n.split())
        for _, o in teams[teams["team_id"] != r["team_id"]].iterrows():
            on = o["_n"]
            if not on or not n:
                continue
            otoks = set(on.split())
            if n == on or (toks < otoks or otoks < toks):
                cand.append({"new_team_id": r["team_id"], "new_team": r["team_name"],
                             "new_gender": r["gender"],
                             "candidate_id": o["team_id"], "candidate": o["team_name"],
                             "candidate_gender": o["gender"],
                             "candidate_matches": o["matches"],
                             "relation": "exact (women/w stripped)" if n == on else "token subset",
                             "same_gender": r["gender"] == o["gender"]})
    cand_df = pd.DataFrame(cand)

    lines += ["## 1. Teams", "",
              f"- dim_team rows: {len(prev_ids) or '?'} before -> {len(teams)} now; "
              f"NEW: {len(new_teams)}",
              f"- team_id_map: {len(tim)} scoped ids, {int(tim['is_remapped'].sum())} "
              f"duplicate ids remapped to a canonical id", "",
              "### 1a. New teams entering L1", ""]
    lines += md_table(new_teams.sort_values(["gender", "matches"], ascending=[True, False]),
                      ["team_id", "team_name", "team_key", "gender", "is_national",
                       "country_code", "matches", "dedupe_status", "duplicate_ids_remapped_in"])
    lines += ["", "### 1b. Possible duplicates for review (NOT merged): new team vs "
              "existing team with the same base name once women/w are stripped", ""]
    if cand_df.empty:
        lines += ["(none)"]
    else:
        same = cand_df[cand_df["same_gender"]].sort_values(["relation", "new_team"])
        cross = cand_df[~cand_df["same_gender"]]
        lines += [f"- same-gender candidates (two ids that MAY be one side): {len(same)} rows "
                  f"below; token-subset rows are mostly senior vs A / U19 / franchise vs state "
                  f"(distinct) — only 'exact' rows are likely duplicates",
                  f"- cross-gender pairs (men's club + its women's side, e.g. 'Perth Scorchers' "
                  f"vs 'Perth Scorchers Women'): {len(cross)} — expected, distinct teams, "
                  f"not listed", ""]
        lines += md_table(same.drop(columns=["same_gender"]))

    # ---- 1d. mechanical guard: no team_id_map merge may cross genders ----
    l0_path = (ROOT / "data" / "lake" / "l0" / "cricket__matches").as_posix()
    rawg = con.execute(f"""
        SELECT team_id, string_agg(gender, '/' ORDER BY gender) AS genders FROM (
            SELECT DISTINCT team_id, gender FROM (
                SELECT CAST(team_a AS BIGINT) AS team_id, gender
                FROM read_parquet('{l0_path}/*.parquet') WHERE format='t20'
                UNION ALL
                SELECT CAST(team_b AS BIGINT), gender
                FROM read_parquet('{l0_path}/*.parquet') WHERE format='t20'))
        GROUP BY team_id
    """).df().set_index("team_id")["genders"]
    merges = tim[tim["is_remapped"]].copy()
    merges["old_genders"] = merges["old_id"].map(rawg)
    merges["canonical_genders"] = merges["canonical_id"].map(rawg)
    names_all = dict(con.execute(f"""
        SELECT CAST(id AS BIGINT), name FROM read_parquet(
            '{(ROOT / 'data' / 'lake' / 'l0' / 'cricket__teams').as_posix()}/*.parquet')
    """).fetchall())
    merges["old_name"] = merges["old_id"].map(names_all)
    merges["canonical_name"] = merges["canonical_id"].map(names_all)
    cross_merge = merges[merges["old_genders"] != merges["canonical_genders"]]
    lines += ["", "### 1d. GUARD — team_id_map merges across genders (must be none; "
              "a women's side folded into a men's id, or vice versa)", ""]
    if cross_merge.empty:
        lines += [f"(none — all {len(merges)} remapped ids share the gender of their "
                  f"canonical id)"]
    else:
        lines += md_table(cross_merge, ["old_id", "old_name", "old_genders",
                                        "canonical_id", "canonical_name", "canonical_genders"])
    lines += ["", "All duplicate ids remapped (old -> canonical), with match genders:", ""]
    lines += md_table(merges.sort_values(["canonical_genders", "canonical_name"]),
                      ["old_id", "old_name", "old_genders", "canonical_id",
                       "canonical_name", "canonical_genders"])

    # watched teams (Spring Challenge / WBBL clubs)
    wbbl_ids = sorted(set(dm[dm["tournament_id"].isin(
        dtr[dtr["tournament_name"].str.lower().str.contains("big bash|spring challenge", na=False)
            & (dtr["gender"] == "female")]["tournament_id"])]
        [["team_a_id", "team_b_id"]].values.ravel()))
    wt = teams[teams["team_id"].isin(wbbl_ids)]
    lines += ["", "### 1c. Women's Big Bash / Spring Challenge teams (dedupe status)", ""]
    lines += md_table(wt.sort_values("team_name"),
                      ["team_id", "team_name", "team_key", "gender", "matches",
                       "dedupe_status", "duplicate_ids_remapped_in"])
    # also list OTHER women's teams whose names contain these club names
    clubs = ["sixers", "thunder", "stars", "renegades", "heat", "hurricanes",
             "scorchers", "strikers", "meteors"]
    pat = "|".join(clubs)
    look = teams[teams["team_name"].str.lower().str.contains(pat, na=False)
                 & (teams["gender"] == "female") & ~teams["team_id"].isin(wbbl_ids)]
    lines += ["", "Other women's teams carrying a BBL club word (sanity list; distinct "
              "teams unless 1b flags them):", ""]
    lines += md_table(look.sort_values("team_name"),
                      ["team_id", "team_name", "team_key", "matches"])

    # ---------------- venues ----------------
    vn = dm.groupby("venue_key").size().rename("matches")
    venues = dv.set_index("venue_key").join(vn).reset_index()
    vim = cur["venue_id_map"]
    merged_in = (vim[vim["is_remapped"]].groupby("canonical_key")["old_key"]
                 .agg(lambda s: ",".join(sorted(s))).rename("keys_merged_in"))
    venues = venues.set_index("venue_key").join(merged_in).reset_index()
    prev_v = set(prev["dim_venue"]["venue_key"]) if prev["dim_venue"] is not None else set()
    new_v = venues[~venues["venue_key"].isin(prev_v)]
    lines += ["", "## 2. Venues", "",
              f"- dim_venue rows: {len(prev_v) or '?'} before -> {len(venues)} now; "
              f"NEW canonical venues: {len(new_v)}",
              f"- venue_id_map: {len(vim)} keys, {int(vim['is_remapped'].sum())} merged "
              f"into a canonical key (revise_l1)", "",
              "### 2a. New venues entering L1", ""]
    lines += md_table(new_v.sort_values("matches", ascending=False),
                      ["venue_key", "venue_name", "city", "country_code", "matches",
                       "keys_merged_in"])
    # new keys that were merged away into an EXISTING venue
    new_merged_away = vim[vim["is_remapped"] & ~vim["old_key"].isin(prev_v)
                          & vim["canonical_key"].isin(prev_v)]
    lines += ["", "### 2b. New venue keys merged (by revise_l1) into an existing venue", ""]
    lines += md_table(new_merged_away.merge(dv, left_on="canonical_key", right_on="venue_key",
                                            how="left")[["old_key", "canonical_key",
                                                         "venue_name", "city"]])

    # ---------------- tournaments ----------------
    tm = dm.groupby("tournament_id").agg(matches=("match_id", "size"),
                                         completed=("is_completed", "sum"),
                                         first=("match_date", "min"),
                                         last=("match_date", "max"),
                                         genders=("gender", lambda s: "/".join(sorted(set(s)))))
    tours = dtr.set_index("tournament_id").join(tm).reset_index()
    prev_t = (set(prev["dim_tournament"]["tournament_id"].astype("int64"))
              if prev["dim_tournament"] is not None else set())
    new_t = tours[~tours["tournament_id"].isin(prev_t)]
    missing = sorted(set(dm["tournament_id"]) - set(dtr["tournament_id"]))
    lines += ["", "## 3. Tournaments", "",
              f"- dim_tournament rows: {len(prev_t) or '?'} before -> {len(tours)} now; "
              f"NEW: {len(new_t)}; league_keys: {tours['league_key'].nunique()}",
              f"- tournament ids in dim_match with NO dim_tournament row (missing from "
              f"cricket__tournaments; league_key NULL downstream): {missing or 'none'}"]
    for tid in missing:
        sub = dm[dm["tournament_id"] == tid]
        lines.append(f"  - {tid}: {len(sub)} matches, {int(sub['is_completed'].sum())} completed, "
                     f"{sub['match_date'].min()} .. {sub['match_date'].max()}, "
                     f"gender={'/'.join(sorted(set(sub['gender'])))}, "
                     f"e.g. '{sub.iloc[0]['match_name']}'")
    lines += ["", "### 3a. New tournaments entering L1", ""]
    lines += md_table(new_t.sort_values(["gender", "league_key", "start_date"]),
                      ["tournament_id", "tournament_name", "league_key", "gender",
                       "start_date", "matches", "completed", "first", "last"])

    lines += ["", "### 3b. league_key grouping for the watched leagues", ""]
    wmask = tours["tournament_name"].str.lower().apply(lambda n: any(w in n for w in watch))
    wmask |= tours["league_key"].fillna("").str.lower().apply(lambda n: any(w in n for w in watch))
    for lk, g in tours[wmask].groupby("league_key", dropna=False):
        lines.append(f"- league_key = `{lk}` ({g['gender'].iloc[0]}; {len(g)} tournament id(s), "
                     f"{int(g['matches'].fillna(0).sum())} matches)")
        for _, r in g.sort_values("start_date").iterrows():
            lines.append(f"    - {int(r['tournament_id'])}  {r['tournament_name']}  "
                         f"[{r['first']} .. {r['last']}]  {int(r['matches'] or 0)} matches, "
                         f"{int(r['completed'] or 0)} completed")
    lines += ["", "### 3c. league_keys shared by BOTH genders (should be none — "
              "women's leagues carry 'women' in the name)", ""]
    both = tours.groupby("league_key")["gender"].nunique()
    both = both[both > 1]
    if both.empty:
        lines.append("(none)")
    else:
        lines += md_table(tours[tours["league_key"].isin(both.index)].sort_values("league_key"),
                          ["league_key", "tournament_id", "tournament_name", "gender", "matches"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWritten: {out}")


if __name__ == "__main__":
    main()
