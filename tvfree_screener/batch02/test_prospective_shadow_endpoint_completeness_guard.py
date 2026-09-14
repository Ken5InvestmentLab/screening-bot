from __future__ import annotations

import unittest

from prospective_shadow_endpoint_completeness_guard import audit_endpoint_completeness


class EndpointCompletenessGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = [
            "2026-09-01",
            "2026-09-02",
            "2026-09-03",
            "2026-09-04",
            "2026-09-07",
            "2026-09-08",
            "2026-09-09",
        ]
        self.shadow = [
            {"symbol": "1234", "signal_date": "2026-09-01"},
            {"symbol": "5678", "signal_date": "2026-09-02"},
        ]
        self.daily = {
            ("1234", "2026-09-02"): {"open": "100", "close": "101"},
            ("1234", "2026-09-08"): {"open": "109", "close": "110"},
            ("5678", "2026-09-03"): {"open": "200", "close": "201"},
            ("5678", "2026-09-09"): {"open": "209", "close": "210"},
        }

    def test_complete_mature_endpoints_pass(self) -> None:
        result = audit_endpoint_completeness(self.shadow, self.daily, self.sessions)
        self.assertTrue(result["endpoint_completeness_valid"])
        self.assertEqual(result["mature_candidate_count"], 2)
        self.assertEqual(result["required_endpoint_pair_count"], 4)
        self.assertEqual(result["missing_required_endpoint_pair_count"], 0)
        self.assertFalse(result["integrity"]["strategy_outcomes_opened"])

    def test_missing_exit_pair_fails_closed(self) -> None:
        daily = dict(self.daily)
        daily.pop(("1234", "2026-09-08"))
        result = audit_endpoint_completeness(self.shadow, daily, self.sessions)
        self.assertFalse(result["endpoint_completeness_valid"])
        self.assertIn("1234|2026-09-08|close", result["missing_required_endpoint_pairs"])

    def test_invalid_required_price_fails_closed(self) -> None:
        daily = dict(self.daily)
        daily[("1234", "2026-09-02")] = {"open": "0", "close": "101"}
        result = audit_endpoint_completeness(self.shadow, daily, self.sessions)
        self.assertFalse(result["endpoint_completeness_valid"])
        self.assertIn("1234|2026-09-02|open", result["invalid_required_endpoint_prices"])

    def test_not_yet_mature_candidate_is_pending_not_failure(self) -> None:
        shadow = [{"symbol": "9999", "signal_date": "2026-09-08"}]
        result = audit_endpoint_completeness(shadow, {}, self.sessions)
        self.assertTrue(result["endpoint_completeness_valid"])
        self.assertEqual(result["pending_candidate_count"], 1)
        self.assertEqual(result["required_endpoint_pair_count"], 0)

    def test_signal_date_outside_pinned_calendar_blocks(self) -> None:
        shadow = [{"symbol": "9999", "signal_date": "2026-09-10"}]
        result = audit_endpoint_completeness(shadow, {}, self.sessions)
        self.assertFalse(result["endpoint_completeness_valid"])
        self.assertTrue(any("signal_date_not_in_calendar" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
