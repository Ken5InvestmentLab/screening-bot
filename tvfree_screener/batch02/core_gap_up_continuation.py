"""Causal gap-up acceptance event and equal-weight cross-sectional rank selector."""
from __future__ import annotations

import numpy as np
import pandas as pd


FAMILY = "core_gap_up_volume_acceptance_v1"
POLICY = "top5_equal_rank_gap_volume_close_one_session_cooldown"
MAX_NAMES_PER_DAY = 5
GAP_MIN = 0.015
VOLUME_RATIO_MIN = 1.5
CLOSE_LOCATION_MIN = 0.70


def build_candidate_pool(panel: pd.DataFrame, sessions: pd.DatetimeIndex, *, start: object, end: object):
    required = {"date", "symbol", "open", "high", "low", "close", "volume", "gap", "volr20_prevavg", "close_location", "body_pct"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"gap-up panel is missing fields: {missing}")
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("gap-up selector needs a unique ordered XTKS calendar")
    frame = panel.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("gap-up panel has duplicate symbol/session rows")
    if not frame["date"].isin(calendar).all():
        raise ValueError("gap-up panel contains a date outside the official XTKS calendar")
    numeric = ["open", "high", "low", "close", "volume", "gap", "volr20_prevavg", "close_location", "body_pct"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    open_, high, low, close, volume = values.T if len(values) else (np.array([]),) * 5
    clean = np.isfinite(values).all(axis=1) if len(values) else np.zeros(0, dtype=bool)
    if len(values):
        clean &= (values[:, :4] > 0).all(axis=1) & (volume > 0)
        clean &= (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    gap = frame["gap"].to_numpy(dtype="float64")
    volr = frame["volr20_prevavg"].to_numpy(dtype="float64")
    close_loc = frame["close_location"].to_numpy(dtype="float64")
    body = frame["body_pct"].to_numpy(dtype="float64")
    feature_valid = np.isfinite(gap) & np.isfinite(volr) & np.isfinite(close_loc) & np.isfinite(body)
    period = frame["date"].between(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()).to_numpy()
    event = clean & feature_valid & (gap >= GAP_MIN) & (volr >= VOLUME_RATIO_MIN) & (close_loc >= CLOSE_LOCATION_MIN) & (body > 0)
    eligible = event & period
    counts = {
        "source_rows_in_period": int(period.sum()),
        "clean_signal_bars": int((clean & period).sum()),
        "feature_complete_rows": int((feature_valid & period).sum()),
        "gap_threshold_rows": int((clean & feature_valid & (gap >= GAP_MIN) & period).sum()),
        "volume_threshold_rows": int((clean & feature_valid & (gap >= GAP_MIN) & (volr >= VOLUME_RATIO_MIN) & period).sum()),
        "positive_body_rows": int((clean & feature_valid & (gap >= GAP_MIN) & (volr >= VOLUME_RATIO_MIN) & (body > 0) & period).sum()),
        "candidate_rows": int(eligible.sum()),
        "candidate_symbols": int(frame.loc[eligible, "symbol"].nunique()),
        "candidate_bearing_days": int(frame.loc[eligible, "date"].nunique()),
    }
    cols = ["date", "symbol", "open", "high", "low", "close", "volume", "gap", "volr20_prevavg", "close_location", "body_pct"]
    pool = frame.loc[eligible, cols].copy()
    pool["family"] = FAMILY
    return pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True), counts


def rank_candidates(pool: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "gap", "volr20_prevavg", "close_location"}
    if not required.issubset(pool.columns):
        raise ValueError("gap-up pool lacks ranking fields")
    if pool.duplicated(["date", "symbol"]).any():
        raise ValueError("gap-up pool is not unique by symbol/session")
    ranked = pool.copy()
    for name, column in (("gap_rank", "gap"), ("volume_rank", "volr20_prevavg"), ("close_rank", "close_location")):
        ranked[name] = ranked.groupby("date", sort=False, observed=True)[column].rank(method="average", pct=True)
    ranked["score"] = ranked[["gap_rank", "volume_rank", "close_rank"]].mean(axis=1)
    ranked = ranked.sort_values(["date", "score", "close_location", "volr20_prevavg", "gap", "symbol"], ascending=[True, False, False, False, False, True], kind="mergesort").copy()
    ranked["raw_rank"] = ranked.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return ranked.reset_index(drop=True)


def select_candidates(ranked: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("gap-up selector needs a unique ordered XTKS calendar")
    if not ranked.empty and not ranked["date"].isin(calendar).all():
        raise ValueError("gap-up signal date is outside the XTKS calendar")
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
