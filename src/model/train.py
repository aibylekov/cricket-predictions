"""
train.py — HEAVY, local only.

Reads 600 MB raw DB, trains the match-outcome model, saves artifact to models/.
Run manually from venv:
    python -m src.model.train

Never called from pipeline.py or GitHub Actions.
"""


def main() -> None:
    raise NotImplementedError("Фаза 2: implement walk-forward training")


if __name__ == "__main__":
    main()
