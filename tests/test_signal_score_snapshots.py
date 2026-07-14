import json
import unittest
from unittest.mock import patch

import pandas as pd

import signal_score_snapshots as snapshots


def session(date_key, hour, open_, high, low, close, volume):
    return {
        "timestamp": pd.Timestamp(f"{date_key} {hour:02d}:00:00"),
        "date": date_key,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def daily(date_key, open_, high, low, close, volume):
    return {
        "date": date_key,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


class SignalScoreSnapshotTest(unittest.TestCase):
    def test_complete_4h_day_wins_and_partial_day_is_wholly_replaced(self):
        rows = [
            session("2026-07-09", 9, 100, 105, 99, 103, 10),
            session("2026-07-09", 13, 103, 108, 102, 107, 20),
            session("2026-07-10", 9, 200, 205, 190, 195, 999),
            session("2026-07-14", 9, 300, 310, 295, 305, 30),
        ]
        yahoo = [
            daily("2026-01-05", 50, 55, 49, 54, 100),
            daily("2026-07-09", 90, 999, 1, 91, 9000),
            daily("2026-07-10", 110, 115, 108, 112, 40),
            daily("2026-07-14", 1, 9999, 1, 9999, 9999),
        ]

        bars, fallback_dates, diagnostics = snapshots.build_feature_daily_bars(
            rows,
            yahoo,
            "2026-07-14",
            "2026-07-14 10:15:00",
        )
        by_date = {bar["date"]: bar for bar in bars}

        self.assertEqual(by_date["2026-07-09"]["close"], 107)
        self.assertEqual(by_date["2026-07-09"]["volume"], 30)
        self.assertEqual(by_date["2026-07-10"], yahoo[2])
        self.assertNotIn("2026-01-05", by_date)
        self.assertEqual(fallback_dates, ["2026-07-10"])
        self.assertFalse(diagnostics["signal_day_from_daily"])

    def test_signal_day_never_uses_daily_and_am_cutoff_ignores_later_13h_bar(self):
        base = [session("2026-07-13", 9, 90, 95, 88, 92, 10),
                session("2026-07-13", 13, 92, 96, 91, 94, 20),
                session("2026-07-14", 9, 100, 104, 98, 102, 30)]
        later = base + [session("2026-07-14", 13, 102, 150, 80, 140, 999)]
        yahoo = [daily("2026-07-14", 1, 999, 1, 888, 9999)]

        am_bars, am_fallback, _ = snapshots.build_feature_daily_bars(
            base, yahoo, "2026-07-14", "2026-07-14 10:00:00"
        )
        pm_rebuild, pm_fallback, _ = snapshots.build_feature_daily_bars(
            later, yahoo, "2026-07-14", "2026-07-14 10:00:00"
        )

        self.assertEqual(am_bars, pm_rebuild)
        self.assertEqual(am_bars[-1]["close"], 102)
        self.assertEqual(am_fallback, [])
        self.assertEqual(pm_fallback, [])

    def test_missing_signal_day_does_not_extend_daily_past_4h_coverage(self):
        rows = [
            session("2026-07-09", 9, 100, 104, 99, 102, 10),
            session("2026-07-09", 13, 102, 105, 101, 104, 20),
            session("2026-07-10", 9, 104, 106, 102, 103, 10),
            session("2026-07-10", 13, 103, 107, 102, 106, 20),
        ]
        yahoo = [
            daily("2026-07-13", 106, 110, 105, 109, 40),
            daily("2026-07-14", 109, 999, 1, 998, 9999),
        ]

        bars, fallback_dates, diagnostics = snapshots.build_feature_daily_bars(
            rows, yahoo, "2026-07-14", "2026-07-14 10:00:00"
        )

        self.assertEqual([bar["date"] for bar in bars], ["2026-07-09", "2026-07-10"])
        self.assertEqual(fallback_dates, [])
        self.assertFalse(diagnostics["signal_day_present"])

    def test_missing_signal_day_never_scores_previous_day(self):
        alert = {
            "alert_id": "missing-signal-day",
            "symbol": "7807",
            "date": "2026-07-14",
            "received_at": "2026-07-14 10:00:00",
        }
        logic = {
            "stable": ["ema25"],
            "sniper": ["vol12"],
            "mega": {},
            "hash": "logic",
        }
        rows = [
            session("2026-07-10", 9, 100, 104, 99, 102, 10),
            session("2026-07-10", 13, 102, 105, 101, 104, 20),
        ]
        with patch.object(snapshots.opt, "get_features") as get_features:
            result = snapshots.compute_snapshot(alert, rows, [], logic)

        get_features.assert_not_called()
        self.assertEqual(result["status"], "FINAL")
        self.assertEqual(result["stable_score"], 0)
        self.assertEqual(result["modes"], [])
        self.assertIn("DEGRADED_SIGNAL_DAY_MISSING", result["input_quality"])

    def test_first_final_snapshot_row_wins(self):
        first = {
            "schema_version": "1",
            "alert_id": "A-7807",
            "symbol": "7807",
            "signal_date": "2026-07-14",
            "received_at": "2026-07-14 10:00",
            "feature_cutoff": "2026-07-14T09:00:00",
            "status": "FINAL",
            "stable_score": 5,
            "sniper_score": 6,
            "stable_filters": ["ema25"],
            "sniper_filters": ["vol12"],
            "modes": ["sniper"],
            "features": {"pre_down3": False},
            "fallback_dates": ["2026-07-10"],
            "input_quality": "PAST_GAPS_FILLED_FROM_1D",
            "logic_hash": "logic-1",
            "input_hash": "input-1",
            "finalized_at": "2026-07-14T14:00:00+09:00",
        }
        second = dict(first, stable_score=6, modes=["stable_s6", "sniper"])
        rows = [
            snapshots.SNAPSHOT_HEADERS,
            snapshots.snapshot_to_row(first),
            snapshots.snapshot_to_row(second),
        ]

        loaded = snapshots.load_snapshot_map(rows)

        self.assertEqual(loaded["A-7807"]["stable_score"], 5)
        self.assertEqual(loaded["A-7807"]["modes"], ["sniper"])
        self.assertEqual(loaded["A-7807"]["features"]["pre_down3"], False)

    def test_computed_snapshot_is_final_even_when_yahoo_is_unavailable(self):
        alert = {
            "alert_id": "A-1",
            "symbol": "7807",
            "date": "2026-07-14",
            "received_at": "2026-07-14 10:00:00",
        }
        logic = {
            "stable": ["ema25", "pre_down3"],
            "sniper": ["vol12"],
            "mega": {"mega5_rebound": ["vol20", "pre_down3"]},
            "hash": "logic",
        }
        features = {
            "ema25": True,
            "pre_down3": False,
            "vol12": True,
            "vol20": False,
            "_atr": 2.5,
        }
        with patch.object(snapshots.opt, "get_features", return_value=features):
            result = snapshots.compute_snapshot(
                alert,
                [session("2026-07-14", 9, 100, 105, 99, 102, 10)],
                [],
                logic,
                yahoo_error="timeout",
            )

        self.assertEqual(result["status"], "FINAL")
        self.assertEqual(result["stable_score"], 1)
        self.assertEqual(result["sniper_score"], 1)
        self.assertEqual(result["modes"], ["sniper"])
        self.assertIn("DEGRADED_YAHOO_UNAVAILABLE", result["input_quality"])
        self.assertEqual(json.loads(snapshots.compact_json(result["features"]))["_atr"], 2.5)

    def test_existing_alert_id_is_not_selected_again(self):
        args = snapshots.build_parser().parse_args(["--all-missing"])
        alerts = [
            {"alert_id": "old", "symbol": "7807", "date": "2026-07-14"},
            {"alert_id": "new", "symbol": "1234", "date": "2026-07-14"},
        ]

        selected = snapshots.select_alerts(alerts, args, {"old": {"status": "FINAL"}})

        self.assertEqual([item["alert_id"] for item in selected], ["new"])


if __name__ == "__main__":
    unittest.main()
