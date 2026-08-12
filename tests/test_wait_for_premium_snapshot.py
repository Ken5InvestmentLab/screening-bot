import unittest
from pathlib import Path

from wait_for_premium_snapshot import (
    DEFAULT_MAX_WAIT_SECONDS,
    expected_bottom_alert_ids,
    normalized_date_prefix,
    posted_bottom_alert_ids,
    summarized_alert_ids,
)


class WaitForPremiumSnapshotTest(unittest.TestCase):
    def test_default_wait_allows_delayed_local_automation_catch_up(self):
        self.assertEqual(DEFAULT_MAX_WAIT_SECONDS, 4 * 60 * 60)

    def test_report_workflow_keeps_matching_wait_and_job_headroom(self):
        workflow = (
            Path(__file__).resolve().parents[1] / ".github" / "workflows" / "mega-validation-report.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(f'PREMIUM_SNAPSHOT_WAIT_SECONDS: "{DEFAULT_MAX_WAIT_SECONDS}"', workflow)
        self.assertIn("timeout-minutes: 300", workflow)

    def test_normalized_date_prefix_accepts_sheet_formats(self):
        self.assertEqual(normalized_date_prefix("2026/07/13 13:01:00"), "2026-07-13")
        self.assertEqual(normalized_date_prefix("2026-7-3"), "2026-07-03")
        self.assertEqual(normalized_date_prefix("2026/99/13"), "")

    def test_expected_alerts_are_bottom_signals_from_target_date(self):
        rows = [
            [],
            [],
            [],
            ["alert_id", "received_at", "signal_type"],
            ["a1", "2026/07/13 13:00:00", "BOTTOM"],
            ["a2", "2026/07/13 15:31:00", "bottom"],
            ["top", "2026/07/13 13:00:00", "TOP"],
            ["old", "2026/07/12 13:00:00", "BOTTOM"],
        ]

        self.assertEqual(expected_bottom_alert_ids(rows, "2026-07-13"), {"a1", "a2"})

    def test_posted_alerts_include_grounded_and_stub_posts(self):
        rows = [
            ["event_at", "event_type", "alert_id", "x", "x", "signal_type"],
            ["2026-07-13", "POSTED", "a1", "", "", "BOTTOM"],
            ["2026-07-13", "posted", "a2", "", "", ""],
            ["2026-07-13", "FAILED", "a3", "", "", "BOTTOM"],
            ["2026-07-13", "POSTED", "top", "", "", "TOP"],
        ]

        self.assertEqual(posted_bottom_alert_ids(rows), {"a1", "a2"})

    def test_missing_alert_summary_is_bounded(self):
        alert_ids = {f"a{index:02d}" for index in range(20)}

        summary = summarized_alert_ids(alert_ids)

        self.assertIn("a00,a01,a02", summary)
        self.assertIn("...(+8 more)", summary)
        self.assertNotIn("a19", summary)


if __name__ == "__main__":
    unittest.main()
