import unittest

import pandas as pd

from tvfree_screener.batch01 import audit_monster_canonical as monster
from tvfree_screener.batch02 import annual_candidate_audit as annual


def _pool(rows):
    return pd.DataFrame([
        {
            "date": pd.Timestamp(day),
            "symbol": symbol,
            "identity_key": symbol,
            "raw_rank": rank,
        }
        for day, symbol, rank in rows
    ])


class AnnualCandidateAuditTests(unittest.TestCase):
    def test_all_candidates_per_day_and_one_previous_official_session_cooldown(self):
        sessions = pd.DatetimeIndex([
            "2024-12-27",  # Friday
            "2024-12-30",  # next official session
            "2025-01-06",  # holiday/weekend gap, still next official session
            "2025-01-07",
            "2025-01-08",
        ])
        pool = _pool([
            ("2024-12-27", "1111", 1),
            ("2024-12-27", "2222", 2),
            ("2024-12-30", "1111", 1),
            ("2024-12-30", "3333", 2),
            ("2025-01-06", "1111", 1),
            ("2025-01-06", "3333", 2),
            # No candidates on Jan 7 clears the prior-session cooldown set.
            ("2025-01-08", "1111", 1),
        ])

        trace = annual.apply_all_candidates_cooldown(pool, sessions)
        day1 = trace.loc[trace["date"].eq(pd.Timestamp("2024-12-27"))]
        day2 = trace.loc[trace["date"].eq(pd.Timestamp("2024-12-30"))]
        day3 = trace.loc[trace["date"].eq(pd.Timestamp("2025-01-06"))]
        day5 = trace.loc[trace["date"].eq(pd.Timestamp("2025-01-08"))]

        self.assertEqual(int(day1["cooldown_status"].eq("DETECTED").sum()), 2)
        self.assertEqual(set(day2.loc[day2["cooldown_status"].eq("DETECTED"), "symbol"]), {"3333"})
        self.assertEqual(set(day2.loc[day2["cooldown_status"].eq("COOLDOWN_BLOCKED"), "symbol"]), {"1111"})
        self.assertEqual(set(day3.loc[day3["cooldown_status"].eq("DETECTED"), "symbol"]), {"1111"})
        self.assertEqual(set(day3.loc[day3["cooldown_status"].eq("COOLDOWN_BLOCKED"), "symbol"]), {"3333"})
        self.assertEqual(set(day5["cooldown_status"]), {"DETECTED"})

    def test_feature_reader_excludes_cached_outcome_columns(self):
        seen = {}
        original = annual.pd.read_csv

        def fake_read_csv(path, **kwargs):
            seen.update(kwargs)
            return pd.DataFrame({
                "date": [pd.Timestamp("2023-01-04")],
                "symbol": ["1111"],
                "ret1": [0.01],
                "ret10": [0.0],
                "volr20": [0.4],
                "tail_cdf": [0.9995],
                "tail_p": [0.9],
                "range_pct": [0.5],
            })

        annual.pd.read_csv = fake_read_csv
        try:
            frame = annual.read_v7_signal_features()
        finally:
            annual.pd.read_csv = original

        self.assertEqual(list(seen["usecols"]), list(annual.TAIL_SIGNAL_COLUMNS))
        self.assertFalse({"target5_no", "target_end_date", "y_hit20", "y_loss10"}.intersection(seen["usecols"]))
        self.assertEqual(frame.loc[0, "symbol"], "1111")

    def test_year_end_crossing_label_is_retained_as_purged_unresolved(self):
        labels = pd.DataFrame({
            "date": [pd.Timestamp("2024-12-27")],
            "symbol": ["1111"],
            "exit_date": [pd.Timestamp("2025-01-06")],
            "gross_return": [0.25],
            "label_status": ["RESOLVED"],
            "label_resolved": [True],
        })

        result = monster._periodized(labels, 2024, "2024-12-30")

        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "label_status"], "PURGED_SPLIT_BOUNDARY")
        self.assertFalse(bool(result.loc[0, "label_resolved"]))
        self.assertTrue(pd.isna(result.loc[0, "gross_return"]))


if __name__ == "__main__":
    unittest.main()

