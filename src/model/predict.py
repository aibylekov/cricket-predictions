"""
predict.py — LIGHT, CI-friendly.

Loads the trained model artifact from models/ and returns a prediction
payload for a single upcoming match.

Usage:
    from src.model.predict import predict_match
    payload = predict_match(match_id="M2026_0001")
"""


def predict_match(match_id: str) -> dict:
    """Return structured prediction payload for one match.

    The payload contains only numbers — no prose. The content layer
    dresses these numbers in text; this function must never generate prose.
    """
    raise NotImplementedError("Фаза 3: implement single-match inference")
