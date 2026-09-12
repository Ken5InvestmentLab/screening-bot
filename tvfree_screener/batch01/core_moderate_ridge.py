"""Registered low-complexity Core family: capped-return expanding Ridge ranker."""
from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json

import numpy as np
import pandas as pd


FEATURES = (
    "ret1", "ret3", "ret5", "ret10", "ret20", "ret40",
    "volr20_prevavg", "atr14p", "pos20", "pos40", "pos60",
    "dd20", "dd40", "dd60", "range_pct", "body_pct",
    "close_location", "gap", "down3", "down5", "consecutive_down",
    "dispersion20", "volume_trend5_20", "market_median_ret1",
    "market_median_ret5", "rel_ret5_lag1",
)

FAMILY_SPEC = {
    "experiment_id": "CORE-RIDGE-20260913-04",
    "family": "core_moderate_capped_return_ridge_v1",
    "purpose": "Rank the full eligible daily TSE universe by a low-complexity estimate of moderate positive five-session returns.",
    "universe": "Every source symbol/session passing positive, internally consistent signal-day OHLCV and all registered feature availability checks; no watchlist-frequency cap, no top-k pool truncation, no fixed maximum names per day.",
    "feature_build": "Compute each symbol independently and append bounded Parquet row groups; market medians come from the full date-limited OHLCV set. The feature panel is a decision-only artifact.",
    "label_scope": "Build outcomes only for every-fifth-session eligible training rows and all scored-period eligible candidate rows; retain the full candidate pool before ranking and selection.",
    "feature_timestamp": "After the signal-date official-session close.",
    "market_feature_lag_sessions": 0,
    "features": list(FEATURES),
    "feature_missingness": "A row is eligible only when every registered feature is finite; no outcome-dependent imputation or row substitution.",
    "signal_quality": "All signal OHLCV finite; open/high/low/close positive; volume positive; high>=max(open,close); low<=min(open,close); high>=low.",
    "target": "gross return from next XTKS session open to close of the fifth XTKS session including entry; training response=min(gross_return,0.30), with all negative responses retained unchanged.",
    "target_cost": "Model fits the gross capped target. Policy evaluation separately reports round-trip cost sensitivities 0%, 0.5%, 1%; 0.5% is not measured execution cost.",
    "training": {
        "algorithm": "Ordinary Ridge regression solved from standardized feature cross-products; intercept unpenalized.",
        "alpha": 10.0,
        "winsorization": "Training-only per-feature 1st/99th percentile clipping.",
        "scaling": "Training-only mean and population standard deviation after clipping; zero-variance features make the fold INCONCLUSIVE.",
        "sample_dates": "One out of each five official sessions, fixed by absolute zero-based XTKS session_index modulo 5 equal to 0; all eligible symbols on sampled sessions.",
        "schedule": "Expanding fit at first official XTKS session of each calendar quarter; fit data includes only sampled rows whose fifth-session label exit is strictly before the quarter's first session.",
        "warmup": "2022-01-04 through 2022-06-30; warm-up is training only.",
        "minimum_resolved_training_rows": 500,
    },
    "ranking": [["predicted_capped_return", "descending"], ["symbol", "ascending"]],
    "selection_study": {
        "top_n": [1, 2, 3, 5],
        "cooldown": "One immediately prior XTKS session per independent Top-N policy; only actually selected names update that policy state; state is not reset at year boundary.",
        "multiple_names_per_day": True,
        "candidate_pool": "All eligible rows retained before ranking/cooldown/Top-N.",
    },
    "discovery_gates": {
        "core_signal_net_at_0_5pct": ["mean>0", "median>0", "mean_excluding_top3_winners>0"],
        "core_complete_daily_cohort_net_at_0_5pct": ["mean>0", "median>0", "mean_excluding_top3_winners>0"],
        "ranking_value_add": "On at least 20 common complete active dates, policy equal-weight daily cohort mean must exceed full candidate-pool equal-weight cohort mean.",
        "tail_risk": "Policy signal-level -10% and -20% rates must not exceed the full candidate-pool rates.",
        "frequency": "Report selected signal count divided by every calendar month in the registered discovery window; 5/month is reported as a separate objective flag, not silently used as a selection gate.",
        "policy_choice": "Among all policies passing every listed gate, choose greatest net complete-cohort mean; exact ties choose smaller Top-N. If none pass, selection remains unresolved and no 2024 policy confirmation opens.",
    },
    "periods": {
        "discovery_selection": "2022-07-01 through 2023-12-31; purge any signal whose fifth-session exit is after the final 2023 XTKS session.",
        "locked_confirmation": "2024 only after a discovery policy passes and its selection count is frozen; purge exits after the final 2024 XTKS session.",
        "2025": "Do not open unless a discovery policy passes and frozen 2024 confirmation passes.",
        "2026": "Report only; no selection or fit from 2026 outcomes.",
    },
    "cost_scenarios": [0.0, 0.005, 0.01],
    "known_evidence_limit": "RETROSPECTIVE_PROVISIONAL; attempt03 opened discovery and may have partially read 2022H2-2023 outcome OHLCV, but produced no persisted result or policy metrics. Attempt04 is a memory-bounded engineering replay, not untouched OOS. The underlying Yahoo-derived universe is not proven point-in-time TSE membership, adjusted for all corporate actions, or executable at open/price limits.",
}

SPEC_CANONICAL_JSON = json.dumps(
    FAMILY_SPEC, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
)
FAMILY_SPEC_SHA256 = hashlib.sha256(SPEC_CANONICAL_JSON.encode("utf-8")).hexdigest()


def signal_quality_mask(frame: pd.DataFrame) -> pd.Series:
    required = {"open", "high", "low", "close", "volume", *FEATURES}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Core Ridge input is missing columns: {missing}")
    feature_values = frame.loc[:, list(FEATURES)].to_numpy(dtype="float32", na_value=np.nan)
    bars = frame.loc[:, ["open", "high", "low", "close", "volume"]].to_numpy(
        dtype="float64", na_value=np.nan,
    )
    open_, high, low, close, volume = bars.T
    valid = np.isfinite(feature_values).all(axis=1)
    valid &= np.isfinite(bars).all(axis=1)
    valid &= (bars[:, :4] > 0).all(axis=1)
    valid &= volume > 0
    valid &= high >= np.maximum(open_, close)
    valid &= low <= np.minimum(open_, close)
    valid &= high >= low
    return pd.Series(valid, index=frame.index, dtype=bool)


def cap_training_target(gross_returns: Sequence[float] | pd.Series) -> np.ndarray:
    values = pd.to_numeric(pd.Series(gross_returns), errors="coerce").to_numpy(dtype="float64")
    if not np.isfinite(values).all():
        raise ValueError("training targets must be finite resolved gross returns")
    return np.minimum(values, 0.30)


def fit_ridge(features: pd.DataFrame | np.ndarray, target: Sequence[float]) -> dict[str, object]:
    """Fit one frozen standardized Ridge model using train-only transforms."""
    matrix = np.asarray(features, dtype="float64")
    response = cap_training_target(target)
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURES):
        raise ValueError("feature matrix does not match the frozen feature count")
    if len(matrix) != len(response) or len(response) < 500:
        raise ValueError("Ridge fit needs aligned data and at least 500 resolved rows")
    if not np.isfinite(matrix).all() or not np.isfinite(response).all():
        raise ValueError("Ridge fit does not silently impute missing features or targets")
    lower = np.quantile(matrix, 0.01, axis=0)
    upper = np.quantile(matrix, 0.99, axis=0)
    clipped = np.clip(matrix, lower, upper)
    mean = clipped.mean(axis=0)
    scale = clipped.std(axis=0, ddof=0)
    if (~np.isfinite(scale)).any() or (scale <= 1e-12).any():
        raise ValueError("zero-variance or invalid feature in Ridge training fold")
    standardized = (clipped - mean) / scale
    target_mean = float(response.mean())
    centered_target = response - target_mean
    gram = standardized.T @ standardized
    rhs = standardized.T @ centered_target
    coefficient = np.linalg.solve(gram + 10.0 * np.eye(gram.shape[0]), rhs)
    return {
        "lower": lower,
        "upper": upper,
        "mean": mean,
        "scale": scale,
        "coefficient": coefficient,
        "intercept": target_mean,
        "n_train": int(len(response)),
        "target_mean": target_mean,
        "training_r2_in_sample": float(1.0 - np.square(centered_target - standardized @ coefficient).sum() / np.square(centered_target).sum())
        if np.square(centered_target).sum() > 0 else None,
    }


def predict_ridge(model: dict[str, object], features: pd.DataFrame | np.ndarray) -> np.ndarray:
    matrix = np.asarray(features, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURES):
        raise ValueError("prediction matrix does not match frozen feature count")
    if not np.isfinite(matrix).all():
        raise ValueError("prediction features must be finite")
    clipped = np.clip(matrix, model["lower"], model["upper"])
    standardized = (clipped - model["mean"]) / model["scale"]
    return float(model["intercept"]) + standardized @ model["coefficient"]
