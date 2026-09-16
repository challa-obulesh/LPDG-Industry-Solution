# NEXORA 2026 / LPDG Innovation Hub
# Part 2: Machine Learning Presentation

## 1. Problem

Each week, operations can select at most 15 gateways for possible field visits. The task is to rank gateways so limited visits are directed toward the gateways most likely to need attention.

This is an operational prioritization problem, not simply a classification-accuracy problem:

- An unnecessary visit costs **€380**.
- A missed broken gateway costs **€600 per week**.
- A ranking that puts the right gateways near the top matters more than a generic accuracy score.

## 2. Why the 3-sigma baseline is useful

The supplied `baseline_3sigma.py` is the official benchmark and remains unchanged. It is useful because it is:

- Simple to reproduce
- Gateway-specific
- Based on recent telemetry anomalies
- Easy for an operations reviewer to understand
- A meaningful benchmark rather than an arbitrary comparison

The baseline computes gateway-specific telemetry behavior over a trailing history, flags unusual recent hours, and ranks gateways by flagged-hour count.

## 3. Why we added ML

The baseline focuses on three anomaly measures. The final Logistic Regression model tests whether a broader, historical view improves prioritization by combining:

- Persistence and trend across multiple telemetry windows
- Signal-quality behavior
- Historical meter-read success
- Stable gateway attributes
- Data-coverage indicators

The goal was not to maximize a generic classification metric. The goal was to reduce operational cost under the fixed 15-visit limit.

## 4. Definition of "needs a visit"

The model uses a historical telemetry proxy target. A gateway is positive when its following complete seven-day window contains:

- At least 84 observed gateway-hours
- Degradation on at least 2 distinct days
- At least 6 degraded hours

A degraded hour is one where at least one condition holds:

- `offline_duration_sec >= 3600`
- `disconnection_cnt >= 3`
- `reboot_cnt >= 1`

**This is not hidden ground truth.** It is a documented, repeatable operational proxy used for historical development only.

## 5. Data and quality issues

The audit found:

- 1,433,387 telemetry rows
- 320 telemetry gateways
- 280 gateways in August 2025
- 308 gateways in March 2026
- 40 gateways first appearing during January-March 2026
- 13,094 telemetry rows in duplicate gateway-timestamp groups
- 55,117 gateway-days without exactly 24 observations
- Meter-read data ending on 2026-01-26

Duplicate timestamps were handled deterministically by grouping normalized gateway ID and timestamp and using median numeric telemetry values. Duplicate counts and rates were retained as quality features. The original data was not modified.

Historical field visits are selection-biased operational evidence, not a complete answer key. Engineer review is also evidence from a selected snapshot, not hidden ground truth.

## 6. Leakage prevention

For a Monday 00:00 UTC cutoff:

- Features use only the preceding historical window.
- Future telemetry is used only to construct historical training labels.
- Future meter values are excluded from features.
- Field-visit outcomes and repair information are excluded.
- Engineer review is excluded from features and labels.
- Future lifecycle dates are excluded.
- Raw gateway IDs are excluded as model features.
- Random hourly-row splitting is not used.

The evaluation is chronological and includes a separate unseen-gateway test.

## 7. Feature engineering

Historical features were calculated over 7-day, 14-day, and 28-day windows. They include:

- Offline-duration aggregates
- Disconnection aggregates
- Reboot aggregates and variability
- Recent-versus-older trends
- RSSI, RSRP, and RSRQ category summaries
- Observed-hour and observed-day counts
- Missingness and duplicate-rate indicators
- Historical meter-read rate and failures
- Stable master-data attributes available by the cutoff

The feature audit distinguishes cutoff-safe features from excluded future or post-intervention information.

## 8. Model choice: Logistic Regression

Regularized Logistic Regression was selected because it is:

- Explainable through coefficients
- Computationally practical
- Suitable for ranking a fixed visit budget
- Easy to modify in a live evaluation
- Compatible with numeric scaling and categorical one-hot encoding

**Final model: Logistic Regression.** I did not assume that a more complex model would automatically perform better. I benchmarked Logistic Regression, Random Forest, Extra Trees and HistGradientBoosting using the same operational evaluation. They produced identical measured results, so I retained Logistic Regression because it provides simpler interpretation and reproducibility.

These results are based on historical proxy labels and should not be presented as official hidden-groundtruth performance.

## 9. Temporal evaluation

Training uses earlier historical gateway-weeks. Validation uses:

```text
2026-01-05
2026-01-12
2026-01-19
2026-01-26
```

The forward test uses complete later weeks:

```text
2026-02-02
2026-02-09
2026-02-16
2026-02-23
2026-03-02
2026-03-09
2026-03-16
2026-03-23
```

The incomplete week beginning 2026-03-30 is excluded.

## 10. Unseen-gateway evaluation

The unseen-gateway slice contains 35 gateways first observed during January-March 2026. These gateways were excluded from model fitting. Their raw IDs were not features, and evaluation uses only their own future label windows.

Historical proxy-label result:

- Precision@15: `0.3540`
- Recall: `0.9524`
- 8 weeks

This is a cold-start robustness result, not hidden-ground-truth performance.

## 11. Cost comparison

The corrected fair comparison uses the same eligible gateway universe, future windows, target, costs, and 15-visit cap for both methods.

| Period | 3-sigma baseline | Logistic Regression |
|---|---:|---:|
| Validation | €166,460 | €130,200 |
| Forward test | €329,400 | €270,600 |

The forward difference is:

```text
€329,400 - €270,600 = €58,800
```

The correct claim is:

> Logistic Regression reduced historical proxy-label cost compared with the unchanged 3-sigma baseline during our forward evaluation. However, this is not official hidden-ground-truth performance because the challenge provides separate hidden evaluation data.

We do not claim that ML officially beats the challenge baseline.

## 12. Explainability

The strongest predictive signals include:

- Recent disconnection activity: a predictive signal of increasing connectivity instability
- Historical meter-read success: a predictive signal of longer-term service impact
- Reboot variability: a predictive signal of unstable gateway behavior
- Long-term disconnection totals: a predictive signal of persistent connectivity problems
- RSSI and related signal-quality measures: predictive context for network conditions
- Offline-duration variability: a predictive signal of inconsistent availability

These are predictive associations, not causal explanations.

## 13. Network and population shift

The network population changes materially, growing from 280 gateways in August to 308 in March. New gateways appear during the evaluation period, telemetry has duplicate and missing observations, and meter-read coverage ends before the forward test.

If the network changes, model scores may shift because the historical feature distribution changes. Practical production mitigation would include:

- Monitoring feature distributions
- Monitoring model-score distributions
- Detecting gateway-population drift
- Periodic retraining
- Explicit cold-start handling
- Falling back to the 3-sigma baseline when history is insufficient

These are recommended controls, not mechanisms claimed to be already implemented.

## 14. Limitations

- The target is a telemetry proxy, not confirmed physical failure.
- Duplicate telemetry can affect historical aggregates.
- Missing gateway-hours are a major data-quality issue.
- Meter data ends before the forward test.
- Gateway population shift creates cold-start and distribution-shift risk.
- Field visits are selected and cannot provide unbiased ground truth.
- Engineer review is evidence, not the hidden answer key.
- The hidden evaluation may behave differently from this historical proxy evaluation.
- Full duplicate-policy sensitivity was not completed within practical runtime; no metrics were fabricated.

## 15. Final decision

**Keep Logistic Regression as the Part 2 candidate, but do not claim official improvement until evaluation against the challenge's hidden ground truth.**

The model is promising on historical proxy labels and forward weeks, but the evidence does not justify an official hidden-ground-truth claim.

## 16. What another two weeks would buy

The highest-value work would be:

1. Obtain independently observed holdout outcomes.
2. Re-evaluate the frozen pipeline against those outcomes.
3. Complete duplicate-policy sensitivity using cached intermediate data.
4. Measure feature and score drift under new gateway populations.
5. Define and test cold-start fallback behavior.

Additional hyperparameter searches or additional model families would be lower priority than improving target validity and independent evaluation.