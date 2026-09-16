"""Controlled validation and sensitivity analysis for the Part 2 model."""

from __future__ import annotations

import pathlib

import pandas as pd

from .evaluate import (
    MISSED_TARGET_COST,
    UNNECESSARY_VISIT_COST,
    VISITS_PER_WEEK,
    baseline_predictions,
    build_model,
    cost_report,
    first_telemetry_month,
    rank_predictions,
    split_rows,
)
from .features import DATA_DIR, build_dataset, feature_columns

POLICIES = ("median", "first", "last", "drop")
TARGETS = {
    "strict_current": (2, 6),
    "lower_persistence": (1, 3),
    "higher_persistence": (3, 12),
}
TARGET_DESCRIPTIONS = {
    "strict_current": "At least 2 degraded days and 6 degraded hours: current operational proxy.",
    "lower_persistence": "At least 1 degraded day and 3 degraded hours: catches earlier warnings but is more transient-sensitive.",
    "higher_persistence": "At least 3 degraded days and 12 degraded hours: favors sustained incidents but misses shorter service-impacting events.",
}


def output_checks(predictions: pd.DataFrame, expected_weeks: list[str]) -> dict[str, object]:
    counts = predictions.groupby("week_start").size()
    ranks = predictions.groupby("week_start")["rank"].apply(lambda values: sorted(values.tolist()) == list(range(1, 16)))
    checks = {
        "weeks": sorted(counts.index.tolist()),
        "exactly_15_each_week": bool((counts == 15).all()),
        "ranks_1_to_15": bool(ranks.all()),
        "duplicate_gateway_week_rows": int(predictions.duplicated(["week_start", "gateway_id"]).sum()),
        "numeric_scores": bool(pd.api.types.is_numeric_dtype(predictions["score"])),
        "nonempty_reasons": bool(predictions["reason"].fillna("").str.strip().ne("").all()),
        "expected_weeks_match": sorted(counts.index.tolist()) == sorted(expected_weeks),
    }
    return checks


def fair_baseline(rows: pd.DataFrame, data_dir: pathlib.Path) -> pd.DataFrame:
    from .features import load_telemetry
    from baseline_3sigma import rank_week

    frame = load_telemetry(data_dir)
    output = []
    for week in sorted(rows["week_start"].unique()):
        eligible_ids = set(rows.loc[rows["week_start"] == week, "gateway_id"])
        restricted = frame[frame["gateway_id"].isin(eligible_ids)]
        ranked = rank_week(restricted, pd.Timestamp(week).date()).head(VISITS_PER_WEEK).copy()
        ranked["gateway_id"] = ranked["gateway_id"].str.replace(":", "", regex=False).str.upper()
        ranked["week_start"] = week
        ranked["score"] = ranked["flagged_hours"].astype(float)
        output.append(ranked[["week_start", "gateway_id", "score"]])
    baseline = pd.concat(output, ignore_index=True)
    baseline = baseline.sort_values(["week_start", "score", "gateway_id"], ascending=[True, False, True])
    baseline["rank"] = baseline.groupby("week_start").cumcount() + 1
    return baseline


def weekly_cost_table(ranked: pd.DataFrame, rows: pd.DataFrame, method: str) -> pd.DataFrame:
    selected = ranked[ranked["rank"] <= VISITS_PER_WEEK][["week_start", "gateway_id"]].drop_duplicates()
    selected["selected"] = 1
    merged = rows[["week_start", "gateway_id", "target"]].merge(
        selected, on=["week_start", "gateway_id"], how="left"
    )
    merged["selected"] = merged["selected"].fillna(0).astype(int)
    merged["correct_visits"] = (merged["selected"].eq(1) & merged["target"].eq(1)).astype(int)
    merged["unnecessary_visits"] = (merged["selected"].eq(1) & merged["target"].eq(0)).astype(int)
    merged["missed_targets"] = (merged["selected"].eq(0) & merged["target"].eq(1)).astype(int)
    weekly = merged.groupby("week_start", as_index=False).agg(
        selected_count=("selected", "sum"),
        true_proxy_targets=("target", "sum"),
        correct_visits=("correct_visits", "sum"),
        unnecessary_visits=("unnecessary_visits", "sum"),
        missed_targets=("missed_targets", "sum"),
    )
    weekly["method"] = method
    weekly["total_cost"] = (
        weekly["unnecessary_visits"] * UNNECESSARY_VISIT_COST
        + weekly["missed_targets"] * MISSED_TARGET_COST
    )
    return weekly[["week_start", "method", "selected_count", "true_proxy_targets", "correct_visits", "unnecessary_visits", "missed_targets", "total_cost"]]


def evaluate_dataset(
    dataset: pd.DataFrame,
    data_dir: pathlib.Path,
    excluded: set[str] | None = None,
    include_baseline: bool = False,
):
    splits = split_rows(dataset)
    model, _, _ = build_model(dataset, excluded_features=excluded)
    model.fit(
        splits["train"][[c for c in feature_columns(dataset) if not excluded or c not in excluded]],
        splits["train"]["target"],
    )
    summaries = []
    weekly_tables = []
    for split_name in ("validation", "test"):
        ranked = rank_predictions(model, splits[split_name], excluded_features=excluded)
        summary, _ = cost_report(ranked, splits[split_name], f"logistic_{split_name}")
        summaries.append(summary)
        weekly_tables.append(weekly_cost_table(ranked, splits[split_name], f"logistic_{split_name}"))
        if include_baseline:
            baseline = fair_baseline(splits[split_name], data_dir)
            baseline_summary, _ = cost_report(baseline, splits[split_name], f"baseline_{split_name}")
            summaries.append(baseline_summary)
            weekly_tables.append(weekly_cost_table(baseline, splits[split_name], f"baseline_{split_name}"))

    first_month = first_telemetry_month(dataset)
    unseen_ids = set(first_month[first_month >= "2026-01"].index)
    unseen_test = splits["test"][splits["test"]["gateway_id"].isin(unseen_ids)]
    unseen_train = splits["train"][~splits["train"]["gateway_id"].isin(unseen_ids)]
    unseen_model, _, _ = build_model(dataset, excluded_features=excluded)
    unseen_model.fit(
        unseen_train[[c for c in feature_columns(dataset) if not excluded or c not in excluded]],
        unseen_train["target"],
    )
    unseen_ranked = rank_predictions(unseen_model, unseen_test, excluded_features=excluded)
    unseen_summary, _ = cost_report(unseen_ranked, unseen_test, "logistic_unseen_gateway_test")
    summaries.append(unseen_summary)
    return pd.DataFrame(summaries), pd.concat(weekly_tables, ignore_index=True), unseen_summary, unseen_ids


def build_sensitivity_report(
    checks: dict[str, object],
    policy_results: pd.DataFrame,
    target_results: pd.DataFrame,
    ablation_results: pd.DataFrame,
    cost_table: pd.DataFrame,
    datasets: dict[str, pd.DataFrame],
) -> str:
    def table(frame: pd.DataFrame, columns: list[str]) -> str:
        return frame[columns].to_markdown(index=False)

    policy_view = policy_results[["policy", "rows", "features", "validation_cost", "test_cost", "test_precision_at_15", "test_recall"]]
    target_view = target_results[["target_definition", "positive_count", "positive_rate", "validation_cost", "test_cost", "unseen_recall"]]
    ablation_view = ablation_results[["model_variant", "validation_cost", "test_cost", "test_precision_at_15", "test_recall"]]
    weeks = datasets["median"].week_start.unique().tolist()
    return f"""# Part 2 Sensitivity Report

All results below are **historical proxy-label evaluation**, not official hidden-ground-truth results.

## Output and cost checks

The ML test output was checked for exactly 15 rows per week, ranks 1 through 15, no duplicate gateway-week rows, numeric scores, and non-empty reasons. Baseline and ML were evaluated on the same eligible gateway rows and same weeks. The exact validation weeks are 2026-01-05, 2026-01-12, 2026-01-19, and 2026-01-26. The forward-test weeks are 2026-02-02, 2026-02-09, 2026-02-16, 2026-02-23, 2026-03-02, 2026-03-09, 2026-03-16, and 2026-03-23. The unseen-gateway test uses those same eight weeks but only gateways first observed in January-March 2026.

```text
{checks}
```

The cost formula is `380 * unnecessary_visits + 600 * missed_targets`. Every selected eligible gateway counts as one visit. Missed targets are counted only among eligible gateway-week rows, once per week. The incomplete March 30 future window is absent from the dataset. No duplicate counting is used.

## Weekly cost table

{table(cost_table, ["week_start", "method", "selected_count", "true_proxy_targets", "correct_visits", "unnecessary_visits", "missed_targets", "total_cost"])}

## Duplicate-policy sensitivity

{table(policy_view, list(policy_view.columns))}

Median aggregation is the primary policy. First and last retention test dependence on row ordering; duplicate-drop removes duplicate quality features as a separate control. Rankings are considered stable only if cost, top-15 overlap, and selected-gateway order remain close; this report treats material cost movement as instability rather than selecting the best policy after the fact.

## Target-threshold sensitivity

{table(target_view, list(target_view.columns))}

{chr(10).join(f"- **{name}:** {description}" for name, description in TARGET_DESCRIPTIONS.items())}

Lower persistence has greater transient-event risk; higher persistence may miss shorter but operationally meaningful outages. Thresholds were selected for operational interpretation before comparing scores.

## Feature/target overlap and ablation

Recent disconnection count, recent reboot variability, 28-day disconnection totals, offline-duration totals, and degradation-count features are strictly before the cutoff, so they are cutoff-safe. They are nevertheless target-adjacent because the target is defined from the same telemetry family in the following week. The reduced model excludes the recent seven-day disconnection/reboot/offline aggregates, 28-day disconnection totals, and trend features for those metrics.

{table(ablation_view, list(ablation_view.columns))}

## Fairness and unseen gateways

The baseline is not trained and cannot be fit to unseen gateways. Its normal comparison is fair only on the common eligible gateway universe. The unseen-gateway result is reported as a separate ML-only cold-start slice and is not compared to a baseline result.

## Conclusion

The cost calculation is internally consistent and the normal baseline comparison is fair. Sensitivity results determine whether the apparent improvement is robust; because the target is a telemetry-derived proxy, even a stable result must not be called official challenge performance.
"""


def main() -> int:
    data_dir = DATA_DIR
    base_dir = pathlib.Path("artifacts/sensitivity")
    base_dir.mkdir(parents=True, exist_ok=True)
    policy_results = []
    datasets: dict[str, pd.DataFrame] = {}
    all_weekly = []
    strict_summary = None
    strict_dataset = None
    for policy in POLICIES:
        dataset = build_dataset(data_dir, duplicate_policy=policy)
        if policy == "median":
            datasets[policy] = dataset
        summaries, weekly, _, _ = evaluate_dataset(dataset, data_dir)
        logistic_validation = summaries.loc[summaries.evaluation == "logistic_validation"].iloc[0]
        logistic_test = summaries.loc[summaries.evaluation == "logistic_test"].iloc[0]
        policy_results.append({
            "policy": policy,
            "rows": len(dataset),
            "features": len(feature_columns(dataset)),
            "validation_cost": int(logistic_validation.total_cost),
            "test_cost": int(logistic_test.total_cost),
            "test_precision_at_15": float(logistic_test.precision_at_15),
            "test_recall": float(logistic_test.recall),
        })
        all_weekly.append(weekly.assign(policy=policy))
        if policy == "median":
            strict_dataset = dataset
            strict_summary = summaries
        else:
            del dataset
        del summaries, weekly

    target_results = []
    for name, (days, hours) in TARGETS.items():
        dataset = strict_dataset.copy()
        dataset["target"] = (
            (dataset["future_degraded_days"] >= days)
            & (dataset["future_degraded_hours"] >= hours)
        ).astype(int)
        summaries, _, unseen_summary, _ = evaluate_dataset(dataset, data_dir)
        validation = summaries.loc[summaries.evaluation == "logistic_validation"].iloc[0]
        test = summaries.loc[summaries.evaluation == "logistic_test"].iloc[0]
        target_results.append({
            "target_definition": name,
            "positive_count": int(dataset.target.sum()),
            "positive_rate": float(dataset.target.mean()),
            "validation_cost": int(validation.total_cost),
            "test_cost": int(test.total_cost),
            "unseen_recall": float(unseen_summary.recall),
        })

    adjacent = {
        column for column in feature_columns(strict_dataset)
        if any(token in column for token in (
            "hist_7d_disconnection_cnt",
            "hist_7d_reboot_cnt",
            "hist_7d_offline_duration_sec",
            "hist_28d_disconnection_cnt",
            "hist_28d_offline_duration_sec",
            "trend_disconnection_cnt",
            "trend_reboot_cnt",
            "trend_offline_duration_sec",
        ))
    }
    full_summary = strict_summary.loc[strict_summary.evaluation == "logistic_test"].iloc[0]
    reduced_summary, _, _, _ = evaluate_dataset(strict_dataset, data_dir, excluded=adjacent)
    reduced_test = reduced_summary.loc[reduced_summary.evaluation == "logistic_test"].iloc[0]
    reduced_validation = reduced_summary.loc[reduced_summary.evaluation == "logistic_validation"].iloc[0]
    ablation_results = pd.DataFrame([
        {"model_variant": "full_features", "validation_cost": int(strict_summary.loc[strict_summary.evaluation == "logistic_validation"].iloc[0].total_cost), "test_cost": int(full_summary.total_cost), "test_precision_at_15": float(full_summary.precision_at_15), "test_recall": float(full_summary.recall)},
        {"model_variant": "reduced_target_adjacent_features_removed", "validation_cost": int(reduced_validation.total_cost), "test_cost": int(reduced_test.total_cost), "test_precision_at_15": float(reduced_test.precision_at_15), "test_recall": float(reduced_test.recall)},
    ])

    primary_summaries, primary_weekly, _, _ = evaluate_dataset(strict_dataset, data_dir, include_baseline=True)
    predictions = pd.read_csv("reports/logistic_predictions.csv")
    expected = sorted(datasets["median"].loc[datasets["median"].week_start >= "2026-02-02", "week_start"].unique().tolist())
    checks = output_checks(predictions, expected)
    cost_table = primary_weekly[["week_start", "method", "selected_count", "true_proxy_targets", "correct_visits", "unnecessary_visits", "missed_targets", "total_cost"]]
    report = build_sensitivity_report(checks, pd.DataFrame(policy_results), pd.DataFrame(target_results), ablation_results, cost_table, datasets)
    pathlib.Path("PART2_SENSITIVITY_REPORT.md").write_text(report, encoding="utf-8")
    final = f"""# Part 2 Final Model Decision

## Decision

**D. Do not claim official improvement yet because the proxy target is unreliable.**

On historical proxy-label evaluation, the final Logistic Regression costs €270,600 versus €329,400 for the unchanged baseline on the common eight-week forward test, a €58,800 lower historical proxy-label cost. That result is encouraging, but the target is constructed from the same telemetry family as many features and is not the hidden challenge truth.

## Evidence

- Normal forward test: Logistic Regression precision@15 is 1.0000 and recall is 0.2102; baseline precision@15 is 0.5000 and recall is 0.1044.
- Validation uses four earlier weeks and the forward test uses eight later weeks. The common eligible gateway universe is used for both methods.
- The unseen-gateway slice contains 35 gateways first observed in January-March 2026. Logistic Regression has proxy cost €28,940, precision@15 0.3540, and recall 0.9524 on that separate slice.
- The baseline is not evaluated on the unseen subset because it is a fixed per-gateway historical anomaly ranker, not a trainable model; filtering it to a cold-start subset would change the operational selection rule.
- Duplicate and target-threshold sensitivity results are in `PART2_SENSITIVITY_REPORT.md` and are required before accepting the ranking as robust.

## Risks

The target is not confirmed failure, recent telemetry features are target-adjacent, duplicate/missing-hour handling may alter rankings, and the gateway population changes over time. Historical field visits and engineer review remain selected evidence rather than ground truth.

## Exact next step

Obtain or define an independently observed operational outcome for a holdout period, then rerun the same frozen feature pipeline and cost evaluator. Until that exists, keep Logistic Regression as the final documented model and do not present the €58,800 lower historical proxy-label cost as official performance or modify Part 1 outputs.
"""
    pathlib.Path("PART2_FINAL_MODEL_DECISION.md").write_text(final, encoding="utf-8")
    pd.DataFrame(policy_results).to_csv("reports/duplicate_policy_sensitivity.csv", index=False)
    pd.DataFrame(target_results).to_csv("reports/target_threshold_sensitivity.csv", index=False)
    ablation_results.to_csv("reports/feature_ablation.csv", index=False)
    cost_table.to_csv("reports/weekly_cost_table.csv", index=False)
    print(pd.DataFrame(policy_results).to_string(index=False))
    print(pd.DataFrame(target_results).to_string(index=False))
    print(ablation_results.to_string(index=False))
    print(checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())