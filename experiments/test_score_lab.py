import math
import unittest

from experiments import score_lab


def make_bar(day, close, volume=100):
    return {
        "date": f"2026-01-{day:02d}",
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": volume,
    }


class ScoreLabTests(unittest.TestCase):
    def test_normalize_date_key(self):
        self.assertEqual(score_lab.normalize_date_key("2026/03/18 13:00"), "2026-03-18")
        self.assertEqual(score_lab.normalize_date_key("2026-03-18"), "2026-03-18")
        self.assertEqual(score_lab.normalize_date_key(""), "")

    def test_parse_alerts_dedupes_by_alert_id(self):
        rows = [
            ["summary"],
            ["summary"],
            [],
            ["alert_id", "signal_type", "symbol_code", "symbol_name", "signal_date", "entry_price", "perf_5bd"],
            ["a1", "BOTTOM", "TYO:1234", "A", "2026/01/10", "100", "5.0%"],
            ["a1", "BOTTOM", "TYO:1234", "A", "2026/01/10", "100", "7.0%"],
            ["a2", "TOP", "TYO:9999", "B", "2026/01/10", "100", "20.0%"],
        ]
        parsed = score_lab.parse_alerts(rows)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["symbol"], "1234")
        self.assertAlmostEqual(parsed[0]["perf"], 0.05)

    def test_compute_features_uses_only_bars_up_to_signal_date(self):
        bars = [make_bar(i, 100 + i) for i in range(1, 31)]
        with_future = [*bars, make_bar(31, 10000, 999999)]
        base = score_lab.compute_features(bars, "2026/01/30")
        future = score_lab.compute_features(with_future, "2026/01/30")
        self.assertIsNotNone(base)
        self.assertIsNotNone(future)
        self.assertEqual(base["signal_bar_date"], "2026-01-30")
        self.assertEqual(future["signal_bar_date"], "2026-01-30")
        self.assertAlmostEqual(base["ret_1d"], future["ret_1d"])
        self.assertAlmostEqual(base["vol_ratio_20"], future["vol_ratio_20"])

    def test_feature_calculation_excludes_current_volume_from_volume_ratio(self):
        bars = []
        for i in range(1, 30):
            bars.append(make_bar(i, 100 + i, volume=100))
        bars.append(make_bar(30, 130, volume=1000))
        features = score_lab.compute_features(bars, "2026/01/30")
        self.assertIsNotNone(features)
        self.assertAlmostEqual(features["vol_ratio_20"], 10.0)
        self.assertGreater(features["body_pct"], 0)
        self.assertTrue(math.isfinite(features["atr14_pct"]))

    def test_score_normalizes_to_100(self):
        row = {"a": 5, "b": 1}
        steps = [
            score_lab.SelectionStep(score_lab.Predicate("a", "x", ">=", threshold=3), 10, weight=2),
            score_lab.SelectionStep(score_lab.Predicate("b", "y", "<=", threshold=2), 10, weight=3),
        ]
        self.assertEqual(score_lab.score_row(row, steps), 100)
        self.assertEqual(score_lab.score_row({"a": 2, "b": 1}, steps), 60)


if __name__ == "__main__":
    unittest.main()
