from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tvfree_screener.batch02.causal_intraday_features import extract_causal_features

JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class Bar:
    session_date: date
    symbol: str
    bin_name: str
    source_tag: str
    feature_cutoff_jst: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class CausalIntradayFeatureTests(unittest.TestCase):
    def make_bars(self, sessions: int = 25) -> list[Bar]:
        start = date(2026, 1, 5)
        bars: list[Bar] = []
        for index in range(sessions):
            day = start + timedelta(days=index)
            for bin_name, hour in (("AM_09_13", 13), ("PM_13_CLOSE", 16)):
                bars.append(Bar(
                    session_date=day,
                    symbol="1111",
                    bin_name=bin_name,
                    source_tag="RAW_CAUSAL_INTRADAY",
                    feature_cutoff_jst=datetime.combine(day, datetime.min.time(), tzinfo=JST).replace(hour=hour),
                    open=100.0,
                    high=105.0,
                    low=98.0,
                    close=102.0,
                    volume=1000.0 + index,
                ))
        return bars

    def test_same_bin_rolling_features_use_only_prior_twenty(self):
        rows = extract_causal_features(self.make_bars())
        am = [row for row in rows if row["bin_name"] == "AM_09_13"]
        self.assertIsNone(am[19]["range_vs_prior20"])
        self.assertIsNotNone(am[20]["range_vs_prior20"])
        self.assertIsNotNone(am[20]["volume_rel20"])
        self.assertEqual(am[20]["prior_same_bin_count"], 20)

    def test_previous_four_shape_features_do_not_need_absolute_price_history(self):
        rows = extract_causal_features(self.make_bars(4))
        self.assertIsNone(rows[3]["prev4_body_mean"])
        self.assertIsNotNone(rows[4]["prev4_body_mean"])

    def test_pm_close_location_is_computed_but_not_model_eligible(self):
        rows = extract_causal_features(self.make_bars(1))
        am = next(row for row in rows if row["bin_name"] == "AM_09_13")
        pm = next(row for row in rows if row["bin_name"] == "PM_13_CLOSE")
        self.assertTrue(am["close_location_model_eligible"])
        self.assertFalse(pm["close_location_model_eligible"])
        self.assertIsInstance(pm["close_location"], float)

    def test_volume_relative_feature_is_explicitly_experimental(self):
        rows = extract_causal_features(self.make_bars())
        self.assertTrue(all(
            row["volume_rel20_status"] == "EXPERIMENTAL_SOURCE_INTERNAL"
            for row in rows
        ))


if __name__ == "__main__":
    unittest.main()
