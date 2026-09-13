from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tvfree_screener.batch02.audit_hourly_daily_consistency import audit_files


class HourlyDailyConsistencyTests(unittest.TestCase):
    def write_csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_hourly_aggregate_matches_daily_ohlcv(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar, daily, hourly = root / "calendar.csv", root / "daily.csv", root / "hourly.csv"
            self.write_csv(calendar, ["date"], [{"date": "2024-01-05"}])
            self.write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 112, "low": 98, "close": 110, "volume": 1000},
            ])
            self.write_csv(hourly, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05T00:00:00+00:00", "symbol": "TYO:1111", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 100},
                {"timestamp": "2024-01-05 10:00:00", "symbol": "1111", "open": 104, "high": 108, "low": 101, "close": 106, "volume": 200},
                {"timestamp": "2024-01-05 11:00:00", "symbol": "1111", "open": 106, "high": 110, "low": 105, "close": 109, "volume": 150},
                {"timestamp": "2024-01-05 12:30:00", "symbol": "1111", "open": 109, "high": 112, "low": 108, "close": 111, "volume": 250},
                {"timestamp": "2024-01-05 14:30:00", "symbol": "1111", "open": 111, "high": 111.5, "low": 98, "close": 110, "volume": 300},
            ])
            result = audit_files(hourly, daily, calendar, root / "out", 60, "start")
            self.assertEqual(result["summary_counts"]["comparison::SOURCE_INTERNAL_COMPARISON_ONLY"], 1)
            for field in ("open", "high", "low", "close", "volume"):
                self.assertEqual(result["field_error_metrics"][field]["exact_match_count"], 1)
            self.assertTrue(result["daily_vs_hourly_is_internal_consistency_not_truth"])

    def test_reports_discrepancies_without_applying_a_threshold(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar, daily, hourly = root / "calendar.csv", root / "daily.csv", root / "hourly.csv"
            self.write_csv(calendar, ["date"], [{"date": "2024-01-05"}])
            self.write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 113, "low": 98, "close": 109, "volume": 1100},
            ])
            self.write_csv(hourly, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05 09:00:00", "symbol": "1111", "open": 100, "high": 112, "low": 98, "close": 110, "volume": 1000},
            ])
            result = audit_files(hourly, daily, calendar, root / "out", 60, "start")
            self.assertEqual(result["field_error_metrics"]["high"]["maximum_absolute_difference"], 1.0)
            self.assertEqual(result["field_error_metrics"]["close"]["maximum_absolute_difference"], 1.0)
            self.assertEqual(result["field_error_metrics"]["volume"]["maximum_absolute_difference"], 100.0)
            with (root / "out" / "hourly_daily_consistency_by_symbol_session.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["comparison_status"], "SOURCE_INTERNAL_COMPARISON_ONLY")
            self.assertEqual(row["high_difference_hourly_minus_daily"], "-1.0")

    def test_daily_only_and_hourly_only_pairs_remain_visible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar, daily, hourly = root / "calendar.csv", root / "daily.csv", root / "hourly.csv"
            self.write_csv(calendar, ["date"], [{"date": "2024-01-05"}])
            self.write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
            ])
            self.write_csv(hourly, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05 09:00:00", "symbol": "2222", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
            ])
            result = audit_files(hourly, daily, calendar, root / "out", 60, "start")
            self.assertEqual(result["summary_counts"]["symbol_session_pairs"], 2)
            self.assertEqual(result["summary_counts"]["daily::AVAILABLE_VALID_OHLCV"], 1)
            self.assertEqual(result["summary_counts"]["daily::MISSING_DAILY_ROW"], 1)
            self.assertEqual(result["summary_counts"]["hourly::NO_HOURLY_ROWS"], 1)

    def test_bar_crossing_lunch_is_kept_for_whole_day_aggregate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar, daily, hourly = root / "calendar.csv", root / "daily.csv", root / "hourly.csv"
            self.write_csv(calendar, ["date"], [{"date": "2024-01-05"}])
            self.write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 200},
            ])
            self.write_csv(hourly, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05 09:00:00", "symbol": "1111", "open": 100, "high": 105, "low": 99, "close": 101, "volume": 100},
                {"timestamp": "2024-01-05 11:30:00", "symbol": "1111", "open": 101, "high": 999, "low": 1, "close": 101, "volume": 999999},
                {"timestamp": "2024-01-05 12:00:00", "symbol": "1111", "open": 101, "high": 104, "low": 100, "close": 104, "volume": 100},
            ])
            result = audit_files(hourly, daily, calendar, root / "out", 60, "start")
            self.assertEqual(result["hourly_input"]["rows"], 3)
            self.assertEqual(result["field_error_metrics"]["high"]["maximum_absolute_difference"], 0.0)
            self.assertEqual(result["field_error_metrics"]["volume"]["maximum_absolute_difference"], 0.0)
            with (root / "out" / "hourly_daily_consistency_by_symbol_session.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["hourly_outside_session_rows"], "1")
            self.assertEqual(row["hourly_session_boundary_crossing_rows"], "1")

    def test_duplicate_timestamp_is_exposed_and_excluded_from_clean_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar, daily, hourly = root / "calendar.csv", root / "daily.csv", root / "hourly.csv"
            self.write_csv(calendar, ["date"], [{"date": "2024-01-05"}])
            self.write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
            ])
            self.write_csv(hourly, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05 09:00:00", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 500},
                {"timestamp": "2024-01-05 09:00:00", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 500},
            ])
            result = audit_files(hourly, daily, calendar, root / "out", 60, "start")
            self.assertEqual(result["summary_counts"]["hourly::DUPLICATE_HOURLY_TIMESTAMP"], 1)
            self.assertEqual(result["summary_counts"]["comparison::UNASSESSABLE_OR_ROW_QUALITY_LIMIT"], 1)

    def test_end_labeled_hour_overlapping_afternoon_reentry_is_included(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar, daily, hourly = root / "calendar.csv", root / "daily.csv", root / "hourly.csv"
            self.write_csv(calendar, ["date"], [{"date": "2024-01-05"}])
            self.write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 100},
            ])
            self.write_csv(hourly, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05 13:00:00", "symbol": "1111", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 100},
            ])
            result = audit_files(hourly, daily, calendar, root / "out", 60, "end")
            self.assertEqual(result["summary_counts"]["comparison::SOURCE_INTERNAL_COMPARISON_ONLY"], 1)
            self.assertEqual(result["hourly_timestamp_label"], "end")


if __name__ == "__main__":
    unittest.main()
