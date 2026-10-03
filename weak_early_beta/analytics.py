"""Aggregate-only analytics for an already selected Cloud report view.

The caller applies membership, signal-year and price-cap visibility and maps
the chosen endpoint into the normal trade columns before invoking this module.
The input and frozen economics are never changed. A lot denotes one original
trade, not the number of shares left after a split. Cash risks describe only
resolved trades, with every day's purchases funded before its sale receipts.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from .config import (
    COMBINED_STACKED_ID, COMBINED_STACKED_NAME,
    COMBINED_UNIQUE_ID, COMBINED_UNIQUE_NAME,
    SELECTOR_ORDER, selector_info,
)
from .entry_feasibility import performance_eligible
from .metrics import summarize
from .trade_basis import PRICE_BASIS_VERSION, TRADE_BASIS_COLUMNS


_KEYS = ["signal_date", "symbol"]
_DATES = ["signal_date", "entry_date", "fifth_xtks_exit_date"]
_NUMBERS = [
    "entry_open", "entry_shares", "entry_cost_yen", "gross_return",
    "one_hundred_shares_pl_yen",
]


def _date(value: Any) -> pd.Timestamp:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return pd.NaT
    result = pd.Timestamp(value)
    if result.tzinfo is not None:
        result = result.tz_convert("Asia/Tokyo").tz_localize(None)
    return result.normalize()


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    for column in [*_DATES, *_NUMBERS, "symbol", "selector_id", "source_scope", "price_basis"]:
        if column not in data:
            data[column] = np.nan
    for column in _DATES:
        data[column] = pd.to_datetime(data[column].map(_date))
    for column in _NUMBERS:
        data[column] = pd.to_numeric(data[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if data.empty:
        data["_resolved"] = pd.Series(dtype=bool)
        return data
    if data["signal_date"].isna().any() or data["symbol"].isna().any() or data["selector_id"].isna().any():
        raise ValueError("analytics requires signal dates, symbols and selector identities")
    data["symbol"] = data["symbol"].astype(str)
    data["_resolved"] = data["gross_return"].notna() & data["one_hundred_shares_pl_yen"].notna()
    # Legacy lots have a pinned 100-share convention. Actual-session receipts
    # must supply their own original quantity; unknown modern quantities stay
    # unknown rather than being replaced with split-adjusted exit quantities.
    legacy = data["price_basis"].fillna("").ne(PRICE_BASIS_VERSION)
    data.loc[legacy & data["entry_shares"].isna(), "entry_shares"] = 100.0
    for column in ["entry_open", "entry_shares", "entry_cost_yen"]:
        if data[column].dropna().le(0).any():
            raise ValueError(f"{column} must be positive and finite")
    # A missing legacy cost can be calculated from its recorded entry price
    # and original quantity. This does not reconstruct or replace any price.
    missing_cost = data["entry_cost_yen"].isna()
    data.loc[missing_cost, "entry_cost_yen"] = (
        data.loc[missing_cost, "entry_open"] * data.loc[missing_cost, "entry_shares"]
    )
    # Validate known components without replacing frozen or legacy amounts.
    # CSV-pinned legacy amounts can carry small decimal round-trip differences.
    expected_cost = data["entry_open"] * data["entry_shares"]
    known_cost = expected_cost.notna() & data["entry_cost_yen"].notna()
    if not np.isclose(data.loc[known_cost, "entry_cost_yen"], expected_cost[known_cost], rtol=1e-8, atol=1e-6).all():
        raise ValueError("entry cost disagrees with recorded price and original shares")
    expected_pl = data["entry_cost_yen"] * data["gross_return"]
    known_pl = expected_pl.notna() & data["one_hundred_shares_pl_yen"].notna()
    if not np.isclose(data.loc[known_pl, "one_hundred_shares_pl_yen"], expected_pl[known_pl], rtol=1e-8, atol=1e-6).all():
        raise ValueError("cash P/L disagrees with recorded entry cost and return")
    reversed_dates = data["fifth_xtks_exit_date"].lt(data["entry_date"])
    if reversed_dates.any():
        raise ValueError("analytics exit session precedes entry session")
    # Fail on conflicting overlap economics, including a completed/pending
    # disagreement, instead of depending on row ordering. Vectorised nunique
    # avoids a Python pass over every signal for every report variant.
    columns = list(dict.fromkeys([
        "entry_date", "fifth_xtks_exit_date", *_NUMBERS, "_resolved", "source_scope",
        *[column for column in ["fifth_xtks_exit_close", *TRADE_BASIS_COLUMNS] if column in data],
    ]))
    conflicts = data.groupby(_KEYS, sort=False)[columns].nunique(dropna=False).gt(1)
    if conflicts.any().any():
        column = conflicts.any()[lambda values: values].index[0]
        raise ValueError(f"overlapping selectors disagree on {column}")
    # Repeated copies of the same selector are one match, not additional lots.
    return data.drop_duplicates([*_KEYS, "selector_id"]).copy()


def _signals(data: pd.DataFrame) -> pd.DataFrame:
    unique = data.drop_duplicates(_KEYS).copy()
    if data.empty:
        unique["_selectors"] = pd.Series(dtype=int)
    else:
        counts = data.groupby(_KEYS, sort=False)["selector_id"].nunique()
        unique["_selectors"] = [int(counts.loc[(row.signal_date, row.symbol)]) for row in unique.itertuples()]
    return unique


def validated_unique_detections(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate overlapping receipts once and return one row per signal.

    This is the vectorised counterpart to ``metrics.combined_detections``
    for presentation code. Eligibility is deliberately the caller's choice:
    detection history retains reference-only records. Preserve source values
    and columns, including unknown quantities, in the returned history rows.
    """
    if frame.empty:
        return frame.copy()
    _normalise(frame)
    data = frame.copy()
    data["signal_date"] = pd.to_datetime(data["signal_date"])
    return data.drop_duplicates(_KEYS).copy()


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float | None:
    if not len(values):
        return None
    order = np.argsort(values, kind="stable")
    values, weights = values[order], weights[order]
    cumulative = np.cumsum(weights)
    size = int(cumulative[-1])
    lower = int(np.searchsorted(cumulative, (size - 1) // 2 + 1))
    upper = int(np.searchsorted(cumulative, size // 2 + 1))
    return float((values[lower] + values[upper]) / 2)


def _return_stats(returns: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    total = int(weights.sum())
    if not total:
        return {key: None for key in ["mean_pct", "median_pct", "win_pct", "average_win_pct", "average_loss_pct", "payoff_ratio"]}
    win, loss = returns > 0, returns < 0
    average_win = float(np.average(returns[win], weights=weights[win]) * 100) if win.any() else None
    average_loss = float(np.average(returns[loss], weights=weights[loss]) * 100) if loss.any() else None
    return {
        "mean_pct": float(np.average(returns, weights=weights) * 100),
        "median_pct": _weighted_median(returns * 100, weights),
        "win_pct": float(weights[win].sum() / total * 100),
        "average_win_pct": average_win,
        "average_loss_pct": average_loss,
        "payoff_ratio": average_win / abs(average_loss) if average_win is not None and average_loss is not None else None,
    }


def _cash_risk(completed: pd.DataFrame, weights: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {
        "minimum_initial_cash_yen": None, "peak_open_principal_yen": None,
        "max_concurrent_lots": 0, "max_concurrent_symbols": 0,
    }
    if completed.empty:
        return result
    if completed[["entry_date", "fifth_xtks_exit_date"]].isna().any().any():
        result["max_concurrent_lots"] = result["max_concurrent_symbols"] = None
        return result
    cost_known = completed["entry_cost_yen"].notna().all()
    events: dict[pd.Timestamp, dict[str, list[tuple[str, int, float, float]]]] = defaultdict(lambda: {"buy": [], "sell": []})
    for row, weight in zip(completed.itertuples(), weights):
        cost = float(row.entry_cost_yen) * int(weight) if cost_known else 0.0
        # D6 views can retain D5 exit_proceeds_yen. Only selected endpoint P/L
        # and the selected original entry cost determine these sale receipts.
        proceeds = cost + float(row.one_hundred_shares_pl_yen) * int(weight) if cost_known else 0.0
        event = (row.symbol, int(weight), cost, proceeds)
        events[row.entry_date]["buy"].append(event)
        events[row.fifth_xtks_exit_date]["sell"].append(event)
    cash = principal = min_cash = peak_principal = 0.0
    open_lots = peak_lots = peak_symbols = 0
    active: dict[str, int] = {}
    for day in sorted(events):
        for symbol, lots, cost, _ in events[day]["buy"]:
            cash -= cost
            principal += cost
            open_lots += lots
            active[symbol] = active.get(symbol, 0) + lots
        min_cash = min(min_cash, cash)
        peak_principal = max(peak_principal, principal)
        peak_lots = max(peak_lots, open_lots)
        peak_symbols = max(peak_symbols, len(active))
        for symbol, lots, cost, proceeds in events[day]["sell"]:
            cash += proceeds
            principal -= cost
            open_lots -= lots
            active[symbol] -= lots
            if active[symbol] == 0:
                del active[symbol]
        min_cash = min(min_cash, cash)
    result.update(max_concurrent_lots=peak_lots, max_concurrent_symbols=peak_symbols)
    if cost_known:
        result.update(minimum_initial_cash_yen=float(-min_cash), peak_open_principal_yen=float(peak_principal))
    return result


def _strategy(signals: pd.DataFrame, *, stacked: bool) -> dict[str, Any]:
    completed = signals.loc[signals["_resolved"]]
    weights = completed["_selectors"].to_numpy(dtype=int) if stacked else np.ones(len(completed), dtype=int)
    pending = signals.loc[~signals["_resolved"]]
    returns = completed["gross_return"].to_numpy(dtype=float)
    cash = completed["one_hundred_shares_pl_yen"].to_numpy(dtype=float) * weights
    signal_stats = _return_stats(returns, np.ones(len(completed), dtype=int))
    lot_stats = _return_stats(returns, weights)
    wins, losses = cash[cash > 0], cash[cash < 0]
    costs_known = completed["entry_cost_yen"].notna().all()
    shares_known = completed["entry_shares"].notna().all()
    risk = _cash_risk(completed, weights)
    if completed.empty or completed["fifth_xtks_exit_date"].isna().any():
        drawdown = None
    else:
        day_pl = pd.Series(cash, index=completed["fifth_xtks_exit_date"]).groupby(level=0).sum().sort_index()
        realised = np.r_[0.0, day_pl.cumsum().to_numpy()]
        drawdown = float((np.maximum.accumulate(realised) - realised).max())
    return {
        "resolved_signals": int(len(completed)), "resolved_lots": int(weights.sum()),
        "pending_signals": int(len(pending)),
        "pending_lots": int(pending["_selectors"].sum()) if stacked else int(len(pending)),
        "cash_pl_yen": float(cash.sum()),
        **{f"signal_{key}": signal_stats[key] for key in ["mean_pct", "median_pct", "win_pct"]},
        **{f"lot_{key}": value for key, value in lot_stats.items()},
        "total_entry_shares": float((completed["entry_shares"].to_numpy() * weights).sum()) if shares_known else None,
        "total_entry_cost_yen": float((completed["entry_cost_yen"].to_numpy() * weights).sum()) if costs_known else None,
        **risk,
        "max_drawdown_yen": drawdown,
        "worst_signal_cash_pl_yen": float(cash.min()) if len(cash) else None,
        "worst_return_pct": float(returns.min() * 100) if len(returns) else None,
        "profit_excluding_best3_signals_yen": float(cash.sum() - np.sort(cash)[-3:].sum()) if len(cash) else None,
        "gross_win_cash_pl_yen": float(wins.sum()),
        "gross_loss_cash_pl_yen": float(losses.sum()),
        "average_win_cash_pl_yen": float(wins.mean()) if len(wins) else None,
        "average_loss_cash_pl_yen": float(losses.mean()) if len(losses) else None,
    }


def _coverage(signals: pd.DataFrame) -> dict[str, Any]:
    data = signals.copy()
    scopes = data["source_scope"].fillna("").astype(str)
    data["_scope"] = np.select([scopes.str.startswith("EXACT_CANONICAL"), scopes.eq("FORWARD_CAUSAL")], ["historical", "forward"], default="other")
    sources = []
    for scope in ["historical", "forward", "other"]:
        group = data.loc[data["_scope"].eq(scope)]
        sources.append({"source_scope": scope, "signals": int(len(group)), "resolved_signals": int(group["_resolved"].sum()), "pending_signals": int((~group["_resolved"]).sum())})
    years = []
    for year, group in data.groupby(data["signal_date"].dt.year, sort=True):
        years.append({"year": int(year), **{scope: int(group["_scope"].eq(scope).sum()) for scope in ["historical", "forward", "other"]}})
    return {"sources": sources, "years": years}


def build_analytics(frame: pd.DataFrame, as_of: Any = None) -> dict[str, Any]:
    """Return JSON-safe aggregates without any symbol, identity or trade rows.

    ``as_of`` is report-date metadata, as in the existing metric API; it does
    not truncate already observed completed rows. A resolved row has finite
    selected-endpoint return and cash P/L. Missing dates/costs leave dependent
    risk values unknown. Return win rates include flat trades in the denominator.
    Normalisations are retrospective rescalings of cash P/L, not portfolios.
    """
    display = _normalise(frame)
    # Apply the reviewed policy independently of the caller's annotations.
    eligible = performance_eligible(display) if not display.empty else display.copy()
    all_signals, signals = _signals(display), _signals(eligible)
    completed = signals.loc[signals["_resolved"]].copy()
    counts = {
        "display_signals": int(len(all_signals)), "display_lots": int(len(display)),
        "eligible_signals": int(len(signals)), "eligible_lots": int(len(eligible)),
        "reference_excluded_signals": int(len(all_signals) - len(signals)),
        "reference_excluded_lots": int(len(display) - len(eligible)),
        "completed_signals": int(len(completed)), "completed_lots": int(completed["_selectors"].sum()),
        "pending_signals": int((~signals["_resolved"]).sum()),
        "pending_lots": int(signals.loc[~signals["_resolved"], "_selectors"].sum()),
    }
    strategies = {name: _strategy(signals, stacked=name == "stacked") for name in ["unique", "stacked"]}
    completed["_unique_pl"] = completed["one_hundred_shares_pl_yen"]
    completed["_stacked_pl"] = completed["_unique_pl"] * completed["_selectors"]
    cumulative = []
    # Never emit a partial curve which omits a resolved undated cash flow.
    if not completed.empty and completed["fifth_xtks_exit_date"].notna().all():
        grouped = completed.groupby("fifth_xtks_exit_date")[["_unique_pl", "_stacked_pl"]].sum().sort_index()
        first = grouped.index.min()
        earliest_entry = completed["entry_date"].min()
        baseline = min(earliest_entry, first) if pd.notna(earliest_entry) else first
        if baseline >= first:
            baseline = first - pd.Timedelta(days=1)
        cumulative.append({"date": baseline.strftime("%Y-%m-%d"), "unique": 0.0, "stacked": 0.0})
        for day, row in grouped.cumsum().iterrows():
            cumulative.append({"date": day.strftime("%Y-%m-%d"), "unique": float(row["_unique_pl"]), "stacked": float(row["_stacked_pl"])})
    annual = []
    for year, group in completed.groupby(completed["signal_date"].dt.year, sort=True):
        annual.append({"year": int(year), "unique": float(group["_unique_pl"].sum()), "stacked": float(group["_stacked_pl"].sum()), "resolved_signals": int(len(group)), "resolved_lots": int(group["_selectors"].sum()), "latest_completed_signal_date": group["signal_date"].max().strftime("%Y-%m-%d")})
    overlap = []
    for selector_count, group in completed.groupby("_selectors", sort=True):
        stats = _return_stats(group["gross_return"].to_numpy(dtype=float), np.ones(len(group), dtype=int))
        overlap.append({"selector_count": int(selector_count), "resolved_signals": int(len(group)), **{key: stats[key] for key in ["mean_pct", "median_pct", "win_pct"]}, "cash_pl_100_yen": float(group["_unique_pl"].sum())})
    unique, stacked = strategies["unique"], strategies["stacked"]
    def ratio(column: str) -> float | None:
        numerator, denominator = unique[column], stacked[column]
        return numerator / denominator if numerator is not None and denominator is not None and denominator > 0 else None
    share_ratio, cost_ratio = ratio("total_entry_shares"), ratio("total_entry_cost_yen")
    return {
        "as_of": _date(as_of).strftime("%Y-%m-%d") if as_of is not None and pd.notna(_date(as_of)) else None,
        "counts": counts, "strategies": strategies, "cumulative": cumulative,
        "annual": annual, "overlap": overlap, "coverage": _coverage(signals),
        "normalization": {
            "hypothetical_ex_post": True,
            "share_ratio": share_ratio, "entry_cost_ratio": cost_ratio,
            "shares_normalized_stacked_pl_yen": stacked["cash_pl_yen"] * share_ratio if share_ratio is not None else None,
            "entry_cost_normalized_stacked_pl_yen": stacked["cash_pl_yen"] * cost_ratio if cost_ratio is not None else None,
        },
        "assumptions": {
            "risk_scope": "eligible_resolved_trades", "cash_receipts": "end_of_day_after_all_purchases",
            "drawdown": "realized_cash_pl_only", "fees_included": False, "dividends_included": False,
            "annual_grouping": "signal_year", "flat_returns_in_win_denominator": True,
        },
    }


def build_presentation_metrics(
    frame: pd.DataFrame,
    as_of: Any = None,
    selector_ids: list[str] | tuple[str, ...] | None = None,
    *,
    _summary_cache: dict[str, dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build existing annual/total and monthly schemas for requested lanes only.

    Presentation variants do not need to repeat all seven modes on every
    page. Validate overlap once, project the wide ledger to metric inputs,
    and use the existing ``summarize`` formulas without modifying metrics.py.
    The result is ``(annual_and_total_metrics, monthly_metrics)``.
    A generation-local ``_summary_cache`` can reuse unchanged monthly subsets
    across caps/scopes. Its keys contain hashes only; each result is copied.
    """
    requested = list(dict.fromkeys(selector_ids if selector_ids is not None else [*SELECTOR_ORDER, COMBINED_STACKED_ID, COMBINED_UNIQUE_ID]))
    supported = {*SELECTOR_ORDER, COMBINED_STACKED_ID, COMBINED_UNIQUE_ID}
    if any(selector_id not in supported for selector_id in requested):
        raise ValueError("unknown presentation metric selector")
    if frame.empty or not requested:
        return pd.DataFrame(), pd.DataFrame()
    history = _normalise(frame)
    min_year = int(history["signal_date"].dt.year.min())
    max_year = int(history["signal_date"].dt.year.max())
    data = performance_eligible(history)
    data = data[["selector_id", "signal_date", "symbol", "entry_date", "entry_open", "entry_shares", "price_basis", "fifth_xtks_exit_date", "gross_return", "one_hundred_shares_pl_yen"]]
    day = pd.Timestamp(as_of if as_of is not None else pd.Timestamp.now()).tz_localize(None)
    total_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    summary_schema_hash = None
    if _summary_cache is not None:
        schema = {
            "version": 1,
            "columns": list(data.columns),
            "dtypes": [str(dtype) for dtype in data.dtypes],
            "index_dtype": str(data.index.dtype),
            "index_names": list(data.index.names),
            "as_of": day.isoformat(),
        }
        summary_schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))
        # Every subset retains this schema and the row order from data. Hash
        # all original values/index once, then carry their hashes through the
        # groupings, including frames whose source index contains duplicates.
        data["_summary_row_hash"] = pd.util.hash_pandas_object(data, index=True).to_numpy(dtype="uint64")

    def summary_for(subset: pd.DataFrame, period: str) -> dict[str, Any]:
        if _summary_cache is None:
            return summarize(subset, period, day)
        digest = summary_schema_hash.copy()
        digest.update(json.dumps(period).encode("utf-8"))
        digest.update(subset["_summary_row_hash"].to_numpy(dtype="uint64").tobytes())
        key = digest.hexdigest()
        if key not in _summary_cache:
            _summary_cache[key] = dict(summarize(subset.drop(columns="_summary_row_hash"), period, day))
        return dict(_summary_cache[key])

    for selector_id in requested:
        if selector_id == COMBINED_STACKED_ID:
            name, lane = COMBINED_STACKED_NAME, data
        elif selector_id == COMBINED_UNIQUE_ID:
            name, lane = COMBINED_UNIQUE_NAME, data.drop_duplicates(_KEYS)
        else:
            name = selector_info(selector_id).display_name
            lane = data.loc[data["selector_id"].eq(selector_id)]
        identity = {"selector_id": selector_id, "selector_name": name}
        for year, yearly in lane.groupby(lane["signal_date"].dt.year, sort=True):
            total_rows.append({**identity, **summary_for(yearly, str(int(year)))})
        total_rows.append({**identity, **summary_for(lane, f"{min_year}-{max_year}")})
        for month, monthly in lane.groupby(lane["signal_date"].dt.to_period("M"), sort=True):
            summary = summary_for(monthly, str(month.year))
            summary["period"] = str(month)
            monthly_rows.append({**identity, **summary})
    return pd.DataFrame(total_rows), pd.DataFrame(monthly_rows)
