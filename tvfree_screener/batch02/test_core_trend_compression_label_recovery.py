from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02.core_trend_compression_label_recovery import join_labels


class LabelRecoveryJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = pd.date_range("2023-01-02", periods=8, freq="D")
        self.calendar = SessionCalendar(self.sessions, "fixture", "unit-test")

    def test_keeps_resolved_and_unresolved_labels_with_canonical_timing(self) -> None:
        decisions = pd.DataFrame({
            "date": [self.sessions[0], self.sessions[0]],
            "symbol": pd.Series(["1111", "2222"], dtype="string"),
        })
        labels = pd.DataFrame({
            "date": [self.sessions[0], self.sessions[0]],
            "symbol": pd.Series(["1111", "2222"], dtype="string"),
            "entry_date": [self.sessions[1], self.sessions[1]],
            "exit_date": [self.sessions[5], self.sessions[5]],
            "entry_price": [10.0, np.nan],
            "exit_price": [11.0, np.nan],
            "gross_return": [0.1, np.nan],
            "label_status": ["RESOLVED", "ZERO_VOLUME_HOLDING_SESSION"],
            "label_resolved": [True, False],
            "label_available_at": [self.sessions[5], self.sessions[5]],
            "family": ["fixture", "fixture"],
            "spec_hash": ["spec", "spec"],
            "session_index": [0, 0],
        })

        joined = join_labels(decisions, labels, self.calendar)

        self.assertEqual(joined["symbol"].tolist(), ["1111", "2222"])
        self.assertEqual(joined["label_status"].tolist(), ["RESOLVED", "ZERO_VOLUME_HOLDING_SESSION"])
        self.assertEqual(joined["label_resolved"].tolist(), [True, False])
        self.assertAlmostEqual(float(joined.loc[0, "gross_return"]), 0.1)

    def test_missing_rebuilt_label_fails_closed(self) -> None:
        decisions = pd.DataFrame({"date": [self.sessions[0]], "symbol": pd.Series(["1111"], dtype="string")})
        labels = pd.DataFrame({
            "date": pd.Series([], dtype="datetime64[ns]"),
            "symbol": pd.Series([], dtype="string"),
            "entry_date": pd.Series([], dtype="datetime64[ns]"),
            "exit_date": pd.Series([], dtype="datetime64[ns]"),
            "entry_price": pd.Series([], dtype="float64"),
            "exit_price": pd.Series([], dtype="float64"),
            "gross_return": pd.Series([], dtype="float64"),
            "label_status": pd.Series([], dtype="object"),
            "label_resolved": pd.Series([], dtype="bool"),
            "label_available_at": pd.Series([], dtype="datetime64[ns]"),
            "family": pd.Series([], dtype="object"),
            "spec_hash": pd.Series([], dtype="object"),
            "session_index": pd.Series([], dtype="int32"),
        })

        with self.assertRaisesRegex(ValueError, "no rebuilt canonical label"):
            join_labels(decisions, labels, self.calendar)


if __name__ == "__main__":
    unittest.main()
