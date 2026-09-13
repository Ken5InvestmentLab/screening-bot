from __future__ import annotations

import unittest

import pandas as pd

from tvfree_screener.batch02.core_support_sweep_report_recovery import match_labels_to_decisions


class SupportSweepReportRecoveryTests(unittest.TestCase):
    def test_policy_metrics_join_exactly_the_frozen_selected_keys(self) -> None:
        keys = pd.DataFrame({"date": ["2023-01-02"], "symbol": ["1000"], "family": ["f"], "spec_hash": ["s"]})
        labels = pd.DataFrame({
            "date": ["2023-01-02", "2023-01-02"], "symbol": ["1000", "1001"],
            "family": ["f", "f"], "spec_hash": ["s", "s"], "gross_return": [0.05, -0.50],
            "label_resolved": [True, True], "label_status": ["RESOLVED", "RESOLVED"],
        })
        joined = match_labels_to_decisions(keys, labels)
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined.loc[0, "symbol"], "1000")
        self.assertEqual(joined.loc[0, "gross_return"], 0.05)

    def test_missing_label_fails_closed(self) -> None:
        keys = pd.DataFrame({"date": ["2023-01-02"], "symbol": ["1000"], "family": ["f"], "spec_hash": ["s"]})
        labels = pd.DataFrame({"date": [], "symbol": [], "family": [], "spec_hash": [], "gross_return": [], "label_resolved": [], "label_status": []})
        with self.assertRaises(ValueError):
            match_labels_to_decisions(keys, labels)


if __name__ == "__main__":
    unittest.main()
