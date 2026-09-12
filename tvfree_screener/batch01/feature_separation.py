"""Causal winner-versus-loser feature separation for registered signal pools."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


EXPLORATORY_FEATURES = (
    "ret1", "ret3", "ret5", "ret10", "ret20", "ret40",
    "volr20_prevavg", "volume_trend5_20", "log_dollar_volume", "dollar_volume_median20",
    "atr14p", "pos20", "pos40", "pos60", "dd20", "dd40", "dd60",
    "gap", "range_pct", "body_pct", "close_location", "red_count5", "down3", "down5",
    "consecutive_down", "days_since_drop5", "ret1_minus_ret5_per5", "dispersion20",
    "market_median_ret1", "market_median_ret5", "market_median_ret1_lag1",
    "market_median_ret5_lag1", "rel_ret5_lag1",
)


def _sign(value: object) -> int:
    if value is None or not np.isfinite(float(value)):
        return 0
    return int(np.sign(float(value)))


def feature_class_separation(
    frame: pd.DataFrame,
    feature: str,
    *,
    winner_threshold: float = 0.10,
    loser_threshold: float = -0.10,
) -> dict[str, object]:
    """Describe feature ordering between resolved large winners and losers.

    Cliff's delta is computed from average ranks and lies in [-1, 1]. Positive
    means larger feature values are more common among winners. This is a
    descriptive effect size, not an independent-sample significance test.
    """
    if feature not in frame or not {"gross_return", "label_resolved"}.issubset(frame.columns):
        raise ValueError("feature frame lacks the requested feature or resolved labels")
    values = pd.to_numeric(frame[feature], errors="coerce").to_numpy(dtype="float64")
    returns = pd.to_numeric(frame["gross_return"], errors="coerce").to_numpy(dtype="float64")
    resolved = frame["label_resolved"].fillna(False).to_numpy(dtype=bool)
    finite = np.isfinite(values) & np.isfinite(returns) & resolved
    winner = values[finite & (returns >= winner_threshold)]
    loser = values[finite & (returns <= loser_threshold)]
    finite_feature = np.isfinite(values)
    resolved_count = int(resolved.sum())
    result: dict[str, object] = {
        "feature": feature,
        "candidate_count": int(len(frame)),
        "resolved_count": resolved_count,
        "finite_feature_candidate_count": int(finite_feature.sum()),
        "missing_feature_candidate_count": int((~finite_feature).sum()),
        "finite_feature_rate": float(finite_feature.mean()) if len(frame) else None,
        "finite_feature_rate_among_resolved": (
            float((finite_feature & resolved).sum() / resolved_count) if resolved_count else None
        ),
        "n_winners": int(len(winner)),
        "n_losers": int(len(loser)),
        "winner_median": float(np.median(winner)) if len(winner) else None,
        "loser_median": float(np.median(loser)) if len(loser) else None,
        "median_delta_winner_minus_loser": None,
        "cliffs_delta": None,
        "auc_winner_higher": None,
        "winner_class_share": (
            float(len(winner) / (len(winner) + len(loser))) if len(winner) + len(loser) else None
        ),
    }
    if not len(winner) or not len(loser):
        return result
    result["median_delta_winner_minus_loser"] = float(np.median(winner) - np.median(loser))
    joined = np.concatenate([winner, loser])
    ranks = pd.Series(joined).rank(method="average").to_numpy(dtype="float64")
    n_winner, n_loser = len(winner), len(loser)
    auc = (float(ranks[:n_winner].sum()) - n_winner * (n_winner + 1) / 2.0) / (n_winner * n_loser)
    result["auc_winner_higher"] = float(auc)
    result["cliffs_delta"] = float(2.0 * auc - 1.0)
    return result


def select_directionally_stable_features(
    effects: Mapping[str, Mapping[str, Mapping[str, object]]],
    *,
    discovery_periods: Sequence[str] = ("2022H2", "2023", "discovery_pooled"),
    max_features: int = 2,
    minimum_class_count: int = 50,
) -> list[dict[str, object]]:
    """Select at most two prelisted features using discovery data only.

    A feature must have enough winners and losers in each discovery split and
    the same nonzero direction for both Cliff's delta and median difference in
    every split. Candidates are ordered by pooled absolute Cliff's delta;
    ties are resolved by feature name. There is no threshold sweep or 2024/2025
    feedback in this rule.
    """
    eligible: list[dict[str, object]] = []
    for feature, per_period in effects.items():
        rows = [per_period.get(period, {}) for period in discovery_periods]
        if any(
            int(row.get("n_winners") or 0) < minimum_class_count
            or int(row.get("n_losers") or 0) < minimum_class_count
            for row in rows
        ):
            continue
        cliff_signs = [_sign(row.get("cliffs_delta")) for row in rows]
        median_signs = [_sign(row.get("median_delta_winner_minus_loser")) for row in rows]
        if not cliff_signs[0] or len(set(cliff_signs)) != 1 or len(set(median_signs)) != 1:
            continue
        if cliff_signs[0] != median_signs[0]:
            continue
        pooled = per_period.get("discovery_pooled", {})
        delta = pooled.get("cliffs_delta")
        if delta is None or not np.isfinite(float(delta)):
            continue
        eligible.append({
            "feature": feature,
            "direction": "higher_for_winners" if cliff_signs[0] > 0 else "lower_for_winners",
            "discovery_cliffs_delta": float(delta),
            "discovery_median_delta": pooled.get("median_delta_winner_minus_loser"),
        })
    eligible.sort(key=lambda row: (-abs(float(row["discovery_cliffs_delta"])), str(row["feature"])))
    return eligible[:max_features]


def discovery_tercile_edges(values: pd.Series) -> tuple[float, float]:
    """Fit broad feature bands to all discovery candidate rows, without labels."""
    numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype="float64")
    finite = numeric[np.isfinite(numeric)]
    if not len(finite):
        raise ValueError("cannot fit discovery bands without finite decision-time feature values")
    lower, upper = np.quantile(finite, [1.0 / 3.0, 2.0 / 3.0])
    return float(lower), float(upper)


def feature_band_metrics(
    frame: pd.DataFrame,
    feature: str,
    *,
    edges: Sequence[float],
    winner_threshold: float = 0.10,
    loser_threshold: float = -0.10,
) -> dict[str, object]:
    """Report fixed discovery-tercile outcome bands in a later period."""
    if len(edges) != 2 or float(edges[0]) > float(edges[1]):
        raise ValueError("feature band edges must be two ascending discovery cutpoints")
    values = pd.to_numeric(frame[feature], errors="coerce")
    bands = pd.Series(pd.NA, index=frame.index, dtype="string")
    finite = np.isfinite(values.to_numpy(dtype="float64"))
    bands.loc[finite & values.le(float(edges[0]))] = "low"
    bands.loc[finite & values.gt(float(edges[0])) & values.le(float(edges[1]))] = "middle"
    bands.loc[finite & values.gt(float(edges[1]))] = "high"
    returns = pd.to_numeric(frame["gross_return"], errors="coerce")
    resolved = frame["label_resolved"].fillna(False).astype(bool)
    result: dict[str, object] = {
        "feature": feature,
        "edges": [float(edges[0]), float(edges[1])],
        "candidate_count": int(len(frame)),
        "finite_feature_candidate_count": int(finite.sum()),
        "missing_feature_candidate_count": int((~finite).sum()),
        "finite_feature_rate": float(finite.mean()) if len(frame) else None,
        "bands": {},
    }
    for band in ("low", "middle", "high"):
        mask = bands.eq(band)
        valid = mask & resolved & returns.notna()
        band_returns = returns.loc[valid]
        n_winners = int((band_returns >= winner_threshold).sum())
        n_losers = int((band_returns <= loser_threshold).sum())
        result["bands"][band] = {
            "candidate_count": int(mask.sum()),
            "resolved_count": int(valid.sum()),
            "unresolved_count": int((mask & ~resolved).sum()),
            "winner_count": n_winners,
            "loser_count": n_losers,
            "extreme_winner_share": (
                float(n_winners / (n_winners + n_losers)) if n_winners + n_losers else None
            ),
            "mean_return": float(band_returns.mean()) if len(band_returns) else None,
            "median_return": float(band_returns.median()) if len(band_returns) else None,
            "plus10_rate": float((band_returns >= winner_threshold).mean()) if len(band_returns) else None,
            "minus10_rate": float((band_returns <= loser_threshold).mean()) if len(band_returns) else None,
        }
    return result


def directional_confirmation(
    effect: Mapping[str, object],
    bands: Mapping[str, object],
    *,
    direction: str,
    minimum_class_count: int = 50,
) -> dict[str, object]:
    """Require effect direction and the predeclared broad-band comparison."""
    expected_sign = 1 if direction == "higher_for_winners" else -1
    cliff = _sign(effect.get("cliffs_delta"))
    median_delta = _sign(effect.get("median_delta_winner_minus_loser"))
    expected_high, expected_low = (
        ("high", "low") if expected_sign > 0 else ("low", "high")
    )
    band_rows = bands.get("bands", {})
    favorable = band_rows.get(expected_high, {})
    unfavorable = band_rows.get(expected_low, {})
    sufficient_extremes = (
        int(favorable.get("winner_count") or 0) >= minimum_class_count
        and int(favorable.get("loser_count") or 0) >= minimum_class_count
        and int(unfavorable.get("winner_count") or 0) >= minimum_class_count
        and int(unfavorable.get("loser_count") or 0) >= minimum_class_count
    )
    favorable_share = favorable.get("extreme_winner_share")
    unfavorable_share = unfavorable.get("extreme_winner_share")
    band_direction = (
        sufficient_extremes
        and favorable_share is not None
        and unfavorable_share is not None
        and float(favorable_share) > float(unfavorable_share)
    )
    return {
        "effect_direction_matches": cliff == expected_sign and median_delta == expected_sign,
        "broad_band_direction_matches": bool(band_direction),
        "sufficient_extreme_class_counts_in_both_outer_bands": bool(sufficient_extremes),
        "confirmed": bool(cliff == expected_sign and median_delta == expected_sign and band_direction),
    }
