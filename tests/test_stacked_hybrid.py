"""
test_stacked_hybrid.py - production model stacked_hybrid_v4 guarantees.

  (A) EQUIVALENCE: the production predictor (src/model/stacked_hybrid) run in
      the walk-forward harness reproduces the evaluated hybrid
      (src/model/stack_hybrid, docs/model/stack_hybrid_report.md) exactly -
      what ships is what passed the adoption bar.
  (B) SCRAMBLED LABELS: shuffling the target block's own results never
      changes its predictions (no target-row label reaches either level).
  (C) FUTURE ROWS: appending matches dated on/after the target to the level-1
      table changes nothing (the stacker only reads rows before the target).
  (D) PAYLOAD: build_payload stamps model_version = "stacked_hybrid_v4".

Run:
  venv/Scripts/python.exe -m pytest tests/test_stacked_hybrid.py -v
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from src.model.stack_hybrid import _new_logs, make_hybrid_stacker
from src.model.stacked_hybrid import (MODEL_VERSION, level1_oof,
                                      make_harness_predictor, predict_hybrid)
from src.model.validation import load_completed, walk_forward


@lru_cache(maxsize=1)
def _data():
    df = load_completed(gender=None)
    return df, level1_oof(df)


def _last_blocks(df, n=3):
    return sorted(df["match_date"].dt.to_period("M").unique())[-n:]


def test_production_equals_evaluated_hybrid():
    df, l1 = _data()
    prod, _ = walk_forward(df, make_harness_predictor(l1))
    ev, _ = walk_forward(df, make_hybrid_stacker(l1, _new_logs()))
    assert len(prod) == len(ev) > 5000
    assert (prod["match_id"].to_numpy() == ev["match_id"].to_numpy()).all()
    assert np.abs(prod["p"].to_numpy() - ev["p"].to_numpy()).max() == 0.0


def test_scrambled_target_labels_do_not_move_predictions():
    df, l1 = _data()
    rng = np.random.default_rng(7)
    for m in _last_blocks(df):
        train = df[df["match_date"] < m.start_time]
        cur = df[df["match_date"].dt.to_period("M") == m]
        scr = cur.assign(y=rng.permutation(cur["y"].to_numpy()))
        assert np.abs(predict_hybrid(train, cur, l1) - predict_hybrid(train, scr, l1)).max() == 0.0


def test_future_level1_rows_are_ignored():
    df, l1 = _data()
    for m in _last_blocks(df):
        train = df[df["match_date"] < m.start_time]
        cur = df[df["match_date"].dt.to_period("M") == m]
        past_only = l1[l1.index.isin(train["match_id"])]
        poisoned = l1.copy()
        future = ~l1.index.isin(train["match_id"])
        poisoned[future] = 1.0 - poisoned[future]           # garbage after the cut
        base = predict_hybrid(train, cur, past_only)
        assert np.abs(base - predict_hybrid(train, cur, l1)).max() == 0.0
        assert np.abs(base - predict_hybrid(train, cur, poisoned)).max() == 0.0


def test_payload_stamps_model_version():
    from src.content.payload import build_payload
    df, _ = _data()
    women = df[df["gender"] == "female"].iloc[-1]
    pl = build_payload(int(women["match_id"]))
    assert MODEL_VERSION == "stacked_hybrid_v4"
    assert pl["prediction"]["model_version"] == MODEL_VERSION
    assert pl["prediction"]["p_home"] is not None
    assert pd.notna(pl["prediction"]["confidence_band"])
