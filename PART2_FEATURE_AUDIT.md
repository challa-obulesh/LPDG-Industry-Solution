# Part 2 Feature Audit

## Dataset contract

The generated table has one row per `(week_start, gateway_id)`. The cutoff is Monday 00:00 UTC. Features use only the preceding 28 days and exclude timestamps at or after the cutoff. Labels use the following complete seven days and are never included in model features.

## Feature decisions

| Feature family | Source | Time window | Leakage risk | Decision | Reason |
|---|---|---|---|---|---|
| Telemetry metric mean/median/std/max/sum | Deduplicated telemetry | Previous 7/14/28 days | Low when cutoff-filtered | Included | Operational degradation level and variability |
| Recent-minus-older trend | Deduplicated telemetry | Recent 7d vs prior 21d | Low when cutoff-filtered | Included | Detects worsening behavior |
| Observed hours/days | Deduplicated telemetry | Previous 7/14/28 days | Low | Included | Measures coverage and history sufficiency |
| Duplicate count/rate | Raw telemetry before deduplication | Previous 7/14/28 days | Low | Included | Captures data-quality conditions without changing source data |
| RSSI/RSRP/RSRQ category means | Deduplicated telemetry | Previous 7/14/28 days | Low | Included | Signal-quality context |
| Historical meter read rate/failures | Meter file | Completed weeks before cutoff, previous 28d | Low | Included | Historical service-impact context |
| Tenant/site/hardware/antenna/firmware | Gateway master | Stable values valid by cutoff | Medium | Included | Static operational context; no future lifecycle fields |
| Installed age | Gateway master | Installed date <= cutoff | Low | Included | Age context; future-dated installations are neutralized |
| Future telemetry | Telemetry | Label window | High | Excluded from features | Used only to construct proxy target |
| Future meter values | Meter file | Prediction week | High | Excluded | Direct future leakage |
| Field visit outcome/parts/hours | Field visits | Post-intervention | High | Excluded | Selected and delayed operational evidence |
| Engineer review | Workbook | 2026-02-15 snapshot | High | Excluded | Post-cutoff selected evidence, not hidden truth |
| Decommissioned date | Gateway master | Future lifecycle event | High | Excluded | Unavailable before the event |
| Raw gateway ID | Any | All | Memorization risk | Excluded | Violates meaningful unseen-gateway testing |
| Target-derived feature | Constructed label | Future window | High | Excluded | Direct target leakage |

## Validation checks

The builder asserts non-empty data, unique gateway-week rows, complete future labels, no feature nulls, binary target values, and no forbidden feature names. The generated artifact is `artifacts/part2_gateway_week.parquet`.

## Target definition

An hour is degraded when `offline_duration_sec >= 3600`, `disconnection_cnt >= 3`, or `reboot_cnt >= 1`. A gateway-week is positive when its complete seven-day future window has at least 84 observed hours, degraded observations on at least two distinct days, and at least six degraded hours. This is a historical operational proxy, not official hidden ground truth.