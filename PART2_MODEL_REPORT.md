# Part 2 Model Report

## Scope

Final model: Logistic Regression. This is an evaluation against the historical proxy label `needs_visit`, not hidden final ground truth. Field-visit outcomes and engineer review were not used as labels or features. Part 1 files remain unchanged.

## Target and split

The target is 1 when the complete seven days after Monday 00:00 UTC contain at least 84 observed gateway-hours, degraded observations on at least two distinct days, and at least six degraded hours. A degraded hour has `offline_duration_sec >= 3600`, `disconnection_cnt >= 3`, or `reboot_cnt >= 1`. Features use only the preceding 28 days, strictly before cutoff.

Training ends 2025-12-29. Validation is 2026-01-05 through 2026-01-26. Test is 2026-02-02 through 2026-03-23. The incomplete 2026-03-30 week is excluded. The unseen-gateway slice contains 35 gateways first observed in January-March 2026.

## Dataset summary

- Rows: 8011
- Gateways: 315
- Cutoff weeks: 30
- Features: 99
- Positive rate: 0.2744
- Duplicate policy: group by normalized `(gateway_id, ts)` before aggregation; numeric telemetry values use the median and duplicate count/rate are retained as quality features.

## Cost results

Costs use €380 per unnecessary visit and €600 per missed proxy-positive gateway per week, with 15 selections per week.

| Evaluation | Rows | Weeks | Total cost | Precision@15 | Recall |
|---|---:|---:|---:|---:|---:|
| logistic_validation | 1038 | 4 | €130200 | 1.0000 | 0.2166 |
| baseline_validation | 1038 | 4 | €166460 | 0.3833 | 0.0830 |
| logistic_test | 2211 | 8 | €270600 | 1.0000 | 0.2102 |
| baseline_test | 2211 | 8 | €329400 | 0.5000 | 0.1051 |
| logistic_unseen_gateway_test | 181 | 8 | €28940 | 0.3540 | 0.9524 |

These are proxy-label results only. `logistic_test` is the forward-time test result; `logistic_unseen_gateway_test` is the separate device-disjoint result. The forward difference is €58,800 lower historical proxy-label cost, not confirmed real-world savings. These results are based on historical proxy labels and should not be presented as official hidden-groundtruth performance.

## Most influential coefficients

```text
                                     feature  coefficient    direction                                                interpretation
      numeric__hist_7d_disconnection_cnt_sum     2.603181 raises score Higher values increase predicted persistent degradation risk.
           numeric__meter_28d_read_rate_mean     2.281137 raises score Higher values increase predicted persistent degradation risk.
             numeric__hist_7d_reboot_cnt_std     2.011607 raises score Higher values increase predicted persistent degradation risk.
     numeric__hist_28d_disconnection_cnt_sum     1.815643 raises score Higher values increase predicted persistent degradation risk.
            numeric__meter_7d_read_rate_mean    -1.802926 lowers score Higher values decrease predicted persistent degradation risk.
      numeric__hist_7d_disconnection_cnt_std     1.721493 raises score Higher values increase predicted persistent degradation risk.
             numeric__hist_7d_rssi_good_mean    -1.667042 lowers score Higher values decrease predicted persistent degradation risk.
  numeric__hist_14d_disconnection_cnt_median     1.569677 raises score Higher values increase predicted persistent degradation risk.
numeric__trend_reboot_cnt_recent_minus_older     1.526166 raises score Higher values increase predicted persistent degradation risk.
            numeric__hist_28d_rssi_good_mean     1.472127 raises score Higher values increase predicted persistent degradation risk.
```

Positive coefficients raise the proxy-risk score; negative coefficients lower it. The generated prediction reasons identify the strongest learned signals, but they summarize model contribution rather than proving causality.

## Leakage and validation checks

- No raw gateway ID is a feature.
- Future telemetry is used only for the label window.
- Future meter values, field-visit outcome/repair fields, engineer review, future decommission dates, and target-derived features are excluded.
- Gateway-week uniqueness and deterministic missing-value handling are asserted by the feature builder.
- The unseen-gateway result is reported separately: €28940 total proxy cost across 8 weeks and 35 held-out gateways.

## Weaknesses and next improvement

The target is persistent telemetry degradation, not confirmed hardware failure. Duplicate/missing-hour handling and gateway churn remain material risks. The next improvement should be a predeclared threshold-sensitivity and duplicate-policy comparison, followed by inspection of high-cost disagreements against any newly available confirmed outcomes. Do not optimize the model before improving target validity.

## Final validation correction

The final validation ranks the unchanged 3-sigma logic within the same eligible gateway universe as ML before taking the top 15. The corrected historical proxy-label totals are €166,460 validation and €329,400 forward test for the baseline, versus €130,200 and €270,600 for Logistic Regression. Both methods select exactly 15 gateways on every shared week.
