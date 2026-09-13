"""Causal daily lower-Bollinger-band rejection setup and fixed Top5 selector."""
from __future__ import annotations

import numpy as np
import pandas as pd


FAMILY = "core_prior20_lower_bollinger_reclaim_v1"
POLICY = "top5_band_reclaim_quality_one_session_symbol_cooldown"
MAX_NAMES_PER_DAY = 5
BAND_WINDOW = 20
BAND_SIGMA = 2.0
CLOSE_LOCATION_MIN = 0.50


def build_candidate_pool(panel: pd.DataFrame, sessions: pd.DatetimeIndex, *, start: object, end: object):
    required = {"date", "symbol", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"Bollinger-reclaim panel is missing fields: {missing}")
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("Bollinger-reclaim needs a unique ordered XTKS calendar")
    frame = panel.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("Bollinger-reclaim panel has duplicate symbol/session rows")
    frame = frame.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    open_, high, low, close, volume = values.T if len(values) else (np.array([]),) * 5
    clean = np.isfinite(values).all(axis=1) if len(values) else np.zeros(0, dtype=bool)
    if len(values):
        clean &= (values[:, :4] > 0).all(axis=1) & (volume > 0)
        clean &= (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    candle_range = high - low
    close_location = np.divide(close - low, candle_range, out=np.full(len(frame), np.nan), where=np.isfinite(candle_range) & (candle_range > 0))
    prior_lower = np.full(len(frame), np.nan, dtype="float64")
    for _, indexes in frame.groupby("symbol", sort=False, observed=True).groups.items():
        rows = np.asarray(list(indexes), dtype="int64")
        dates = pd.DatetimeIndex(frame.loc[rows, "date"])
        closes = pd.Series(frame.loc[rows, "close"].to_numpy(dtype="float64"), index=dates).reindex(calendar)
        previous = closes.shift(1)
        lower = previous.rolling(BAND_WINDOW, min_periods=BAND_WINDOW).mean() - BAND_SIGMA * previous.rolling(BAND_WINDOW, min_periods=BAND_WINDOW).std(ddof=0)
        prior_lower[rows] = lower.reindex(dates).to_numpy(dtype="float64")
    frame["prior_lower_band"] = prior_lower
    finite_band = np.isfinite(prior_lower)
    reclaim = finite_band & (low < prior_lower) & (close > prior_lower)
    setup = clean & reclaim & (close_location >= CLOSE_LOCATION_MIN)
    reclaim_quality = np.divide(close - prior_lower, candle_range, out=np.full(len(frame), np.nan), where=np.isfinite(candle_range) & (candle_range > 0))
    frame["close_location"] = close_location
    frame["band_reclaim_quality"] = reclaim_quality
    in_period = frame["date"].between(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()).to_numpy()
    counts = {
        "source_rows_in_period": int(in_period.sum()),
        "clean_signal_bars": int((clean & in_period).sum()),
        "rows_with_complete_prior20_sessions": int((finite_band & in_period).sum()),
        "lower_band_undercut_and_reclaimed": int((reclaim & in_period).sum()),
        "candidate_rows": int((setup & in_period).sum()),
        "candidate_symbols": int(frame.loc[setup & in_period, "symbol"].nunique()),
        "candidate_bearing_days": int(frame.loc[setup & in_period, "date"].nunique()),
    }
    cols = ["date", "symbol", "open", "high", "low", "close", "volume", "prior_lower_band", "close_location", "band_reclaim_quality"]
    pool = frame.loc[setup & in_period, cols].copy()
    pool["score"] = (pool["close_location"] + pool["band_reclaim_quality"]) / 2.0
    pool["family"] = FAMILY
    return pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True), counts


def rank_candidates(pool: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "score", "close_location", "band_reclaim_quality"}
    if not required.issubset(pool.columns):
        raise ValueError("Bollinger-reclaim pool lacks ranking fields")
    if pool.duplicated(["date", "symbol"]).any():
        raise ValueError("Bollinger-reclaim pool is not unique by session and symbol")
    ranked = pool.sort_values(["date", "score", "close_location", "band_reclaim_quality", "symbol"], ascending=[True, False, False, False, True], kind="mergesort").copy()
    ranked["raw_rank"] = ranked.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return ranked.reset_index(drop=True)


def select_candidates(ranked: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("Bollinger-reclaim selector needs a unique ordered XTKS calendar")
    if not ranked.empty and not ranked["date"].isin(calendar).all():
        raise ValueError("Bollinger-reclaim signal is outside the official calendar")
    if ranked.empty:
        return ranked.assign(policy_id=pd.Series(dtype="object"), policy_rank=pd.Series(dtype="int32"))
    position = {pd.Timestamp(day): index for index, day in enumerate(calendar)}
    last_selected: dict[str, int] = {}
    chosen: list[pd.Series] = []
    for day, group in ranked.groupby("date", sort=True, observed=True):
        slot, count = position[pd.Timestamp(day)], 0
        for _, row in group.iterrows():
            symbol = str(row["symbol"])
            if last_selected.get(symbol) == slot - 1:
                continue
            item = row.copy()
            item["policy_id"] = POLICY
            item["selection_status"] = "SELECTED_TOP5"
            chosen.append(item)
            last_selected[symbol] = slot
            count += 1
            if count == MAX_NAMES_PER_DAY:
                break
    if not chosen:
        return ranked.iloc[0:0].assign(policy_id=pd.Series(dtype="object"), policy_rank=pd.Series(dtype="int32"))
    selected = pd.DataFrame(chosen).reset_index(drop=True)
    selected["policy_rank"] = selected.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return selected.sort_values(["date", "policy_rank", "symbol"], kind="mergesort").reset_index(drop=True)
