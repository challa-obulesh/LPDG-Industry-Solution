# Final Submission Audit

## Overall Status

**PASS WITH ACTIONS**

The protected Part 1 submission is valid, and the Part 2 implementation and documentation are internally consistent after correcting the fair baseline comparison. The remaining actions are submission hygiene: review/stage the uncommitted work, make a real commit if required by the challenge process, and complete the requested recording.

## Part 1

- **Baseline:** `baseline_3sigma.py` was not changed. Its working-tree hash matches `HEAD`.
- **Predictions:** `predictions.csv` was regenerated with the official baseline and remains unchanged at SHA-256 `68F5C8D7A18944BE01E710E004A1BD19F9FCE39096B5249E573A165126004CB7`.
- **Validator:** `python validate_submission.py predictions.csv` passes as `predictions.csv: OK` when run with the project virtual environment.
- **Coverage:** 120 rows, 8 prediction weeks, 15 rows per week, ranks 1 through 15, no duplicate gateway/week combinations, required columns, numeric scores, and non-empty reasons under the 300-character limit.
- **Reproducibility:** The documented relative data path works from the repository root. Dependencies are documented in `requirements.txt`; the project `.venv` contains the required imports.
- **Original data protection:** No challenge-data files were modified during this audit. The official baseline and validator are protected by exact hash comparison; the challenge data has no committed reference hash available for an independent byte-for-byte comparison.

## Part 2

- **Target:** A historical proxy target for persistent telemetry degradation in the complete seven days after each Monday cutoff: at least 84 observed hours, degradation on at least 2 distinct days, and at least 6 degraded hours.
- **Model:** Existing regularized Logistic Regression retained unchanged. No new model or tuning was performed.
- **Leakage:** Features use only data strictly before the cutoff. Future telemetry is used only for labels; future meter values, field outcomes, engineer review, future lifecycle fields, target-derived fields, and raw gateway IDs are excluded.
- **Temporal evaluation:** Training ends 2025-12-29; validation covers 2026-01-05 through 2026-01-26; forward test covers 2026-02-02 through 2026-03-23. The incomplete 2026-03-30 week is excluded.
- **Unseen gateways:** 35 gateways first observed in January-March 2026 are evaluated separately without fitting on those gateways.
- **Sensitivity:** Target-threshold and feature-ablation sensitivity are recorded. Duplicate handling uses deterministic median aggregation and retains duplicate-rate features; full alternate duplicate-policy metrics are explicitly not fabricated.
- **Fair cost comparison:** The primary baseline evaluator now restricts both methods to the same eligible gateway-week population before selecting 15. The cost formula is €380 per unnecessary visit plus €600 per missed proxy-positive gateway per week.

## Verified Results

- **Forward baseline:** €329,400 historical proxy-label cost.
- **Forward Logistic Regression:** €270,600 historical proxy-label cost.
- **Difference:** €58,800 lower historical proxy-label cost.
- **Unseen gateway result:** 35 gateways, 8 weeks; Logistic Regression proxy cost €28,940, precision@15 0.3540, recall 0.9524.
- **Interpretation:** The difference is not confirmed real-world savings, not hidden-ground-truth performance, and not official challenge performance.

## Documentation

- **README:** Includes Part 1 commands, Part 2 dependencies, the one-command Part 2 reproduction command, and the proxy-result warning.
- **DECISIONS:** Contains exactly five numbered decisions. Each records the choice, alternative, reasoning, and relevant trade-off.
- **AI-USAGE:** Records where AI was used, manual verification, a real mistaken direction that was corrected, and the rule that generated results were not trusted blindly.
- **Part 2 reports:** Target, leakage, duplicate/missingness, population-shift, cost, and limitation statements are documented consistently.
- **Presentation:** Covers the requested story from problem through final decision and presents €329,400, €270,600, and €58,800 with the hidden-ground-truth warning.
- **Dashboard:** The read-only dashboard presents the final Logistic Regression model, baseline comparison, weekly costs, feature importance, unseen-gateway metrics, and methodology limitations.

## Git

- **Repository status:** Git repository exists on `main`, tracking `origin/main`.
- **Commit status:** Part 1 history is logical through the existing dashboard commit. Part 2 reports, scripts, artifacts, models, and the audit are currently uncommitted; no history was rewritten and no commits were fabricated.
- **Remaining action:** Review and stage the intended Part 2 submission files, then create a real commit if the challenge requires committed evidence. Do not commit generated or sensitive data unless that is explicitly intended.

## Recording

A recording is still required if the challenge instructions require the live demonstration. Recommended content: run the documented Part 1 command and validator, show the weekly 15-gateway output, explain the unchanged baseline, describe the Part 2 proxy target and leakage controls, show the fair forward comparison, and state clearly that the result is not hidden-groundtruth performance. Do not present €58,800 as confirmed savings; call it lower historical proxy-label cost.

## Remaining Actions

1. Review the uncommitted-file list and stage only the intended final submission artifacts.
2. Create a genuine commit if required by the submission process; do not invent historical commits.
3. Complete the recording or live demonstration if required.
4. Run the final commands below from the repository root using the project virtual environment.

## Final Verification Commands

```powershell
.venv\Scripts\python.exe baseline_3sigma.py --data 03-challenge-data/data --out predictions.csv
.venv\Scripts\python.exe validate_submission.py predictions.csv
.venv\Scripts\python.exe run_part2.py
.venv\Scripts\python.exe -m compileall -q baseline_3sigma.py validate_submission.py run.py run_part2.py src app.py
```
