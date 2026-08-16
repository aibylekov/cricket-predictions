"""
framing.py - Phase 3, step 1: CONFIDENCE & FRAMING layer.

Maps the calibrated v2 model probability to a confidence band. The band
drives the article's TONE and FRAMING - never whether we publish (README
principle #5: no gating; every match gets a prediction).

Bands work on p_max = max(p_home, p_away), i.e. the predicted winner's
probability. Thresholds live in BAND_CONFIG and will be tuned later
(e.g. against the calibration table: v2's 60-70% bucket is nearly exact,
so 0.65 as the "confident" floor is a defensible starting point).
"""
from __future__ import annotations

# ---- tunable thresholds (locked format; values will be tuned later) ------
BAND_CONFIG = {
    "confident": 0.65,     # p_max >= 0.65            -> "confident"
    "moderate": 0.55,      # 0.55 <= p_max < 0.65     -> "moderate"
                           # p_max < 0.55             -> "close_call"
}

BANDS = ("confident", "moderate", "close_call")


def confidence_band(p_max: float) -> str:
    """Band for the predicted winner's probability p_max (in [0.5, 1])."""
    if p_max >= BAND_CONFIG["confident"]:
        return "confident"
    if p_max >= BAND_CONFIG["moderate"]:
        return "moderate"
    return "close_call"


def frame(p_home: float) -> dict:
    """
    Full framing for a home-win probability:
      predicted side (tie -> home, consistent with the harness), p_max, band.
    """
    p_home = float(p_home)
    side = "home" if p_home >= 0.5 else "away"
    p_max = p_home if side == "home" else 1.0 - p_home
    return {
        "predicted_winner": side,
        "p_max": p_max,
        "confidence_band": confidence_band(p_max),
    }
