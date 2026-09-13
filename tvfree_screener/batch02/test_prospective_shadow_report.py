import unittest

from tvfree_screener.batch02.prospective_shadow_report import build_report, metrics


class ProspectiveShadowReportTests(unittest.TestCase):
    def test_resolved_only_metrics(self):
        rows = [
            {"status":"RESOLVED","ret5bd_gross":0.20},
            {"status":"RESOLVED","ret5bd_gross":-0.10},
            {"status":"PENDING_5BD"},
        ]
        out = metrics(rows, 0.005)
        self.assertEqual(out["rows"], 3)
        self.assertEqual(out["resolved"], 2)
        self.assertEqual(out["status_counts"]["PENDING_5BD"], 1)
        self.assertAlmostEqual(out["gross_ge20_rate"], 0.5)
        self.assertAlmostEqual(out["gross_le10_rate"], 0.5)

    def test_resolved_missing_return_is_error(self):
        with self.assertRaises(ValueError):
            metrics([{"status":"RESOLVED"}])

    def test_groups_by_freeze_and_month(self):
        rows = [
            {"experiment_id":"E","model_freeze_id":"F1","signal_date":"2026-09-14","status":"RESOLVED","ret5bd_gross":0.1},
            {"experiment_id":"E","model_freeze_id":"F2","signal_date":"2026-10-01","status":"PENDING_5BD"},
        ]
        out = build_report(rows)
        self.assertIn("E|F1", out["by_model_freeze"])
        self.assertIn("E|F2", out["by_model_freeze"])
        self.assertIn("2026-09", out["by_signal_month"])
        self.assertIn("2026-10", out["by_signal_month"])
        self.assertFalse(out["selection_or_threshold_tuning_allowed"])

    def test_top_removed_means(self):
        rows = [
            {"status":"RESOLVED","ret5bd_gross":0.50},
            {"status":"RESOLVED","ret5bd_gross":0.10},
            {"status":"RESOLVED","ret5bd_gross":0.00},
            {"status":"RESOLVED","ret5bd_gross":-0.10},
            {"status":"RESOLVED","ret5bd_gross":-0.20},
        ]
        out = metrics(rows, 0.0)
        self.assertAlmostEqual(out["top1_removed_net_mean"], -0.05)
        self.assertAlmostEqual(out["top3_removed_net_mean"], -0.15)


if __name__ == "__main__":
    unittest.main()
