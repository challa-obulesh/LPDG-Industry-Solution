"""Train and evaluate the Part 2 logistic ranking model."""

from __future__ import annotations

import argparse
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import DATA_DIR, feature_columns, normalize_gateway_id

VISITS_PER_WEEK = 15
UNNECESSARY_VISIT_COST = 380
MISSED_TARGET_COST = 600
TRAIN_END = "2025-12-29"
VALIDATION_START = "2026-01-05"
VALIDATION_END = "2026-01-26"
TEST_START = "2026-02-02"
TEST_END = "2026-03-23"


def split_rows(dataset: pd.DataFrame) -> dict[str, pd.DataFrame]:
    weeks = pd.to_datetime(dataset["week_start"])
    train = dataset[weeks <= pd.Timestamp(TRAIN_END)].copy()
    validation = dataset[(weeks >= pd.Timestamp(VALIDATION_START)) & (weeks <= pd.Timestamp(VALIDATION_END))].copy()
    test = dataset[(weeks >= pd.Timestamp(TEST_START)) & (weeks <= pd.Timestamp(TEST_END))].copy()
    return {"train": train, "validation": validation, "test": test}


def first_telemetry_month(dataset: pd.DataFrame) -> pd.Series:
    return dataset.groupby("gateway_id")["week_start"].min().map(lambda value: str(value)[:7])


def build_model(
    dataset: pd.DataFrame,
    excluded_features: set[str] | None = None,
) -> tuple[Pipeline, list[str], list[str]]:
    columns = [
        column for column in feature_columns(dataset)
        if not excluded_features or column not in excluded_features
    ]
    categorical = [column for column in columns if not pd.api.types.is_numeric_dtype(dataset[column])]
    numeric = [column for column in columns if column not in categorical]
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", Pipeline([("scale", StandardScaler())]), numeric),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
        ],
        remainder="drop",
    )
    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )
    return model, numeric, categorical


def rank_predictions(
    model: Pipeline,
    rows: pd.DataFrame,
    excluded_features: set[str] | None = None,
) -> pd.DataFrame:
    columns = [
        column for column in feature_columns(rows)
        if not excluded_features or column not in excluded_features
    ]
    scores = model.predict_proba(rows[columns])[:, 1]
    ranked = rows.copy()
    ranked["score"] = scores
    ranked = ranked.sort_values(["week_start", "score", "gateway_id"], ascending=[True, False, True])
    ranked["rank"] = ranked.groupby("week_start").cumcount() + 1
    return ranked


_BASELINE_FRAMES: dict[str, pd.DataFrame] = {}


def baseline_predictions(rows: pd.DataFrame, data_dir: pathlib.Path) -> pd.DataFrame:
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from baseline_3sigma import load, rank_week

    cache_key = str(data_dir.resolve())
    if cache_key not in _BASELINE_FRAMES:
        _BASELINE_FRAMES[cache_key] = load(data_dir)
    frame = _BASELINE_FRAMES[cache_key]
    output = []
    for week in sorted(rows["week_start"].unique()):
        monday = pd.Timestamp(week, tz="UTC").date()
        eligible_ids = set(rows.loc[rows["week_start"] == week, "gateway_id"])
        ranked = rank_week(frame[frame["gateway_id"].isin(eligible_ids)], monday).copy()
        ranked["gateway_id"] = normalize_gateway_id(ranked["gateway_id"])
        ranked = ranked.head(VISITS_PER_WEEK)
        ranked["week_start"] = week
        ranked["score"] = ranked["flagged_hours"].astype(float)
        output.append(ranked[["week_start", "gateway_id", "score"]])
    return pd.concat(output, ignore_index=True)


def cost_report(ranked: pd.DataFrame, label_rows: pd.DataFrame, name: str) -> tuple[dict[str, object], pd.DataFrame]:
    selected = ranked[ranked["rank"] <= VISITS_PER_WEEK][["week_start", "gateway_id"]].copy()
    selected["selected"] = 1
    merged = label_rows[["week_start", "gateway_id", "target"]].merge(
        selected, on=["week_start", "gateway_id"], how="left"
    )
    merged["selected"] = merged["selected"].fillna(0).astype(int)
    merged["unnecessary_visit"] = (merged["selected"].eq(1) & merged["target"].eq(0)).astype(int)
    merged["missed_target"] = (merged["selected"].eq(0) & merged["target"].eq(1)).astype(int)
    weekly = merged.groupby("week_start", as_index=False).agg(
        unnecessary_visits=("unnecessary_visit", "sum"),
        missed_targets=("missed_target", "sum"),
        positives=("target", "sum"),
        selected=("selected", "sum"),
    )
    weekly["cost"] = (
        weekly["unnecessary_visits"] * UNNECESSARY_VISIT_COST
        + weekly["missed_targets"] * MISSED_TARGET_COST
    )
    summary = {
        "evaluation": name,
        "weeks": int(len(weekly)),
        "rows": int(len(merged)),
        "total_cost": int(weekly["cost"].sum()),
        "cost_per_week": float(weekly["cost"].mean()),
        "unnecessary_visits": int(merged["unnecessary_visit"].sum()),
        "missed_targets": int(merged["missed_target"].sum()),
        "precision_at_15": float(precision_score(merged["target"], merged["selected"], zero_division=0)),
        "recall": float(recall_score(merged["target"], merged["selected"], zero_division=0)),
        "positive_targets": int(merged["target"].sum()),
    }
    return summary, weekly


def coefficients(model: Pipeline) -> pd.DataFrame:
    preprocessor = model.named_steps["preprocessor"]
    classifier = model.named_steps["classifier"]
    names = preprocessor.get_feature_names_out()
    values = classifier.coef_[0]
    report = pd.DataFrame({"feature": names, "coefficient": values})
    report["direction"] = np.where(report["coefficient"] >= 0, "raises score", "lowers score")
    report["absolute_coefficient"] = report["coefficient"].abs()
    report["interpretation"] = report.apply(
        lambda row: (
            "Higher values increase predicted persistent degradation risk."
            if row["coefficient"] >= 0
            else "Higher values decrease predicted persistent degradation risk."
        ),
        axis=1,
    )
    return report.sort_values("absolute_coefficient", ascending=False)


def _reason(model: Pipeline, row: pd.Series) -> str:
    feature_names = model.named_steps["preprocessor"].get_feature_names_out()
    transformed = model.named_steps["preprocessor"].transform(
        row[feature_columns(row.to_frame().T)].to_frame().T
    )
    transformed_array = transformed.toarray() if hasattr(transformed, "toarray") else np.asarray(transformed)
    contributions = (transformed_array * model.named_steps["classifier"].coef_[0]).ravel()
    positive = pd.DataFrame({"feature": feature_names, "contribution": contributions})
    positive = positive[positive["contribution"] > 0].sort_values("contribution", ascending=False).head(3)
    names = positive["feature"].str.replace("numeric__", "", regex=False).str.replace("categorical__", "", regex=False)
    if positive.empty:
        return "Proxy-risk ranking; no single positive feature contribution dominated this score."
    return "Proxy-risk ranking; this gateway was elevated by " + ", ".join(names.tolist())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=pathlib.Path, default=pathlib.Path("artifacts/part2_gateway_week.parquet"))
    parser.add_argument("--data", type=pathlib.Path, default=DATA_DIR)
    args = parser.parse_args()
    dataset = pd.read_parquet(args.dataset)
    splits = split_rows(dataset)
    model, _, _ = build_model(dataset)
    model.fit(splits["train"][feature_columns(dataset)], splits["train"]["target"])

    out_dir = pathlib.Path("reports")
    model_dir = pathlib.Path("models")
    out_dir.mkdir(exist_ok=True)
    model_dir.mkdir(exist_ok=True)
    joblib.dump(model, model_dir / "logistic_regression.joblib")

    predictions = {}
    all_summaries = []
    all_weekly = []
    for split_name in ("validation", "test"):
        predictions[split_name] = rank_predictions(model, splits[split_name])
        summary, weekly = cost_report(predictions[split_name], splits[split_name], f"logistic_{split_name}")
        all_summaries.append(summary)
        weekly["evaluation"] = summary["evaluation"]
        all_weekly.append(weekly)
        baseline = baseline_predictions(splits[split_name], args.data)
        baseline["rank"] = baseline.groupby("week_start").cumcount() + 1
        baseline_summary, baseline_weekly = cost_report(baseline, splits[split_name], f"baseline_{split_name}")
        all_summaries.append(baseline_summary)
        baseline_weekly["evaluation"] = baseline_summary["evaluation"]
        all_weekly.append(baseline_weekly)

    new_gateway_month = first_telemetry_month(dataset)
    unseen_ids = set(new_gateway_month[new_gateway_month >= "2026-01"].index)
    unseen_test = splits["test"][splits["test"]["gateway_id"].isin(unseen_ids)].copy()
    unseen_train = splits["train"][~splits["train"]["gateway_id"].isin(unseen_ids)].copy()
    unseen_model, _, _ = build_model(dataset)
    unseen_model.fit(unseen_train[feature_columns(dataset)], unseen_train["target"])
    unseen_ranked = rank_predictions(unseen_model, unseen_test)
    unseen_summary, unseen_weekly = cost_report(unseen_ranked, unseen_test, "logistic_unseen_gateway_test")
    all_summaries.append(unseen_summary)
    unseen_weekly["evaluation"] = unseen_summary["evaluation"]
    all_weekly.append(unseen_weekly)

    coefficient_report = coefficients(model)
    coefficient_report.to_csv(out_dir / "feature_importance.csv", index=False)
    pd.DataFrame(all_summaries).to_csv(out_dir / "part2_metrics.csv", index=False)
    pd.concat(all_weekly, ignore_index=True).to_csv(out_dir / "part2_weekly_metrics.csv", index=False)

    test_predictions = predictions["test"].copy()
    test_predictions["reason"] = test_predictions.apply(lambda row: _reason(model, row), axis=1)
    test_predictions[test_predictions["rank"] <= VISITS_PER_WEEK][["week_start", "rank", "gateway_id", "score", "reason"]].to_csv(
        out_dir / "logistic_predictions.csv", index=False
    )
    report = make_model_report(dataset, splits, all_summaries, coefficient_report, len(unseen_ids), unseen_summary)
    pathlib.Path("PART2_MODEL_REPORT.md").write_text(report, encoding="utf-8")
    print(pd.DataFrame(all_summaries).to_string(index=False))
    print(f"train_rows={len(splits['train'])} validation_rows={len(splits['validation'])} test_rows={len(splits['test'])}")
    print(f"gateways={dataset.gateway_id.nunique()} features={len(feature_columns(dataset))} unseen_gateways={len(unseen_ids)}")
    return 0


def make_model_report(dataset, splits, summaries, coefficient_report, unseen_count, unseen_summary) -> str:
    metrics = pd.DataFrame(summaries)
    rows = []
    for _, row in metrics.iterrows():
        rows.append(f"| {row['evaluation']} | {int(row['rows'])} | {int(row['weeks'])} | €{int(row['total_cost'])} | {row['precision_at_15']:.4f} | {row['recall']:.4f} |")
    top = coefficient_report.head(10)[["feature", "coefficient", "direction", "interpretation"]].to_string(index=False)
    return f"""# Part 2 Model Report

## Scope

This is a development evaluation against the historical proxy label `needs_visit`. It is not hidden final ground truth. Field-visit outcomes and engineer review were not used as labels or features. Part 1 files remain unchanged.

## Target and split

The target is 1 when the complete seven days after Monday 00:00 UTC contain at least 84 observed gateway-hours, degraded observations on at least two distinct days, and at least six degraded hours. A degraded hour has `offline_duration_sec >= 3600`, `disconnection_cnt >= 3`, or `reboot_cnt >= 1`. Features use only the preceding 28 days, strictly before cutoff.

Training ends 2025-12-29. Validation is 2026-01-05 through 2026-01-26. Test is 2026-02-02 through 2026-03-23. The incomplete 2026-03-30 week is excluded. The unseen-gateway slice contains {unseen_count} gateways first observed in January-March 2026.

## Dataset summary

- Rows: {len(dataset)}
- Gateways: {dataset.gateway_id.nunique()}
- Cutoff weeks: {dataset.week_start.nunique()}
- Features: {len([c for c in dataset.columns if c not in {'week_start','cutoff','gateway_id','target','label_available','future_observed_hours','future_degraded_hours','future_degraded_days'}])}
- Positive rate: {dataset.target.mean():.4f}
- Duplicate policy: group by normalized `(gateway_id, ts)` before aggregation; numeric telemetry values use the median and duplicate count/rate are retained as quality features.

## Cost results

Costs use €380 per unnecessary visit and €600 per missed proxy-positive gateway per week, with 15 selections per week.

| Evaluation | Rows | Weeks | Total cost | Precision@15 | Recall |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

These are proxy-label results only. `logistic_test` is the forward-time test result; `logistic_unseen_gateway_test` is the separate device-disjoint result. ML beats the baseline only on an evaluation slice where its measured total cost is lower; no claim is made about hidden challenge ground truth.

## Most influential coefficients

```text
{top}
```

Positive coefficients raise the proxy-risk score; negative coefficients lower it. The generated prediction reasons identify the strongest learned signals, but they summarize model contribution rather than proving causality.

## Leakage and validation checks

- No raw gateway ID is a feature.
- Future telemetry is used only for the label window.
- Future meter values, field-visit outcome/repair fields, engineer review, future decommission dates, and target-derived features are excluded.
- Gateway-week uniqueness and deterministic missing-value handling are asserted by the feature builder.
- The unseen-gateway result is reported separately: €{int(unseen_summary['total_cost'])} total proxy cost across {int(unseen_summary['weeks'])} weeks and {unseen_count} held-out gateways.

## Weaknesses and next improvement

The target is persistent telemetry degradation, not confirmed hardware failure. Duplicate/missing-hour handling and gateway churn remain material risks. The next improvement should be a predeclared threshold-sensitivity and duplicate-policy comparison, followed by inspection of high-cost disagreements against any newly available confirmed outcomes. Do not optimize the model before improving target validity.
"""


if __name__ == "__main__":
    raise SystemExit(main())