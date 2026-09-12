"""Causal daily OHLCV features aligned to the frozen XTKS session calendar."""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd


OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
RETURN_WINDOWS = (1, 3, 5, 10, 20, 40)
ROLL_WINDOWS = (5, 20, 40, 60)
LOCAL_FEATURE_COLUMNS = (
    "ret1", "ret3", "ret5", "ret10", "ret20", "ret40",
    "volr5_inclusive", "volr20_inclusive", "volr20_prevavg",
    "atr14p", "pos20", "pos40", "pos60", "dd20", "dd40", "dd60",
    "range_pct", "body_pct", "close_location", "gap",
    "red_count5", "down3", "down5", "consecutive_down",
    "days_since_drop5", "ret1_minus_ret5_per5",
    "log_dollar_volume", "dollar_volume_median20", "dispersion20",
    "volume_trend5_20",
)
MARKET_FEATURE_COLUMNS = (
    "market_median_ret1", "market_median_ret5", "market_median_ret1_lag1",
    "market_median_ret5_lag1", "rel_ret5_lag1",
)
FEATURE_COLUMNS = (*LOCAL_FEATURE_COLUMNS, *MARKET_FEATURE_COLUMNS)


def _rolling(series: pd.Series, window: int, operation: str) -> pd.Series:
    rolling = series.rolling(window=window, min_periods=window)
    return getattr(rolling, operation)()


def compute_symbol_features(
    bars: pd.DataFrame,
    *,
    sessions: Sequence[object],
) -> pd.DataFrame:
    """Compute features on official sessions, leaving missing sessions as gaps.

    A return or rolling feature cannot bridge an absent session. The returned
    rows contain only dates present in the source; NaN features remain visible
    for explicit eligibility decisions.
    """
    required = {"date", "symbol", *OHLCV_COLUMNS}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"OHLCV input missing columns: {missing}")
    if bars.empty:
        return pd.DataFrame(columns=["date", "symbol", *OHLCV_COLUMNS, *FEATURE_COLUMNS])
    if bars["symbol"].astype(str).nunique() != 1:
        raise ValueError("compute_symbol_features accepts exactly one symbol")

    official = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    if official.has_duplicates or not official.is_monotonic_increasing:
        raise ValueError("sessions must be unique and sorted")
    source = bars.copy().sort_values("date", kind="mergesort")
    source["date"] = pd.to_datetime(source["date"], errors="raise").dt.normalize()
    source["symbol"] = source["symbol"].astype("string")
    for column in OHLCV_COLUMNS:
        source[column] = pd.to_numeric(source[column], errors="coerce").astype("float64")
    if source["date"].duplicated().any():
        raise ValueError("duplicate symbol/date OHLCV row")
    if not set(source["date"]).issubset(set(official)):
        raise ValueError("OHLCV row falls outside the official session calendar")

    symbol = source["symbol"].iloc[0]
    first = source["date"].min()
    last = source["date"].max()
    index = official[(official >= first) & (official <= last)]
    aligned = source.set_index("date").reindex(index)
    aligned["symbol"] = symbol
    close = aligned["close"]
    volume = aligned["volume"]

    for window in RETURN_WINDOWS:
        aligned[f"ret{window}"] = close / close.shift(window) - 1.0

    for window in (5, 20):
        current_mean = _rolling(volume, window, "mean")
        previous_mean = _rolling(volume.shift(1), window, "mean")
        aligned[f"volr{window}_inclusive"] = volume / current_mean.replace(0, np.nan)
        if window == 20:
            aligned["volr20_prevavg"] = volume / previous_mean.replace(0, np.nan)

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            aligned["high"] - aligned["low"],
            (aligned["high"] - previous_close).abs(),
            (aligned["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    aligned["atr14p"] = _rolling(true_range, 14, "mean") / close

    for window in (20, 40, 60):
        high = _rolling(aligned["high"], window, "max")
        low = _rolling(aligned["low"], window, "min")
        aligned[f"pos{window}"] = (close - low) / (high - low).replace(0, np.nan)
        aligned[f"dd{window}"] = close / high - 1.0

    candle_range = aligned["high"] - aligned["low"]
    aligned["range_pct"] = candle_range / close
    aligned["body_pct"] = (aligned["close"] - aligned["open"]) / candle_range.replace(0, np.nan)
    aligned["close_location"] = (close - aligned["low"]) / candle_range.replace(0, np.nan)
    aligned["gap"] = aligned["open"] / previous_close - 1.0
    candle_complete = aligned[["open", "high", "low", "close", "volume"]].notna().all(axis=1)
    red = (close < aligned["open"]).where(candle_complete).astype("float64")
    aligned["red_count5"] = red.rolling(5, min_periods=5).sum()
    down = (close < previous_close).where(close.notna() & previous_close.notna()).astype("float64")
    aligned["down3"] = down.rolling(3, min_periods=3).sum()
    aligned["down5"] = down.rolling(5, min_periods=5).sum()
    down_groups = down.ne(1).cumsum()
    consecutive = down.eq(1).astype("int64").groupby(down_groups, sort=False).cumsum()
    aligned["consecutive_down"] = consecutive.astype("float64").where(down.notna())

    session_positions = pd.Series(np.arange(len(aligned), dtype="float64"), index=aligned.index)
    return_groups = aligned["ret1"].isna().cumsum()
    last_drop = session_positions.where(aligned["ret1"].le(-0.05)).groupby(return_groups, sort=False).ffill()
    aligned["days_since_drop5"] = (session_positions - last_drop).where(
        aligned["ret1"].notna() & last_drop.notna()
    )
    aligned["ret1_minus_ret5_per5"] = aligned["ret1"] - aligned["ret5"] / 5.0

    aligned["log_dollar_volume"] = np.log1p(close.clip(lower=0) * volume.clip(lower=0))
    dollar_volume = close * volume
    aligned["dollar_volume_median20"] = dollar_volume.rolling(20, min_periods=20).median()
    aligned["dispersion20"] = aligned["ret1"].rolling(20, min_periods=20).std(ddof=0)
    vol5 = _rolling(volume.shift(1), 5, "mean")
    vol20 = _rolling(volume.shift(1), 20, "mean")
    aligned["volume_trend5_20"] = vol5 / vol20.replace(0, np.nan)

    result = aligned.loc[source["date"].sort_values().unique()].copy()
    result.index.name = "date"
    result = result.reset_index()
    result = result.loc[:, ["date", "symbol", *OHLCV_COLUMNS, *LOCAL_FEATURE_COLUMNS]]
    result.loc[:, LOCAL_FEATURE_COLUMNS] = result.loc[:, LOCAL_FEATURE_COLUMNS].astype("float32")
    return result


def add_market_features(
    panel: pd.DataFrame,
    *,
    sessions: Sequence[object],
) -> pd.DataFrame:
    """Attach same-day and prior-session cross-sectional market summaries."""
    if panel.empty:
        return panel.copy()
    calendar = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("sessions must be unique and sorted")
    dates = pd.to_datetime(panel["date"], errors="raise").dt.normalize()
    daily = panel.assign(date=dates).groupby("date", sort=True).agg(
        market_median_ret1=("ret1", "median"),
        market_median_ret5=("ret5", "median"),
    )
    missing = set(daily.index).difference(calendar)
    if missing:
        raise ValueError("market panel contains dates outside the official calendar")
    aligned = daily.reindex(calendar)
    aligned["market_median_ret5_lag1"] = aligned["market_median_ret5"].shift(1)
    aligned["market_median_ret1_lag1"] = aligned["market_median_ret1"].shift(1)
    out = panel.copy()
    out["date"] = dates
    for column in aligned.columns:
        out[column] = out["date"].map(aligned[column])
    out["rel_ret5_lag1"] = out["ret5"] - out["market_median_ret5_lag1"]
    out.loc[:, MARKET_FEATURE_COLUMNS] = out.loc[:, MARKET_FEATURE_COLUMNS].astype("float32")
    return out


def build_market_return_table(
    bars: pd.DataFrame,
    *,
    sessions: Sequence[object],
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Calculate cross-sectional market medians from exact official-session returns."""
    required = {"date", "symbol", "close"}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"market-return input missing columns: {missing}")
    source = bars.loc[:, ["date", "symbol", "close"]].copy()
    source["date"] = pd.to_datetime(source["date"], errors="raise").dt.normalize()
    source["symbol"] = source["symbol"].astype("string")
    source["close"] = pd.to_numeric(source["close"], errors="coerce")
    if source.duplicated(["date", "symbol"]).any():
        raise ValueError("duplicate symbol/date market-return row")
    calendar = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("sessions must be unique and sorted")
    if not set(source["date"]).issubset(set(calendar)):
        raise ValueError("market-return row falls outside the official session calendar")

    symbols = source["symbol"].astype(str).nunique()
    if not symbols:
        return pd.DataFrame(columns=["date", *MARKET_FEATURE_COLUMNS])

    # One dense official-session matrix avoids thousands of per-symbol pandas
    # group/sort/reindex operations. pct_change(fill_method=None) preserves
    # missing-session gaps instead of carrying a stale close forward.
    close = source.pivot(index="date", columns="symbol", values="close").reindex(calendar)
    ret1_matrix = close.pct_change(periods=1, fill_method=None).to_numpy(dtype="float32")
    ret5_matrix = close.pct_change(periods=5, fill_method=None).to_numpy(dtype="float32")
    med_ret1 = _rowwise_nanmedian(ret1_matrix)
    med_ret5 = _rowwise_nanmedian(ret5_matrix)
    if progress is not None:
        progress(symbols, symbols)
    daily = pd.DataFrame({
        "market_median_ret1": med_ret1,
        "market_median_ret5": med_ret5,
    }, index=calendar)
    daily["market_median_ret1_lag1"] = daily["market_median_ret1"].shift(1)
    daily["market_median_ret5_lag1"] = daily["market_median_ret5"].shift(1)
    return daily.rename_axis("date").reset_index()


def _rowwise_nanmedian(values: np.ndarray) -> np.ndarray:
    """Exact finite-value median per row using one NumPy partition per session."""
    if values.ndim != 2:
        raise ValueError("median input must be a two-dimensional session-by-symbol matrix")
    result = np.full(values.shape[0], np.nan, dtype="float64")
    for row_idx in range(values.shape[0]):
        finite = values[row_idx, np.isfinite(values[row_idx])]
        count = len(finite)
        if not count:
            continue
        upper = count // 2
        if count % 2:
            result[row_idx] = float(np.partition(finite, upper)[upper])
        else:
            lower_value, upper_value = np.partition(finite, (upper - 1, upper))[[upper - 1, upper]]
            result[row_idx] = (float(lower_value) + float(upper_value)) / 2.0
    return result


def build_feature_panel(
    bars: pd.DataFrame,
    *,
    sessions: Sequence[object],
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Build a signal-time-only panel from raw OHLCV; no labels are created."""
    required = {"date", "symbol", *OHLCV_COLUMNS}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"OHLCV input missing columns: {missing}")
    source = bars.loc[:, ["date", "symbol", *OHLCV_COLUMNS]].copy()
    source["date"] = pd.to_datetime(source["date"], errors="raise").dt.normalize()
    source["symbol"] = source["symbol"].astype("string")
    if source.duplicated(["date", "symbol"]).any():
        raise ValueError("duplicate symbol/date OHLCV row")
    groups = source.groupby("symbol", sort=True, observed=True)
    symbol_count = int(source["symbol"].nunique())
    batches = []
    parts = []
    for idx, (_symbol, group) in enumerate(groups, start=1):
        parts.append(compute_symbol_features(group, sessions=sessions))
        if len(parts) >= 100 or idx == symbol_count:
            batches.append(pd.concat(parts, ignore_index=True))
            parts.clear()
            if progress is not None:
                progress(idx, symbol_count)
    panel = pd.concat(batches, ignore_index=True) if batches else pd.DataFrame()
    panel = add_market_features(panel, sessions=sessions)
    if panel.duplicated(["date", "symbol"]).any():
        raise RuntimeError("feature panel is not unique by date/symbol")
    panel = panel.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    panel["symbol"] = panel["symbol"].astype("category")
    return panel
