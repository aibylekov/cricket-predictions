"""
train_logistic.py - Phase 2, step 3: FIRST TRAINED MODEL (iteration 2).

Logistic regression (scikit-learn 1.9.0 - cp314 wheels installed fine, so no
fallback implementation was needed) on the MVP feature set from L3, scored
through the SAME walk-forward harness as the baselines (identical splits,
identical metrics). Reads L3 only; writes nothing.

Bar to beat: form_favourite (acc 0.5726 / log_loss 0.6888 / brier 0.2473);
IPL is the hard case (form there: 0.5185 acc / 0.7112 log_loss).

ITERATION 2 DECISIONS (locked in chat):
  1. C = 0.01 (strong L2, calibration-first): publishing strategy is
     confidence-based framing, so honest probabilities matter most -
     log_loss/brier are primary metrics, accuracy secondary. (C=1.0 was
     over-confident in the tails: 90-100% bucket predicted 0.95, won 0.50.)
  2. league_key one-hot: a league gets its own 0/1 column when it has
     >= LEAGUE_MIN_TRAIN (=50) completed matches IN THE TRAIN FOLD (learned
     per fold - no peeking); everything else falls in the implicit "other"
     bucket (all-zeros row, absorbed by the intercept). Unseen leagues at
     predict time are likewise "other".
  3. Form-gap features: home-away differences (gap_win_pct_last5/_tourn,
     gap_avg_margin_last5/_tourn) so the model starts from the baseline's
     signal and adds on top. (Margin gap computed for both windows; the
     spec left the margin window open - documented choice.)

FEATURES (MVP, home_/away_ blocks)
----------------------------------
  * win_pct + avg_margin        (last5 AND tournament windows)
  * form gaps (home - away)     (win_pct both windows, avg_margin both)
  * phase rates rr_pp/mid/death + econ_pp/mid/death  (last5 window)
  * venue_avg_first_innings, venue_batfirst_win_pct, venue_chase_win_pct
  * is_neutral_venue, day_night (as 0/1), dew_flag
  * matches_in_window (last5 + tournament) as reliability signals
  * league_key one-hot (>=50 train matches; else "other")
  * EXCLUDED by design: odds/devig columns (model must stay independent of
    the market for an honest comparison) and toss (NULL at prediction time
    for upcoming matches - lifecycle).

PREPROCESSING (inside the predictor, fit on TRAIN fold only - no peeking)
-------------------------------------------------------------------------
  * was_missing indicators for the phase-rate block, one per side
    (home_phase_missing / away_phase_missing): within a side the six phase
    columns are missing together (no ball data), so per-side flags capture
    it without 12 collinear columns. Missingness itself is informative.
  * NULLs imputed with TRAIN-fold means (win_pct NULLs carry no extra
    indicator: matches_in_window=0 already encodes "no history").
  * Standardized with TRAIN-fold mean/std (std==0 guarded to 1).
  * L2 regularization C=0.01 (lambda = 1/C = 100; adopted per decision #1).

INTERPRETABILITY
----------------
Walk-forward refits a model per monthly block (honest metrics). For the
coefficient report we fit ONE model on ALL completed data with the same
pipeline - interpretation only, never used for scoring.

Run:
    venv/Scripts/python.exe -m src.model.train_logistic
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.model.validation import (
    IPL, calibration, load_completed, metrics, predict_always_half, walk_forward,
)
from src.model.baselines import baseline_form_favourite

C_REG = 0.01         # strong L2 (lambda=100) - calibration-first, decision #1
MAX_ITER = 1000
LEAGUE_MIN_TRAIN = 50   # league gets a one-hot column at >=50 TRAIN-fold matches

# ---- feature lists -------------------------------------------------------
PHASE_METRICS = ["rr_powerplay", "rr_middle", "rr_death",
                 "econ_powerplay", "econ_middle", "econ_death"]

def _side_cols(s: str) -> list[str]:
    cols = [f"{s}_win_pct_last5", f"{s}_win_pct_tourn",
            f"{s}_avg_margin_last5", f"{s}_avg_margin_tourn",
            f"{s}_matches_in_window_last5", f"{s}_matches_in_window_tourn"]
    cols += [f"{s}_{m}_last5" for m in PHASE_METRICS]
    return cols

SIDE_COLS = _side_cols("home") + _side_cols("away")
VENUE_COLS = ["venue_avg_first_innings", "venue_batfirst_win_pct",
              "venue_chase_win_pct"]
PHASE_COLS = {s: [f"{s}_{m}_last5" for m in PHASE_METRICS]
              for s in ("home", "away")}
GAP_SPECS = [("gap_win_pct_last5",   "home_win_pct_last5",   "away_win_pct_last5"),
             ("gap_win_pct_tourn",   "home_win_pct_tourn",   "away_win_pct_tourn"),
             ("gap_avg_margin_last5", "home_avg_margin_last5", "away_avg_margin_last5"),
             ("gap_avg_margin_tourn", "home_avg_margin_tourn", "away_avg_margin_tourn")]

BASE_FEATURES = (SIDE_COLS + [g for g, _, _ in GAP_SPECS] + VENUE_COLS
                 + ["is_neutral_venue", "day_night_flag", "dew_flag",
                    "home_phase_missing", "away_phase_missing"])


def league_list(train: pd.DataFrame) -> list[str]:
    """Leagues earning a one-hot column, learned from the TRAIN fold only."""
    counts = train["league_key"].value_counts()
    return sorted(counts[counts >= LEAGUE_MIN_TRAIN].index.tolist())


def _slug(lk: str) -> str:
    return "lg_" + "".join(ch if ch.isalnum() else "_" for ch in str(lk))[:28]


# ---- design matrix -------------------------------------------------------
def design_matrix(df: pd.DataFrame, leagues: list[str]) -> pd.DataFrame:
    """Raw (un-imputed) feature frame incl. engineered 0/1 + league dummies."""
    X = pd.DataFrame(index=df.index)
    for c in SIDE_COLS + VENUE_COLS:
        X[c] = pd.to_numeric(df[c], errors="coerce")
    for gap, hc, ac in GAP_SPECS:
        X[gap] = X[hc] - X[ac]                       # NaN if either side NaN
    X["is_neutral_venue"] = pd.to_numeric(df["is_neutral_venue"],
                                          errors="coerce").fillna(0)
    X["day_night_flag"] = (df["day_night"] == "day_night").astype(float)
    X["dew_flag"] = pd.to_numeric(df["dew_flag"], errors="coerce").fillna(0)
    for s in ("home", "away"):
        X[f"{s}_phase_missing"] = df[PHASE_COLS[s]].isna().any(axis=1).astype(float)
    for lk in leagues:                               # "other" = all zeros
        X[_slug(lk)] = (df["league_key"] == lk).astype(float)
    return X[BASE_FEATURES + [_slug(lk) for lk in leagues]]


class _Prep:
    """Impute (train means) + standardize (train mean/std). Fit on train only."""

    def fit(self, X: pd.DataFrame) -> "_Prep":
        # .fillna(0.0) guards columns that are ALL-NaN in an early train fold
        # (e.g. venue_avg_first_innings before any ball data exists).
        self.impute_means = X.mean(axis=0).fillna(0.0)
        Xi = X.fillna(self.impute_means)
        self.mu = Xi.mean(axis=0)
        self.sd = Xi.std(axis=0, ddof=0).replace(0.0, 1.0).fillna(1.0)
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        Xi = X.fillna(self.impute_means)
        return ((Xi - self.mu) / self.sd).to_numpy(dtype=float)


def predict_logistic(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    """Harness predictor: fit on train fold, return P(home win) for current."""
    leagues = league_list(train)                     # learned from train only
    prep = _Prep().fit(design_matrix(train, leagues))
    Xtr = prep.transform(design_matrix(train, leagues))
    ytr = train["y"].to_numpy(dtype=int)
    if len(np.unique(ytr)) < 2:                      # degenerate early fold guard
        return np.full(len(current), float(ytr.mean()))
    clf = LogisticRegression(C=C_REG, max_iter=MAX_ITER)  # L2 is the default penalty
    clf.fit(Xtr, ytr)
    return clf.predict_proba(prep.transform(design_matrix(current, leagues)))[:, 1]


# ---- reporting -----------------------------------------------------------
def _m(sub: pd.DataFrame) -> dict:
    if len(sub) == 0:
        return {"n": 0, "accuracy": float("nan"), "log_loss": float("nan"),
                "brier": float("nan"), "base_rate": float("nan")}
    return metrics(sub["y"].values, sub["p"].values)


def _print_calibration(title: str, oof: pd.DataFrame) -> None:
    print(f"\n  CALIBRATION ({title}) - predicted-avg vs actual per decile:")
    cal = calibration(oof["y"].values, oof["p"].values)
    print(f"    {'bucket':10s} {'count':>6s} {'pred_avg':>9s} {'actual':>9s}")
    print("    " + "-" * 38)
    for r in cal.itertuples():
        pa = "  -  " if np.isnan(r.pred_avg) else f"{r.pred_avg:.4f}"
        aw = "  -  " if np.isnan(r.actual_win_rate) else f"{r.actual_win_rate:.4f}"
        print(f"    {r.bucket:10s} {r.count:6d} {pa:>9s} {aw:>9s}")


def coefficient_report(df: pd.DataFrame) -> None:
    """Full-data fit (same pipeline) for interpretation only."""
    leagues = league_list(df)
    names = BASE_FEATURES + [_slug(lk) for lk in leagues]
    prep = _Prep().fit(design_matrix(df, leagues))
    X = prep.transform(design_matrix(df, leagues))
    clf = LogisticRegression(C=C_REG, max_iter=MAX_ITER)  # L2 is the default penalty
    clf.fit(X, df["y"].to_numpy(dtype=int))
    coefs = sorted(zip(names, clf.coef_[0]), key=lambda t: -abs(t[1]))
    print("\n" + "=" * 78)
    print("COEFFICIENTS (standardized scale; full-data fit, interpretation only)")
    print(f"  positive -> pushes P(home win) up; {len(names)} features "
          f"({len(leagues)} league dummies at >= {LEAGUE_MIN_TRAIN} matches)")
    print("=" * 78)
    print(f"  intercept: {clf.intercept_[0]:+.4f}")
    for name, c in coefs:
        print(f"  {name:34s} {c:+.4f}")


def main() -> None:
    df = load_completed()
    print(f"Loaded {len(df)} completed matches; base features "
          f"{len(BASE_FEATURES)} + per-fold league dummies "
          f"(>= {LEAGUE_MIN_TRAIN} train matches); L2 C={C_REG}")

    runs = {}
    for name, pred in [("logistic", predict_logistic),
                       ("form_favourite", baseline_form_favourite),
                       ("always_half", predict_always_half)]:
        oof, info = walk_forward(df, pred)
        runs[name] = (oof, info)

    info = runs["logistic"][1]
    print(f"\nWalk-forward: evaluated={info['evaluated']}  "
          f"skipped_insufficient_history={info['skipped_insufficient_history']}  "
          f"blocks={info['blocks_used']}  min_train={info['min_train']}")

    # ---- Table A: overall ----
    print("\n" + "=" * 78)
    print("TABLE A - OVERALL (same walk-forward splits for all)")
    print("=" * 78)
    for name in ("logistic", "form_favourite", "always_half"):
        m = _m(runs[name][0])
        tag = "   <- model" if name == "logistic" else ""
        print(f"  {name:16s} n={m['n']:5d}  acc={m['accuracy']:.4f}  "
              f"log_loss={m['log_loss']:.4f}  brier={m['brier']:.4f}{tag}")

    # ---- Table B: per-league side-by-side ----
    oof_m, oof_f = runs["logistic"][0], runs["form_favourite"][0]
    print("\n" + "=" * 78)
    print("TABLE B - PER LEAGUE (model vs form_favourite; eval n>=30, IPL always)")
    print("=" * 78)
    print(f"  {'league_key':28s} {'n':>5s} | {'acc_mdl':>7s} {'acc_frm':>7s} | "
          f"{'ll_mdl':>7s} {'ll_frm':>7s} | {'d_ll':>7s}")
    print("  " + "-" * 76)
    leagues = (oof_m.groupby("league_key").size()
               .sort_values(ascending=False))
    for lk, n in leagues.items():
        if n < 30 and lk != IPL:
            continue
        mm = _m(oof_m[oof_m["league_key"] == lk])
        mf = _m(oof_f[oof_f["league_key"] == lk])
        d_ll = mm["log_loss"] - mf["log_loss"]      # negative = model better
        tag = "  <<< IPL" if lk == IPL else ""
        print(f"  {str(lk)[:28]:28s} {mm['n']:5d} | {mm['accuracy']:7.4f} "
              f"{mf['accuracy']:7.4f} | {mm['log_loss']:7.4f} "
              f"{mf['log_loss']:7.4f} | {d_ll:+7.4f}{tag}")
    print("\n  (d_ll = model log_loss minus form log_loss; NEGATIVE = model better)")

    # ---- calibration ----
    _print_calibration("model, overall", oof_m)
    ipl_oof = oof_m[oof_m["league_key"] == IPL]
    if len(ipl_oof):
        _print_calibration("model, IPL only", ipl_oof)

    # ---- coefficients ----
    coefficient_report(df)


if __name__ == "__main__":
    main()
