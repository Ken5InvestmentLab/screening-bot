"""Candidate and rank policy for a five-session support-sweep reclaim setup."""
from __future__ import annotations

import numpy as np
import pandas as pd


FAMILY = "core_five_session_support_sweep_reclaim_v1"
POLICY = "top5_reclaim_quality_one_session_symbol_cooldown"
MAX_NAMES_PER_DAY = 5
SUPPORT_WINDOW = 5
CLOSE_LOCATION_MIN = 0.75


def build_candidate_pool(
    panel: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    *,
    start: object,
    end: object,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Find bars that undercut and recover the preceding five XTKS-session low."""
    required = {"date", "symbol", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"support-sweep panel is missing fields: {missing}")
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("support-sweep needs a unique ordered XTKS calendar")
    frame = panel.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("support-sweep panel has duplicate symbol/session rows")
    frame = frame.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    open_, high, low, close, volume = values.T if len(values) else (np.array([]),) * 5
    clean = np.isfinite(values).all(axis=1) if len(values) else np.zeros(0, dtype=bool)
    if len(values):
        clean &= (values[:, :4] > 0).all(axis=1) & (volume > 0)
        clean &= (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    frame["close_location"] = np.divide(
        close - low, high - low,
        out=np.full(len(frame), np.nan, dtype="float64"),
        where=np.isfinite(high - low) & ((high - low) > 0),
    )

    # Reindex each symbol to the full official calendar before rolling. A missing
    # stock bar therefore breaks the five-session lookback instead of bridging it.
    prior_low = np.full(len(frame), np.nan, dtype="float64")
    for _, indexes in frame.groupby("symbol", sort=False, observed=True).groups.items():
        rows = np.asarray(list(indexes), dtype="int64")
        dates = pd.DatetimeIndex(frame.loc[rows, "date"])
        lows = pd.Series(frame.loc[rows, "low"].to_numpy(dtype="float64"), index=dates)
        aligned = lows.reindex(calendar)
        support = aligned.shift(1).rolling(SUPPORT_WINDOW, min_periods=SUPPORT_WINDOW).min()
        prior_low[rows] = support.reindex(dates).to_numpy(dtype="float64")
    frame["prior5_low"] = prior_low
    finite_support = np.isfinite(prior_low)
    sweep = finite_support & (low < prior_low) & (close > prior_low)
    setup = clean & sweep & (frame["close_location"].to_numpy(dtype="float64") >= CLOSE_LOCATION_MIN)
    reclaim = np.divide(
        close - prior_low,
        high - low,
        out=np.full(len(frame), np.nan, dtype="float64"),
        where=np.isfinite(high - low) & ((high - low) > 0),
    )
    frame["support_reclaim_quality"] = reclaim
    in_period = frame["date"].between(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()).to_numpy()
    counts = {
        "source_rows_in_period": int(in_period.sum()),
        "clean_signal_bars": int((clean & in_period).sum()),
        "rows_with_complete_prior5_sessions": int((finite_support & in_period).sum()),
        "support_undercut_and_reclaimed": int((sweep & in_period).sum()),
        "candidate_rows": int((setup & in_period).sum()),
        "candidate_symbols": int(frame.loc[setup & in_period, "symbol"].nunique()),
        "candidate_bearing_days": int(frame.loc[setup & in_period, "date"].nunique()),
    }
    columns = ["date", "symbol", "open", "high", "low", "close", "volume", "prior5_low", "close_location", "support_reclaim_quality"]
    pool = frame.loc[setup & in_period, columns].copy()
    pool["score"] = (pool["close_location"] + pool["support_reclaim_quality"]) / 2.0
    pool["family"] = FAMILY
    return pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True), counts


def rank_candidates(pool: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "score", "close_location", "support_reclaim_quality"}
    if not required.issubset(pool.columns):
        raise ValueError("support-sweep pool lacks ranking fields")
    if pool.duplicated(["date", "symbol"]).any():
        raise ValueError("support-sweep pool is not unique by session and symbol")
    ranked = pool.sort_values(
        ["date", "score", "close_location", "support_reclaim_quality", "symbol"],
        ascending=[True, False, False, False, True],
        kind="mergesort",
    ).copy()
    ranked["raw_rank"] = ranked.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return ranked.reset_index(drop=True)


def select_candidates(ranked: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if calendar.empty or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("support-sweep selector needs a unique ordered XTKS calendar")
    if not ranked.empty and not ranked["date"].isin(calendar).all():
        raise ValueError("support-sweep signal date is outside the XTKS calendar")
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
            selected = row.copy()
            selected["policy_id"] = POLICY
            selected["selection_status"] = "SELECTED_TOP5"
            chosen.append(selected)
            last_selected[symbol] = slot
            count += 1
            if count >= MAX_NAMES_PER_DAY:
                break
    if not chosen:
        return ranked.iloc[0:0].assign(policy_id=pd.Series(dtype="object"), policy_rank=pd.Series(dtype="int32"))
    selected = pd.DataFrame(chosen).reset_index(drop=True)
    selected["policy_rank"] = selected.groupby("date", sort=False, observed=True).cumcount().add(1).astype("int32")
    return selected.sort_values(["date", "policy_rank", "symbol"], kind="mergesort").reset_index(drop=True)
