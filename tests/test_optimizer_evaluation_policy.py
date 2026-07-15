import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import generate_mega_validation_report as report
import optimize_screener as opt


def stats_frame(perfs, date="2026-07-15"):
    values = np.asarray(perfs, dtype=float)
    return pd.DataFrame(
        {
            "date": [date] * len(values),
            "perf_5bd": values,
            "win_5bd": values > 0,
            "win10": values >= opt.WIN_THRESHOLD,
            "lose10": values <= opt.LOSE_THRESHOLD,
        }
    )


def session(date_key, hour, close):
    return {
        "timestamp": pd.Timestamp(f"{date_key} {hour:02d}:00:00"),
        "date": date_key,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 10,
    }


class OptimizerEvaluationPolicyTest(unittest.TestCase):
    def test_recent_frame_includes_365th_day_and_excludes_366th(self):
        frame = pd.DataFrame(
            {
                "date": ["2025-07-15", "2025-07-16", "2026-07-15"],
                "value": ["old", "boundary", "today"],
            }
        )

        actual = opt.recent_calendar_day_df(frame, 365, today="2026-07-15")

        self.assertEqual(actual["value"].tolist(), ["boundary", "today"])

    def test_signal_received_cutoff_ignores_later_same_day_bar(self):
        alert = pd.Series(
            {
                "date": "2026/07/15",
                "_received_at_dt": pd.Timestamp("2026-07-15 10:00:00"),
            }
        )
        rows = [
            session("2026-07-14", 9, 90),
            session("2026-07-14", 13, 95),
            session("2026-07-15", 9, 102),
            session("2026-07-15", 13, 140),
        ]

        bars = opt.daily_bars_for_signal_features(rows, alert)

        self.assertEqual(bars[-1]["date"], "2026-07-15")
        self.assertEqual(bars[-1]["close"], 102)

    def test_first_final_snapshot_features_and_membership_win(self):
        header = [
            "alert_id",
            "status",
            "stable_score",
            "sniper_score",
            "modes_json",
            "features_json",
        ]
        rows = [
            header,
            ["A1", "FINAL", "5", "6", '["sniper"]', '{"ema25": true}'],
            ["A1", "FINAL", "6", "0", "[]", '{"ema25": false}'],
        ]
        snapshots = opt.load_final_signal_snapshot_map(rows)
        raw = pd.DataFrame(
            [{"alert_id": "A1", "date": "2026-07-15", "ema25": False}]
        )

        actual = opt.optimizer_evaluation_frame(
            raw,
            snapshots,
            today="2026-07-15",
        )

        self.assertTrue(bool(actual.iloc[0]["ema25"]))
        self.assertEqual(actual.iloc[0]["_snapshot_stable_score"], 5)
        self.assertTrue(
            bool(opt.published_mode_mask(actual, "sniper", [False]).iloc[0])
        )
        self.assertEqual(
            int(opt.published_stable_score(actual, [0]).iloc[0]),
            5,
        )

    def test_snapshot_only_record_is_kept_and_overlaid(self):
        snapshots = {
            "A1": {
                "status": "FINAL",
                "stable_score": 6,
                "sniper_score": 6,
                "modes": ["sniper"],
                "features": {"ema25": True, "vol20": False},
            }
        }
        alert = pd.Series({"alert_id": "A1", "date": "2026-07-15"})

        record = opt.optimizer_feature_record(alert, None, snapshots)
        actual = opt.optimizer_evaluation_frame(
            pd.DataFrame([record]),
            snapshots,
            today="2026-07-15",
        )

        self.assertIsNotNone(record)
        self.assertTrue(bool(actual.iloc[0]["ema25"]))
        self.assertFalse(bool(actual.iloc[0]["vol20"]))

    def test_published_selection_overrides_only_rows_with_final_snapshot(self):
        frame = pd.DataFrame(
            {
                "_snapshot_final": [True, False],
                "_snapshot_modes": [("sniper",), tuple()],
                "_snapshot_stable_score": [6, np.nan],
            }
        )

        modes = opt.published_mode_mask(frame, "sniper", [False, True])
        scores = opt.published_stable_score(frame, [1, 4])

        self.assertEqual(modes.tolist(), [True, True])
        self.assertEqual(scores.tolist(), [6, 4])

    def test_received_at_lookup_matches_report_first_row_wins(self):
        header = ["alert_id", "received_at"]
        raw = [[], [], [], header, ["A1", "2026-07-15 10:00:00"]]
        archive = [[], [], [], header, ["A1", "2026-07-15 15:00:00"]]

        actual = opt.alert_received_at_lookup(raw, archive)

        self.assertEqual(actual["A1"], "2026-07-15 10:00:00")

    def test_zero_percent_draws_are_excluded_in_all_stats_paths(self):
        perfs = [0.01] * 17 + [0.0] * 2 + [-0.01] * 5
        frame = stats_frame(perfs)
        expected_wr = 17 / 22

        regular = opt.calc_stats(frame)
        arrays = opt._prepare_stats_arrays(frame)
        vectorized = opt._calc_stats_mask(np.ones(len(frame), dtype=bool), arrays)
        mega = opt._mega_base_stats(frame, "perf_5bd", 0.0)
        mega_vectorized = opt._mega_stats_from_mask(
            np.ones(len(frame), dtype=bool),
            frame["perf_5bd"].to_numpy(dtype=float),
            0.0,
        )

        for stats in (regular, vectorized, mega, mega_vectorized):
            self.assertEqual(stats["n"], 24)
            self.assertEqual(stats["decisive_n"], 22)
            self.assertAlmostEqual(stats["wr_raw"], expected_wr)
        self.assertEqual(mega["target_hits"], 19)
        self.assertEqual(mega_vectorized["target_hits"], 19)

    def test_sniper_candidate_below_html_baseline_is_rejected_even_in_rescue(self):
        baseline_wr = 17 / 22
        candidate = {"n": 13, "wr_raw": 10 / 13, "avg_raw": 0.00954}

        reason = opt.sniper_baseline_gate_reject_reason(
            candidate,
            baseline_wr,
            baseline_avg=0.04604,
        )

        self.assertIsNotNone(reason)
        self.assertIn("勝率が現行以下", reason)

    def test_all_active_optimizer_paths_use_shared_evaluation_frame(self):
        for source in (
            inspect.getsource(opt.build_sniper_feature_frame),
            inspect.getsource(opt.build_mega_report_feature_frames),
            inspect.getsource(opt.main),
        ):
            self.assertIn("optimizer_evaluation_frame", source)
            self.assertIn("optimizer_feature_record", source)

    def test_report_and_optimizer_share_the_same_365_day_policy(self):
        self.assertEqual(opt.EVALUATION_BACKTEST_DAYS, 365)
        self.assertEqual(report.REPORT_BACKTEST_DAYS, opt.EVALUATION_BACKTEST_DAYS)
        policy = opt.evaluation_policy_payload()
        self.assertEqual(policy["calendar_days"], 365)
        self.assertEqual(policy["win_rate"], "exclude_zero_percent_draws")

    def test_stale_pending_policy_is_rejected_and_deleted(self):
        current = {"evaluation_policy": opt.evaluation_policy_payload()}
        self.assertTrue(opt.pending_evaluation_policy_is_current(current))
        self.assertFalse(opt.pending_evaluation_policy_is_current({}))

        with tempfile.TemporaryDirectory() as temp_dir:
            pending_path = os.path.join(temp_dir, "pending.json")
            Path(pending_path).write_text("{}", encoding="utf-8")
            discarded = opt.discard_stale_pending_payload(
                {},
                pending_path,
                "test pending",
            )
            self.assertTrue(discarded)
            self.assertFalse(os.path.exists(pending_path))

    def test_apply_path_guards_all_pending_types(self):
        source = inspect.getsource(opt.main)
        self.assertGreaterEqual(source.count("discard_stale_pending_payload("), 3)
        for label in ("Stable pending", "Sniper pending", "Mega pending"):
            self.assertIn(label, source)

    def test_rescue_state_is_versioned_by_evaluation_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "rescue_state.json")
            with mock.patch.object(opt, "RESCUE_STATE_PATH", state_path):
                opt.save_rescue_state({"status": "healthy"})
                loaded = opt.load_rescue_state()
                self.assertEqual(
                    loaded["evaluation_policy"],
                    opt.evaluation_policy_payload(),
                )
                opt.save_rescue_state({"sniper": {"streak": 2}})
                opt.save_rescue_state({"status": "healthy"})
                self.assertEqual(opt.load_rescue_state()["sniper"]["streak"], 2)
                Path(state_path).write_text(
                    json.dumps({"status": "healthy"}),
                    encoding="utf-8",
                )
                self.assertEqual(opt.load_rescue_state(), {})

    def test_workflow_stages_pending_deletions(self):
        workflow = Path(".github/workflows/optimize.yml").read_text(encoding="utf-8")
        self.assertIn('git add -A -- "$path"', workflow)
        self.assertIn('git ls-files --error-unmatch "$path"', workflow)


if __name__ == "__main__":
    unittest.main()
