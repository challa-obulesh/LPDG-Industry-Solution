"""Future-window target construction for Part 2."""

from __future__ import annotations

import pandas as pd

LABEL_WINDOW_DAYS = 7
MIN_FUTURE_OBSERVED_HOURS = 84
MIN_DEGRADED_DAYS = 2
MIN_DEGRADED_HOURS = 6


def label_future_week(
    telemetry: pd.DataFrame,
    cutoff: pd.Timestamp,
    min_degraded_days: int = MIN_DEGRADED_DAYS,
    min_degraded_hours: int = MIN_DEGRADED_HOURS,
) -> dict[str, int | bool] | None:
    """Return the persistent-degradation label for one gateway and cutoff.

    A telemetry hour is degraded when it has at least one hour offline, at least
    three disconnections, or at least one reboot. Persistence requires degraded
    observations on two distinct days and six degraded hours in the complete
    seven-day future window. At least 84 observed hours are required so a sparse
    future window is not silently treated as healthy.
    """
    end = cutoff + pd.Timedelta(days=LABEL_WINDOW_DAYS)
    future = telemetry[(telemetry["ts"] >= cutoff) & (telemetry["ts"] < end)]
    if future.empty:
        return None

    observed_hours = len(future)
    if observed_hours < MIN_FUTURE_OBSERVED_HOURS:
        return None

    degraded = (
        (future["offline_duration_sec"] >= 3600)
        | (future["disconnection_cnt"] >= 3)
        | (future["reboot_cnt"] >= 1)
    )
    degraded_rows = future.loc[degraded].copy()
    degraded_rows["day"] = degraded_rows["ts"].dt.floor("D")
    degraded_hours = len(degraded_rows)
    degraded_days = degraded_rows["day"].nunique()
    return {
        "label_available": True,
        "target": int(
            degraded_days >= min_degraded_days
            and degraded_hours >= min_degraded_hours
        ),
        "future_observed_hours": observed_hours,
        "future_degraded_hours": degraded_hours,
        "future_degraded_days": int(degraded_days),
    }