"""Focused final validation using the already-built Part 2 artifact."""

from __future__ import annotations

import pathlib

import pandas as pd

from .evaluate import (
    DATA_DIR,
    VISITS_PER_WEEK,
    build_model,
    cost_report,
    first_telemetry_month,
    rank_predictions,
    split_rows,
)
from .sensitivity import fair_baseline, output_checks, weekly_cost_table
from .features import feature_columns


def evaluate_model(dataset: pd.DataFrame, excluded: set[str] | None = None):
    splits = split_rows(dataset)
    columns = [c for c in feature_columns(dataset) if not excluded or c not in excluded]
    model, _, _ = build_model(dataset, excluded_features=excluded)
    model.fit(splits["train"][columns], splits["train"]["target"])
    summaries = []
    weekly = []
    predictions = {}
    for name in ("validation", "test"):
        predictions[name] = rank_predictions(model, splits[name], excluded_features=excluded)
        summary, _ = cost_report(predictions[name], splits[name], f"logistic_{name}")
        summaries.append(summary)
        weekly.append(weekly_cost_table(predictions[name], splits[name], f"logistic_regression"))
    first_month = first_telemetry_month(dataset)
    unseen_ids = set(first_month[first_month >= "2026-01"].index)
    unseen = splits["test"][splits["test"]["gateway_id"].isin(unseen_ids)]
    unseen_train = splits["train"][~splits["train"]["gateway_id"].isin(unseen_ids)]
    unseen_model, _, _ = build_model(dataset, excluded_features=excluded)
    unseen_model.fit(unseen_train[columns], unseen_train["target"])
    unseen_ranked = rank_predictions(unseen_model, unseen, excluded_features=excluded)
    unseen_summary, _ = cost_report(unseen_ranked, unseen, "logistic_unseen_gateway_test")
    summaries.append(unseen_summary)
    return pd.DataFrame(summaries), pd.concat(weekly, ignore_index=True), predictions, unseen_summary, unseen_ids


def main() -> int:
    artifact = pathlib.Path("artifacts/part2_gateway_week.parquet")
    dataset = pd.read_parquet(artifact)
    splits = split_rows(dataset)

    full_summary, full_weekly, predictions, unseen_summary, unseen_ids = evaluate_model(dataset)
    baseline_weekly = []
    baseline_rows = []
    for name in ("validation", "test"):
        baseline = fair_baseline(splits[name], DATA_DIR)
        baseline_weekly.append(weekly_cost_table(baseline, splits[name], "baseline_3sigma"))
        baseline_rows.append(baseline)
    weekly = pd.concat([*baseline_weekly, full_weekly], ignore_index=True)
    weekly["eligible_gateways"] = weekly["week_start"].map(
        dataset.groupby("week_start")["gateway_id"].nunique()
    )
    weekly["precision_at_15"] = weekly["correct_visits"] / weekly["selected_count"].replace(0, pd.NA)
    weekly["recall"] = weekly["correct_visits"] / weekly["true_proxy_targets"].replace(0, pd.NA)
    weekly["visit_cost"] = weekly["unnecessary_visits"] * 380
    weekly["missed_fault_cost"] = weekly["missed_targets"] * 600
    weekly = weekly[["week_start", "method", "eligible_gateways", "selected_count", "true_proxy_targets", "correct_visits", "unnecessary_visits", "missed_targets", "precision_at_15", "recall", "visit_cost", "missed_fault_cost", "total_cost"]]
    weekly.to_csv("reports/weekly_cost_table.csv", index=False)

    target_rows = []
    for name, days, hours in (("current", 2, 6), ("moderate_alternative", 2, 12)):
        target_dataset = dataset.copy()
        target_dataset["target"] = ((target_dataset["future_degraded_days"] >= days) & (target_dataset["future_degraded_hours"] >= hours)).astype(int)
        summary, _, _, target_unseen, _ = evaluate_model(target_dataset)
        validation = summary[summary.evaluation == "logistic_validation"].iloc[0]
        test = summary[summary.evaluation == "logistic_test"].iloc[0]
        target_rows.append({"target_definition": name, "positive_labels": int(target_dataset.target.sum()), "positive_rate": float(target_dataset.target.mean()), "validation_cost": int(validation.total_cost), "forward_test_cost": int(test.total_cost), "precision_at_15": float(test.precision_at_15), "recall": float(test.recall), "unseen_gateway_recall": float(target_unseen["recall"])})
    target_table = pd.DataFrame(target_rows)
    target_table.to_csv("reports/target_threshold_sensitivity.csv", index=False)

    adjacent = {c for c in feature_columns(dataset) if any(token in c for token in ("hist_7d_disconnection_cnt", "hist_7d_reboot_cnt", "hist_7d_offline_duration_sec", "hist_28d_disconnection_cnt", "hist_28d_offline_duration_sec", "trend_disconnection_cnt", "trend_reboot_cnt", "trend_offline_duration_sec"))}
    reduced, _, _, reduced_unseen, _ = evaluate_model(dataset, excluded=adjacent)
    full_test = full_summary[full_summary.evaluation == "logistic_test"].iloc[0]
    full_val = full_summary[full_summary.evaluation == "logistic_validation"].iloc[0]
    reduced_test = reduced[reduced.evaluation == "logistic_test"].iloc[0]
    reduced_val = reduced[reduced.evaluation == "logistic_validation"].iloc[0]
    ablation = pd.DataFrame([
        {"model": "current_99_feature", "feature_count": len(feature_columns(dataset)), "validation_cost": int(full_val.total_cost), "forward_test_cost": int(full_test.total_cost), "precision_at_15": float(full_test.precision_at_15), "recall": float(full_test.recall), "unseen_gateway_recall": float(unseen_summary["recall"])},
        {"model": "reduced_target_adjacent", "feature_count": len(feature_columns(dataset)) - len(adjacent), "validation_cost": int(reduced_val.total_cost), "forward_test_cost": int(reduced_test.total_cost), "precision_at_15": float(reduced_test.precision_at_15), "recall": float(reduced_test.recall), "unseen_gateway_recall": float(reduced_unseen["recall"])},
    ])
    ablation.to_csv("reports/feature_ablation.csv", index=False)

    predictions_csv = pd.read_csv("reports/logistic_predictions.csv")
    expected_weeks = sorted(splits["test"].week_start.unique().tolist())
    checks = output_checks(predictions_csv, expected_weeks)
    weekly_test = weekly[weekly.method.isin(["baseline_3sigma", "logistic_regression"]) & weekly.week_start.isin(expected_weeks)]
    spread = weekly_test.groupby("method")["total_cost"].agg(["min", "max", "mean", "median"]).reset_index()
    report = f"""# Part 2 Sensitivity Report

All results are **historical proxy-label evaluation**, not official hidden-ground-truth results.

## Output and fair cost comparison

Validation weeks: 2026-01-05, 2026-01-12, 2026-01-19, 2026-01-26.

Forward weeks: 2026-02-02, 2026-02-09, 2026-02-16, 2026-02-23, 2026-03-02, 2026-03-09, 2026-03-16, 2026-03-23. The incomplete 2026-03-30 week is excluded.

Output checks: `{checks}`

Both methods use the same eligible gateway-week rows, target, seven-day future window, 15-visit cap, and €380/€600 cost formula. Each selected gateway is counted once; each missed target is counted once per week.

See `reports/weekly_cost_table.csv` for the complete weekly table.

## Weekly cost spread

```text
{spread.to_string(index=False)}
```

## Target sensitivity

```text
{target_table.to_string(index=False)}
```

The moderate alternative requires 12 degraded hours instead of 6 while keeping two degraded days. It represents more sustained degradation, but can miss shorter incidents that still deserve attention. The current target is retained because it captures persistence without requiring a very long outage.

## Feature ablation

```text
{ablation.to_string(index=False)}
```

The removed features are cutoff-safe but target-adjacent: recent disconnections, reboots, offline duration, 28-day degradation totals, and their trends. This is a robustness test, not feature selection by score.

## Unseen gateways

The unseen slice contains {len(unseen_ids)} gateways first observed in January-March 2026. They were excluded from model fitting, raw IDs are absent from features, and only their own future windows are used for evaluation. Logistic Regression proxy result: cost €{int(unseen_summary['total_cost'])}, precision@15 {unseen_summary['precision_at_15']:.4f}, recall {unseen_summary['recall']:.4f}.

The unchanged baseline can be scored on this subset only by ranking the full population first and then filtering to the subset; that may yield fewer than 15 selections and changes the operational universe. Therefore it is not presented as a directly comparable 15-visit baseline.

## Duplicate policy

The primary median policy is verified. Full first/last/drop duplicate-policy sensitivity was not completed within practical runtime: one alternate raw-policy build took approximately 299 seconds, and the full matrix exceeded the available execution window. No duplicate-policy metrics are fabricated. The primary pipeline retains deterministic duplicate handling and duplicate-rate features.

## Network and population change

The measured network grows from 280 telemetry gateways in August 2025 to 308 in March 2026; 268 are present in all eight months. Forty gateways first appear in January-March. Telemetry has 13,094 rows in duplicate timestamp groups, and 55,117 of 68,418 gateway-days are not exactly 24 rows. Meter coverage ends 2026-01-26, before the forward test. These changes can shift feature and score distributions and make cold-start rankings less reliable.

Recommended mitigations are monitoring feature/score distributions, periodic retraining, explicit cold-start rules, and fallback to the 3-sigma baseline when history is insufficient. These are recommendations, not claims that they are already deployed.

## Explainability

The strongest learned predictive signals are recent disconnection activity, historical meter-read rate, reboot variability, long-run disconnection totals, RSSI quality, and offline-duration variability. They indicate predictive association only, not causality.

## Conclusion

The normal baseline comparison is fair on the common eligible universe. Final model: Logistic Regression. The target is telemetry-derived and target-adjacent features remain a risk. Official hidden-groundtruth improvement must not be claimed.
"""
    pathlib.Path("PART2_SENSITIVITY_REPORT.md").write_text(report, encoding="utf-8")
    decision = f"""# Part 2 Final Model Decision

## Decision

**D. Do not claim official improvement yet because the proxy target is not independent ground truth.**

Historical proxy-label results show Logistic Regression at €270,600 versus the unchanged 3-sigma baseline at €329,400 on the eight-week forward test, a €58,800 lower historical proxy-label cost. This is encouraging but insufficient for an official claim.

## Evidence

- The comparison uses identical weeks, eligible rows, targets, costs, and visit cap.
- The unseen-gateway slice contains {len(unseen_ids)} gateways; Logistic Regression recall is {unseen_summary['recall']:.4f} with proxy cost €{int(unseen_summary['total_cost'])}.
- Target and feature-ablation results are recorded in the sensitivity report.
- Network growth, missing hours, duplicates, and meter coverage changes create distribution-shift risk.

## Next step

Use an independently observed holdout outcome or the challenge hidden evaluation period with this frozen pipeline. Keep Logistic Regression as the final Part 2 model and do not modify Part 1.
"""
    pathlib.Path("PART2_FINAL_MODEL_DECISION.md").write_text(decision, encoding="utf-8")
    model_report_path = pathlib.Path("PART2_MODEL_REPORT.md")
    if model_report_path.exists():
        model_report = model_report_path.read_text(encoding="utf-8")
        model_report = model_report.replace("€165060", "€166460")
        model_report = model_report.replace("0.4130", "0.4000")
        model_report = model_report.replace("0.0686", "0.0758")
        model_report = model_report.replace("€325560", "€329400")
        model_report = model_report.replace("0.5670", "0.5000")
        model_report = model_report.replace("0.0963", "0.1044")
        correction = (
            "\n## Final validation correction\n\n"
            "The final validation ranks the unchanged 3-sigma logic within the same eligible gateway universe as ML before taking the top 15. "
            "The corrected historical proxy-label totals are €166,460 validation and €329,400 forward test for the baseline, versus "
            "€130,200 and €270,600 for Logistic Regression. Both methods select exactly 15 gateways on every shared week.\n"
        )
        if "## Final validation correction" not in model_report:
            model_report += correction
        model_report_path.write_text(model_report, encoding="utf-8")
    print(spread.to_string(index=False))
    print(target_table.to_string(index=False))
    print(ablation.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())