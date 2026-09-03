# Part 1 Decisions

This document records exactly five important decisions for the LPDG Innovation Hub Selection Challenge 2026 Part 1 submission. Part 2 is documented as a future choice only; it has not been implemented.

## 1. Ranking method

**A. What I chose:** I used the official supplied `baseline_3sigma.py` without changing its ranking algorithm. It uses per-gateway telemetry baselines and selects the 15 gateways with the most recent anomalous hours.

**B. Alternative:** I could have created a new statistical method or a machine-learning model.

**C. Why I did not choose it:** The challenge provides this baseline as the official benchmark, and Part 1 does not require a new model. Preserving it keeps the result explainable, comparable, and easy for a reviewer to reproduce.

## 2. Historical anomaly window

**A. What I chose:** I used the supplied 28-day historical window and the most recent seven days within that history. A telemetry hour is flagged when one of the three baseline metrics exceeds its gateway-specific mean by more than three standard deviations.

**B. Alternative:** I could have used a different history length, a rolling median, or a different threshold.

**C. Why I did not choose it:** The supplied baseline defines this method, and changing the window or threshold would create a different ranking method. The selected approach is simple and gives an operationally understandable score: the number of flagged recent hours.

## 3. Prediction data cutoff

**A. What I chose:** For every prediction Monday, I used only telemetry strictly before Monday 00:00 UTC. The baseline filters records with `timestamp < Monday 00:00 UTC` before calculating the historical and recent windows.

**B. Alternative:** I could have included data from the prediction week or data recorded after the Monday cutoff.

**C. Why I did not choose it:** That would leak future information into the prediction and violate the challenge requirement. Strict UTC filtering makes the timing rule explicit and reproducible.

## 4. Output and operational reasons

**A. What I chose:** I generated exactly 15 ranked gateways for each of the eight required weeks, with ranks 1 through 15, numeric scores, and a short reason for every row. The output has exactly the five required columns: `week_start`, `rank`, `gateway_id`, `score`, and `reason`.

**B. Alternative:** I could have returned more than 15 gateways, returned only gateway IDs, or supplied longer technical explanations.

**C. Why I did not choose it:** Fifteen visits is a hard challenge limit. The required schema needs a score and reason, and concise reasons are easier for an operations reviewer to use while remaining within the validator's 300-character limit.

## 5. Part 2 area choice

**A. What I chose:** I intend to choose Data Science / Machine Learning for Part 2. Part 1 uses a simple official 3-sigma baseline, while Part 2 could investigate whether additional data and features, together with a learned approach, improve gateway prioritisation. The future work should remain explainable and reproducible.

**B. Alternative:** I could have chosen Software Development, DevOps, MLOps, or another challenge area.

**C. Why I did not choose it:** Data Science / Machine Learning is the area most directly suited to testing whether field visits, meter-read success, gateway metadata, engineer review, and historical outcomes add predictive value beyond telemetry anomalies. This is only a documented Part 2 choice; no ML model or Part 2 implementation has been added.

# What This Solution Cannot Do

The baseline detects unusual telemetry behavior; it does not directly determine whether a gateway is physically broken. An anomalous `offline_duration_sec`, `disconnection_cnt`, or `reboot_cnt` value can have a temporary or non-hardware cause. Conversely, a gateway with no three-sigma breach can still need attention.

The operational trade-off is asymmetric: an unnecessary visit costs EUR 380, while leaving a broken gateway unattended costs EUR 600 per week. The current result is therefore an anomaly detector and prioritisation ranking, not a perfect fault predictor. The CSV validator confirms format and required coverage, but it cannot measure false visits, missed faults, or economic value.

The supplied telemetry also contains duplicate `(gateway_id, ts_utc)` records in the September 2025, November 2025, and January 2026 partitions. The official baseline was required for Part 1 and was left unchanged, so these duplicates may influence its means, standard deviations, and scores. This is a known data limitation, not a CSV validation error. Optional missing fields in the master and operational files are not used by the official baseline.

# What Another Two Weeks Could Improve

Two additional weeks of work and labelled operational outcomes could support a careful comparison of anomaly windows and thresholds, quantify false-visit and missed-fault rates, and evaluate whether field visits, meter-read success, engineer review, or gateway metadata improve prioritisation. It could also test duplicate handling and tie-breaking choices. Two weeks would provide useful evidence, but would not guarantee a perfect predictor because field outcomes and failure causes can remain uncertain.

# Part 1 Run and Validation

From the repository root, install the required baseline dependencies:

```powershell
python -m pip install pandas numpy pyarrow
```

Generate the submission using the relative supplied-data path:

```powershell
python baseline_3sigma.py --data 03-challenge-data/data --out predictions.csv
```

Validate it with the official validator:

```powershell
python validate_submission.py predictions.csv
```

The verified result is 120 rows across the eight required weeks, with 15 gateways per week. The official validator returned `predictions.csv: OK`.
