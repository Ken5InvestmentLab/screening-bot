from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tvfree_screener.batch02.core_market_state_audit import (
    FEATURES,
    build_universe_pool,
    confirm_features,
    discover_features,
    period_frames,
)


def _joined(rows: int = 100) -> pd.DataFrame:
    half = rows // 2
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2022-07-04"] * rows),
        "symbol": pd.Series([f"{index:04d}" for index in range(rows)], dtype="string"),
        "gross_return": np.r_[np.full(half, 0.12), np.full(rows - half, -0.12)],
        "label_resolved": True,
    })
    for feature in FEATURES:
        frame[feature] = np.r_[np.ones(half), -np.ones(rows - half)]
    return frame


class MarketStateAuditTests(unittest.TestCase):
    def test_universe_pool_keeps_valid_bars_and_filters_period_and_bad_gap(self) -> None:
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2023-01-04", "2023-01-04", "2023-01-04", "2024-01-04", "2025-01-06"]),
            "symbol": pd.Series(["1111", "2222", "3333", "4444", "5555"], dtype="string"),
            "open": [100, 100, 100, 100, 100],
            "high": [102, 102, 102, 102, 102],
            "low": [99, 99, 99, 99, 99],
            "close": [101, 101, 101, 101, 101],
            "volume": [1000, 1000, 0, 1000, 1000],
            "gap": [0.0, 0.5, 0.0, 0.0, 0.0],
        })
        for feature in FEATURES:
            if feature != "gap":
                frame[feature] = 0.0

        pool, counts = build_universe_pool(frame, start="2023-01-01", end="2024-12-20")

        self.assertEqual(pool["symbol"].tolist(), ["1111", "4444"])
        self.assertEqual(counts["source_rows_in_period"], 4)
        self.assertEqual(counts["eligible_signal_rows"], 2)

    def test_discovery_requires_consistent_effect_direction_and_selects_at_most_two(self) -> None:
        first = _joined()
        second = _joined()
        pooled = pd.concat([first, second], ignore_index=True)
        effects, selected = discover_features({"2022H2": first, "2023": second, "discovery_pooled": pooled})

        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["feature"], "atr14p")
        self.assertEqual(selected[0]["direction"], "higher_for_winners")
        self.assertEqual(effects["ret1"]["2022H2"]["n_winners"], 50)

    def test_period_frames_keep_separately_purged_boundaries(self) -> None:
        frame = pd.DataFrame({"date": pd.to_datetime(["2022-12-23", "2022-12-26", "2023-12-22", "2023-12-25", "2024-12-20", "2024-12-23"])})

        periods = period_frames(frame)

        self.assertEqual(periods["2022H2"]["date"].dt.strftime("%Y-%m-%d").tolist(), ["2022-12-23"])
        self.assertEqual(periods["2023"]["date"].dt.strftime("%Y-%m-%d").tolist(), ["2023-12-22"])
        self.assertEqual(periods["2024_confirmation"]["date"].dt.strftime("%Y-%m-%d").tolist(), ["2024-12-20"])

    def test_2024_confirmation_requires_effect_and_frozen_outer_band_directions(self) -> None:
        frame = pd.DataFrame({
            "gross_return": np.r_[np.full(70, 0.12), np.full(50, -0.12), np.full(50, 0.12), np.full(70, -0.12)],
            "label_resolved": True,
            "ret1": np.r_[np.ones(120), -np.ones(120)],
        })
        frozen = [{"feature": "ret1", "direction": "higher_for_winners", "tercile_edges": [-0.3, 0.3]}]

        result = confirm_features(frame, frozen)

        self.assertTrue(result[0]["confirmation_checks"]["confirmed"])


if __name__ == "__main__":
    unittest.main()
