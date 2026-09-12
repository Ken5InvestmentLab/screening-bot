"""Separate point-in-time selections from forward labels and cohort returns."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import numpy as np
import pandas as pd

from .session_calendar import SessionCalendar, validate_sessions


PRICE_COLUMNS = ("date", "symbol", "open", "high", "low", "close", "volume")
JOIN_COLUMNS = ("date", "symbol", "family", "spec_hash")


def _normalize_dates(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    out = frame.copy()
    out[column] = pd.to_datetime(out[column], errors="raise").dt.normalize()
    return out


def build_five_session_labels(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    calendar: SessionCalendar,
) -> pd.DataFrame:
    """Attach fixed next-session-open to fifth-session-close labels.

    Every input signal gets one output row, including unavailable and
    unresolved labels. A missing price never removes or replaces a selected
    candidate. Daily OHLCV cannot prove queue priority or execution at limits;
    open-price fills are therefore explicitly marked as a proxy assumption.
    """
    missing_prices = sorted(set(PRICE_COLUMNS).difference(prices.columns))
    if missing_prices:
        raise ValueError(f"missing OHLCV columns: {missing_prices}")
    missing_signals = sorted({"date", "symbol"}.difference(signals.columns))
    if missing_signals:
        raise ValueError(f"missing signal columns: {missing_signals}")

    price = _normalize_dates(prices.loc[:, list(PRICE_COLUMNS)])
    price["symbol"] = price["symbol"].astype("string")
    if price.duplicated(["date", "symbol"]).any():
        raise ValueError("OHLCV has duplicate symbol/date bars")
    for column in ("open", "high", "low", "close", "volume"):
        price[column] = pd.to_numeric(price[column], errors="coerce")

    rows = _normalize_dates(signals).reset_index(drop=True)
    rows["symbol"] = rows["symbol"].astype("string")
    if rows[["date", "symbol"]].isna().any().any():
        raise ValueError("signals contain a missing date or symbol")
    if not rows["date"].isin(calendar.sessions).all():
        raise ValueError("signal date is absent from the official session calendar")
    if rows.duplicated(["date", "symbol", *[c for c in ("family", "spec_hash", "policy_id", "top_n") if c in rows.columns]]).any():
        raise ValueError("signals contain duplicate policy/symbol/date rows")

    date_positions = {pd.Timestamp(day): index for index, day in enumerate(calendar.sessions)}
    entry_dates: list[pd.Timestamp | pd.NaT] = []
    exit_dates: list[pd.Timestamp | pd.NaT] = []
    holding_dates: list[list[pd.Timestamp] | None] = []
    initial_status: list[str | None] = []
    for signal_date in rows["date"]:
        position = date_positions[pd.Timestamp(signal_date)]
        if position + 5 >= len(calendar.sessions):
            entry_dates.append(pd.NaT)
            exit_dates.append(pd.NaT)
            holding_dates.append(None)
            initial_status.append("CALENDAR_HORIZON_NOT_AVAILABLE")
        else:
            entry_dates.append(pd.Timestamp(calendar.sessions[position + 1]))
            exit_dates.append(pd.Timestamp(calendar.sessions[position + 5]))
            holding_dates.append([
                pd.Timestamp(day) for day in calendar.sessions[position + 1:position + 6]
            ])
            initial_status.append(None)
    rows["entry_date"] = entry_dates
    rows["exit_date"] = exit_dates
    rows["gross_return"] = np.nan
    rows["entry_price"] = np.nan
    rows["exit_price"] = np.nan
    rows["label_status"] = initial_status
    rows["entry_fill_quality"] = "not_available"

    needed_dates = set(rows["date"]) | {
        day for window in holding_dates if window is not None for day in window
    }
    relevant = price.loc[price["date"].isin(needed_dates)]
    if relevant.duplicated(["date", "symbol"]).any():
        raise ValueError("filtered OHLCV lookup is ambiguous")
    lookup = relevant.set_index(["date", "symbol"], drop=False)

    for index, row in rows.loc[rows["label_status"].isna()].iterrows():
        signal_key = (row["date"], row["symbol"])
        if signal_key not in lookup.index:
            rows.at[index, "label_status"] = "MISSING_SIGNAL_CLOSE_BAR"
            continue
        signal_bar = lookup.loc[signal_key]
        if isinstance(signal_bar, pd.DataFrame):
            raise ValueError("OHLCV lookup returned multiple signal-date bars")
        previous_close = float(signal_bar["close"]) if pd.notna(signal_bar["close"]) else np.nan
        if not np.isfinite(previous_close) or previous_close <= 0:
            rows.at[index, "label_status"] = "INVALID_SIGNAL_CLOSE"
            continue

        window = holding_dates[index]
        bars = []
        unresolved = None
        for day_number, day in enumerate(window or [], start=1):
            key = (day, row["symbol"])
            if key not in lookup.index:
                unresolved = (
                    "MISSING_ENTRY_BAR" if day_number == 1
                    else "MISSING_EXIT_BAR" if day_number == 5
                    else "MISSING_HOLDING_SESSION_BAR"
                )
                break
            bar = lookup.loc[key]
            if isinstance(bar, pd.DataFrame):
                raise ValueError("OHLCV lookup returned multiple bars in holding window")
            try:
                open_price, high, low, close, volume = (
                    float(bar[name]) for name in ("open", "high", "low", "close", "volume")
                )
            except (TypeError, ValueError):
                unresolved = (
                    "NON_NUMERIC_ENTRY_OHLCV" if day_number == 1
                    else "NON_NUMERIC_EXIT_OHLCV" if day_number == 5
                    else "NON_NUMERIC_HOLDING_OHLCV"
                )
                break
            if not all(np.isfinite(value) for value in (open_price, high, low, close, volume)):
                unresolved = (
                    "NON_NUMERIC_ENTRY_OHLCV" if day_number == 1
                    else "NON_NUMERIC_EXIT_OHLCV" if day_number == 5
                    else "NON_NUMERIC_HOLDING_OHLCV"
                )
                break
            if min(open_price, high, low, close) <= 0 or volume < 0:
                unresolved = (
                    "INVALID_ENTRY_PRICE_OR_VOLUME" if day_number == 1
                    else "INVALID_EXIT_PRICE_OR_VOLUME" if day_number == 5
                    else "INVALID_HOLDING_PRICE_OR_VOLUME"
                )
                break
            tolerance = max(0.01, max(abs(open_price), abs(close)) * 1e-7)
            if low > min(open_price, close) + tolerance or high < max(open_price, close) - tolerance or high < low:
                unresolved = (
                    "INVALID_ENTRY_OHLC_RANGE" if day_number == 1
                    else "INVALID_EXIT_OHLC_RANGE" if day_number == 5
                    else "INVALID_HOLDING_OHLC_RANGE"
                )
                break
            if volume == 0:
                unresolved = "ENTRY_ZERO_OR_UNKNOWN_VOLUME" if day_number == 1 else "ZERO_VOLUME_HOLDING_SESSION"
                break
            gap_ratio = open_price / previous_close
            # A 40% overnight discontinuity is beyond ordinary TSE daily
            # price-limit movement and requires a corporate-action/source check.
            # It is preserved as unresolved, never silently adjusted.
            if gap_ratio < 0.60 or gap_ratio > 1.40:
                unresolved = "POTENTIAL_SPLIT_OR_EXTREME_GAP"
                break
            bars.append(bar)
            previous_close = close
        if unresolved:
            rows.at[index, "label_status"] = unresolved
            continue

        entry_bar = bars[0]
        exit_bar = bars[-1]
        open_price = float(entry_bar["open"])
        close_price = float(exit_bar["close"])
        rows.at[index, "entry_price"] = open_price
        rows.at[index, "exit_price"] = close_price
        rows.at[index, "gross_return"] = close_price / open_price - 1.0
        same_price_bar = (
            np.isclose(float(entry_bar["high"]), float(entry_bar["low"]))
            and np.isclose(float(entry_bar["open"]), float(entry_bar["close"]))
        )
        rows.at[index, "entry_fill_quality"] = (
            "single_price_bar_execution_unverified" if same_price_bar
            else "open_price_proxy_execution_unverified"
        )
        rows.at[index, "label_status"] = "RESOLVED"
    rows["label_resolved"] = rows["label_status"].eq("RESOLVED")
    rows["label_definition"] = "v1_next_xtks_open_to_fifth_close_with_ohlcv_actionability_guards"
    return rows


def return_metrics(
    returns: Sequence[float] | pd.Series,
    *,
    requested_count: int | None = None,
) -> dict[str, object]:
    values = pd.to_numeric(pd.Series(returns), errors="coerce").dropna().astype(float)
    n = int(len(values))
    draws = int(np.isclose(values.to_numpy(), 0.0, atol=1e-12).sum()) if n else 0
    win_denominator = n - draws
    winners = values[values > 0]

    def mean_without_best_winners(count: int) -> float | None:
        if n == 0:
            return None
        drop_indexes = winners.nlargest(count).index if len(winners) else []
        remaining = values.drop(index=drop_indexes)
        return float(remaining.mean()) if len(remaining) else None

    return {
        "n": n,
        "requested_count": int(requested_count if requested_count is not None else n),
        "resolved_count": n,
        "draw_count": draws,
        "win_rate": float((values > 0).sum() / win_denominator) if win_denominator else None,
        "win_rate_denominator_excludes_draws": True,
        "mean": float(values.mean()) if n else None,
        "median": float(values.median()) if n else None,
        "plus10_rate": float((values >= 0.10).mean()) if n else None,
        "plus20_rate": float((values >= 0.20).mean()) if n else None,
        "plus50_rate": float((values >= 0.50).mean()) if n else None,
        "minus10_rate": float((values <= -0.10).mean()) if n else None,
        "minus20_rate": float((values <= -0.20).mean()) if n else None,
        "mean_excluding_top1_winner": mean_without_best_winners(1),
        "mean_excluding_top3_winners": mean_without_best_winners(3),
    }


def label_summary(
    labels: pd.DataFrame,
    *,
    costs: Sequence[float] = (0.0, 0.005, 0.01),
) -> dict[str, object]:
    """Report selected and resolved sample sizes without dropping failures."""
    if not {"label_resolved", "label_status", "gross_return"}.issubset(labels.columns):
        raise ValueError("labels lack resolution or return fields")
    resolved = labels.loc[labels["label_resolved"].astype(bool), "gross_return"]
    result: dict[str, object] = {
        "selected_count": int(len(labels)),
        "resolved_count": int(labels["label_resolved"].astype(bool).sum()),
        "unresolved_count": int((~labels["label_resolved"].astype(bool)).sum()),
        "unresolved_by_status": {
            str(key): int(value)
            for key, value in labels.loc[~labels["label_resolved"].astype(bool), "label_status"].value_counts(dropna=False).items()
        },
        "gross": return_metrics(resolved, requested_count=len(labels)),
        "round_trip_cost_scenarios": {},
    }
    for cost in costs:
        if cost < 0 or cost >= 1:
            raise ValueError("round-trip cost must be in [0, 1)")
        net = pd.to_numeric(resolved, errors="coerce") - float(cost)
        result["round_trip_cost_scenarios"][f"{cost:g}"] = return_metrics(
            net, requested_count=len(labels)
        )
    return result


def daily_cohorts(
    selections: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    sessions: Sequence[object],
    join_columns: Sequence[str] = JOIN_COLUMNS,
) -> pd.DataFrame:
    """One equal-weight return per selection day; partial cohorts stay missing."""
    calendar = validate_sessions(sessions)
    join_columns = tuple(join_columns)
    missing_selection = sorted(set(join_columns).difference(selections.columns))
    missing_labels = sorted(set(join_columns + ("gross_return", "label_resolved", "label_status")).difference(labels.columns))
    if missing_selection or missing_labels:
        raise ValueError(f"missing join fields: selections={missing_selection}, labels={missing_labels}")
    # Selection frames may carry similarly named audit or display columns.
    # Only the registered identity keys belong on the selection side of this join.
    left = _normalize_dates(selections.loc[:, list(join_columns)])
    right = _normalize_dates(labels)
    if left.duplicated(list(join_columns)).any() or right.duplicated(list(join_columns)).any():
        raise ValueError("daily cohort join keys are not unique")
    merged = left.merge(
        right.loc[:, [*join_columns, "gross_return", "label_resolved", "label_status"]],
        on=list(join_columns), how="left", validate="one_to_one", indicator=True,
    )
    merged["label_resolved"] = merged["label_resolved"].fillna(False).astype(bool)
    merged["gross_return"] = pd.to_numeric(merged["gross_return"], errors="coerce")
    daily_rows: list[dict[str, object]] = []
    for day in calendar:
        date = pd.Timestamp(day)
        group = merged.loc[merged["date"].eq(date)]
        count = int(len(group))
        unresolved = int((~group["label_resolved"]).sum()) if count else 0
        if count == 0:
            status, cohort_return = "ABSTAIN", np.nan
        elif unresolved:
            status, cohort_return = "PARTIAL_UNRESOLVED", np.nan
        else:
            status, cohort_return = "COMPLETE", float(group["gross_return"].mean())
        daily_rows.append({
            "date": date, "selected_count": count, "unresolved_count": unresolved,
            "cohort_status": status, "cohort_return": cohort_return,
        })
    return pd.DataFrame(daily_rows)


def weekly_block_bootstrap(
    daily: pd.DataFrame,
    *,
    repetitions: int = 2000,
    seed: int = 20260912,
) -> dict[str, object]:
    """Resample ISO-week blocks of complete daily cohort observations."""
    if repetitions < 100:
        raise ValueError("use at least 100 bootstrap repetitions")
    complete = daily.loc[
        daily["cohort_status"].eq("COMPLETE") & daily["cohort_return"].notna(),
        ["date", "cohort_return"],
    ].copy()
    if complete.empty:
        return {"weeks": 0, "observations": 0, "repetitions": repetitions, "lower_95": None, "upper_95": None, "p_mean_le_zero": None}
    complete["week"] = pd.to_datetime(complete["date"]).dt.strftime("%G-W%V")
    blocks = [group["cohort_return"].to_numpy(dtype=float) for _, group in complete.groupby("week", sort=True)]
    if len(blocks) < 2:
        return {"weeks": len(blocks), "observations": len(complete), "repetitions": repetitions, "lower_95": None, "upper_95": None, "p_mean_le_zero": None}
    rng = np.random.default_rng(seed)
    means = np.empty(repetitions, dtype=float)
    for i in range(repetitions):
        sampled = rng.integers(0, len(blocks), size=len(blocks))
        values = np.concatenate([blocks[j] for j in sampled])
        means[i] = float(values.mean())
    return {
        "weeks": len(blocks),
        "observations": int(len(complete)),
        "repetitions": repetitions,
        "seed": seed,
        "lower_95": float(np.quantile(means, 0.025)),
        "upper_95": float(np.quantile(means, 0.975)),
        "p_mean_le_zero": float((means <= 0).mean()),
    }


def cohort_summary(daily: pd.DataFrame, *, repetitions: int = 2000) -> dict[str, object]:
    """Summarize complete cohorts and expose incomplete/abstained dates."""
    complete = daily.loc[daily["cohort_status"].eq("COMPLETE"), "cohort_return"]
    metrics = return_metrics(complete, requested_count=int(daily["selected_count"].sum()))
    metrics["active_days"] = int(daily["selected_count"].gt(0).sum())
    metrics["abstain_days"] = int(daily["cohort_status"].eq("ABSTAIN").sum())
    metrics["incomplete_days"] = int(daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum())
    monthly = daily.loc[daily["cohort_status"].eq("COMPLETE")].copy()
    if not monthly.empty:
        monthly["month"] = pd.to_datetime(monthly["date"]).dt.to_period("M").astype(str)
        metrics["monthly"] = {
            str(month): return_metrics(group["cohort_return"])
            for month, group in monthly.groupby("month", sort=True)
        }
        week_frame = monthly.assign(
            week=pd.to_datetime(monthly["date"]).dt.strftime("%G-W%V")
        )
        metrics["weekly"] = {
            str(week): return_metrics(group["cohort_return"])
            for week, group in week_frame.groupby("week", sort=True)
        }
        if monthly["month"].nunique() > 1:
            best_month = monthly.groupby("month")["cohort_return"].mean().idxmax()
            metrics["mean_excluding_best_month"] = float(
                monthly.loc[monthly["month"].ne(best_month), "cohort_return"].mean()
            )
        else:
            metrics["mean_excluding_best_month"] = None
    else:
        metrics.update({"monthly": {}, "weekly": {}, "mean_excluding_best_month": None})
    metrics["weekly_block_bootstrap"] = weekly_block_bootstrap(
        daily, repetitions=repetitions
    )
    return metrics


def apply_round_trip_costs(labels: pd.DataFrame, costs: Sequence[float] = (0.0, 0.005, 0.01)) -> pd.DataFrame:
    """Create fee-scenario outcomes without altering candidate membership."""
    out = labels.copy()
    if not out["label_resolved"].equals(out["label_status"].eq("RESOLVED")):
        raise ValueError("label resolution fields disagree")
    for cost in costs:
        if cost < 0 or cost >= 1:
            raise ValueError("round-trip cost must be in [0, 1)")
        out[f"net_return_cost_{cost:g}"] = np.where(
            out["label_resolved"], out["gross_return"] - float(cost), np.nan
        )
    return out
