"""Signal-time all-market feature audit for large five-session winners/losers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tvfree_screener.batch01.feature_separation import (
    discovery_tercile_edges,
    feature_band_metrics,
    feature_class_separation,
)


FEATURES = (
    "ret1", "ret3", "ret5", "ret10", "ret20", "ret40",
    "volr20_prevavg", "volume_trend5_20", "log_dollar_volume", "dollar_volume_median20",
    "atr14p", "pos20", "pos40", "pos60", "dd20", "dd40",
    "gap", "range_pct", "body_pct", "close_location", "red_count5", "down3", "down5",
    "consecutive_down", "ret1_minus_ret5_per5", "dispersion20",
    "market_median_ret1", "market_median_ret5", "market_median_ret1_lag1",
    "market_median_ret5_lag1", "rel_ret5_lag1",
)

WINNER_THRESHOLD = 0.10
LOSER_THRESHOLD = -0.10
MIN_CLASS_COUNT = 50
MIN_FINITE_RATE = 0.95
MIN_ABSOLUTE_POOLED_CLIFFS_DELTA = 0.10
MAX_SELECTED_FEATURES = 2
SIGNAL_GAP_RATIO_MIN = 0.60
SIGNAL_GAP_RATIO_MAX = 1.40


def build_universe_pool(panel: pd.DataFrame, *, start: object, end: object) -> tuple[pd.DataFrame, dict[str, int]]:
    """Retain all valid, actionable daily bars in the requested signal period."""
    required = {"date", "symbol", "open", "high", "low", "close", "volume", "gap", *FEATURES}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"market-state panel is missing fields: {missing}")
    columns = list(dict.fromkeys(["date", "symbol", "open", "high", "low", "close", "volume", "gap", *FEATURES]))
    frame = panel.loc[:, columns].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    frame = frame.loc[frame["date"].between(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize())].copy()
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("market-state panel has duplicate symbol/session rows")
    for column in ("open", "high", "low", "close", "volume", "gap"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    ohlcv = frame.loc[:, ["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    clean = np.isfinite(ohlcv).all(axis=1)
    if len(frame):
        open_, high, low, close, volume = ohlcv.T
        clean &= (ohlcv[:, :4] > 0).all(axis=1) & (volume > 0)
        clean &= (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    gap = frame["gap"].to_numpy(dtype="float64")
    gap_ratio = 1.0 + gap
    gap_ok = np.isfinite(gap) & (gap_ratio >= SIGNAL_GAP_RATIO_MIN) & (gap_ratio <= SIGNAL_GAP_RATIO_MAX)
    eligible = clean & gap_ok
    counts = {
        "source_rows_in_period": int(len(frame)),
        "clean_signal_bars": int(clean.sum()),
        "signal_bars_outside_gap_actionability_range": int((clean & ~gap_ok).sum()),
        "eligible_signal_rows": int(eligible.sum()),
        "eligible_symbols": int(frame.loc[eligible, "symbol"].nunique()),
        "eligible_signal_days": int(frame.loc[eligible, "date"].nunique()),
    }
    pool = frame.loc[eligible].copy().sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    return pool, counts


def period_frames(joined: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return separately purged, predeclared comparison periods."""
    ranges = {
        "2022H2": ("2022-07-01", "2022-12-23"),
        "2023": ("2023-01-01", "2023-12-22"),
        "discovery_pooled": ("2022-07-01", "2023-12-22"),
        "2024_confirmation": ("2024-01-01", "2024-12-20"),
    }
    return {
        name: joined.loc[joined["date"].between(start, end)].copy()
        for name, (start, end) in ranges.items()
    }


def discover_features(frames: dict[str, pd.DataFrame]) -> tuple[dict[str, dict[str, dict[str, object]]], list[dict[str, object]]]:
    """Select at most two sizable, sufficiently covered discovery directions."""
    periods = ("2022H2", "2023", "discovery_pooled")
    effects: dict[str, dict[str, dict[str, object]]] = {}
    eligible: list[dict[str, object]] = []
    for feature in FEATURES:
        per_period = {
            period: feature_class_separation(frames[period], feature, winner_threshold=WINNER_THRESHOLD, loser_threshold=LOSER_THRESHOLD)
            for period in periods
        }
        effects[feature] = per_period
        rows = [per_period[period] for period in periods]
        if any(
            int(row["n_winners"]) < MIN_CLASS_COUNT
            or int(row["n_losers"]) < MIN_CLASS_COUNT
            or float(row["finite_feature_rate_among_resolved"] or 0.0) < MIN_FINITE_RATE
            for row in rows
        ):
            continue
        cliff_signs = [int(np.sign(float(row["cliffs_delta"] or 0.0))) for row in rows]
        median_signs = [int(np.sign(float(row["median_delta_winner_minus_loser"] or 0.0))) for row in rows]
        pooled_delta = per_period["discovery_pooled"]["cliffs_delta"]
        if not cliff_signs[0] or not median_signs[0] or len(set(cliff_signs)) != 1 or len(set(median_signs)) != 1:
            continue
        if pooled_delta is None or abs(float(pooled_delta)) < MIN_ABSOLUTE_POOLED_CLIFFS_DELTA:
            continue
        eligible.append({
            "feature": feature,
            "direction": "higher_for_winners" if cliff_signs[0] > 0 else "lower_for_winners",
            "pooled_cliffs_delta": float(pooled_delta),
            "pooled_median_delta": float(per_period["discovery_pooled"]["median_delta_winner_minus_loser"]),
        })
    eligible.sort(key=lambda row: (-abs(float(row["pooled_cliffs_delta"])), str(row["feature"])))
    return effects, eligible[:MAX_SELECTED_FEATURES]


def freeze_discovery_bands(discovery_candidates: pd.DataFrame, selected: list[dict[str, object]]) -> list[dict[str, object]]:
    frozen: list[dict[str, object]] = []
    for item in selected:
        feature = str(item["feature"])
        edges = discovery_tercile_edges(discovery_candidates[feature])
        frozen.append({**item, "tercile_edges": [float(edges[0]), float(edges[1])]})
    return frozen


def confirm_features(frame: pd.DataFrame, frozen: list[dict[str, object]]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for item in frozen:
        feature = str(item["feature"])
        direction = str(item["direction"])
        effect = feature_class_separation(frame, feature, winner_threshold=WINNER_THRESHOLD, loser_threshold=LOSER_THRESHOLD)
        bands = feature_band_metrics(frame, feature, edges=item["tercile_edges"], winner_threshold=WINNER_THRESHOLD, loser_threshold=LOSER_THRESHOLD)
        expected_sign = 1 if direction == "higher_for_winners" else -1
        cliff = int(np.sign(float(effect["cliffs_delta"] or 0.0)))
        median_delta = int(np.sign(float(effect["median_delta_winner_minus_loser"] or 0.0)))
        band_rows = bands["bands"]
        favorable_name, unfavorable_name = (("high", "low") if expected_sign > 0 else ("low", "high"))
        favorable = band_rows[favorable_name]
        unfavorable = band_rows[unfavorable_name]
        enough = all(
            int(band_rows[name][key]) >= MIN_CLASS_COUNT
            for name in (favorable_name, unfavorable_name)
            for key in ("winner_count", "loser_count")
        )
        favorable_share = favorable["extreme_winner_share"]
        unfavorable_share = unfavorable["extreme_winner_share"]
        band_matches = bool(
            enough and favorable_share is not None and unfavorable_share is not None
            and float(favorable_share) > float(unfavorable_share)
        )
        results.append({
            "feature": feature,
            "discovery_direction": direction,
            "effect": effect,
            "broad_bands": bands,
            "confirmation_checks": {
                "effect_direction_matches": cliff == expected_sign and median_delta == expected_sign,
                "broad_band_direction_matches": band_matches,
                "sufficient_winner_and_loser_counts_in_both_outer_bands": bool(enough),
                "confirmed": bool(cliff == expected_sign and median_delta == expected_sign and band_matches),
            },
        })
    return results
