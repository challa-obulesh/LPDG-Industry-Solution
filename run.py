from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "03-challenge-data" / "data"
OUTPUT = ROOT / "predictions.csv"

if not DATA.exists():
    raise SystemExit(f"Data folder not found: {DATA}")

print("Running Part 1 gateway ranking...")

subprocess.run([
    sys.executable,
    str(ROOT / "baseline_3sigma.py"),
    "--data", str(DATA),
    "--out", str(OUTPUT)
], check=True)

print("\nValidating predictions...")

subprocess.run([
    sys.executable,
    str(ROOT / "validate_submission.py"),
    str(OUTPUT)
], check=True)

print("\nPart 1 completed successfully.")
