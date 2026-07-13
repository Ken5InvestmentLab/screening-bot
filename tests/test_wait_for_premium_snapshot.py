import unittest

from wait_for_premium_snapshot import (
    expected_bottom_alert_ids,
    normalized_date_prefix,
    posted_bottom_alert_ids,
)


class WaitForPremiumSnapshotTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
