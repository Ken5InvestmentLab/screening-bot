import copy
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

    def test_mega_rejects_win_rate_drop_hidden_by_one_extreme_winner(self):
        current_values = [0.634, 0.527, 0.130, 0.076, 0.035, -0.032, -0.192, -0.325]
        candidate_values = [
            4.654, 0.618, 0.617, 0.249, 0.130, 0.099,
            -0.011, -0.019, -0.037, -0.075, -0.087, -0.154,
        ]
        current_rows = pd.DataFrame({"perf_40bd": current_values})
        candidate_rows = pd.DataFrame({"perf_40bd": candidate_values})
        current_stats = opt._mega_base_stats(current_rows, "perf_40bd", 0.50)
        candidate_stats = opt._mega_base_stats(candidate_rows, "perf_40bd", 0.50)

        reason = opt.mega_outlier_dependency_reject_reason(
            "Mega40 下ヒゲ回復",
            current_stats,
            candidate_stats,
            candidate_rows,
            "perf_40bd",
            0.50,
        )

        self.assertIsNotNone(reason)
        self.assertIn("最大1銘柄に依存", reason)
        self.assertIn("勝率が現行比12.5pt悪化", reason)

    def test_mega_keeps_broad_based_candidate_despite_lower_win_rate(self):
        current_values = [0.634, 0.527, 0.130, 0.076, 0.035, -0.032, -0.192, -0.325]
        candidate_values = [
            0.700, 0.650, 0.600, 0.550, 0.200, 0.150,
            -0.010, -0.020, -0.030, -0.040, -0.050, -0.060,
        ]
        current_rows = pd.DataFrame({"perf_40bd": current_values})
        candidate_rows = pd.DataFrame({"perf_40bd": candidate_values})
        current_stats = opt._mega_base_stats(current_rows, "perf_40bd", 0.50)
        candidate_stats = opt._mega_base_stats(candidate_rows, "perf_40bd", 0.50)

        reason = opt.mega_outlier_dependency_reject_reason(
            "Mega40 下ヒゲ回復",
            current_stats,
            candidate_stats,
            candidate_rows,
            "perf_40bd",
            0.50,
        )

        self.assertIsNone(reason)

    def test_mega_proposal_checks_outlier_dependency_before_notification(self):
        source = inspect.getsource(opt._run_mega_report_logic_proposal)

        self.assertIn("mega_outlier_dependency_reject_reason(", source)
        self.assertLess(
            source.index("mega_outlier_dependency_reject_reason("),
            source.index("notify_discord_mega_approval("),
        )

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

    def test_august_3_stable_proposal_fails_dramatic_improvement_gate(self):
        rejects = opt.stable_replacement_gate_rejects(
            {"n": 47, "wr_raw": 0.5531914894, "avg_raw": 0.0746595745},
            {"n": 26, "wr_raw": 0.60, "avg_raw": 0.0528846154},
            {"n": 7, "wr_raw": 0.2857142857, "avg_raw": 0.04},
            {"n": 7, "wr_raw": 0.6666666667, "avg_raw": 0.0204285714},
            {"n": 16, "wr_raw": 0.5625, "avg_raw": 0.002},
            {"n": 9, "wr_raw": 0.4444444444, "avg_raw": 0.0257777778},
            bootstrap_ci_low=0.40,
            kfold_wins=1,
            permutation_pvalue=0.0,
            mode="normal",
            data_mode="strict",
        )

        self.assertTrue(any("+8.0pt" in reason for reason in rejects))
        self.assertTrue(any("公開365日平均" in reason for reason in rejects))
        self.assertTrue(any("公開365日件数" in reason for reason in rejects))
        self.assertTrue(any("検証平均" in reason for reason in rejects))
        self.assertTrue(any("Lockbox勝率" in reason for reason in rejects))
        self.assertTrue(any("Bootstrap" in reason for reason in rejects))
        self.assertTrue(any("K-Fold" in reason for reason in rejects))

    def test_august_4_rescue_proposal_fails_same_dramatic_improvement_gate(self):
        rejects = opt.stable_replacement_gate_rejects(
            {"n": 47, "wr_raw": 0.5531914894, "avg_raw": 0.0746595745},
            {"n": 24, "wr_raw": 0.6086956522, "avg_raw": 0.0577916667},
            {"n": 7, "wr_raw": 0.2857142857, "avg_raw": 0.04},
            {"n": 8, "wr_raw": 0.5714285714, "avg_raw": 0.015},
            {"n": 16, "wr_raw": 0.5625, "avg_raw": 0.002},
            {"n": 5, "wr_raw": 0.40, "avg_raw": 0.0004},
            bootstrap_ci_low=0.4347826087,
            kfold_wins=1,
            permutation_pvalue=0.0,
            mode="rescue",
            data_mode="strict",
        )

        self.assertTrue(any("+8.0pt" in reason for reason in rejects))
        self.assertTrue(any("公開365日平均" in reason for reason in rejects))
        self.assertTrue(any("公開365日件数" in reason for reason in rejects))
        self.assertTrue(any("検証平均" in reason for reason in rejects))
        self.assertTrue(any("Lockbox件数" in reason for reason in rejects))
        self.assertTrue(any("Lockbox勝率" in reason for reason in rejects))
        self.assertTrue(any("Bootstrap" in reason for reason in rejects))
        self.assertTrue(any("K-Fold" in reason for reason in rejects))

    def test_stable_dramatic_improvement_gate_accepts_exact_policy_boundaries(self):
        rejects = opt.stable_replacement_gate_rejects(
            {"n": 20, "wr_raw": 0.55, "avg_raw": 0.06},
            {"n": 18, "wr_raw": 0.63, "avg_raw": 0.06},
            {"n": 10, "wr_raw": 0.60, "avg_raw": 0.02},
            {"n": 8, "wr_raw": 0.60, "avg_raw": 0.02},
            {"n": 10, "wr_raw": 0.60, "avg_raw": 0.01},
            {"n": 8, "wr_raw": 0.60, "avg_raw": 0.01},
            bootstrap_ci_low=0.550001,
            kfold_wins=2,
            permutation_pvalue=0.049,
            mode="normal",
            data_mode="strict",
        )

        self.assertEqual(rejects, [])

    def test_each_stable_dramatic_improvement_requirement_is_mandatory(self):
        base = {
            "current": {"n": 20, "wr_raw": 0.55, "avg_raw": 0.06},
            "candidate": {"n": 18, "wr_raw": 0.63, "avg_raw": 0.06},
            "current_valid": {"n": 10, "wr_raw": 0.60, "avg_raw": 0.02},
            "candidate_valid": {"n": 8, "wr_raw": 0.60, "avg_raw": 0.02},
            "current_lockbox": {"n": 10, "wr_raw": 0.60, "avg_raw": 0.01},
            "candidate_lockbox": {"n": 8, "wr_raw": 0.60, "avg_raw": 0.01},
            "bootstrap_ci_low": 0.550001,
            "kfold_wins": 2,
            "permutation_pvalue": 0.049,
        }
        cases = {
            "win_rate": ("candidate", "wr_raw", 0.629),
            "average": ("candidate", "avg_raw", 0.059),
            "full_count": ("candidate", "n", 17),
            "validation_count": ("candidate_valid", "n", 7),
            "validation_win_rate": ("candidate_valid", "wr_raw", 0.59),
            "validation_average": ("candidate_valid", "avg_raw", 0.019),
            "lockbox_count": ("candidate_lockbox", "n", 7),
            "lockbox_win_rate": ("candidate_lockbox", "wr_raw", 0.59),
            "lockbox_average": ("candidate_lockbox", "avg_raw", 0.009),
            "bootstrap": (None, "bootstrap_ci_low", 0.55),
            "kfold": (None, "kfold_wins", 1),
            "permutation": (None, "permutation_pvalue", 0.05),
        }

        for label, (section, key, value) in cases.items():
            with self.subTest(label=label):
                case = copy.deepcopy(base)
                if section is None:
                    case[key] = value
                else:
                    case[section][key] = value
                rejects = opt.stable_replacement_gate_rejects(
                    case["current"],
                    case["candidate"],
                    case["current_valid"],
                    case["candidate_valid"],
                    case["current_lockbox"],
                    case["candidate_lockbox"],
                    case["bootstrap_ci_low"],
                    case["kfold_wins"],
                    case["permutation_pvalue"],
                    mode="normal",
                    data_mode="strict",
                )
                self.assertNotEqual(rejects, [])

    def test_rescue_final_criteria_do_not_bypass_existing_relative_gates(self):
        baseline = {
            "n": 20,
            "wr_raw": 0.60,
            "avg_raw": 0.06,
            "composite": 100.0,
            "win10_raw": 6.0,
        }
        candidate = {
            "n": 20,
            "wr_raw": 0.61,
            "avg_raw": 0.06,
            "composite": 90.0,
            "win10_raw": 6.0,
            "lose10_raw": 0.0,
        }
        validation = {"n": 8, "wr_raw": 0.60, "avg_raw": 0.01}

        exploratory_ok, _, _ = opt.check_criteria(
            candidate,
            baseline,
            validation,
            mode="rescue",
            baseline_validation_stats=validation,
        )
        final_ok, _, _ = opt.check_criteria(
            candidate,
            baseline,
            validation,
            mode="rescue",
            baseline_validation_stats=validation,
            enforce_relative=True,
        )

        self.assertTrue(exploratory_ok)
        self.assertFalse(final_ok)

    def test_rescue_no_candidate_notification_contains_rejection_reason(self):
        response = mock.MagicMock()
        response.status = 204
        with mock.patch.object(opt, "APPROVAL_WEBHOOK_URL", "https://example.invalid/webhook"), \
                mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = response
            opt.notify_discord_rescue_no_candidate(
                {"n": 47, "wr_raw": 0.55, "avg_raw": 0.07},
                {"n": 7, "wr_raw": 0.29, "avg_raw": 0.04},
                ["rescue test"],
                100,
                rejection_reason="劇的改善ゲート未達: Lockbox勝率が現行未満",
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        fields = payload["embeds"][0]["fields"]
        reason_field = next(field for field in fields if field["name"] == "今回の見送り理由")
        self.assertIn("Lockbox勝率", reason_field["value"])

    def test_stable_replacement_rejection_returns_before_pending_save(self):
        source = inspect.getsource(opt.main)
        gate_index = source.index("replacement_rejects = stable_replacement_gate_rejects(")
        rejection_index = source.index("if replacement_rejects:", gate_index)
        pending_index = source.index("if args.propose:", rejection_index)
        rejection_block = source[rejection_index:pending_index]

        self.assertIn("handle_no_stable_candidate(msg)", rejection_block)
        self.assertIn("return", rejection_block)
        self.assertNotIn('if adoption_mode != "rescue":', source)

    def test_threshold_sweep_treats_all_final_gate_rejections_as_ng(self):
        cases = {
            "quality": "✅ 最終採用条件未達: ✗ 通常条件①",
            "dramatic": "⛔ 劇的改善ゲート未達: 公開365日勝率の改善が+5.6pt",
            "force": "❌ Stable強制ゲートで却下: 未確定平均が現行比で悪化",
            "delta": "Stable: 差分品質ゲートで見送り。件数が減少",
        }

        for expected_kind, output in cases.items():
            with self.subTest(expected_kind=expected_kind):
                summary = opt._parse_sweep_output(output, 0.10)
                self.assertEqual(summary["verdict"], "NG")
                self.assertEqual(summary["ng_kind"], expected_kind)

    def test_workflow_stages_pending_deletions(self):
        workflow = Path(".github/workflows/optimize.yml").read_text(encoding="utf-8")
        self.assertIn('git add -A -- "$path"', workflow)
        self.assertIn('git ls-files --error-unmatch "$path"', workflow)

    def test_approval_notices_are_queued_until_explicit_flush(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
                mock.patch.dict(os.environ, {"DISCORD_APPROVAL_NOTICE_DIR": temp_dir}), \
                mock.patch.object(opt, "_post_discord_webhook", return_value=True) as post:
            attachment = {
                "filename": "comparison.xlsx",
                "content_type": "application/test",
                "content": b"test-workbook",
            }
            opt._queue_or_post_discord_approval(
                {"content": "Sniper"}, attachment=attachment, label="Sniper approval"
            )
            opt._queue_or_post_discord_approval(
                {"content": "Stable"}, label="Stable approval"
            )

            post.assert_not_called()
            self.assertEqual(opt.flush_discord_approval_notices(), 2)
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args_list[0].kwargs["attachment"]["content"], b"test-workbook")
            self.assertFalse((Path(temp_dir) / "notices.json").exists())

    def test_workflow_sends_approval_requests_only_after_pending_push(self):
        workflow = Path(".github/workflows/optimize.yml").read_text(encoding="utf-8")
        self.assertIn("DISCORD_APPROVAL_NOTICE_DIR: /tmp/optimizer-approval-notices", workflow)
        self.assertLess(
            workflow.index("git push"),
            workflow.index("python optimize_screener.py --flush-approval-notices"),
        )

    def test_sniper_apply_uses_current_logic_signature_not_stored_win_rate(self):
        current = {"conditions": ["ema75", "rsi5070"], "thresholds": {}, "wr_raw": 0.99}
        matching = {
            "current_logic": {"conditions": ["ema75", "rsi5070"], "thresholds": {}},
            "stats": {"wr_raw": 0.68},
        }
        changed = copy.deepcopy(matching)
        changed["current_logic"]["conditions"] = ["ema75", "stoch75"]

        self.assertTrue(opt.sniper_pending_matches_current_logic(matching, current))
        self.assertFalse(opt.sniper_pending_matches_current_logic(changed, current))
        self.assertTrue(opt.sniper_pending_matches_current_logic({"stats": {"wr_raw": 0.68}}, current))
        self.assertNotIn("_current_sniper_wr", inspect.getsource(opt.main))


if __name__ == "__main__":
    unittest.main()
