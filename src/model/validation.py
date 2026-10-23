"""
validation.py - Phase 2 VALIDATION HARNESS (measuring instrument only).

No model here. This is the honest scorer that any future predictor will be
run through. Reads L3 (data/lake/l3/); never modifies L0/L1/L2/L3; writes
nothing to disk.

WALK-FORWARD (expanding window, monthly step)
---------------------------------------------
All COMPLETED T20-men matches (winner in {home, away}) are ordered by
match_date and walked forward month by month:

    for each calendar month M:
        train   = every completed match STRICTLY BEFORE the first day of M
        predict = the completed matches that fall within M

The predictor only ever sees `train`; it returns P(home win) for each row of
`predict`. Because train is cut at the month boundary, no evaluation match is
ever in its own training set and no future match can leak backward - this is
the as_of_date rule enforced at the model level.

Trade-off (documented): a match on the 20th does not see same-month matches
from the 3rd. That is deliberately conservative (never anti-conservative), so
it can only under-state a model, never inflate it. Monthly stepping keeps the
harness usable for models that are expensive to retrain; swap STEP if needed.

METRICS (on the out-of-sample walk-forward predictions)
-------------------------------------------------------
accuracy (higher-probability side won), log_loss, brier_score, a decile
calibration table (predicted-avg vs actual-win-rate per 10% bucket), and the
home base_rate. Everything is reported OVERALL and BY league_key (IPL shown
explicitly).

Predictor contract
------------------
    predictor(train_df: DataFrame, predict_df: DataFrame) -> array[float]
returns P(home win) in [0,1], one per row of predict_df, using ONLY train_df
(and predict_df's non-target features). It must not read predict_df['winner'].

Run:
    venv/Scripts/python.exe -m src.model.validation
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
L3 = (ROOT / "data" / "lake" / "l3" / "feature_rows" / "feature_rows.parquet").as_posix()

MIN_TRAIN = 100          # skip eval matches without at least this much history
EPS = 1e-15              # log-loss clip (keeps p=0/1 predictors finite)
IPL = "indian premier league"

Predictor = Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def load_completed(gender: str | None = "male") -> pd.DataFrame:
    """Completed T20 matches with a defined home/away target, date-sorted.

    gender: "male" (DEFAULT — L3 now also holds women's T20s, but the Phase-2
    training set stays men-only until the men+women, league-aware retrain;
    the default keeps every training/backtest script's data unchanged),
    "female", or None for all genders (the content payload filters per match).
    """
    con = duckdb.connect()
    gender_clause = f"AND gender = '{gender}'" if gender else ""
    df = con.execute(f"""
        SELECT * FROM read_parquet('{L3}')
        WHERE winner IN ('home','away') {gender_clause}
        ORDER BY match_date, match_id
    """).df()
    con.close()
    df["match_date"] = pd.to_datetime(df["match_date"])
    df["y"] = (df["winner"] == "home").astype(int)     # 1 = home won
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# walk-forward
# --------------------------------------------------------------------------
def walk_forward(df: pd.DataFrame, predictor: Predictor,
                 min_train: int = MIN_TRAIN):
    """
    Expanding-window monthly walk-forward. Returns (oof_df, info) where oof_df
    has columns [match_id, match_date, league_key, p, y] for every evaluated
    match, and info reports counts (evaluated / skipped / blocks).
    """
    months = pd.period_range(df["match_date"].min(),
                             df["match_date"].max(), freq="M")
    rows = []
    skipped_hist = 0
    blocks_used = 0
    for m in months:
        start = m.start_time
        end = (m + 1).start_time
        cur = df[(df["match_date"] >= start) & (df["match_date"] < end)]
        if cur.empty:
            continue
        train = df[df["match_date"] < start]
        if len(train) < min_train:
            skipped_hist += len(cur)
            continue
        p = np.asarray(predictor(train, cur), dtype=float)
        assert len(p) == len(cur), "predictor returned wrong length"
        blocks_used += 1
        block = cur[["match_id", "match_date", "league_key", "y"]].copy()
        block["p"] = np.clip(p, 0.0, 1.0)
        rows.append(block)

    oof = (pd.concat(rows, ignore_index=True) if rows
           else pd.DataFrame(columns=["match_id", "match_date", "league_key", "y", "p"]))
    info = {
        "total_completed": len(df),
        "evaluated": len(oof),
        "skipped_insufficient_history": skipped_hist,
        "blocks_used": blocks_used,
        "min_train": min_train,
    }
    return oof, info


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    pc = np.clip(p, EPS, 1 - EPS)
    pred_home = p >= 0.5                       # tie -> predict home (documented)
    return {
        "n": int(len(y)),
        "accuracy": float(np.mean(pred_home == (y == 1))) if len(y) else float("nan"),
        "log_loss": float(np.mean(-(y * np.log(pc) + (1 - y) * np.log(1 - pc)))) if len(y) else float("nan"),
        "brier": float(np.mean((p - y) ** 2)) if len(y) else float("nan"),
        "base_rate": float(np.mean(y)) if len(y) else float("nan"),
    }


def calibration(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    idx = np.clip((p * bins).astype(int), 0, bins - 1)   # 0.0..1.0 -> 0..bins-1
    out = []
    for b in range(bins):
        mask = idx == b
        c = int(mask.sum())
        out.append({
            "bucket": f"{b*10:3d}-{(b+1)*10:3d}%",
            "count": c,
            "pred_avg": float(p[mask].mean()) if c else float("nan"),
            "actual_win_rate": float(y[mask].mean()) if c else float("nan"),
        })
    return pd.DataFrame(out)


def by_league(oof: pd.DataFrame, min_n: int = 20) -> pd.DataFrame:
    recs = []
    for lk, g in oof.groupby("league_key"):
        mrec = metrics(g["y"].values, g["p"].values)
        mrec["league_key"] = lk
        recs.append(mrec)
    tbl = pd.DataFrame(recs).sort_values("n", ascending=False)
    # keep leagues with enough eval matches, but ALWAYS keep IPL if present
    keep = (tbl["n"] >= min_n) | (tbl["league_key"] == IPL)
    return tbl[keep].reset_index(drop=True)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def _fmt_metrics(m: dict) -> str:
    return (f"n={m['n']:5d}  acc={m['accuracy']:.4f}  "
            f"log_loss={m['log_loss']:.4f}  brier={m['brier']:.4f}  "
            f"base_rate(home)={m['base_rate']:.4f}")


def report(name: str, oof: pd.DataFrame, info: dict) -> None:
    print("\n" + "=" * 78)
    print(f"PREDICTOR: {name}")
    print("=" * 78)
    print(f"  completed={info['total_completed']}  evaluated={info['evaluated']}  "
          f"skipped_insufficient_history={info['skipped_insufficient_history']}  "
          f"(min_train={info['min_train']}, monthly blocks used={info['blocks_used']})")

    overall = metrics(oof["y"].values, oof["p"].values)
    print(f"\n  OVERALL   {_fmt_metrics(overall)}")

    print("\n  BY league_key (eval n>=20, IPL always shown):")
    tbl = by_league(oof)
    print(f"    {'league_key':30s} {'n':>5s} {'acc':>7s} {'logloss':>8s} "
          f"{'brier':>7s} {'home%':>7s}")
    print("    " + "-" * 68)
    for r in tbl.itertuples():
        tag = "  <<< IPL" if r.league_key == IPL else ""
        print(f"    {str(r.league_key)[:30]:30s} {r.n:5d} {r.accuracy:7.4f} "
              f"{r.log_loss:8.4f} {r.brier:7.4f} {r.base_rate:7.4f}{tag}")

    print("\n  CALIBRATION (overall) - predicted-avg vs actual-win-rate per decile:")
    cal = calibration(oof["y"].values, oof["p"].values)
    print(f"    {'bucket':10s} {'count':>6s} {'pred_avg':>9s} {'actual':>9s}")
    print("    " + "-" * 38)
    for r in cal.itertuples():
        pa = "  -  " if np.isnan(r.pred_avg) else f"{r.pred_avg:.4f}"
        aw = "  -  " if np.isnan(r.actual_win_rate) else f"{r.actual_win_rate:.4f}"
        print(f"    {r.bucket:10s} {r.count:6d} {pa:>9s} {aw:>9s}")

    ipl = oof[oof["league_key"] == IPL]
    if len(ipl):
        print("\n  CALIBRATION (IPL only):")
        cal_i = calibration(ipl["y"].values, ipl["p"].values)
        print(f"    {'bucket':10s} {'count':>6s} {'pred_avg':>9s} {'actual':>9s}")
        print("    " + "-" * 38)
        for r in cal_i.itertuples():
            pa = "  -  " if np.isnan(r.pred_avg) else f"{r.pred_avg:.4f}"
            aw = "  -  " if np.isnan(r.actual_win_rate) else f"{r.actual_win_rate:.4f}"
            print(f"    {r.bucket:10s} {r.count:6d} {pa:>9s} {aw:>9s}")


# --------------------------------------------------------------------------
# trivial self-test predictors (harness validation ONLY - not models)
# --------------------------------------------------------------------------
def predict_always_home(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    return np.ones(len(current))


def predict_always_half(train: pd.DataFrame, current: pd.DataFrame) -> np.ndarray:
    return np.full(len(current), 0.5)


def self_test() -> None:
    df = load_completed()
    print(f"Loaded {len(df)} completed T20-men matches with target "
          f"({df['match_date'].min().date()} .. {df['match_date'].max().date()}), "
          f"home base_rate={df['y'].mean():.4f}")
    print("\nHARNESS SELF-TEST (trivial predictors - proving the instrument, "
          "not a model)")
    print("Expected: always-0.5 -> log_loss ~= 0.6931, brier=0.2500, acc=base_rate;")
    print("          always-home -> brier=away_rate, acc=base_rate, large finite log_loss.")

    for name, pred in [("always_half (p=0.5)", predict_always_half),
                       ("always_home (p=1.0)", predict_always_home)]:
        oof, info = walk_forward(df, pred)
        report(name, oof, info)


if __name__ == "__main__":
    self_test()
