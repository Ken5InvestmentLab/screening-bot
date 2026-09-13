from __future__ import annotations

import math
import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tvfree_screener.batch02.causal_intraday_features import (
    MODEL_CANDIDATE_FEATURES_V1,
    extract_causal_features,
)

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
    session_regime: str = "POST"


class CausalIntradayFeatureTests(unittest.TestCase):
    def make_bars(self, sessions: int = 25, regime: str = "POST") -> list[Bar]:
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
                    feature_cutoff_jst=datetime.combine(
                        day, datetime.min.time(), tzinfo=JST
                    ).replace(hour=hour),
                    open=100.0,
                    high=105.0,
                    low=98.0,
                    close=102.0,
                    volume=1000.0 + index,
                    session_regime="AM_STABLE" if bin_name == "AM_09_13" else regime,
                ))
        return bars

    def test_same_bin_rolling_features_use_only_prior_twenty(self):
        rows = extract_causal_features(self.make_bars())
        am = [row for row in rows if row["bin_name"] == "AM_09_13"]
        self.assertIsNone(am[19]["range_vs_prior20"])
        self.assertIsNone(am[19]["log_range_vs_prior20"])
        self.assertIsNotNone(am[20]["range_vs_prior20"])
        self.assertAlmostEqual(
            am[20]["log_range_vs_prior20"],
            math.log1p(am[20]["range_vs_prior20"]),
        )
        self.assertIsNotNone(am[20]["volume_rel20"])
        self.assertEqual(am[20]["prior_same_bin_count"], 20)

    def test_pm_same_bin_history_resets_when_close_regime_changes(self):
        pre = self.make_bars(21, regime="PM_PRE_20241105")
        post = self.make_bars(1, regime="PM_POST_20241105")
        # Move the post bars after the pre bars in time.
        shifted = []
        for bar in post:
            shifted.append(Bar(
                **{**bar.__dict__,
                   "session_date": date(2026, 2, 20),
                   "feature_cutoff_jst": bar.feature_cutoff_jst.replace(month=2, day=20)}
            ))
        rows = extract_causal_features(pre + shifted)
        post_pm = next(
            row for row in rows
            if row["bin_name"] == "PM_13_CLOSE"
            and row["session_regime"] == "PM_POST_20241105"
        )
        self.assertEqual(post_pm["prior_same_bin_count"], 0)
        self.assertIsNone(post_pm["range_vs_prior20"])

    def test_previous_four_shape_features_do_not_need_absolute_price_history(self):
        rows = extract_causal_features(self.make_bars(4))
        self.assertIsNone(rows[3]["prev4_log_return_mean"])
        self.assertIsNotNone(rows[4]["prev4_log_return_mean"])

    def test_bar_log_return_is_scale_invariant(self):
        base = self.make_bars(1)[0]
        scaled = Bar(
            **{**base.__dict__,
               "symbol": "2222",
               "open": base.open * 10,
               "high": base.high * 10,
               "low": base.low * 10,
               "close": base.close * 10}
        )
        rows = extract_causal_features([base, scaled])
        self.assertAlmostEqual(rows[0]["bar_log_return"], rows[1]["bar_log_return"])
        self.assertAlmostEqual(rows[0]["range_pct"], rows[1]["range_pct"])

    def test_pm_close_location_is_computed_but_not_model_eligible(self):
        rows = extract_causal_features(self.make_bars(1))
        am = next(row for row in rows if row["bin_name"] == "AM_09_13")
        pm = next(row for row in rows if row["bin_name"] == "PM_13_CLOSE")
        self.assertTrue(am["close_location_model_eligible"])
        self.assertFalse(pm["close_location_model_eligible"])

    def test_volume_relative_feature_is_explicitly_experimental_and_not_v1(self):
        rows = extract_causal_features(self.make_bars())
        self.assertNotIn("volume_rel20", MODEL_CANDIDATE_FEATURES_V1)
        self.assertTrue(all(
            row["volume_rel20_status"] == "EXPERIMENTAL_SOURCE_INTERNAL"
            for row in rows
        ))


if __name__ == "__main__":
    unittest.main()
