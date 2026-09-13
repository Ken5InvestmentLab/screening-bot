from __future__ import annotations

import unittest

import pandas as pd

from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02.endpoint_labels import (
    ENDPOINT_TARGET_ID,
    build_endpoint_only_labels,
    endpoint_label_summary,
)


SESSIONS = pd.DatetimeIndex(pd.to_datetime([
    "2024-01-04", "2024-01-05", "2024-01-09", "2024-01-10",
    "2024-01-11", "2024-01-12", "2024-01-15", "2024-01-16",
    "2024-01-17", "2024-01-18", "2024-01-19",
]))
CALENDAR = SessionCalendar(SESSIONS, "synthetic", "unit-test")


def bars(symbol: str, *, missing: set[str] | None = None, zero_volume: set[str] | None = None):
    missing = missing or set()
    zero_volume = zero_volume or set()
    rows = []
    for day in SESSIONS:
        date = day.strftime("%Y-%m-%d")
        if date in missing:
            continue
        close = 110.0 if date == "2024-01-15" else 100.0
        volume = 0.0 if date in zero_volume else 1000.0
        rows.append({
            "date": date, "symbol": symbol, "open": 100.0, "high": max(100.0, close),
            "low": min(100.0, close), "close": close, "volume": volume,
        })
    return rows


class EndpointLabelTests(unittest.TestCase):
    def test_morning_and_afternoon_signals_share_exact_daily_endpoint(self):
        signals = pd.DataFrame([
            {"date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s", "signal_time": "09:30"},
            {"date": "2024-01-05", "symbol": "2222", "family": "f", "spec_hash": "s", "signal_time": "13:30"},
        ])
        labels = build_endpoint_only_labels(
            pd.DataFrame(bars("1111") + bars("2222")), signals, CALENDAR
        )
        self.assertEqual(labels["entry_date"].tolist(), [pd.Timestamp("2024-01-09")] * 2)
        self.assertEqual(labels["exit_date"].tolist(), [pd.Timestamp("2024-01-15")] * 2)
        self.assertEqual(len(labels), 2)
        for value in labels["endpoint_gross_return"]:
            self.assertAlmostEqual(float(value), 0.10)
        self.assertEqual(labels["endpoint_target_id"].tolist(), [ENDPOINT_TARGET_ID] * 2)
        self.assertEqual(labels["signal_time"].tolist(), ["09:30", "13:30"])

    def test_missing_interior_session_keeps_endpoint_return_and_marks_path_incomplete(self):
        signals = pd.DataFrame([{
            "date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s",
        }])
        labels = build_endpoint_only_labels(
            pd.DataFrame(bars("1111", missing={"2024-01-10"})), signals, CALENDAR
        )
        row = labels.iloc[0]
        self.assertTrue(row.endpoint_label_resolved)
        self.assertAlmostEqual(row.endpoint_gross_return, 0.10)
        self.assertFalse(row.daily_path_resolved)
        self.assertEqual(row.daily_path_status, "MISSING_HOLDING_SESSION_BAR")

    def test_zero_volume_endpoint_is_reported_separately_from_mark_to_market(self):
        signals = pd.DataFrame([{
            "date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s",
        }])
        labels = build_endpoint_only_labels(
            pd.DataFrame(bars("1111", zero_volume={"2024-01-09"})), signals, CALENDAR
        )
        row = labels.iloc[0]
        self.assertTrue(row.endpoint_label_resolved)
        self.assertEqual(row.endpoint_entry_volume_status, "ZERO")
        self.assertFalse(row.daily_path_resolved)
        self.assertEqual(row.daily_path_status, "ENTRY_ZERO_OR_UNKNOWN_VOLUME")

    def test_missing_endpoints_remain_unresolved_and_rows_are_preserved(self):
        signals = pd.DataFrame([
            {"date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s"},
            {"date": "2024-01-05", "symbol": "2222", "family": "f", "spec_hash": "s"},
        ])
        prices = pd.DataFrame(
            bars("1111", missing={"2024-01-09"}) + bars("2222", missing={"2024-01-15"})
        )
        labels = build_endpoint_only_labels(prices, signals, CALENDAR)
        self.assertEqual(len(labels), 2)
        self.assertEqual(set(labels.endpoint_label_status), {
            "MISSING_ENTRY_DAILY_BAR", "MISSING_EXIT_DAILY_BAR",
        })
        self.assertFalse(labels.endpoint_label_resolved.any())

    def test_summary_keeps_endpoint_and_path_metrics_separate(self):
        signals = pd.DataFrame([{
            "date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s",
        }])
        labels = build_endpoint_only_labels(pd.DataFrame(bars("1111")), signals, CALENDAR)
        summary = endpoint_label_summary(labels, costs=(0.0, 0.005))
        self.assertEqual(summary["requested_count"], 1)
        self.assertEqual(summary["endpoint_resolved_count"], 1)
        self.assertEqual(summary["daily_path_resolved_count"], 1)
        self.assertEqual(summary["resolved_by_both_count"], 1)
        self.assertEqual(summary["endpoint_vs_path_equal_return_count"], 1)
        self.assertAlmostEqual(
            summary["endpoint_net_return_metrics_by_round_trip_cost"]["0.005"]["mean"],
            0.095,
        )


if __name__ == "__main__":
    unittest.main()
