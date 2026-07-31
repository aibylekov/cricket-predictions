"""
pipeline.py — one prediction end-to-end, LIGHT, CI-friendly.

Orchestrates: ingest → features → predict → content → publish.
Touches only the small trained model artifact and live API data for
a single upcoming match. Never reads the 600 MB raw DB.

Usage:
    python -m src.pipeline --match-id M2026_0001 [--dry-run]
"""
import argparse


def run(match_id: str, dry_run: bool = False) -> None:
    """Run the full prediction pipeline for one match."""
    raise NotImplementedError("Фаза 0→3: implement step by step per phase")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cricket prediction pipeline")
    parser.add_argument("--match-id", required=True, help="Internal match identifier")
    parser.add_argument("--dry-run", action="store_true", help="Skip publish step")
    args = parser.parse_args()
    run(match_id=args.match_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
