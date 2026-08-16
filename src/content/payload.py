"""
payload.py - Phase 3, step 1: PREDICTION PAYLOAD assembler.

build_payload(match_id) -> JSON-serializable dict for ONE match, pulled ONLY
from existing layers: the L3 feature row, the v2 model prediction, and the
framing layer. THE WALL: this payload is the only thing the LLM article
generator will ever see. Nothing invented, nothing estimated ad hoc - a
missing value is null and its completeness flag is false.

Prediction rule (works for BOTH completed and upcoming matches):
    train = all completed matches with match_date STRICTLY BEFORE the target
    match's date (same anti-leakage rule as the harness; for an upcoming
    match this is simply "all completed so far"). If history < MIN_TRAIN
    (100), the prediction block is null and prediction_available = false.
    Note: for completed matches this is slightly better-informed than the
    harness's monthly-block OOF (train cuts at the match date, not the month
    start) - same rule, finer cut - so a demo match's band can occasionally
    differ from its OOF band.

The payload deliberately EXCLUDES the actual result even for completed
matches: the generator must never see outcomes.

DEMO:
    venv/Scripts/python.exe -m src.content.payload
prints three sample payloads (confident / moderate / close_call, the
close_call from IPL where possible) + the historical band distribution over
all walk-forward out-of-sample predictions.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src.content.framing import confidence_band, frame
from src.model.train_logistic import C_REG, predict_logistic
from src.model.validation import IPL, MIN_TRAIN, load_completed, walk_forward

ROOT = Path(__file__).resolve().parents[2]
L1 = ROOT / "data" / "lake" / "l1"
L2 = ROOT / "data" / "lake" / "l2"
L3_PATH = (ROOT / "data" / "lake" / "l3" / "feature_rows" / "feature_rows.parquet").as_posix()

# dim_match.result strings like "won by 24 runs" / "won by 6 wkts"
_MARGIN_RE = re.compile(r"by\s+(\d+)\s+(runs?|wkts?|wickets?)", re.IGNORECASE)

MODEL_VERSION = f"logistic_v2_C{C_REG:g}"          # -> "logistic_v2_C0.01"

PHASE_METRICS = ["rr_powerplay", "rr_middle", "rr_death",
                 "econ_powerplay", "econ_middle", "econ_death"]

# ---- lazy module caches (demo builds several payloads) -------------------
_CACHE: dict = {}


def _tables():
    if "l3" not in _CACHE:
        con = duckdb.connect()
        _CACHE["l3"] = con.execute(
            f"SELECT * FROM read_parquet('{L3_PATH}')").df()
        _CACHE["l3"]["match_date"] = pd.to_datetime(_CACHE["l3"]["match_date"])
        _CACHE["team"] = dict(con.execute(f"""
            SELECT CAST(team_id AS BIGINT), team_name
            FROM read_parquet('{(L1/'dim_team'/'dim_team.parquet').as_posix()}')
        """).fetchall())
        _CACHE["venue"] = dict(con.execute(f"""
            SELECT venue_key, venue_name
            FROM read_parquet('{(L1/'dim_venue'/'dim_venue.parquet').as_posix()}')
        """).fetchall())
        _CACHE["tourn"] = dict(con.execute(f"""
            SELECT CAST(tournament_id AS BIGINT), tournament_name
            FROM read_parquet('{(L1/'dim_tournament'/'dim_tournament.parquet').as_posix()}')
        """).fetchall())
        _CACHE["train"] = load_completed()
        # iteration-2 content-layer tables
        _CACHE["player_form"] = con.execute(f"""
            SELECT * FROM read_parquet(
                '{(L2/'player_form'/'player_form.parquet').as_posix()}')
        """).df()
        _CACHE["standings"] = con.execute(f"""
            SELECT * FROM read_parquet(
                '{(L2/'standings'/'standings.parquet').as_posix()}')
        """).df()
        _CACHE["standings"]["as_of_date"] = pd.to_datetime(
            _CACHE["standings"]["as_of_date"])
        _CACHE["tf_event"] = con.execute(f"""
            SELECT match_id, team_id, matches_in_window, win_pct, avg_margin
            FROM read_parquet(
                '{(L2/'team_form'/'team_form.parquet').as_posix()}')
            WHERE "window" = 'current_event'
        """).df()
        _CACHE["home_ground"] = con.execute(f"""
            SELECT match_id, team_id, league_matches_before, at_venue_before,
                   is_home_ground
            FROM read_parquet(
                '{(L2/'home_ground'/'home_ground.parquet').as_posix()}')
        """).df()
        _CACHE["venue_n"] = con.execute(f"""
            SELECT venue_key, as_of_date, matches_at_venue
            FROM read_parquet(
                '{(L2/'venue_stats'/'venue_stats.parquet').as_posix()}')
        """).df()
        _CACHE["venue_n"]["as_of_date"] = pd.to_datetime(
            _CACHE["venue_n"]["as_of_date"])
        _CACHE["dim_match"] = con.execute(f"""
            SELECT CAST(match_id AS BIGINT)      AS match_id,
                   CAST(tournament_id AS BIGINT) AS tournament_id,
                   CAST(team_a_id AS BIGINT)     AS team_a_id,
                   CAST(team_b_id AS BIGINT)     AS team_b_id,
                   CAST(start_at AS DATE)        AS match_date,
                   start_at, winner, result, result_type
            FROM read_parquet(
                '{(L1/'dim_match'/'dim_match.parquet').as_posix()}')
        """).df()
        _CACHE["dim_match"]["match_date"] = pd.to_datetime(
            _CACHE["dim_match"]["match_date"])
        con.close()
    return _CACHE


# ---- null-safe converters (numpy/pandas -> plain JSON types) -------------
def _f(v, nd=4):
    """float or None (NaN/NA -> None)."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    return round(float(v), nd)


def _i(v):
    if v is None or pd.isna(v):
        return None
    return int(v)


def _s(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    return str(v)


def _form_side(row: pd.Series, side: str, event: dict) -> dict:
    """Form block for one side. last5/tournament come from the L3 row (the
    model's own features); current_event ("this season/tour so far") comes
    from L2 team_form and is content-layer only."""
    phase = {m: _f(row.get(f"{side}_{m}_last5")) for m in PHASE_METRICS}
    return {
        "win_pct": {"last5": _f(row.get(f"{side}_win_pct_last5")),
                    "tournament": _f(row.get(f"{side}_win_pct_tourn")),
                    "current_event": event.get("win_pct")},
        "avg_margin": {"last5": _f(row.get(f"{side}_avg_margin_last5")),
                       "tournament": _f(row.get(f"{side}_avg_margin_tourn")),
                       "current_event": event.get("avg_margin")},
        "matches_in_window": {
            "last5": _i(row.get(f"{side}_matches_in_window_last5")),
            "tournament": _i(row.get(f"{side}_matches_in_window_tourn")),
            "current_event": event.get("matches_in_window")},
        "phase_rates_last5": phase,
    }


def _event_form(t: dict, match_id: int, team_id: int | None) -> dict:
    """current_event window row from L2 team_form (empty dict -> nulls)."""
    if team_id is None:
        return {}
    tf = t["tf_event"]
    hit = tf[(tf["match_id"] == match_id) & (tf["team_id"] == team_id)]
    if hit.empty:
        return {}
    r = hit.iloc[0]
    n = _i(r["matches_in_window"])
    if not n:
        return {}
    return {"win_pct": _f(r["win_pct"]), "avg_margin": _f(r["avg_margin"]),
            "matches_in_window": n}


# ---- iteration-2 blocks: players / standings / match context -------------
def _player_side(t: dict, match_id: int, team_id: int | None) -> dict | None:
    """Top 3 batters (by runs) + top 3 bowlers (by wickets, tie-break
    economy) for one team, from L2 player_form. Window selection: prefer
    current_event ("this tour so far") when the event has history for the
    team, else last5. Stats are the selected window's."""
    if team_id is None:
        return None
    pf = t["player_form"]
    mine = pf[(pf["match_id"] == match_id) & (pf["team_id"] == team_id)]
    if mine.empty:
        return None
    window = ("current_event" if (mine["window"] == "current_event").any()
              else "last5")
    w = mine[mine["window"] == window]

    bats = w[(w["bat_innings"].fillna(0) > 0) & w["bat_runs"].notna()]
    bats = bats.sort_values(["bat_runs", "strike_rate"],
                            ascending=[False, False]).head(3)
    top_batters = [{
        "name": _s(r["player_name"]),
        "runs": _i(r["bat_runs"]),
        "balls": _i(r["bat_balls"]),
        "innings": _i(r["bat_innings"]),
        "strike_rate": _f(r["strike_rate"], 1),
    } for _, r in bats.iterrows()]

    bowls = w[(w["bowl_innings"].fillna(0) > 0) & w["wickets"].notna()]
    bowls = bowls.sort_values(["wickets", "economy"],
                              ascending=[False, True]).head(3)
    top_bowlers = [{
        "name": _s(r["player_name"]),
        "wickets": _i(r["wickets"]),
        "overs": _f(r["overs"], 1),
        "economy": _f(r["economy"], 2),
        "innings_bowled": _i(r["bowl_innings"]),
    } for _, r in bowls.iterrows()]

    if not top_batters and not top_bowlers:
        return None
    return {"stats_window": window, "top_batters": top_batters,
            "top_bowlers": top_bowlers}


def _standings_block(t: dict, row: pd.Series) -> dict | None:
    """Point-in-time standings (strictly before match date = through the day
    before) for league events (3+ teams). None for bilateral series."""
    st = t["standings"]
    tid = _i(row["tournament_id"])
    hit = st[(st["tournament_id"] == tid)
             & (st["as_of_date"] == row["match_date"])]
    if hit.empty or int(hit.iloc[0]["n_teams_in_event"]) < 3:
        return None

    def side(team_id):
        r = hit[hit["team_id"] == team_id]
        if r.empty:
            return None
        r = r.iloc[0]
        return {"position": _i(r["position"]), "points": _i(r["points"]),
                "played": _i(r["played"]), "won": _i(r["won"]),
                "lost": _i(r["lost"])}

    home, away = side(_i(row["home_team_id"])), side(_i(row["away_team_id"]))
    if home is None and away is None:
        return None
    return {
        "n_teams_in_event": int(hit.iloc[0]["n_teams_in_event"]),
        "teams_with_results": int(len(hit)),   # >=1 decided match so far
        "home": home,
        "away": away,
        "note": "derived from decided matches only; points = two per win; "
                "when teams are level on points the listed order is "
                "approximate - describe them as level, never explain "
                "the tie-break",
    }


def _parse_margin(result, result_type) -> tuple[int | None, str | None]:
    if result_type == "tie_breaker":
        return None, "super_over"
    if isinstance(result, str):
        m = _MARGIN_RE.search(result)
        if m:
            unit = "runs" if m.group(2).lower().startswith("run") else "wickets"
            return int(m.group(1)), unit
    return None, None


def _last5_results(t: dict, team_id: int | None, before: pd.Timestamp,
                   teams: dict) -> list[dict]:
    """The window matches behind form.last5, as tellable facts: opponent,
    won/lost, margin (parsed from the official result string)."""
    if team_id is None:
        return []
    dm = t["dim_match"]
    mine = dm[((dm["team_a_id"] == team_id) | (dm["team_b_id"] == team_id))
              & dm["winner"].isin(["a", "b"])
              & (dm["match_date"] < before)]
    mine = mine.sort_values(["match_date", "match_id"],
                            ascending=[False, False]).head(5)
    out = []
    for _, r in mine.iterrows():
        is_a = r["team_a_id"] == team_id
        opp_id = _i(r["team_b_id"] if is_a else r["team_a_id"])
        won = (r["winner"] == "a") == is_a
        margin, margin_type = _parse_margin(r["result"], r["result_type"])
        out.append({"opponent": teams.get(opp_id), "won": bool(won),
                    "margin": margin, "margin_type": margin_type})
    return out


def _venue_ownership(t: dict, match_id: int, home_id, away_id) -> dict:
    """Whose ground is this actually? From L2 home_ground (point-in-time,
    HIGH-confidence gate: >=10 prior same-league matches at the venue AND
    >=30% share; medium derivations await the editor's home-grounds review).
    null side = no league history to judge from."""
    hg = t["home_ground"]

    def side(team_id):
        if team_id is None:
            return None
        r = hg[(hg["match_id"] == match_id) & (hg["team_id"] == team_id)]
        if r.empty or not _i(r.iloc[0]["league_matches_before"]):
            return None
        r = r.iloc[0]
        return {"at_own_ground": bool(r["is_home_ground"]),
                "team_matches_at_this_venue": _i(r["at_venue_before"]),
                "league_matches_total": _i(r["league_matches_before"])}

    return {"home_team": side(home_id), "away_team": side(away_id)}


def _match_context(t: dict, row: pd.Series, teams: dict) -> dict:
    """Schedule-derived context: Nth match of the event, series game number
    for the pair. Schedule facts (start times) are known pre-match, so no
    leakage; last5_results applies the strictly-before rule."""
    dm = t["dim_match"]
    tid = _i(row["tournament_id"])
    match_id = _i(row["match_id"])
    home_id, away_id = _i(row["home_team_id"]), _i(row["away_team_id"])

    ev = dm[dm["tournament_id"] == tid].sort_values(["start_at", "match_id"])
    ev_ids = ev["match_id"].tolist()
    match_no = ev_ids.index(match_id) + 1 if match_id in ev_ids else None

    pair = ev[((ev["team_a_id"] == home_id) & (ev["team_b_id"] == away_id))
              | ((ev["team_a_id"] == away_id) & (ev["team_b_id"] == home_id))]
    pair_ids = pair["match_id"].tolist()
    pair_no = pair_ids.index(match_id) + 1 if match_id in pair_ids else None

    return {
        "match_number_in_event": match_no,
        "total_scheduled_in_event": int(len(ev)),
        "pair_meeting_number_in_event": pair_no,
        "pair_total_scheduled_in_event": int(len(pair)),
        "last5_results": {
            "home": _last5_results(t, home_id, row["match_date"], teams),
            "away": _last5_results(t, away_id, row["match_date"], teams),
        },
    }


# ---- the assembler -------------------------------------------------------
def build_payload(match_id: int) -> dict:
    t = _tables()
    l3, teams, venues, tourns, train_all = (
        t["l3"], t["team"], t["venue"], t["tourn"], t["train"])

    hit = l3[l3["match_id"] == match_id]
    if hit.empty:
        raise KeyError(f"match_id {match_id} not found in L3")
    row = hit.iloc[0]

    # ---- prediction: train strictly before this match's date ----
    train = train_all[train_all["match_date"] < row["match_date"]]
    p_home = None
    if len(train) >= MIN_TRAIN:
        p_home = float(predict_logistic(train, hit)[0])

    home_name = teams.get(_i(row["home_team_id"]))
    away_name = teams.get(_i(row["away_team_id"]))

    if p_home is not None:
        fr = frame(p_home)
        prediction = {
            "p_home": _f(p_home),
            "p_away": _f(1.0 - p_home),
            "predicted_winner": fr["predicted_winner"],
            "confidence_band": fr["confidence_band"],
            "model_version": MODEL_VERSION,
        }
        display = {
            "probability_pct": int(round(fr["p_max"] * 100)),
            "predicted_winner_name": (home_name if fr["predicted_winner"] == "home"
                                      else away_name),
            "framing_note": fr["confidence_band"],
        }
    else:
        prediction = {"p_home": None, "p_away": None, "predicted_winner": None,
                      "confidence_band": None, "model_version": MODEL_VERSION}
        display = {"probability_pct": None, "predicted_winner_name": None,
                   "framing_note": None}

    # ---- completeness flags ----
    phase_ok = all(not pd.isna(row.get(f"{s}_{m}_last5"))
                   for s in ("home", "away") for m in PHASE_METRICS)
    odds_ok = not pd.isna(row.get("home_devig"))
    toss_ok = not pd.isna(row.get("toss_winner"))

    market = None
    if odds_ok:
        market = {
            "home_devig": _f(row["home_devig"]),
            "away_devig": _f(row["away_devig"]),
            "orientation_unverified": True,   # carried caveat: odds-feed
            "note": "devig follows the odds-feed home/away; alignment to our "
                    "home_team is not yet verified (Phase 2 odds-bridge task)",
        }

    toss_winner_id = _i(row.get("toss_winner"))

    # iteration-2 blocks
    home_id, away_id = _i(row["home_team_id"]), _i(row["away_team_id"])
    players = {"home": _player_side(t, match_id, home_id),
               "away": _player_side(t, match_id, away_id)}
    standings = _standings_block(t, row)
    match_context = _match_context(t, row, teams)
    venue_ownership = _venue_ownership(t, match_id, home_id, away_id)

    vn = t["venue_n"]
    vhit = vn[(vn["venue_key"] == row["venue_key"])
              & (vn["as_of_date"] == row["match_date"])]
    venue_sample = _i(vhit.iloc[0]["matches_at_venue"]) if len(vhit) else None

    payload = {
        "match": {
            "match_id": _i(row["match_id"]),
            "date": str(pd.Timestamp(row["match_date"]).date()),
            "league_key": _s(row["league_key"]),
            "tournament": tourns.get(_i(row["tournament_id"])),
            "venue": venues.get(row["venue_key"]),
            "day_night": _s(row["day_night"]),
            "is_neutral_venue": _i(row["is_neutral_venue"]),
            "home_team": home_name,
            "away_team": away_name,
        },
        "prediction": prediction,
        "display": display,
        "form": {"home": _form_side(row, "home",
                                    _event_form(t, match_id, home_id)),
                 "away": _form_side(row, "away",
                                    _event_form(t, match_id, away_id))},
        "players": players,                           # null side = no data
        "standings": standings,                       # null = bilateral/no data
        "match_context": match_context,
        "venue_stats": {
            "avg_first_innings": _f(row.get("venue_avg_first_innings"), 1),
            "batfirst_win_pct": _f(row.get("venue_batfirst_win_pct")),
            "chase_win_pct": _f(row.get("venue_chase_win_pct")),
            "matches_at_venue_total": venue_sample,   # cite with any venue pct
        },
        "venue_ownership": venue_ownership,
        "conditions": {
            "toss": ({"winner_team": teams.get(toss_winner_id),
                      "decision": _s(row.get("toss_decision"))}
                     if toss_ok else None),           # NULL pre-toss (lifecycle)
            "dew_flag": _i(row.get("dew_flag")),
            "day_night": _s(row["day_night"]),
        },
        "market": market,                             # null unless priced
        "meta": {
            "as_of_date": str(pd.Timestamp(row["as_of_date"]).date()),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "is_completed_match": bool(row["is_completed"]),
            "data_completeness": {
                "prediction_available": p_home is not None,
                "phase_data_available": bool(phase_ok),
                "odds_available": bool(odds_ok),
                "toss_known": bool(toss_ok),
                "players_available": bool(players["home"] and players["away"]),
                "standings_available": standings is not None,
            },
        },
    }
    return payload


# ---- demo ----------------------------------------------------------------
def _band_distribution(oof: pd.DataFrame) -> None:
    p = oof["p"].to_numpy(dtype=float)
    y = oof["y"].to_numpy(dtype=float)
    p_max = np.maximum(p, 1 - p)
    bands = np.array([confidence_band(v) for v in p_max])
    hit = ((p >= 0.5) == (y == 1))                    # predicted side won
    print("\n" + "=" * 70)
    print(f"BAND DISTRIBUTION - all walk-forward OOS predictions (n={len(p)})")
    print("=" * 70)
    print(f"  {'band':12s} {'n':>6s} {'share':>7s} {'acc_in_band':>12s}")
    print("  " + "-" * 42)
    for b in ("confident", "moderate", "close_call"):
        m = bands == b
        share = 100.0 * m.sum() / len(p)
        acc = 100.0 * hit[m].mean() if m.sum() else float("nan")
        print(f"  {b:12s} {int(m.sum()):6d} {share:6.1f}% {acc:11.1f}%")


def _pick_demo_matches(oof: pd.DataFrame) -> dict:
    """One match per band; close_call from IPL if possible. Verified against
    the payload's own (finer-cut) prediction so demo bands are consistent."""
    p_max = np.maximum(oof["p"], 1 - oof["p"])
    oof = oof.assign(band=[confidence_band(v) for v in p_max])
    picks = {}
    for band in ("confident", "moderate", "close_call"):
        cands = oof[oof["band"] == band]
        if band == "close_call":
            ipl = cands[cands["league_key"] == IPL]
            cands = ipl if len(ipl) else cands
        for _, c in cands.sort_values("match_date", ascending=False).iterrows():
            pl = build_payload(int(c["match_id"]))
            if pl["prediction"]["confidence_band"] == band:
                picks[band] = pl
                break
    return picks


def main() -> None:
    df = load_completed()
    print(f"Building v2 walk-forward predictions for band stats "
          f"({len(df)} completed matches) ...")
    oof, _info = walk_forward(df, predict_logistic)

    _band_distribution(oof)

    print("\nSelecting demo matches (payload band verified) ...")
    picks = _pick_demo_matches(oof)
    for band, pl in picks.items():
        print("\n" + "=" * 70)
        print(f"SAMPLE PAYLOAD - {band.upper()}"
              + ("  (IPL)" if pl["match"]["league_key"] == IPL else ""))
        print("=" * 70)
        print(json.dumps(pl, indent=2))


if __name__ == "__main__":
    main()
