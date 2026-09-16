"""Build and validate the cutoff-safe Part 2 gateway-week dataset."""

from __future__ import annotations

import argparse
import pathlib
from typing import Iterable

import numpy as np
import pandas as pd

from .labels import label_future_week

DATA_DIR = pathlib.Path("03-challenge-data/data")
TELEMETRY_METRICS = [
    "offline_duration_sec",
    "disconnection_cnt",
    "reboot_cnt",
]
QUALITY_METRICS = [
    "rssi_good",
    "rssi_normal",
    "rssi_bad",
    "rscp_rsrp_good",
    "rscp_rsrp_normal",
    "rscp_rsrp_bad",
    "ecio_rsrq_good",
    "ecio_rsrq_normal",
    "ecio_rsrq_bad",
]
MASTER_CATEGORICALS = [
    "tenant",
    "site_type",
    "region",
    "hw_model",
    "antenna_type",
    "fw_version",
]
WINDOWS = (7, 14, 28)
FORBIDDEN_FEATURE_TOKENS = (
    "target",
    "future",
    "review",
    "outcome",
    "parts",
    "gateway_id",
    "visit",
)


def normalize_gateway_id(values: pd.Series) -> pd.Series:
    return values.astype("string").str.replace(":", "", regex=False).str.upper()


def load_telemetry(data_dir: pathlib.Path, duplicate_policy: str = "median") -> pd.DataFrame:
    if duplicate_policy not in {"median", "first", "last", "drop"}:
        raise ValueError(f"Unknown duplicate policy: {duplicate_policy}")
    columns = ["gateway_id", "ts_utc", *TELEMETRY_METRICS, *QUALITY_METRICS]
    frame = pd.read_parquet(data_dir / "telemetry", columns=columns)
    frame["gateway_id"] = normalize_gateway_id(frame["gateway_id"])
    frame["ts"] = pd.to_datetime(frame["ts_utc"], utc=True)
    frame = frame.drop(columns=["ts_utc"])
    frame = frame.sort_values(["gateway_id", "ts"], kind="mergesort")

    duplicate_group_size = frame.groupby(["gateway_id", "ts"], sort=False)["ts"].transform("size")
    frame["duplicate_group_size"] = duplicate_group_size.astype("int16")
    frame["duplicate_row"] = (duplicate_group_size > 1).astype("int8")

    numeric = [*TELEMETRY_METRICS, *QUALITY_METRICS]
    value_aggregation = "median" if duplicate_policy == "median" else "first"
    aggregations = {column: value_aggregation for column in numeric}
    aggregations["duplicate_group_size"] = "max" if duplicate_policy != "drop" else "first"
    aggregations["duplicate_row"] = "max" if duplicate_policy != "drop" else "first"
    clean = (
        frame.groupby(["gateway_id", "ts"], as_index=False, sort=False)
        .agg(aggregations)
        .sort_values(["gateway_id", "ts"], kind="mergesort")
    )
    if duplicate_policy == "drop":
        clean["duplicate_group_size"] = 1
        clean["duplicate_row"] = 0
    return clean


def load_master(data_dir: pathlib.Path) -> pd.DataFrame:
    master = pd.read_csv(data_dir / "gateway_master.csv", encoding="cp1252")
    master["gateway_id"] = normalize_gateway_id(master["gateway_id"])
    master["installed_on"] = pd.to_datetime(master["installed_on"], errors="coerce")
    master["fw_updated_on"] = pd.to_datetime(master["fw_updated_on"], errors="coerce")
    return master


def load_meter(data_dir: pathlib.Path) -> pd.DataFrame:
    meter = pd.read_csv(data_dir / "meter_read_success.csv")
    meter["gateway_id"] = normalize_gateway_id(meter["gateway_id"])
    meter["week_start"] = pd.to_datetime(meter["week_start"], utc=True)
    meter["read_rate"] = meter["meters_read"] / meter["meters_expected"]
    return meter


def monday_cutoffs() -> list[pd.Timestamp]:
    return list(pd.date_range("2025-09-01", "2026-03-23", freq="W-MON", tz="UTC"))


def _safe_master_features(master: pd.DataFrame, cutoff: pd.Timestamp) -> dict[str, object]:
    eligible = master[master["installed_on"].isna() | (master["installed_on"] <= cutoff.tz_localize(None))]
    if eligible.empty:
        return {column: "unknown" for column in MASTER_CATEGORICALS} | {"installed_age_days": 0.0}
    row = eligible.iloc[0]
    values = {column: str(row[column]) if pd.notna(row[column]) else "unknown" for column in MASTER_CATEGORICALS}
    installed = row["installed_on"]
    values["installed_age_days"] = (
        float((cutoff.tz_localize(None) - installed).days) if pd.notna(installed) else 0.0
    )
    return values


def _window_features(history: pd.DataFrame, cutoff: pd.Timestamp) -> dict[str, float]:
    result: dict[str, float] = {}
    for days in WINDOWS:
        start = cutoff - pd.Timedelta(days=days)
        window = history[(history["ts"] >= start) & (history["ts"] < cutoff)]
        prefix = f"hist_{days}d"
        result[f"{prefix}_observed_hours"] = float(len(window))
        result[f"{prefix}_observed_days"] = float(window["ts"].dt.floor("D").nunique())
        result[f"{prefix}_duplicate_rows"] = float(window["duplicate_row"].sum())
        result[f"{prefix}_duplicate_rate"] = float(
            window["duplicate_row"].mean() if len(window) else 0.0
        )
        for column in TELEMETRY_METRICS:
            values = window[column]
            result[f"{prefix}_{column}_mean"] = float(values.mean()) if len(values) else 0.0
            result[f"{prefix}_{column}_median"] = float(values.median()) if len(values) else 0.0
            result[f"{prefix}_{column}_std"] = float(values.std(ddof=0)) if len(values) else 0.0
            result[f"{prefix}_{column}_max"] = float(values.max()) if len(values) else 0.0
            result[f"{prefix}_{column}_sum"] = float(values.sum()) if len(values) else 0.0
        for column in QUALITY_METRICS:
            values = window[column]
            result[f"{prefix}_{column}_mean"] = float(values.mean()) if len(values) else 0.0
    recent = history[(history["ts"] >= cutoff - pd.Timedelta(days=7)) & (history["ts"] < cutoff)]
    older = history[(history["ts"] >= cutoff - pd.Timedelta(days=28)) & (history["ts"] < cutoff - pd.Timedelta(days=7))]
    for column in TELEMETRY_METRICS:
        result[f"trend_{column}_recent_minus_older"] = float(
            recent[column].mean() - older[column].mean()
            if len(recent) and len(older)
            else 0.0
        )
    return result


def _meter_features(meter: pd.DataFrame, gateway_id: str, cutoff: pd.Timestamp) -> dict[str, float]:
    history = meter[(meter["gateway_id"] == gateway_id) & (meter["week_start"] < cutoff)]
    history = history[history["week_start"] >= cutoff - pd.Timedelta(days=28)]
    recent = history[history["week_start"] >= cutoff - pd.Timedelta(days=7)]
    result = {
        "meter_28d_weeks": float(len(history)),
        "meter_28d_read_rate_mean": float(history["read_rate"].mean()) if len(history) else 0.0,
        "meter_28d_read_rate_min": float(history["read_rate"].min()) if len(history) else 0.0,
        "meter_28d_failure_count": float((history["meters_expected"] - history["meters_read"]).sum()) if len(history) else 0.0,
        "meter_7d_read_rate_mean": float(recent["read_rate"].mean()) if len(recent) else 0.0,
    }
    return result


def build_dataset(
    data_dir: pathlib.Path = DATA_DIR,
    duplicate_policy: str = "median",
    min_degraded_days: int = 2,
    min_degraded_hours: int = 6,
) -> pd.DataFrame:
    telemetry = load_telemetry(data_dir, duplicate_policy=duplicate_policy)
    master = load_master(data_dir).set_index("gateway_id")
    meter = load_meter(data_dir)
    rows: list[dict[str, object]] = []
    telemetry_by_gateway = {
        gateway_id: gateway_frame
        for gateway_id, gateway_frame in telemetry.groupby("gateway_id", sort=False)
    }
    for cutoff in monday_cutoffs():
        historical = telemetry[telemetry["ts"] < cutoff]
        for gateway_id, gateway_history in historical.groupby("gateway_id", sort=False):
            history_28d = gateway_history[gateway_history["ts"] >= cutoff - pd.Timedelta(days=28)]
            if len(history_28d) < 24 or history_28d["ts"].dt.floor("D").nunique() < 14:
                continue
            label = label_future_week(
                telemetry_by_gateway[gateway_id],
                cutoff,
                min_degraded_days=min_degraded_days,
                min_degraded_hours=min_degraded_hours,
            )
            if label is None:
                continue
            values: dict[str, object] = {
                "week_start": cutoff.date().isoformat(),
                "cutoff": cutoff.isoformat(),
                "gateway_id": gateway_id,
                **_window_features(gateway_history, cutoff),
                **_meter_features(meter, gateway_id, cutoff),
            }
            if gateway_id in master.index:
                values.update(_safe_master_features(master.loc[[gateway_id]], cutoff))
            else:
                values.update({column: "unknown" for column in MASTER_CATEGORICALS})
                values["installed_age_days"] = 0.0
            values.update(label)
            rows.append(values)
    dataset = pd.DataFrame(rows)
    return validate_dataset(dataset)


def feature_columns(dataset: pd.DataFrame) -> list[str]:
    metadata = {"week_start", "cutoff", "gateway_id", "target", "label_available"}
    label_details = {"future_observed_hours", "future_degraded_hours", "future_degraded_days"}
    return [column for column in dataset.columns if column not in metadata | label_details]


def validate_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        raise ValueError("No eligible gateway-week rows were created")
    if dataset.duplicated(["week_start", "gateway_id"]).any():
        raise ValueError("Duplicate gateway-week rows detected")
    if not dataset["label_available"].astype(bool).all():
        raise ValueError("Rows without complete future labels were included")
    if dataset[feature_columns(dataset)].isna().any().any():
        raise ValueError("Feature missing values were not deterministically filled")
    feature_names = feature_columns(dataset)
    forbidden = [
        column for column in feature_names
        if any(token in column.lower() for token in FORBIDDEN_FEATURE_TOKENS)
    ]
    if forbidden:
        raise ValueError(f"Forbidden feature names detected: {forbidden}")
    if set(dataset["target"].unique()) - {0, 1}:
        raise ValueError("Target must be binary")
    if dataset["cutoff"].isna().any():
        raise ValueError("Missing cutoff timestamps")
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=pathlib.Path, default=DATA_DIR)
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("artifacts/part2_gateway_week.parquet"))
    args = parser.parse_args()
    result = build_dataset(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(args.out, index=False)
    print(
        f"wrote {args.out}: rows={len(result)} gateways={result.gateway_id.nunique()} "
        f"weeks={result.week_start.nunique()} features={len(feature_columns(result))} "
        f"positive_rate={result.target.mean():.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())