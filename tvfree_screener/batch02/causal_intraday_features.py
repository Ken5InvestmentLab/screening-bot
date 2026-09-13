"""Scale-invariant causal features derived from raw intraday clock bins."""
from __future__ import annotations

from collections import defaultdict, deque
from math import isfinite
from statistics import median
from typing import Iterable


def _bar_shape(bar: object) -> dict[str, float]:
    op = float(bar.open)
    high = float(bar.high)
    low = float(bar.low)
    close = float(bar.close)
    if not all(isfinite(value) for value in (op, high, low, close)) or op <= 0:
        raise ValueError("invalid clock-bin OHLC")
    bar_range = high - low
    return {
        "body_pct": close / op - 1.0,
        "range_pct": bar_range / op,
        "body_to_range": (close - op) / bar_range if bar_range > 0 else 0.0,
        "upper_wick_pct": (high - max(op, close)) / op,
        "lower_wick_pct": (min(op, close) - low) / op,
        "close_location": (close - low) / bar_range if bar_range > 0 else 0.5,
    }


def extract_causal_features(bars: Iterable[object]) -> list[dict[str, object]]:
    """Build only cutoff-safe, mostly scale-invariant features.

    Rolling baselines use only already-completed bars. Volume-relative features
    remain explicitly experimental because raw-source volume semantics are not
    yet fully reconciled.
    """
    ordered = sorted(
        bars,
        key=lambda bar: (bar.symbol, bar.feature_cutoff_jst, bar.bin_name),
    )
    history_shape = defaultdict(lambda: deque(maxlen=20))
    history_same_range = defaultdict(lambda: deque(maxlen=20))
    history_same_volume = defaultdict(lambda: deque(maxlen=20))
    output: list[dict[str, object]] = []

    for bar in ordered:
        shape = _bar_shape(bar)
        same_bin_key = (bar.symbol, bar.bin_name)
        prior_shapes = history_shape[bar.symbol]
        prior_ranges = history_same_range[same_bin_key]
        prior_volumes = history_same_volume[same_bin_key]

        row: dict[str, object] = {
            "session_date": bar.session_date.isoformat(),
            "symbol": bar.symbol,
            "bin_name": bar.bin_name,
            "feature_cutoff_jst": bar.feature_cutoff_jst.isoformat(),
            "source_tag": bar.source_tag,
            **shape,
            # PM close-location was materially less stable under the
            # post-close reconstruction comparison, so keep it out of model
            # eligibility until the source audit improves.
            "close_location_model_eligible": bar.bin_name == "AM_09_13",
            "volume_rel20_status": "EXPERIMENTAL_SOURCE_INTERNAL",
            "prior_shape_count": len(prior_shapes),
            "prior_same_bin_count": len(prior_ranges),
        }

        if len(prior_shapes) >= 4:
            last4 = list(prior_shapes)[-4:]
            row["prev4_body_mean"] = sum(item["body_pct"] for item in last4) / 4.0
            row["prev4_abs_body_mean"] = sum(abs(item["body_pct"]) for item in last4) / 4.0
            row["prev4_range_mean"] = sum(item["range_pct"] for item in last4) / 4.0
        else:
            row["prev4_body_mean"] = None
            row["prev4_abs_body_mean"] = None
            row["prev4_range_mean"] = None

        if len(prior_ranges) == 20:
            range_median = median(prior_ranges)
            row["prior20_same_bin_range_median"] = range_median
            row["range_vs_prior20"] = (
                shape["range_pct"] / range_median if range_median > 0 else None
            )
        else:
            row["prior20_same_bin_range_median"] = None
            row["range_vs_prior20"] = None

        if len(prior_volumes) == 20:
            volume_median = median(prior_volumes)
            row["prior20_same_bin_volume_median"] = volume_median
            row["volume_rel20"] = (
                float(bar.volume) / volume_median if volume_median > 0 else None
            )
        else:
            row["prior20_same_bin_volume_median"] = None
            row["volume_rel20"] = None

        output.append(row)

        history_shape[bar.symbol].append(shape)
        history_same_range[same_bin_key].append(shape["range_pct"])
        history_same_volume[same_bin_key].append(float(bar.volume))

    return output
