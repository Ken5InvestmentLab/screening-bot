from __future__ import annotations

import unittest

import pandas as pd

from .feature_separation import (
    directional_confirmation,
    feature_band_metrics,
    feature_class_separation,
    select_directionally_stable_features,
)


class FeatureSeparationTests(unittest.TestCase):
    def test_cliffs_delta_and_median_difference_point_to_winner_direction(self) -> None:
        frame = pd.DataFrame({
            "signal_state": [1.0, 2.0, 3.0, 5.0, 6.0, 7.0, float("nan")],
            "gross_return": [-0.12, -0.10, -0.20, 0.10, 0.15, 0.20, 0.01],
            "label_resolved": [True] * 7,
        })
        result = feature_class_separation(frame, "signal_state")
        self.assertEqual(result["cliffs_delta"], 1.0)
        self.assertGreater(result["median_delta_winner_minus_loser"], 0)
        self.assertEqual(result["n_winners"], 3)
        self.assertEqual(result["n_losers"], 3)
        self.assertEqual(result["missing_feature_candidate_count"], 1)
        self.assertAlmostEqual(result["finite_feature_rate"], 6 / 7)

    def test_feature_selection_requires_stable_direction_in_both_discovery_splits(self) -> None:
        stable = {
            "n_winners": 100,
            "n_losers": 100,
            "cliffs_delta": 0.20,
            "median_delta_winner_minus_loser": 0.10,
        }
        opposite = {**stable, "cliffs_delta": -0.05, "median_delta_winner_minus_loser": -0.01}
        effects = {
            "stable": {"2022H2": stable, "2023": stable, "discovery_pooled": stable},
            "unstable": {"2022H2": stable, "2023": opposite, "discovery_pooled": stable},
        }
        chosen = select_directionally_stable_features(effects)
        self.assertEqual([row["feature"] for row in chosen], ["stable"])

    def test_frozen_outer_tercile_direction_confirms_only_with_class_effect(self) -> None:
        lows = pd.DataFrame({
            "state": [1.0] * 200,
            "gross_return": [-0.12] * 140 + [0.12] * 60,
            "label_resolved": True,
        })
        highs = pd.DataFrame({
            "state": [5.0] * 200,
            "gross_return": [-0.12] * 60 + [0.12] * 140,
            "label_resolved": True,
        })
        frame = pd.concat([lows, pd.DataFrame({
            "state": [3.0] * 20,
            "gross_return": [0.0] * 20,
            "label_resolved": True,
        }), highs], ignore_index=True)
        effect = feature_class_separation(frame, "state")
        bands = feature_band_metrics(frame, "state", edges=[2.0, 4.0])
        confirmation = directional_confirmation(effect, bands, direction="higher_for_winners")
        self.assertTrue(confirmation["confirmed"])
        self.assertGreater(
            bands["bands"]["high"]["extreme_winner_share"],
            bands["bands"]["low"]["extreme_winner_share"],
        )


if __name__ == "__main__":
    unittest.main()
