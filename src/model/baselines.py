"""
baselines.py - Phase 2 baseline predictors, scored through the walk-forward
validation harness (src/model/validation.py).

NO trained model here. These are simple rule-based bars the real model must
beat. Each matches the harness predictor contract:

    predictor(train_df, predict_df) -> np.ndarray of P(home win), one per row,
    using ONLY train_df and predict_df's NON-target features (never 'winner').

Baselines
---------
1) baseline_home_always     - constant = the past (train) home base rate (~0.53).
2) baseline_form_favourite  - favourite = better recent form (last5 win_pct;
                              tie -> tournament win_pct; tie -> home). Probability
                              scales with the win_pct gap: p = clip(0.5 + 0.30*gap,
                              0.20, 0.80). Works on ALL completed matches.
3) baseline_odds_favourite  - favourite = higher devig (lower odds) side, fixed
                              p=0.60/0.40. PRICED subset only (NaN elsewhere).
4) baseline_odds_devig_raw  - the market's implied prob directly: p = home_devig.
                              The HONEST BAR TO BEAT. PRICED subset only.

CAVEATS (surfaced in the report):
  * ODDS ORIENTATION (carried-forward Phase 2 task): L2 home_devig follows the
    ODDS-FEED home/away, not verified to match our assigned home_team. So #3/#4
    numbers are PROVISIONAL until the team-level odds bridge exists. (Sniff test:
    the higher-devig side wins ~70% of the time, which is what you'd expect if the
    orientation is mostly correct - but individual matches may be inverted.)
  * SMALL SAMPLE: only ~46 completed priced matches. Treat #3/#4 as DIRECTIONAL,
    not firm.

Run:
    venv/Scripts/python.exe -m src.model.baselines
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.model.validation import (
    load_completed, walk_forward, metrics, IPL, predict_always_half,
)


# --------------------------------------------------------------------------
# baseline predictors
# --------------------------------------------------------------------------
def baseline_home_always(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    """Constant = home base rate learned from PAST (train) matches only."""
    return np.full(len(current), float(train["y"].mean()))


def baseline_form_favourite(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    """Better recent form is favourite; probability scales with the win_pct gap."""
    h5 = current["home_win_pct_last5"].to_numpy(dtype=float)
    a5 = current["away_win_pct_last5"].to_numpy(dtype=float)
    ht = current["home_win_pct_tourn"].to_numpy(dtype=float)
    at = current["away_win_pct_tourn"].to_numpy(dtype=float)
    use_l5 = ~np.isnan(h5) & ~np.isnan(a5) & (h5 != a5)
    use_tn = ~np.isnan(ht) & ~np.isnan(at) & (ht != at)
    gap = np.where(use_l5, h5 - a5, np.where(use_tn, ht - at, 0.0))
    # gap in [-1,1]; tie (gap=0) -> p=0.5 -> harness predicts home (documented)
    return np.clip(0.5 + 0.30 * gap, 0.20, 0.80)


def baseline_odds_favourite(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    """Higher-devig (lower-odds) side is favourite, fixed p. NaN where unpriced."""
    hd = current["home_devig"].to_numpy(dtype=float)
    ad = current["away_devig"].to_numpy(dtype=float)
    both = ~np.isnan(hd) & ~np.isnan(ad)
    return np.where(both, np.where(hd >= ad, 0.60, 0.40), np.nan)


def baseline_odds_devig_raw(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    """Market implied prob directly. NaN where unpriced."""
    return current["home_devig"].to_numpy(dtype=float)


BASELINES = [
    ("home_always",        baseline_home_always,     "all"),
    ("form_favourite",     baseline_form_favourite,  "all"),
    ("odds_favourite",     baseline_odds_favourite,  "priced"),
    ("odds_devig_raw",     baseline_odds_devig_raw,  "priced"),
    ("always_half (ref)",  predict_always_half,      "all"),
]


# --------------------------------------------------------------------------
# scoring helpers
# --------------------------------------------------------------------------
def _m(sub: pd.DataFrame) -> dict:
    if len(sub) == 0:
        return {"n": 0, "accuracy": float("nan"), "log_loss": float("nan"),
                "brier": float("nan"), "base_rate": float("nan")}
    return metrics(sub["y"].values, sub["p"].values)


def _row(name: str, subset: str, m: dict, tag: str = "") -> str:
    return (f"  {name:20s} {subset:12s} n={m['n']:5d}  acc={m['accuracy']:.4f}  "
            f"log_loss={m['log_loss']:7.4f}  brier={m['brier']:.4f}{tag}")


def run_all(df: pd.DataFrame):
    priced_ids = set(df.loc[df["home_devig"].notna(), "match_id"])
    results = {}
    for name, pred, subset in BASELINES:
        oof, info = walk_forward(df, pred)
        oof = oof[oof["p"].notna()].copy()            # drop unpriced NaNs
        results[name] = (oof, info, subset)
    return results, priced_ids


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def per_league(oof: pd.DataFrame, min_n: int = 30) -> pd.DataFrame:
    recs = []
    for lk, g in oof.groupby("league_key"):
        if len(g) < min_n and lk != IPL:
            continue
        r = _m(g)
        r["league_key"] = lk
        recs.append(r)
    return (pd.DataFrame(recs).sort_values("n", ascending=False).reset_index(drop=True)
            if recs else pd.DataFrame())


def _print_per_league(name: str, oof: pd.DataFrame):
    tbl = per_league(oof)
    print(f"\n  per-league: {name}  (eval n>=30, IPL always shown)")
    print(f"    {'league_key':30s} {'n':>5s} {'acc':>7s} {'logloss':>8s} {'brier':>7s}")
    print("    " + "-" * 62)
    for r in tbl.itertuples():
        tag = "  <<< IPL" if r.league_key == IPL else ""
        print(f"    {str(r.league_key)[:30]:30s} {r.n:5d} {r.accuracy:7.4f} "
              f"{r.log_loss:8.4f} {r.brier:7.4f}{tag}")


def main():
    df = load_completed()
    results, priced_ids = run_all(df)
    n_priced_total = len(priced_ids)

    print("=" * 82)
    print("PHASE 2 BASELINES - scored through walk-forward harness (no trained model)")
    print("=" * 82)
    print(f"  completed matches with target: {len(df)}   "
          f"home base_rate: {df['y'].mean():.4f}")
    print(f"  priced subset (home_devig present, completed): {n_priced_total} matches")
    print("\n  CAVEATS:")
    print("   * ODDS ORIENTATION (Phase 2 task): home_devig follows the ODDS-FEED")
    print("     home/away, NOT verified vs our home_team. #3/#4 are PROVISIONAL.")
    print("   * SMALL SAMPLE: priced subset is tiny - treat #3/#4 as DIRECTIONAL.")

    # ---- Table 1: FULL-SAMPLE overall (all-completed predictors) ----
    print("\n" + "=" * 82)
    print("TABLE 1 - FULL SAMPLE overall (every completed match)")
    print("=" * 82)
    for name in ("home_always", "form_favourite", "always_half (ref)"):
        oof, info, _ = results[name]
        print(_row(name, "all", _m(oof)))
    print(f"\n  (evaluated {results['home_always'][1]['evaluated']} matches; "
          f"skipped {results['home_always'][1]['skipped_insufficient_history']} "
          f"for insufficient history; min_train="
          f"{results['home_always'][1]['min_train']})")

    # ---- Table 2: per-league for the two real full-sample baselines ----
    print("\n" + "=" * 82)
    print("TABLE 2 - FULL SAMPLE per league_key")
    print("=" * 82)
    _print_per_league("form_favourite", results["form_favourite"][0])
    _print_per_league("home_always", results["home_always"][0])

    # ---- Table 3: PRICED subset - the honest-bar comparison ----
    print("\n" + "=" * 82)
    print(f"TABLE 3 - PRICED SUBSET (~{n_priced_total} matches, SMALL/DIRECTIONAL)")
    print("  All predictors restricted to the SAME priced matches (apples-to-apples).")
    print("  odds_devig_raw = the market's own probability = the HONEST BAR TO BEAT.")
    print("=" * 82)
    for name, _, _subset in BASELINES:
        oof = results[name][0]
        sub = oof[oof["match_id"].isin(priced_ids)]
        tag = "   <- market bar" if name == "odds_devig_raw" else ""
        print(_row(name, "priced", _m(sub), tag))
    # priced-IPL (very thin) note
    ipl_priced = results["odds_devig_raw"][0]
    ipl_priced = ipl_priced[(ipl_priced["match_id"].isin(priced_ids)) &
                            (ipl_priced["league_key"] == IPL)]
    print(f"\n  (priced-IPL subset is only n={len(ipl_priced)} - far too small to report)")

    print("\n" + "=" * 82)
    print("READING IT: form_favourite is the bar for the FULL sample; odds_devig_raw")
    print("is the bar on the priced subset. A real model must beat form_favourite")
    print("overall AND approach/beat odds_devig_raw where the market exists.")
    print("Odds numbers stay PROVISIONAL until the team-level odds bridge is built.")


if __name__ == "__main__":
    main()
