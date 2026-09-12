from __future__ import annotations

import unittest

from .cli import _console_safe, command_result


class ResearchCliTests(unittest.TestCase):
    def test_screen_command_is_a_non_scanning_no_candidate_dry_run(self):
        board = {
            "core": {"decision": "NO_VIABLE_CANDIDATE"},
            "production_migration_decision": "NO_GO",
        }
        result = command_result("screen", board)
        self.assertEqual(result["status"], "NO_VIABLE_CANDIDATE")
        self.assertFalse(result["screening_executed"])
        self.assertFalse(result["market_data_loaded"])
        self.assertEqual(result["recommendations"], [])

    def test_screen_command_fails_closed_if_a_candidate_state_changes(self):
        board = {
            "core": {"decision": "PROMOTED"},
            "production_migration_decision": "NO_GO",
        }
        with self.assertRaises(ValueError):
            command_result("screen", board)

    def test_audit_command_reports_source_count_and_migration_gate(self):
        board = {
            "production_migration_decision": "NO_GO",
            "source_reports": ["a.json", "b.json"],
            "same_definition_outperformance_over_current_bot_established": False,
        }
        result = command_result("audit", board)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["pinned_source_report_count"], 2)
        self.assertFalse(result["same_definition_outperformance_established"])

    def test_report_output_is_safe_for_windows_code_pages(self):
        safe = _console_safe("日本語 — local report", "cp932")
        self.assertEqual(safe, "日本語 \\u2014 local report")
        safe.encode("cp932")


if __name__ == "__main__":
    unittest.main()