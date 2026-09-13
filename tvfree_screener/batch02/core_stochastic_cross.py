"""Causal daily stochastic oversold cross and fixed Top5 selector."""
from __future__ import annotations

import numpy as np
import pandas as pd


FAMILY = "core_stochastic14_3_oversold_cross_v1"
POLICY = "top5_stochastic_cross_strength_one_session_symbol_cooldown"
MAX_NAMES_PER_DAY = 5
K_WINDOW = 14
D_WINDOW = 3
OVERSOLD_MAX = 20.0
CLOSE_LOCATION_MIN = 0.50


def build_candidate_pool(panel: pd.DataFrame, sessions: pd.DatetimeIndex, *, start: object, end: object):
    required = {"date", "symbol", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"stochastic panel is missing fields: {missing}")
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("stochastic selector needs a unique ordered XTKS calendar")
    frame = panel.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("stochastic panel has duplicate symbol/session rows")
    frame = frame.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    open_, high, low, close, volume = values.T if len(values) else (np.array([]),) * 5
    clean = np.isfinite(values).all(axis=1) if len(values) else np.zeros(0, dtype=bool)
    if len(values):
        clean &= (values[:, :4] > 0).all(axis=1) & (volume > 0)
        clean &= (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    close_location = np.divide(close - low, high - low, out=np.full(len(frame), np.nan), where=np.isfinite(high - low) & ((high - low) > 0))
    k = np.full(len(frame), np.nan, dtype="float64")
    d = np.full(len(frame), np.nan, dtype="float64")
    for _, indexes in frame.groupby("symbol", sort=False, observed=True).groups.items():
        rows = np.asarray(list(indexes), dtype="int64")
        dates = pd.DatetimeIndex(frame.loc[rows, "date"])
        aligned = frame.loc[rows, ["high", "low", "close"]].set_axis(dates).reindex(calendar)
        low14 = aligned["low"].rolling(K_WINDOW, min_periods=K_WINDOW).min()
        high14 = aligned["high"].rolling(K_WINDOW, min_periods=K_WINDOW).max()
        fast_k = 100.0 * (aligned["close"] - low14) / (high14 - low14).replace(0, np.nan)
        slow_d = fast_k.rolling(D_WINDOW, min_periods=D_WINDOW).mean()
        k[rows] = fast_k.reindex(dates).to_numpy(dtype="float64")
        d[rows] = slow_d.reindex(dates).to_numpy(dtype="float64")
    frame["stoch_k"] = k
    frame["stoch_d"] = d
    previous_k = np.full(len(frame), np.nan, dtype="float64")
    previous_d = np.full(len(frame), np.nan, dtype="float64")
    for _, indexes in frame.groupby("symbol", sort=False, observed=True).groups.items():
        rows = np.asarray(list(indexes), dtype="int64")
        dates = pd.DatetimeIndex(frame.loc[rows, "date"])
        kval = pd.Series(k[rows], index=dates).reindex(calendar).shift(1)
        dval = pd.Series(d[rows], index=dates).reindex(calendar).shift(1)
        previous_k[rows] = kval.reindex(dates).to_numpy(dtype="float64")
        previous_d[rows] = dval.reindex(dates).to_numpy(dtype="float64")
    frame["previous_stoch_k"] = previous_k
    frame["previous_stoch_d"] = previous_d
    crossover = np.isfinite(k) & np.isfinite(d) & np.isfinite(previous_k) & np.isfinite(previous_d) & (previous_k <= previous_d) & (previous_k <= OVERSOLD_MAX) & (k > d)
    setup = clean & crossover & (close_location >= CLOSE_LOCATION_MIN)
    frame["cross_strength"] = k - d
    in_period = frame["date"].between(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()).to_numpy()
    counts = {
        "source_rows_in_period": int(in_period.sum()), "clean_signal_bars": int((clean & in_period).sum()),
        "complete_stochastic_rows": int((np.isfinite(k) & np.isfinite(d) & np.isfinite(previous_k) & np.isfinite(previous_d) & in_period).sum()),
        "oversold_cross_rows": int((crossover & in_period).sum()), "candidate_rows": int((setup & in_period).sum()),
        "candidate_symbols": int(frame.loc[setup & in_period, "symbol"].nunique()), "candidate_bearing_days": int(frame.loc[setup & in_period, "date"].nunique()),
    }
    cols = ["date", "symbol", "open", "high", "low", "close", "volume", "stoch_k", "stoch_d", "previous_stoch_k", "previous_stoch_d", "cross_strength"]
    pool = frame.loc[setup & in_period, cols].copy()
    pool["close_location"] = close_location[setup & in_period]
    pool["score"] = pool["cross_strength"]
    pool["family"] = FAMILY
    return pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True), counts


def rank_candidates(pool: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "score", "close_location", "cross_strength"}
    if not required.issubset(pool.columns):
        raise ValueError("stochastic pool lacks ranking fields")
    if pool.duplicated(["date", "symbol"]).any():
        raise ValueError("stochastic pool is not unique by symbol/session")
    ranked = pool.sort_values(["date", "score", "close_location", "symbol"], ascending=[True, False, False, True], kind="mergesort").copy()
    ranked["raw_rank"] = ranked.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return ranked.reset_index(drop=True)


def select_candidates(ranked: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("stochastic selector needs a unique ordered XTKS calendar")
    if not ranked.empty and not ranked["date"].isin(calendar).all():
        raise ValueError("stochastic signal date is outside the XTKS calendar")
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
            item = row.copy(); item["policy_id"] = POLICY; item["selection_status"] = "SELECTED_TOP5"; chosen.append(item)
            last_selected[symbol] = slot; count += 1
            if count == MAX_NAMES_PER_DAY:
                break
    if not chosen:
        return ranked.iloc[0:0].assign(policy_id=pd.Series(dtype="object"), policy_rank=pd.Series(dtype="int32"))
    selected = pd.DataFrame(chosen).reset_index(drop=True)
    selected["policy_rank"] = selected.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return selected.sort_values(["date", "policy_rank", "symbol"], kind="mergesort").reset_index(drop=True)
