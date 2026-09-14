from __future__ import annotations

import unittest

from prospective_shadow_resolution_continuity_guard import compare_resolution_snapshots


def base_row(**kw):
    row = {
        "key": "EXP|FREEZE|1111.T|2026-09-15|AM_09_13",
        "experiment_id": "EXP",
        "model_freeze_id": "FREEZE",
        "symbol": "1111.T",
        "signal_date": "2026-09-15",
        "bin_name": "AM_09_13",
        "feature_cutoff": "2026-09-15T13:00:00+09:00",
        "source_tag": "RAW_CAUSAL_INTRADAY",
        "score": None,
        "rank": 1,
        "payload_sha256": None,
        "status": "PENDING_5BD",
    }
    row.update(kw)
    return row


def resolved(**kw):
    row = base_row(
        status="RESOLVED",
        entry_date="2026-09-16",
        exit_date="2026-09-22",
        entry_open=100.0,
        exit_close=120.0,
        ret5bd_gross=0.2,
    )
    row.update(kw)
    return row


class ResolutionContinuityGuardTests(unittest.TestCase):
    def test_unchanged_resolved_row_passes(self):
        old = [resolved()]
        new = [resolved()]
        out = compare_resolution_snapshots(old, new)
        self.assertTrue(out["resolution_continuity_valid"])

    def test_pending_to_resolved_is_allowed(self):
        old = [base_row()]
        new = [resolved()]
        out = compare_resolution_snapshots(old, new)
        self.assertTrue(out["resolution_continuity_valid"])

    def test_unresolved_to_resolved_same_dates_is_allowed(self):
        old = [base_row(status="UNRESOLVED_ENDPOINT", entry_date="2026-09-16", exit_date="2026-09-22")]
        new = [resolved()]
        out = compare_resolution_snapshots(old, new)
        self.assertTrue(out["resolution_continuity_valid"])

    def test_resolved_endpoint_mutation_blocks(self):
        old = [resolved()]
        new = [resolved(exit_close=121.0, ret5bd_gross=0.21)]
        out = compare_resolution_snapshots(old, new)
        self.assertFalse(out["resolution_continuity_valid"])
        self.assertTrue(any("resolved_field_changed" in err for err in out["errors"]))

    def test_resolved_to_unresolved_regression_blocks(self):
        old = [resolved()]
        new = [base_row(status="UNRESOLVED_ENDPOINT", entry_date="2026-09-16", exit_date="2026-09-22")]
        out = compare_resolution_snapshots(old, new)
        self.assertFalse(out["resolution_continuity_valid"])
        self.assertTrue(any("invalid_status_transition" in err for err in out["errors"]))

    def test_candidate_removal_blocks(self):
        second = base_row(
            key="EXP|FREEZE|2222.T|2026-09-16|PM_13_CLOSE",
            symbol="2222.T",
            signal_date="2026-09-16",
            bin_name="PM_13_CLOSE",
            feature_cutoff="2026-09-16T15:30:00+09:00",
        )
        old = [base_row(), second]
        new = [base_row()]
        out = compare_resolution_snapshots(old, new)
        self.assertFalse(out["resolution_continuity_valid"])
        self.assertIn("candidate_rows_removed", out["errors"])

    def test_candidate_reorder_blocks(self):
        first = base_row()
        second = base_row(
            key="EXP|FREEZE|2222.T|2026-09-16|PM_13_CLOSE",
            symbol="2222.T",
            signal_date="2026-09-16",
            bin_name="PM_13_CLOSE",
            feature_cutoff="2026-09-16T15:30:00+09:00",
        )
        out = compare_resolution_snapshots([first, second], [second, first])
        self.assertFalse(out["resolution_continuity_valid"])
        self.assertIn("candidate_order_or_prefix_changed", out["errors"])

    def test_new_appended_candidate_is_allowed(self):
        old = [resolved()]
        second = base_row(
            key="EXP|FREEZE|2222.T|2026-09-23|AM_09_13",
            symbol="2222.T",
            signal_date="2026-09-23",
            feature_cutoff="2026-09-23T13:00:00+09:00",
        )
        out = compare_resolution_snapshots(old, [resolved(), second])
        self.assertTrue(out["resolution_continuity_valid"])
        self.assertEqual(out["new_rows"], 1)

    def test_unresolved_endpoint_date_change_blocks(self):
        old = [base_row(status="UNRESOLVED_ENDPOINT", entry_date="2026-09-16", exit_date="2026-09-22")]
        new = [base_row(status="UNRESOLVED_ENDPOINT", entry_date="2026-09-17", exit_date="2026-09-23")]
        out = compare_resolution_snapshots(old, new)
        self.assertFalse(out["resolution_continuity_valid"])
        self.assertTrue(any("endpoint_date_changed" in err for err in out["errors"]))

    def test_inconsistent_return_blocks_even_on_first_snapshot(self):
        out = compare_resolution_snapshots([], [resolved(ret5bd_gross=0.5)])
        self.assertFalse(out["resolution_continuity_valid"])
        self.assertTrue(any("ret5bd_gross_inconsistent" in err for err in out["errors"]))


if __name__ == "__main__":
    unittest.main()
