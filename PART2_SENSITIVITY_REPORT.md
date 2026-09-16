# Part 2 Sensitivity Report

All results are **historical proxy-label evaluation**, not official hidden-ground-truth results.

## Output and fair cost comparison

Validation weeks: 2026-01-05, 2026-01-12, 2026-01-19, 2026-01-26.

Forward weeks: 2026-02-02, 2026-02-09, 2026-02-16, 2026-02-23, 2026-03-02, 2026-03-09, 2026-03-16, 2026-03-23. The incomplete 2026-03-30 week is excluded.

Output checks: `{'weeks': ['2026-02-02', '2026-02-09', '2026-02-16', '2026-02-23', '2026-03-02', '2026-03-09', '2026-03-16', '2026-03-23'], 'exactly_15_each_week': True, 'ranks_1_to_15': True, 'duplicate_gateway_week_rows': 0, 'numeric_scores': True, 'nonempty_reasons': True, 'expected_weeks_match': True}`

Both methods use the same eligible gateway-week rows, target, seven-day future window, 15-visit cap, and €380/€600 cost formula. Each selected gateway is counted once; each missed target is counted once per week.

See `reports/weekly_cost_table.csv` for the complete weekly table.

## Weekly cost spread

```text
             method   min   max    mean  median
    baseline_3sigma 37240 48200 41175.0 40650.0
logistic_regression 29400 38400 33825.0 33300.0
```

## Target sensitivity

```text
   target_definition  positive_labels  positive_rate  validation_cost  forward_test_cost  precision_at_15   recall  unseen_gateway_recall
             current             2198       0.274373           130200             270600         1.000000 0.210158               0.952381
moderate_alternative             1611       0.201098            84600             172580         0.991667 0.293103               1.000000
```

The moderate alternative requires 12 degraded hours instead of 6 while keeping two degraded days. It represents more sustained degradation, but can miss shorter incidents that still deserve attention. The current target is retained because it captures persistence without requiring a very long outage.

## Feature ablation

```text
                  model  feature_count  validation_cost  forward_test_cost  precision_at_15   recall  unseen_gateway_recall
     current_99_feature             99           130200             270600         1.000000 0.210158               0.952381
reduced_target_adjacent             71           130200             271580         0.991667 0.208406               0.952381
```

The removed features are cutoff-safe but target-adjacent: recent disconnections, reboots, offline duration, 28-day degradation totals, and their trends. This is a robustness test, not feature selection by score.

## Unseen gateways

The unseen slice contains 35 gateways first observed in January-March 2026. They were excluded from model fitting, raw IDs are absent from features, and only their own future windows are used for evaluation. Logistic Regression proxy result: cost €28940, precision@15 0.3540, recall 0.9524.

The unchanged baseline can be scored on this subset only by ranking the full population first and then filtering to the subset; that may yield fewer than 15 selections and changes the operational universe. Therefore it is not presented as a directly comparable 15-visit baseline.

## Duplicate policy

The primary median policy is verified. Full first/last/drop duplicate-policy sensitivity was not completed within practical runtime: one alternate raw-policy build took approximately 299 seconds, and the full matrix exceeded the available execution window. No duplicate-policy metrics are fabricated. The primary pipeline retains deterministic duplicate handling and duplicate-rate features.

## Network and population change

The measured network grows from 280 telemetry gateways in August 2025 to 308 in March 2026; 268 are present in all eight months. Forty gateways first appear in January-March. Telemetry has 13,094 rows in duplicate timestamp groups, and 55,117 of 68,418 gateway-days are not exactly 24 rows. Meter coverage ends 2026-01-26, before the forward test. These changes can shift feature and score distributions and make cold-start rankings less reliable.

Recommended mitigations are monitoring feature/score distributions, periodic retraining, explicit cold-start rules, and fallback to the 3-sigma baseline when history is insufficient. These are recommendations, not claims that they are already deployed.

## Explainability

The strongest learned predictive signals are recent disconnection activity, historical meter-read rate, reboot variability, long-run disconnection totals, RSSI quality, and offline-duration variability. They indicate predictive association only, not causality.

## Conclusion

Final model: Logistic Regression. The controlled benchmark found identical measured operational results for Logistic Regression, Random Forest, Extra Trees and HistGradientBoosting, so Logistic Regression was retained for simpler interpretation and reproducibility. The €58,800 figure is lower historical proxy-label cost, not confirmed real-world savings. These results are based on historical proxy labels and should not be presented as official hidden-groundtruth performance.
