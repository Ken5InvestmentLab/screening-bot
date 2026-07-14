import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import generate_mega_validation_report as report


class ReportSignalSnapshotTest(unittest.TestCase):
    def test_snapshot_sheet_read_failure_falls_back_to_empty_map(self):
        module = SimpleNamespace(load_snapshot_map=lambda rows: {"unexpected": {}})
        with patch.object(report, "signal_score_snapshots", module), patch.object(
            report.opt,
            "fetch",
            side_effect=RuntimeError("missing sheet"),
        ):
            self.assertEqual(report.load_final_signal_snapshots(object()), {})

    def test_snapshot_sheet_rows_are_parsed_by_shared_module(self):
        rows = [["alert_id"], ["a1"]]
        expected = {"a1": {"status": "FINAL"}}
        module = SimpleNamespace(load_snapshot_map=lambda loaded: expected if loaded is rows else {})
        with patch.object(report, "signal_score_snapshots", module), patch.object(
            report.opt,
            "fetch",
            return_value=rows,
        ) as fetch:
            self.assertEqual(report.load_final_signal_snapshots("service"), expected)
        fetch.assert_called_once_with("service", "signal_feature_snapshots")

    def test_final_snapshot_overlays_only_signal_feature_keys(self):
        live_features = {"ema25": False, "_atr": 4.0}
        snapshot = {
            "status": "FINAL",
            "stable_score": 5,
            "modes": ["sniper"],
            "features": {
                "ema25": True,
                "_atr": 2.5,
                "latest_close": 999999,
                "cur_perf": 9.99,
            },
        }

        features, metadata = report.apply_final_signal_snapshot(live_features, snapshot)

        self.assertEqual(features, {"ema25": True, "_atr": 2.5})
        self.assertEqual(metadata["_snapshot_stable_score"], 5)
        self.assertEqual(metadata["_snapshot_modes"], ("sniper",))
        self.assertNotIn("latest_close", features)
        self.assertNotIn("cur_perf", features)

    def test_final_snapshot_features_survive_missing_live_feature_recalculation(self):
        features, metadata = report.apply_final_signal_snapshot(
            {},
            {
                "status": "FINAL",
                "stable_score": 1,
                "modes": [],
                "features": {"ema25": True, "_atr": 3.5},
            },
        )

        self.assertEqual(features, {"ema25": True, "_atr": 3.5})
        self.assertTrue(metadata["_snapshot_final"])

    def test_final_score_and_modes_do_not_require_features_json(self):
        features, metadata = report.apply_final_signal_snapshot(
            {"ema25": False},
            {
                "status": "FINAL",
                "stable_score": 5,
                "modes": ["sniper"],
            },
        )

        self.assertEqual(features, {"ema25": False})
        self.assertEqual(metadata["_snapshot_stable_score"], 5)
        self.assertEqual(metadata["_snapshot_modes"], ("sniper",))

    def test_final_snapshot_modes_override_recomputed_conditions(self):
        sniper = next(candidate for candidate in report.CANDIDATES if candidate["id"] == "sniper")
        row = {condition: True for condition in sniper["conditions"]}
        row.update(
            {
                "_snapshot_final": True,
                "_snapshot_modes": [],
            }
        )
        frame = pd.DataFrame([row])

        self.assertFalse(bool(report.candidate_mask(frame, sniper).iloc[0]))
        self.assertFalse(report.row_matches_candidate(frame.iloc[0], sniper))

    def test_final_snapshot_can_select_mode_when_live_conditions_are_false(self):
        sniper = next(candidate for candidate in report.CANDIDATES if candidate["id"] == "sniper")
        row = {condition: False for condition in sniper["conditions"]}
        row.update(
            {
                "_snapshot_final": "FINAL",
                "_snapshot_modes": '["sniper"]',
            }
        )
        frame = pd.DataFrame([row])

        self.assertTrue(bool(report.candidate_mask(frame, sniper).iloc[0]))
        self.assertTrue(report.row_matches_candidate(frame.iloc[0], sniper))

    def test_final_snapshot_star_score_overrides_condition_count(self):
        row = {condition: False for condition in report.STABLE_CONDITIONS}
        row.update(
            {
                "_snapshot_final": True,
                "_snapshot_stable_score": 5,
                "_snapshot_modes": ["sniper"],
            }
        )

        self.assertEqual(report.stable_star_score(pd.Series(row)), 5)
        self.assertEqual(
            [candidate["id"] for candidate in report.row_mode_matches(pd.Series(row))],
            ["sniper"],
        )

    def test_rows_without_snapshot_keep_existing_calculation(self):
        stable = next(candidate for candidate in report.CANDIDATES if candidate["id"] == "stable_s6")
        row = {condition: True for condition in stable["conditions"]}
        frame = pd.DataFrame([row])

        self.assertTrue(bool(report.candidate_mask(frame, stable).iloc[0]))
        self.assertEqual(report.stable_star_score(frame.iloc[0]), len(report.STABLE_CONDITIONS))


if __name__ == "__main__":
    unittest.main()
