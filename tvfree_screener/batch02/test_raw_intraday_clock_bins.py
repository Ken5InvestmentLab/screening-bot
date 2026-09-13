from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tvfree_screener.batch02.raw_intraday_clock_bins import build_clock_bins

JST = ZoneInfo("Asia/Tokyo")


class RawIntradayClockBinTests(unittest.TestCase):
    def row(self, hour: int, **overrides):
        row = {
            "timestamp": datetime(2026, 9, 11, hour, 0, tzinfo=JST),
            "symbol": "TYO:1111",
            "open": 100 + hour,
            "high": 102 + hour,
            "low": 99 + hour,
            "close": 101 + hour,
            "volume": 100,
        }
        row.update(overrides)
        return row

    def test_am_can_be_complete_when_pm_is_missing(self):
        rows = [self.row(hour) for hour in [9, 10, 11, 12, 13, 14]]
        bins, _ = build_clock_bins(rows)
        self.assertEqual([item.bin_name for item in bins], ["AM_09_13"])

    def test_complete_am_and_pm_have_independent_cutoffs(self):
        rows = [self.row(hour) for hour in [9, 10, 11, 12, 13, 14, 15]]
        bins, _ = build_clock_bins(rows)
        self.assertEqual(len(bins), 2)
        am = next(item for item in bins if item.bin_name == "AM_09_13")
        pm = next(item for item in bins if item.bin_name == "PM_13_CLOSE")
        self.assertEqual(am.row_count, 4)
        self.assertEqual(pm.row_count, 3)
        self.assertEqual(am.feature_cutoff_jst.hour, 13)
        self.assertEqual(pm.feature_cutoff_jst.hour, 16)

    def test_closing_snapshot_is_not_a_required_volume_bar(self):
        rows = [self.row(hour) for hour in [9, 10, 11, 12, 13, 14, 15]]
        rows.append(self.row(15, is_closing_snapshot=1, volume=0))
        bins, _ = build_clock_bins(rows)
        self.assertEqual(len(bins), 2)

    def test_duplicate_hour_invalidates_only_its_bin(self):
        rows = [self.row(hour) for hour in [9, 10, 11, 12, 13, 14, 15]]
        rows.append(self.row(10))
        bins, _ = build_clock_bins(rows)
        self.assertEqual([item.bin_name for item in bins], ["PM_13_CLOSE"])

    def test_invalid_required_bar_is_rejected(self):
        rows = [self.row(hour) for hour in [9, 10, 11, 12]]
        rows[2]["low"] = 999
        bins, _ = build_clock_bins(rows)
        self.assertEqual(len(bins), 0)


if __name__ == "__main__":
    unittest.main()
