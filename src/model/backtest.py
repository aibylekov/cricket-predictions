"""
backtest.py — HEAVY, local only.

Walk-forward validation against historical L3 feature rows.
Outputs log loss / Brier score / calibration / accuracy metrics.
Run manually from venv:
    python -m src.model.backtest

Never called from pipeline.py or GitHub Actions.
"""


def main() -> None:
    raise NotImplementedError("Фаза 2: implement walk-forward backtest")


if __name__ == "__main__":
    main()
