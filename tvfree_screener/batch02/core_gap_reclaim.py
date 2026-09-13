"""Signal-time candidate and selector for the gap-down reclaim hypothesis."""
from __future__ import annotations

import numpy as np
import pandas as pd


FAMILY = "core_gap_down_partial_reclaim_v1"
POLICY = "daily_score_q80_one_session_symbol_cooldown"
GAP_MAX = -0.01
RECLAIM_MIN = 0.50
RECLAIM_MAX_EXCLUSIVE = 1.0
CLOSE_LOCATION_MIN = 0.75
DAILY_SCORE_QUANTILE = 0.80


def build_candidate_pool(panel: pd.DataFrame, *, start: object, end: object) -> tuple[pd.DataFrame, dict[str, int]]:
    """Keep every clean partial gap-reclaim setup using signal-date fields only."""
    required = {"date", "symbol", "open", "high", "low", "close", "volume", "gap", "close_location"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"gap-reclaim panel is missing fields: {missing}")
    frame = panel.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    frame = frame.loc[frame["date"].between(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize())].copy()
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("gap-reclaim signal panel has duplicate symbol/session rows")
    numeric_columns = ["open", "high", "low", "close", "volume", "gap", "close_location"]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame.loc[:, ["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    open_, high, low, close, volume = values.T if len(values) else (np.array([]),) * 5
    clean = np.isfinite(values).all(axis=1) if len(values) else np.zeros(0, dtype=bool)
    if len(values):
        clean &= (values[:, :4] > 0).all(axis=1) & (volume > 0)
        clean &= (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    finite_setup = np.isfinite(frame["gap"].to_numpy(dtype="float64")) & np.isfinite(frame["close_location"].to_numpy(dtype="float64"))
    previous_close = np.divide(
        open_, 1.0 + frame["gap"].to_numpy(dtype="float64"),
        out=np.full(len(frame), np.nan, dtype="float64"),
        where=np.isfinite(frame["gap"].to_numpy(dtype="float64")) & (1.0 + frame["gap"].to_numpy(dtype="float64") > 0),
    )
    gap_size = previous_close - open_
    reclaim_fraction = np.divide(
        close - open_, gap_size,
        out=np.full(len(frame), np.nan, dtype="float64"),
        where=np.isfinite(gap_size) & (gap_size > 0),
    )
    frame["previous_close_from_gap"] = previous_close
    frame["gap_reclaim_fraction"] = reclaim_fraction
    setup = (
        clean
        & finite_setup
        & (frame["gap"].to_numpy(dtype="float64") <= GAP_MAX)
        & (frame["close_location"].to_numpy(dtype="float64") >= CLOSE_LOCATION_MIN)
        & (reclaim_fraction >= RECLAIM_MIN)
        & (reclaim_fraction < RECLAIM_MAX_EXCLUSIVE)
    )
    counts = {
        "source_rows_in_period": int(len(frame)),
        "clean_signal_bars": int(clean.sum()),
        "invalid_signal_bars": int((~clean).sum()),
        "finite_gap_and_close_location": int(finite_setup.sum()),
        "candidate_rows": int(setup.sum()),
        "candidate_symbols": int(frame.loc[setup, "symbol"].nunique()),
        "candidate_bearing_days": int(frame.loc[setup, "date"].nunique()),
    }
    pool = frame.loc[setup, ["date", "symbol", "open", "high", "low", "close", "volume", "gap", "close_location"]].copy()
    pool["previous_close_from_gap"] = previous_close[setup]
    pool["gap_reclaim_fraction"] = reclaim_fraction[setup]
    pool["score"] = (pool["close_location"] + pool["gap_reclaim_fraction"]) / 2.0
    pool["family"] = FAMILY
    pool = pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    return pool, counts


def rank_candidates(pool: pd.DataFrame) -> pd.DataFrame:
    """Rank a daily candidate set by an equal-weight reclaim-quality score."""
    required = {"date", "symbol", "score", "gap_reclaim_fraction", "close_location"}
    if not required.issubset(pool.columns):
        raise ValueError("gap-reclaim candidate pool lacks ranking fields")
    if pool.duplicated(["date", "symbol"]).any():
        raise ValueError("gap-reclaim candidates are not unique by session and symbol")
    ranked_parts: list[pd.DataFrame] = []
    for _, group in pool.groupby("date", sort=True, observed=True):
        part = group.copy()
        cutoff = float(part["score"].quantile(DAILY_SCORE_QUANTILE, interpolation="linear"))
        part["daily_score_cutoff"] = cutoff
        part["daily_candidate_count"] = int(len(part))
        part["raw_rank"] = part["score"].rank(method="min", ascending=False).astype("int32")
        part = part.sort_values(
            ["score", "gap_reclaim_fraction", "close_location", "symbol"],
            ascending=[False, False, False, True],
            kind="mergesort",
        )
        ranked_parts.append(part)
    if not ranked_parts:
        return pool.assign(daily_score_cutoff=pd.Series(dtype="float64"), daily_candidate_count=pd.Series(dtype="int32"), raw_rank=pd.Series(dtype="int32"))
    return pd.concat(ranked_parts, ignore_index=True).sort_values(
        ["date", "score", "gap_reclaim_fraction", "close_location", "symbol"],
        ascending=[True, False, False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)


def select_candidates(ranked: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Select every score at or above each day's q80, with one XTKS-session cooldown."""
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("gap-reclaim selector needs a unique, ordered XTKS calendar")
    if ranked.empty:
        return ranked.assign(policy_id=pd.Series(dtype="object"), policy_rank=pd.Series(dtype="int32"), selection_status=pd.Series(dtype="object"))
    if not ranked["date"].isin(calendar).all():
        raise ValueError("gap-reclaim signal date is outside the XTKS calendar")
    position = {pd.Timestamp(day): index for index, day in enumerate(calendar)}
    last_selected: dict[str, int] = {}
    chosen: list[pd.Series] = []
    for day, group in ranked.groupby("date", sort=True, observed=True):
        session_index = position[pd.Timestamp(day)]
        eligible = group.loc[group["score"] >= group["daily_score_cutoff"]]
        for _, row in eligible.iterrows():
            symbol = str(row["symbol"])
            if last_selected.get(symbol) == session_index - 1:
                continue
            selected = row.copy()
            selected["policy_id"] = POLICY
            selected["selection_status"] = "SELECTED_Q80"
            chosen.append(selected)
            last_selected[symbol] = session_index
    if not chosen:
        return ranked.iloc[0:0].assign(policy_id=pd.Series(dtype="object"), policy_rank=pd.Series(dtype="int32"), selection_status=pd.Series(dtype="object"))
    selected = pd.DataFrame(chosen).reset_index(drop=True)
    selected["policy_rank"] = selected.groupby("date", sort=False, observed=True)["score"].rank(method="first", ascending=False).astype("int32")
    return selected.sort_values(["date", "policy_rank", "symbol"], kind="mergesort").reset_index(drop=True)
