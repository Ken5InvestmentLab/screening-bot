"""Daily endpoint-only returns kept separate from strict daily-path diagnostics."""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import numpy as np
import pandas as pd

from tvfree_screener.batch01.evaluation import (
    PRICE_COLUMNS,
    build_five_session_labels,
    return_metrics,
)
from tvfree_screener.batch01.session_calendar import SessionCalendar


ENDPOINT_TARGET_ID = "v2_next_xtks_open_to_fifth_close_endpoint_mark_to_market"
PATH_TARGET_ID = "v1_next_xtks_open_to_fifth_close_with_daily_path_and_actionability_guards"
_PATH_OUTPUT_COLUMNS = (
    "gross_return",
    "entry_price",
    "exit_price",
    "label_status",
    "label_resolved",
    "entry_fill_quality",
    "label_definition",
)


def _volume_status(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if not np.isfinite(number) or number < 0:
        return "INVALID_OR_UNKNOWN"
    if number == 0:
        return "ZERO"
    return "POSITIVE"


def build_endpoint_only_labels(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    calendar: SessionCalendar,
) -> pd.DataFrame:
    """Calculate daily endpoint returns while retaining strict path status.

    The endpoint result uses only the exact next-session open and fifth-session
    close. Interior daily bars and volume do not erase that mark-to-market
    calculation, but the existing strict labeler is run unchanged and exposed
    as separate diagnostics. Neither result proves an executable fill.
    """
    strict = build_five_session_labels(prices, signals, calendar)
    strict_status = strict["label_status"].astype("string").copy()
    strict_resolved = strict["label_resolved"].astype(bool).copy()
    strict_return = pd.to_numeric(strict["gross_return"], errors="coerce").copy()
    strict_entry = pd.to_numeric(strict["entry_price"], errors="coerce").copy()
    strict_exit = pd.to_numeric(strict["exit_price"], errors="coerce").copy()

    price = prices.loc[:, list(PRICE_COLUMNS)].copy()
    price["date"] = pd.to_datetime(price["date"], errors="raise").dt.normalize()
    price["symbol"] = price["symbol"].astype("string")
    if price.duplicated(["date", "symbol"]).any():
        raise ValueError("daily OHLCV has duplicate symbol/date bars")
    for column in ("open", "high", "low", "close", "volume"):
        price[column] = pd.to_numeric(price[column], errors="coerce")
    lookup = price.set_index(["date", "symbol"], drop=False)

    out = strict.drop(columns=list(_PATH_OUTPUT_COLUMNS)).copy()
    out["daily_path_status"] = strict_status
    out["daily_path_resolved"] = strict_resolved
    out["daily_path_gross_return"] = strict_return
    out["daily_path_entry_price"] = strict_entry
    out["daily_path_exit_price"] = strict_exit
    out["daily_path_target_id"] = PATH_TARGET_ID
    out["endpoint_entry_price"] = np.nan
    out["endpoint_exit_price"] = np.nan
    out["endpoint_gross_return"] = np.nan
    out["endpoint_entry_volume_status"] = "UNKNOWN"
    out["endpoint_exit_volume_status"] = "UNKNOWN"
    out["endpoint_label_status"] = pd.Series([None] * len(out), dtype="object")
    out["endpoint_label_resolved"] = False
    out["endpoint_target_id"] = ENDPOINT_TARGET_ID
    out["endpoint_fill_assumption"] = "next_xtks_daily_open_proxy_execution_unverified"
    out["endpoint_available_at"] = out["exit_date"]

    for index, row in out.iterrows():
        if pd.isna(row["entry_date"]) or pd.isna(row["exit_date"]):
            out.at[index, "endpoint_label_status"] = "CALENDAR_HORIZON_NOT_AVAILABLE"
            continue

        entry_key = (row["entry_date"], row["symbol"])
        exit_key = (row["exit_date"], row["symbol"])
        if entry_key not in lookup.index:
            out.at[index, "endpoint_label_status"] = "MISSING_ENTRY_DAILY_BAR"
            continue
        if exit_key not in lookup.index:
            out.at[index, "endpoint_label_status"] = "MISSING_EXIT_DAILY_BAR"
            continue
        entry_bar = lookup.loc[entry_key]
        exit_bar = lookup.loc[exit_key]
        if isinstance(entry_bar, pd.DataFrame) or isinstance(exit_bar, pd.DataFrame):
            raise ValueError("daily OHLCV endpoint lookup is ambiguous")

        try:
            entry_price = float(entry_bar["open"])
        except (TypeError, ValueError):
            out.at[index, "endpoint_label_status"] = "INVALID_ENTRY_DAILY_OPEN"
            continue
        try:
            exit_price = float(exit_bar["close"])
        except (TypeError, ValueError):
            out.at[index, "endpoint_label_status"] = "INVALID_EXIT_DAILY_CLOSE"
            continue
        if not np.isfinite(entry_price) or entry_price <= 0:
            out.at[index, "endpoint_label_status"] = "INVALID_ENTRY_DAILY_OPEN"
            continue
        if not np.isfinite(exit_price) or exit_price <= 0:
            out.at[index, "endpoint_label_status"] = "INVALID_EXIT_DAILY_CLOSE"
            continue

        out.at[index, "endpoint_entry_price"] = entry_price
        out.at[index, "endpoint_exit_price"] = exit_price
        out.at[index, "endpoint_gross_return"] = exit_price / entry_price - 1.0
        out.at[index, "endpoint_entry_volume_status"] = _volume_status(entry_bar["volume"])
        out.at[index, "endpoint_exit_volume_status"] = _volume_status(exit_bar["volume"])
        out.at[index, "endpoint_label_status"] = "RESOLVED"
        out.at[index, "endpoint_label_resolved"] = True

    endpoint_flag = out["endpoint_label_resolved"].fillna(False).astype(bool).to_numpy()
    endpoint_status = out["endpoint_label_status"].eq("RESOLVED").fillna(False).astype(bool).to_numpy()
    if not np.array_equal(endpoint_flag, endpoint_status):
        raise AssertionError("endpoint label status and resolution flag disagree")
    return out


def endpoint_label_summary(
    labels: pd.DataFrame,
    *,
    costs: Sequence[float] = (0.0, 0.005, 0.01),
) -> dict[str, object]:
    """Summarize endpoint and strict-path populations in separately named fields."""
    required = {
        "endpoint_gross_return",
        "endpoint_label_status",
        "endpoint_label_resolved",
        "daily_path_gross_return",
        "daily_path_status",
        "daily_path_resolved",
    }
    missing = sorted(required.difference(labels.columns))
    if missing:
        raise ValueError(f"missing endpoint summary fields: {missing}")
    endpoint_flag = labels["endpoint_label_resolved"].fillna(False).astype(bool).to_numpy()
    endpoint_status = labels["endpoint_label_status"].eq("RESOLVED").fillna(False).astype(bool).to_numpy()
    path_flag = labels["daily_path_resolved"].fillna(False).astype(bool).to_numpy()
    path_status = labels["daily_path_status"].eq("RESOLVED").fillna(False).astype(bool).to_numpy()
    if not np.array_equal(endpoint_flag, endpoint_status):
        raise ValueError("endpoint status and resolution fields disagree")
    if not np.array_equal(path_flag, path_status):
        raise ValueError("daily path status and resolution fields disagree")

    requested = int(len(labels))
    endpoint_mask = labels["endpoint_label_resolved"].astype(bool)
    path_mask = labels["daily_path_resolved"].astype(bool)
    endpoint_returns = pd.to_numeric(
        labels.loc[endpoint_mask, "endpoint_gross_return"], errors="coerce"
    )
    path_returns = pd.to_numeric(
        labels.loc[path_mask, "daily_path_gross_return"], errors="coerce"
    )
    both = endpoint_mask & path_mask
    differences = (
        pd.to_numeric(labels.loc[both, "endpoint_gross_return"], errors="coerce")
        - pd.to_numeric(labels.loc[both, "daily_path_gross_return"], errors="coerce")
    ).abs()

    cost_metrics: dict[str, object] = {}
    for cost in costs:
        cost = float(cost)
        if cost < 0 or cost >= 1:
            raise ValueError("round-trip cost must be in [0, 1)")
        cost_metrics[f"{cost:g}"] = return_metrics(
            endpoint_returns - cost, requested_count=requested
        )

    return {
        "endpoint_target_id": ENDPOINT_TARGET_ID,
        "path_target_id": PATH_TARGET_ID,
        "requested_count": requested,
        "endpoint_resolved_count": int(endpoint_mask.sum()),
        "endpoint_unresolved_count": int((~endpoint_mask).sum()),
        "endpoint_status_counts": {
            str(key): int(value)
            for key, value in Counter(labels["endpoint_label_status"].astype(str)).items()
        },
        "endpoint_gross_return_metrics": return_metrics(
            endpoint_returns, requested_count=requested
        ),
        "endpoint_net_return_metrics_by_round_trip_cost": cost_metrics,
        "daily_path_resolved_count": int(path_mask.sum()),
        "daily_path_incomplete_count": int((~path_mask).sum()),
        "daily_path_status_counts": {
            str(key): int(value)
            for key, value in Counter(labels["daily_path_status"].astype(str)).items()
        },
        "daily_path_gross_return_metrics": return_metrics(
            path_returns, requested_count=requested
        ),
        "resolved_by_both_count": int(both.sum()),
        "endpoint_vs_path_equal_return_count": int((differences <= 1e-12).sum()),
        "endpoint_vs_path_max_abs_return_delta": (
            float(differences.max()) if not differences.empty else None
        ),
        "endpoint_entry_volume_status_counts": {
            str(key): int(value)
            for key, value in Counter(labels["endpoint_entry_volume_status"].astype(str)).items()
        },
        "endpoint_exit_volume_status_counts": {
            str(key): int(value)
            for key, value in Counter(labels["endpoint_exit_volume_status"].astype(str)).items()
        },
        "execution_warning": (
            "Daily endpoint returns are mark-to-market proxies. They do not establish "
            "intraday path, queue priority, limit fills, liquidity, or executable entry."
        ),
    }
