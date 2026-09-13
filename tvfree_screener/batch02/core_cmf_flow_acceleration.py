"""Causal volume-weighted buying-pressure acceleration selector."""
from __future__ import annotations

import numpy as np
import pandas as pd


FAMILY = "core_cmf_flow_acceleration_v1"
POLICY = "top5_cmf5_positive_above_cmf20_one_session_cooldown"
MAX_NAMES_PER_DAY = 5


def build_candidate_pool(panel: pd.DataFrame, sessions: pd.DatetimeIndex, *, start: object, end: object):
    required = {"date", "symbol", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"CMF panel is missing fields: {missing}")
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("CMF selector needs a unique ordered XTKS calendar")
    frame = panel.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("CMF panel has duplicate symbol/session rows")
    if not frame["date"].isin(calendar).all():
        raise ValueError("CMF panel contains a date outside the official XTKS calendar")
    numeric = ["open", "high", "low", "close", "volume"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame[numeric].to_numpy(dtype="float64")
    if len(values):
        open_, high, low, close, volume = values.T
        valid = np.isfinite(values).all(axis=1)
        valid &= (values[:, :4] > 0).all(axis=1) & (volume > 0)
        valid &= (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high > low)
    else:
        valid = np.zeros(0, dtype=bool)
    frame["bar_valid"] = valid
    frame = frame.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    frame["session_index"] = frame["date"].map(pd.Series(np.arange(len(calendar)), index=calendar)).astype("int64")
    candle_range = frame["high"] - frame["low"]
    multiplier = ((frame["close"] - frame["low"]) - (frame["high"] - frame["close"])) / candle_range
    frame["money_flow_volume"] = (multiplier * frame["volume"]).where(frame["bar_valid"])
    frame["flow_volume"] = frame["volume"].where(frame["bar_valid"])
    grouped = frame.groupby("symbol", sort=False, observed=True)
    for window in (5, 20):
        flow_sum = grouped["money_flow_volume"].rolling(window, min_periods=window).sum().reset_index(level=0, drop=True)
        volume_sum = grouped["flow_volume"].rolling(window, min_periods=window).sum().reset_index(level=0, drop=True)
        frame[f"cmf{window}"] = flow_sum / volume_sum.replace(0, np.nan)
    grouped = frame.groupby("symbol", sort=False, observed=True)
    consecutive5 = frame["session_index"].sub(grouped["session_index"].shift(4)).eq(4)
    consecutive20 = frame["session_index"].sub(grouped["session_index"].shift(19)).eq(19)
    complete = frame["cmf5"].notna() & frame["cmf20"].notna() & consecutive5 & consecutive20
    frame["cmf_delta"] = frame["cmf5"] - frame["cmf20"]
    frame["flow_complete"] = complete
    period = frame["date"].between(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize())
    positive = complete & frame["cmf5"].gt(0)
    improving = positive & frame["cmf_delta"].gt(0)
    eligible = improving & period
    counts = {
        "source_rows_in_period": int(period.sum()),
        "valid_ohlcv_rows": int((frame["bar_valid"] & period).sum()),
        "complete_consecutive_flow_rows": int((complete & period).sum()),
        "positive_cmf5_rows": int((positive & period).sum()),
        "improving_flow_rows": int((improving & period).sum()),
        "candidate_rows": int(eligible.sum()),
        "candidate_symbols": int(frame.loc[eligible, "symbol"].nunique()),
        "candidate_bearing_days": int(frame.loc[eligible, "date"].nunique()),
    }
    pool = frame.loc[eligible, ["date", "symbol", "cmf5", "cmf20", "cmf_delta"]].copy()
    pool["family"] = FAMILY
    return pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True), counts


def rank_candidates(pool: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "cmf5", "cmf20", "cmf_delta"}
    if not required.issubset(pool.columns):
        raise ValueError("CMF pool lacks ranking fields")
    if pool.duplicated(["date", "symbol"]).any():
        raise ValueError("CMF pool is not unique by symbol/session")
    ranked = pool.sort_values(
        ["date", "cmf_delta", "cmf5", "cmf20", "symbol"],
        ascending=[True, False, False, False, True],
        kind="mergesort",
    ).copy()
    ranked["raw_rank"] = ranked.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return ranked.reset_index(drop=True)


def select_candidates(ranked: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("CMF selector needs a unique ordered XTKS calendar")
    if not ranked.empty and not ranked["date"].isin(calendar).all():
        raise ValueError("CMF signal date is outside the XTKS calendar")
    if ranked.empty:
        return ranked.assign(policy_id=pd.Series(dtype="object"), policy_rank=pd.Series(dtype="int32"))
    position = {pd.Timestamp(day): index for index, day in enumerate(calendar)}
    last_selected: dict[str, int] = {}
    chosen: list[pd.Series] = []
    for day, group in ranked.groupby("date", sort=True, observed=True):
        slot = position[pd.Timestamp(day)]
        count = 0
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
