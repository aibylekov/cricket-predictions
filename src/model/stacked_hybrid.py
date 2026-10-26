"""
stacked_hybrid.py - PRODUCTION model "stacked_hybrid_v4" (adopted 2026-10-26).

Two levels, both refit per prediction on completed matches strictly before
the target match's date (the payload's anti-leakage rule):

  Level 1 - v3.1 pooled logistic (src/model/retrain_men_women.predict_pooled:
            the v2 pipeline on men+women history + is_female, C=0.01).
  Level 2 - form-anchored logistic stacker (C=1.0) on
            [logit(p_v3.1), form_gap_tourn, form_gap_last5 (+ is_female)]:
              men   -> GLOBAL stacker, fit on all genders' history, with the
                       is_female flag;
              women -> WOMEN-ONLY stacker, fit on women's history, no flag.
            The stacker's training rows are level-1 OUT-OF-SAMPLE predictions
            (monthly walk-forward of v3.1, level1_oof below), restricted to
            matches before the target date. Fewer than STACK_MIN_TRAIN (200)
            such rows for the target's pool -> p_v3.1 passes through.

Evaluation: docs/model/stack_hybrid_report.md (src/model/stack_hybrid.py) -
passes the adoption bar: WBBL matches form_favourite (CI includes 0), men =
global stacker, women better than v3.1. predict_hybrid run inside the harness
reproduces that report's hybrid predictions exactly (tests/test_stacked_hybrid.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.model.retrain_men_women import predict_pooled
from src.model.stack_form import STACK_C, STACK_MIN_TRAIN, stack_features
from src.model.validation import walk_forward

MODEL_VERSION = "stacked_hybrid_v4"


def level1_oof(completed: pd.DataFrame) -> pd.Series:
    """match_id -> v3.1 out-of-sample p (monthly walk-forward; each value comes
    from a model trained before its own month, so any subset of rows before a
    target date is leak-free stacker training data)."""
    oof, _ = walk_forward(completed, predict_pooled)
    return oof.set_index("match_id")["p"]


def _stacker_pool(hist: pd.DataFrame, gender: str) -> tuple[pd.DataFrame, bool]:
    """(training rows, with_gender) for the target's gender."""
    if gender == "female":
        return hist[hist["gender"] == "female"], False
    return hist, True


def predict_hybrid(train: pd.DataFrame, target: pd.DataFrame,
                   level1: pd.Series) -> np.ndarray:
    """P(home win) for each target row. train = completed matches strictly
    before every target row (all genders); level1 = level1_oof(...)."""
    assert train["match_date"].max() < target["match_date"].min()
    p1 = np.asarray(predict_pooled(train, target), float)
    out = p1.copy()
    hist = train[train["match_id"].isin(level1.index)]
    for g in target["gender"].unique():
        m = (target["gender"] == g).to_numpy()
        pool, with_gender = _stacker_pool(hist, g)
        if len(pool) < STACK_MIN_TRAIN or pool["y"].nunique() < 2:
            continue                                       # cold start: pass-through
        clf = LogisticRegression(C=STACK_C, max_iter=1000)
        clf.fit(stack_features(pool, pool["match_id"].map(level1).to_numpy(float), with_gender),
                pool["y"].to_numpy(int))
        out[m] = clf.predict_proba(stack_features(target[m], p1[m], with_gender))[:, 1]
    return out


def make_harness_predictor(level1: pd.Series):
    """predict_hybrid in the walk_forward(train, current) shape."""
    return lambda train, current: predict_hybrid(train, current, level1)
