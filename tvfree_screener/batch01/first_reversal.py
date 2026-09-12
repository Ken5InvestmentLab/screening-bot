"""Reconstructed First Reversal candidate-pool generation, with no outcome fields."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence

import pandas as pd

from .feature_panel import FEATURE_COLUMNS, build_market_return_table, compute_symbol_features


FIRST_REVERSAL_SPEC = {
    "spec_id": "first_reversal_reconstructed_v1",
    "market_feature": "previous official-session cross-sectional median of exact 5-session returns",
    "market_feature_lag_sessions": 1,
    "market_gate": {"feature": "market_median_ret5_lag1", "operator": "<=", "value": -0.01},
    "individual_prefilter": {
        "ret5": {"min_inclusive": -0.08, "max_inclusive": 0.0},
        "ret1": {"min_inclusive": 0.005, "max_inclusive": 0.08},
        "ret10": {"max_inclusive": 0.12},
        "volr20_inclusive": {"max_inclusive": 1.8},
    },
    "volume_ratio_definition": "current volume divided by 20-session mean including current session; legacy reconstruction field",
    "signal_data_quality": "positive OHLCV, high>=max(open,close), low<=min(open,close), and high>=low",
    "ranking_terms": [["ret1_minus_ret5_per5", "descending"]],
    "tie_break": "symbol ascending",
    "pool_cut": "none; retain every candidate before cooldown or Top-N selection",
    "feature_timestamp": "signal-date close; market gate uses the prior official session",
    "target": "next official TSE session open to close of fifth session including entry session",
}
FIRST_REVERSAL_SPEC_SHA256 = hashlib.sha256(
    json.dumps(FIRST_REVERSAL_SPEC, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
).hexdigest()
FAMILY = str(FIRST_REVERSAL_SPEC["spec_id"])


def _usable_signal_rows(features: pd.DataFrame) -> pd.Series:
    numeric = ["ret1", "ret5", "ret10", "volr20_inclusive", "ret1_minus_ret5_per5"]
    valid = features[numeric].notna().all(axis=1)
    valid &= features["open"].gt(0) & features["high"].gt(0) & features["low"].gt(0)
    valid &= features["close"].gt(0) & features["volume"].gt(0)
    valid &= features["high"].ge(features[["open", "close"]].max(axis=1))
    valid &= features["low"].le(features[["open", "close"]].min(axis=1))
    valid &= features["high"].ge(features["low"])
    valid &= features["ret5"].between(-0.08, 0.0, inclusive="both")
    valid &= features["ret1"].between(0.005, 0.08, inclusive="both")
    valid &= features["ret10"].le(0.12)
    valid &= features["volr20_inclusive"].le(1.8)
    return valid


def build_first_reversal_candidate_pool(
    bars: pd.DataFrame,
    *,
    sessions: Sequence[object],
    market_table: pd.DataFrame | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Compute market medians from all input names but retain only prefilter rows."""
    required = {"date", "symbol", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"OHLCV input missing columns: {missing}")
    source = bars.loc[:, ["date", "symbol", "open", "high", "low", "close", "volume"]].copy()
    source["date"] = pd.to_datetime(source["date"], errors="raise").dt.normalize()
    source["symbol"] = source["symbol"].astype("string")
    if source.duplicated(["date", "symbol"]).any():
        raise ValueError("duplicate symbol/date OHLCV row")

    calendar = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("sessions must be unique and sorted")
    if not set(source["date"]).issubset(set(calendar)):
        raise ValueError("OHLCV row falls outside the official session calendar")

    if market_table is None:
        market_table = build_market_return_table(source, sessions=calendar)
    required_market = {
        "date", "market_median_ret1", "market_median_ret5",
        "market_median_ret1_lag1", "market_median_ret5_lag1",
    }
    missing_market = sorted(required_market.difference(market_table.columns))
    if missing_market:
        raise ValueError(f"market-return table missing columns: {missing_market}")
    daily_market = market_table.loc[:, sorted(required_market)].copy()
    daily_market["date"] = pd.to_datetime(daily_market["date"], errors="raise").dt.normalize()
    if daily_market["date"].duplicated().any():
        raise ValueError("market-return table has duplicate dates")
    if set(daily_market["date"]) != set(calendar):
        raise ValueError("market-return table must cover the complete official calendar")
    aligned_market = daily_market.set_index("date").reindex(calendar)

    groups = source.groupby("symbol", sort=True, observed=True)
    symbol_count = int(source["symbol"].nunique())
    candidate_parts: list[pd.DataFrame] = []
    for index, (_symbol, group) in enumerate(groups, start=1):
        features = compute_symbol_features(group, sessions=sessions)
        candidates = features.loc[_usable_signal_rows(features)]
        if not candidates.empty:
            candidate_parts.append(candidates.copy())
        if progress is not None and (index % 100 == 0 or index == symbol_count):
            progress(index, symbol_count)

    if not symbol_count:
        raise ValueError("no OHLCV symbols were available")

    pool = pd.concat(candidate_parts, ignore_index=True) if candidate_parts else pd.DataFrame()
    if pool.empty:
        raise ValueError("First Reversal prefilter produced no candidates")
    for column in ("market_median_ret1", "market_median_ret5", "market_median_ret1_lag1", "market_median_ret5_lag1"):
        pool[column] = pool["date"].map(aligned_market[column]).astype("float32")
    if pool[["market_median_ret5_lag1", "market_median_ret5"]].isna().any().any():
        raise ValueError("First Reversal candidate has missing required market-return features")
    pool["rel_ret5_lag1"] = (pool["ret5"] - pool["market_median_ret5_lag1"]).astype("float32")
    pool = pool.loc[pool["market_median_ret5_lag1"].le(-0.01)].copy()
    if pool.empty:
        raise ValueError("previous-session weak-market condition produced no candidates")
    if pool.duplicated(["date", "symbol"]).any():
        raise RuntimeError("candidate pool is not unique by date/symbol")

    pool["date"] = pd.to_datetime(pool["date"], errors="raise").dt.normalize()
    pool["family"] = FAMILY
    pool["spec_hash"] = FIRST_REVERSAL_SPEC_SHA256
    pool["identity_key"] = pool["symbol"].astype("string")
    pool["candidate_id"] = pool["date"].dt.strftime("%Y%m%d") + ":" + pool["symbol"].astype("string")
    pool["inclusion_reason"] = "weak_previous_session_market_and_fixed_individual_prefilter_v1"
    pool["feature_timestamp"] = pool["date"].dt.strftime("%Y-%m-%d") + " close"
    keep = [
        "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
        "inclusion_reason", "feature_timestamp", "open", "high", "low", "close", "volume",
        *FEATURE_COLUMNS,
    ]
    pool = pool.loc[:, list(dict.fromkeys(keep))]
    pool = pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    return pool
