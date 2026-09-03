# AI Usage

AI assistance was used during Part 1 to:

- Inspect the supplied README, baseline, validator, PDFs, CSV files, workbook, and telemetry partitions.
- Confirm the actual prediction weeks and required output schema.
- Check the Python environment and identify the dependencies needed to run the supplied baseline.
- Run the official baseline and validation commands.
- Independently check row counts, weekly counts, ranks, duplicate gateway/week combinations, duplicate week/rank combinations, missing values, score types, and reason lengths.
- Draft and review the Part 1 documentation.

The official `baseline_3sigma.py`, `validate_submission.py`, challenge PDFs, and original data files were preserved. No machine-learning model, Data Science implementation, or alternate ranking method was used for Part 1.

## Real mistake caught

Earlier AI assistance started implementing a FastAPI and Software Development Part 2 solution even though the active request had been narrowed to Part 1 only. This was caught by the user, and those Part 2 files were removed. The final workspace contains only the Part 1 submission work requested here.

The final predictions were regenerated directly with the official baseline and checked with the official validator rather than trusting generated code or an existing output file.
