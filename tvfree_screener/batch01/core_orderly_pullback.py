"""Registered Core-3 orderly pullback ranker; selection only uses signal-time data."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from .selection import rank_candidate_pool as rank_full_candidate_pool


FAMILY_SPEC = {
    "schema_version": 1,
    "experiment_id": "CORE-ORDERLY-PULLBACK-20260913-01",
    "family": "core_orderly_uptrend_pullback_rank_v1",
    "purpose": "Rank moderate orderly pullbacks within a positive 20-session trend by path efficiency and recent volume contraction.",
    "universe": "All preserved daily source symbol/session rows with valid signal-day OHLCV and finite required signal-time features; no watchlist cap, no one-name-per-day cap, no arbitrary liquidity or market-regime gate.",
    "candidate_pool": "ret20 > 0 and ret5 < 0, with finite 20-session path efficiency and volume_trend5_20.",
    "feature_timestamp": "After the signal-date XTKS close.",
    "market_feature_lag_sessions": 0,
    "features": {
        "ret5": "Signal close / close 5 XTKS sessions earlier - 1.",
        "ret20": "Signal close / close 20 XTKS sessions earlier - 1.",
        "path_efficiency20": "ret20 divided by the sum of absolute close-to-close returns over the same 20 XTKS sessions; all 20 returns must be observed, with no forward fill.",
        "volume_trend5_20": "Mean volume over the five sessions immediately before signal date divided by mean volume over the 20 sessions immediately before signal date; signal-day volume excluded.",
    },
    "ranking": {
        "score": "Arithmetic mean of the within-date average percentile rank of path_efficiency20 (higher is better) and volume_trend5_20 (lower is better).",
        "tie_break": ["path_efficiency20 descending", "volume_trend5_20 ascending", "symbol ascending"],
    },
    "target": "Gross return from next XTKS session open to close of the fifth XTKS session including entry; unresolved/actionability failures remain in the requested cohort.",
    "selection": {
        "top_n": [1, 2, 3, 5],
        "cooldown": "One immediately prior XTKS session per independent Top-N policy; only actually selected symbols update that policy state; state carries across year boundaries.",
        "multiple_names_per_day": True,
        "candidate_pool_saved_before_outcome_access": True,
    },
    "periods": {
        "warmup": "2022-01-04 through 2022-06-30 for feature initialization only.",
        "discovery": "2022-07-01 through the final XTKS session of 2023; candidates whose fifth-session exit is beyond the final 2023 session are purged.",
        "confirmation": "2024 is opened only after discovery pool KEEP and one unchanged Top-N policy passes all frozen gates; historical and retrospective, never true OOS.",
        "2025": "Locked replay only after unchanged 2024 confirmation passes.",
        "2026": "Report only; no fitting, feature, candidate, rank, or policy selection from 2026 outcomes.",
    },
    "family_gate": "At assumed 0.5% round-trip cost, candidate-pool signal mean, median, and top-three-winner-excluded mean must be positive; complete daily cohort mean, median, and top-three-winner-excluded mean must also be positive. Insufficient complete-cohort coverage is INCONCLUSIVE; unresolved rows are not dropped.",
    "selection_policy_gate": "Apply the registered batch01 Core gates unchanged: positive net signal/cohort mean, median and top-three-winner-excluded means; at least 20 common complete active dates and positive paired pool-relative cohort value add; selected -10%/-20% rates no worse than the full pool. If the pool has no complete cohorts, value-add is not established and no N can pass.",
    "data_quality": "Yahoo-derived current-universe daily history is not proven point-in-time membership, full delisted coverage, corporate-action adjusted, or executable at next open. All historical results are RETROSPECTIVE_PROVISIONAL.",
    "no_tuning": "No threshold, feature weight, candidate rule, missingness rule, target, or Top-N changes after any discovery outcomes are opened.",
    "production_boundary": "Research only. Any future scorer must run entirely in the ordinary production runtime without Codex, LLM, or external model calls. No production wiring is part of this experiment.",
}

SPEC_CANONICAL_JSON = json.dumps(
    FAMILY_SPEC, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
)
FAMILY_SPEC_SHA256 = hashlib.sha256(SPEC_CANONICAL_JSON.encode("utf-8")).hexdigest()

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
SOURCE_FEATURES = ("ret1", "ret5", "ret20", "volume_trend5_20")
RANK_FEATURES = (
    "ret5", "ret20", "path_abs_sum20", "path_efficiency20",
    "volume_trend5_20", "path_efficiency_pct", "volume_contraction_pct",
    "quality_score", "close",
)


def _valid_ohlcv(frame: pd.DataFrame) -> pd.Series:
    bars = frame.loc[:, list(OHLCV_COLUMNS)].to_numpy(dtype="float64", na_value=np.nan)
    open_, high, low, close, volume = bars.T
    valid = np.isfinite(bars).all(axis=1)
    valid &= (bars[:, :4] > 0).all(axis=1)
    valid &= volume > 0
    valid &= high >= np.maximum(open_, close)
    valid &= low <= np.minimum(open_, close)
    valid &= high >= low
    return pd.Series(valid, index=frame.index, dtype=bool)


def build_candidate_pool(panel: pd.DataFrame, *, spec_hash: str) -> pd.DataFrame:
    """Build and rank every qualifying candidate using decision-time fields only."""
    required = {"date", "symbol", *OHLCV_COLUMNS, *SOURCE_FEATURES}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"daily feature panel is missing fields: {missing}")
    work = panel.loc[:, sorted(required)].copy()
    work["date"] = pd.to_datetime(work["date"], errors="raise").dt.normalize()
    work["symbol"] = work["symbol"].astype("string")
    if work[["date", "symbol"]].isna().any().any() or work.duplicated(["date", "symbol"]).any():
        raise ValueError("daily panel keys must be present and unique")
    work = work.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    for column in (*OHLCV_COLUMNS, *SOURCE_FEATURES):
        work[column] = pd.to_numeric(work[column], errors="coerce")

    # `ret1` was computed after reindexing each symbol to the official TSE
    # calendar. Missing source sessions therefore leave a NaN and invalidate
    # any rolling 20-return path that crosses the gap.
    work["path_abs_sum20"] = work.groupby("symbol", sort=False)["ret1"].transform(
        lambda values: values.abs().rolling(20, min_periods=20).sum()
    )
    valid = _valid_ohlcv(work)
    valid &= np.isfinite(work.loc[:, list(SOURCE_FEATURES)].to_numpy(dtype="float64")).all(axis=1)
    valid &= work["ret20"].gt(0) & work["ret5"].lt(0)
    valid &= np.isfinite(work["path_abs_sum20"]) & work["path_abs_sum20"].gt(0)
    pool = work.loc[valid].copy()
    pool["path_efficiency20"] = pool["ret20"] / pool["path_abs_sum20"]
    pool = pool.loc[np.isfinite(pool["path_efficiency20"])].copy()

    if pool.empty:
        return pd.DataFrame(columns=[
            "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
            "feature_timestamp", "inclusion_reason", *OHLCV_COLUMNS,
            "ret1", "ret5", "ret20", "path_abs_sum20", "path_efficiency20",
            "volume_trend5_20",
        ])

    pool["family"] = FAMILY_SPEC["family"]
    pool["spec_hash"] = str(spec_hash)
    pool["identity_key"] = pool["symbol"]
    pool["candidate_id"] = pool["date"].dt.strftime("%Y%m%d") + ":" + pool["symbol"].astype("string")
    pool["feature_timestamp"] = pool["date"].dt.strftime("%Y-%m-%d") + " close"
    pool["inclusion_reason"] = "ret20>0_and_ret5<0_with_finite_path_efficiency_and_volume_trend"
    return pool.loc[:, [
        "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
        "feature_timestamp", "inclusion_reason", *OHLCV_COLUMNS, "ret1", "ret5", "ret20",
        "path_abs_sum20", "path_efficiency20", "volume_trend5_20",
    ]].reset_index(drop=True)


def rank_orderly_pool(pool: pd.DataFrame, *, sessions: list[object] | pd.DatetimeIndex) -> pd.DataFrame:
    """Apply the frozen equal-weight rank after the complete raw pool is saved."""
    if pool.empty:
        return pd.DataFrame(columns=[
            "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
            "score", "raw_rank", "daily_candidate_count", *RANK_FEATURES,
        ])
    work = pool.copy()
    work["date"] = pd.to_datetime(work["date"], errors="raise").dt.normalize()
    by_date = work.groupby("date", sort=False)
    work["path_efficiency_pct"] = by_date["path_efficiency20"].rank(
        method="average", pct=True, ascending=True,
    )
    work["volume_contraction_pct"] = by_date["volume_trend5_20"].rank(
        method="average", pct=True, ascending=False,
    )
    work["quality_score"] = (
        work["path_efficiency_pct"] + work["volume_contraction_pct"]
    ) / 2.0
    features = (
        "ret5", "ret20", "path_abs_sum20", "path_efficiency20",
        "volume_trend5_20", "path_efficiency_pct", "volume_contraction_pct",
        "quality_score", "close",
    )
    return rank_full_candidate_pool(
        work,
        sessions=sessions,
        feature_columns=features,
        ranking_terms=[
            ("quality_score", False),
            ("path_efficiency20", False),
            ("volume_trend5_20", True),
        ],
    )
