"""Build the Part 2 dataset and run the initial evaluation in one command."""

from __future__ import annotations

import os
import pathlib

from src.features import build_dataset
from src.evaluate import main as evaluate_main
from src.finalize import main as finalize_main


def main() -> int:
    os.chdir(pathlib.Path(__file__).resolve().parent)
    artifact = pathlib.Path("artifacts/part2_gateway_week.parquet")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    build_dataset(pathlib.Path("03-challenge-data/data")).to_parquet(artifact, index=False)
    evaluate_main()
    return finalize_main()


if __name__ == "__main__":
    raise SystemExit(main())