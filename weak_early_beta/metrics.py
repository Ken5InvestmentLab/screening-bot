"""User-facing performance metrics for five beta lanes."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .config import (
    COMBINED_STACKED_ID,
    COMBINED_STACKED_NAME,
    COMBINED_UNIQUE_ID,
    COMBINED_UNIQUE_NAME,
    SELECTOR_ORDER,
    selector_info,
)


def combined_detections(ledger: pd.DataFrame) -> pd.DataFrame:
    """Count one trade per signal-date/symbol across overlapping selectors."""
    if ledger.empty:
        return ledger.copy()
    data = ledger.copy()
    data["signal_date"] = pd.to_datetime(data["signal_date"])
    contract_columns = [
        "entry_date", "entry_open", "fifth_xtks_exit_date",
        "fifth_xtks_exit_close", "gross_return", "one_hundred_shares_pl_yen",
    ]
    for identity, group in data.groupby(["signal_date", "symbol"], sort=False):
        for column in contract_columns:
            values = group[column].dropna().astype(str).unique()
            if len(values) > 1:
                raise RuntimeError(
                    f"overlapping selectors disagree on {column} for {identity}: {values[:3]}"
                )
    return data.drop_duplicates(["signal_date", "symbol"], keep="first").copy()


def required_capital(frame: pd.DataFrame) -> float:
    events: list[tuple[pd.Timestamp, int, float]] = []
    for row in frame.itertuples():
        if pd.isna(row.entry_date) or pd.isna(row.fifth_xtks_exit_date) or pd.isna(row.entry_open):
            continue
        principal = float(row.entry_open) * 100
        events.append((pd.Timestamp(row.entry_date), 1, principal))
        events.append((pd.Timestamp(row.fifth_xtks_exit_date), -1, -principal))
    current = peak = 0.0
    # Entry happens at the open and exit at the close.  On the same session the
    # entry capital is needed before the closing exit releases old capital.
    for _, order, delta in sorted(events, key=lambda item: (item[0], -item[1])):
        current += delta
        peak = max(peak, current)
    return peak


def coverage_years(frame: pd.DataFrame, as_of: pd.Timestamp) -> float:
    """Return the actual observed span instead of assuming full calendar years."""
    signal_dates = pd.to_datetime(frame["signal_date"], errors="coerce").dropna()
    if signal_dates.empty:
        return 1 / 365.2425
    exit_dates = pd.to_datetime(frame.get("fifth_xtks_exit_date"), errors="coerce").dropna()
    start = signal_dates.min().normalize()
    observed_end = max(signal_dates.max(), exit_dates.max() if not exit_dates.empty else signal_dates.max())
    end = min(as_of.normalize(), observed_end.normalize())
    return max((end - start).days / 365.2425, 1 / 365.2425)


def summarize(frame: pd.DataFrame, period: str, as_of: pd.Timestamp) -> dict[str, Any]:
    completed = frame[pd.to_numeric(frame["gross_return"], errors="coerce").notna()].copy()
    returns = pd.to_numeric(completed["gross_return"], errors="coerce")
    capital = required_capital(completed)
    cash_pl = float(pd.to_numeric(completed["one_hundred_shares_pl_yen"], errors="coerce").sum())
    top3_ex = returns.nlargest(3).index
    top3_ex_mean = returns.drop(index=top3_ex).mean() if len(returns) > 3 else np.nan
    capital_return = cash_pl / capital if capital > 0 else np.nan
    return {
        "period": period,
        "n": int(len(completed)),
        "pending": int(len(frame) - len(completed)),
        "mean_pct": float(returns.mean() * 100) if len(returns) else np.nan,
        "median_pct": float(returns.median() * 100) if len(returns) else np.nan,
        "win_pct": float((returns > 0).mean() * 100) if len(returns) else np.nan,
        "plus10_pct": float((returns >= .10).mean() * 100) if len(returns) else np.nan,
        "plus20_pct": float((returns >= .20).mean() * 100) if len(returns) else np.nan,
        "minus10_pct": float((returns <= -.10).mean() * 100) if len(returns) else np.nan,
        "minus20_pct": float((returns <= -.20).mean() * 100) if len(returns) else np.nan,
        "max_up_pct": float(returns.max() * 100) if len(returns) else np.nan,
        "max_down_pct": float(returns.min() * 100) if len(returns) else np.nan,
        "top3_ex_mean_pct": float(top3_ex_mean * 100) if pd.notna(top3_ex_mean) else np.nan,
        "cash_pl_100_yen": cash_pl,
        "required_capital_yen": capital,
        "capital_return_pct": float(capital_return * 100) if pd.notna(capital_return) else np.nan,
        "simple_annualized_pct": (
            float(capital_return * 100 / coverage_years(frame, as_of))
            if pd.notna(capital_return) else np.nan
        ),
    }


def build_metrics(ledger: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    as_of = pd.Timestamp(as_of or pd.Timestamp.now()).tz_localize(None)
    data = ledger.copy()
    data["signal_date"] = pd.to_datetime(data["signal_date"])
    min_year = int(data["signal_date"].dt.year.min())
    max_year = int(data["signal_date"].dt.year.max())
    rows = []
    for selector_id in SELECTOR_ORDER:
        lane = data[data["selector_id"].eq(selector_id)]
        for year in range(min_year, max_year + 1):
            yearly = lane[lane["signal_date"].dt.year.eq(year)]
            if yearly.empty:
                continue
            rows.append({
                "selector_id": selector_id,
                "selector_name": selector_info(selector_id).display_name,
                **summarize(yearly, str(year), as_of),
            })
        total_period = f"{min_year}-{max_year}"
        rows.append({
            "selector_id": selector_id,
            "selector_name": selector_info(selector_id).display_name,
            **summarize(lane, total_period, as_of),
        })
    combined_modes = (
        (COMBINED_STACKED_ID, COMBINED_STACKED_NAME, data),
        (COMBINED_UNIQUE_ID, COMBINED_UNIQUE_NAME, combined_detections(data)),
    )
    for combined_id, combined_name, combined in combined_modes:
        for year in range(min_year, max_year + 1):
            yearly = combined[combined["signal_date"].dt.year.eq(year)]
            if yearly.empty:
                continue
            rows.append({
                "selector_id": combined_id,
                "selector_name": combined_name,
                **summarize(yearly, str(year), as_of),
            })
        rows.append({
            "selector_id": combined_id,
            "selector_name": combined_name,
            **summarize(combined, f"{min_year}-{max_year}", as_of),
        })
    return pd.DataFrame(rows)


def build_monthly_metrics(
    ledger: pd.DataFrame,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Monthly detail for the five modes and both combined allocations."""
    if ledger.empty:
        return pd.DataFrame()
    as_of = pd.Timestamp(as_of or pd.Timestamp.now()).tz_localize(None)
    data = ledger.copy()
    data["signal_date"] = pd.to_datetime(data["signal_date"])
    modes = [
        (selector_id, selector_info(selector_id).display_name, data[data["selector_id"].eq(selector_id)])
        for selector_id in SELECTOR_ORDER
    ]
    modes.extend([
        (COMBINED_STACKED_ID, COMBINED_STACKED_NAME, data),
        (COMBINED_UNIQUE_ID, COMBINED_UNIQUE_NAME, combined_detections(data)),
    ])
    rows = []
    for selector_id, selector_name, lane in modes:
        periods = lane["signal_date"].dt.to_period("M")
        for month, monthly in lane.groupby(periods, sort=True):
            summary = summarize(monthly, str(month.year), as_of)
            summary["period"] = str(month)
            rows.append({
                "selector_id": selector_id,
                "selector_name": selector_name,
                # Annualization is not presented for monthly rows. Passing the
                # year keeps the shared capital calculation deterministic.
                **summary,
            })
    return pd.DataFrame(rows)
