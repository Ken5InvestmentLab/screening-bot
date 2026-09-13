from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tvfree_screener.batch02.audit_intraday_daily_coverage import audit_csv_files


class IntradayDailyCoverageTests(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_classifies_missing_partial_daily_available_invalid_and_unmatched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar = root / "calendar.csv"
            daily = root / "daily.csv"
            four_hour = root / "four_hour.csv"
            self._write_csv(calendar, ["date", "session_index"], [
                {"date": "2024-01-04", "session_index": 0},
                {"date": "2024-01-05", "session_index": 1},
                {"date": "2024-01-09", "session_index": 2},
            ])
            self._write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
                {"date": "2024-01-05", "symbol": "2222", "open": 200, "high": 201, "low": 198, "close": 199, "volume": 500},
                {"date": "2024-01-05", "symbol": "3333", "open": 50, "high": 55, "low": 49, "close": 54, "volume": 0},
                {"date": "2024-01-05", "symbol": "4444", "open": 10, "high": 8, "low": 9, "close": 9, "volume": 10},
            ])
            self._write_csv(four_hour, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05T00:00:00+00:00", "symbol": "TYO:1111", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 400},
                {"timestamp": "2024-01-05 13:00:00", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 600},
                {"timestamp": "2024-01-05 09:00:00", "symbol": "2222", "open": 200, "high": 201, "low": 199, "close": 200, "volume": 200},
                {"timestamp": "2024-01-05 09:00:00", "symbol": "3333", "open": 50, "high": 53, "low": 49, "close": 51, "volume": 0},
                {"timestamp": "2024-01-05 09:00:00", "symbol": "5555", "open": 70, "high": 71, "low": 69, "close": 70, "volume": 10},
            ])
            output = root / "out"
            summary = audit_csv_files(four_hour, daily, calendar, output)
            self.assertEqual(summary["daily_symbol_session_pairs_in_scope"], 4)
            self.assertEqual(summary["symbol_session_pairs_with_missing_partial_or_invalid_four_hour_data"], 3)
            self.assertEqual(summary["daily_ohlcv_available_for_four_hour_gaps"], 2)
            self.assertEqual(summary["zero_volume_daily_bars_among_four_hour_gaps"], 1)
            self.assertEqual(summary["four_hour_observed_keys_without_same_day_daily_row"], 1)

            with (output / "missing_four_hour_symbol_sessions.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = {row["symbol"]: row for row in csv.DictReader(stream)}
            self.assertEqual(rows["2222"]["four_hour_status"], "MISSING_AFTERNOON_BAR")
            self.assertEqual(rows["3333"]["daily_status"], "AVAILABLE_ZERO_VOLUME")
            self.assertEqual(rows["4444"]["four_hour_status"], "NO_4H_BARS")
            self.assertEqual(rows["4444"]["daily_status"], "INVALID_DAILY_OHLCV")
            with (output / "four_hour_keys_without_daily.csv").open(encoding="utf-8-sig", newline="") as stream:
                unmatched = list(csv.DictReader(stream))
            self.assertEqual([(row["symbol"], row["daily_status"]) for row in unmatched], [("5555", "MISSING_DAILY_ROW")])
            reread = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(reread["external_fetch"], False)

    def test_duplicate_intraday_slot_and_duplicate_daily_key_are_not_silently_collapsed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar = root / "calendar.csv"
            daily = root / "daily.csv"
            four_hour = root / "four_hour.csv"
            self._write_csv(calendar, ["date", "session_index"], [
                {"date": "2024-01-05", "session_index": 0},
            ])
            daily_rows = [
                {"date": "2024-01-05", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
            ]
            self._write_csv(daily, ["date", "symbol", "open", "high", "low", "close", "volume"], daily_rows * 2)
            self._write_csv(four_hour, ["timestamp", "symbol", "open", "high", "low", "close", "volume"], [
                {"timestamp": "2024-01-05 09:00:00", "symbol": "1111", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 400},
                {"timestamp": "2024-01-05 09:00:00", "symbol": "1111", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 400},
                {"timestamp": "2024-01-05 13:00:00", "symbol": "1111", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 600},
            ])
            summary = audit_csv_files(four_hour, daily, calendar, root / "out")
            with (root / "out" / "missing_four_hour_symbol_sessions.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["four_hour_status"], "DUPLICATE_OR_UNEXPECTED_4H_BARS")
            self.assertEqual(row["daily_status"], "DUPLICATE_DAILY_KEY")
            self.assertFalse(row["daily_ohlcv_available"] == "true")
            self.assertEqual(summary["symbol_session_pairs_with_missing_partial_or_invalid_four_hour_data"], 1)


if __name__ == "__main__":
    unittest.main()
