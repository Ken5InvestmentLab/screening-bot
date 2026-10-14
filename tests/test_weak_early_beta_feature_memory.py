"""Exact frozen-feature equivalence and bounded market attachment regressions."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from weak_early_beta import model

class FeatureMemoryTests(unittest.TestCase):
    @staticmethod
    def legacy_eligible(features, price_cap=0):
        prior_close = features.groupby("symbol")["actual_close"].shift(1)
        prior_volume = features.groupby("symbol")["actual_volume"].shift(1)
        mask = ((prior_volume >= 10000) & (features.actual_volume >= 5000)
                & (features.actual_close >= 20))
        usable = features.source_usable
        mask &= usable & usable.groupby(features.symbol).shift(1).eq(True)
        if price_cap:
            mask &= prior_close <= price_cap
        return features.loc[mask].dropna(subset=model.base.FEATURES).copy()

    @classmethod
    def legacy_prepare(cls, raw):
        features = model.build_live_features(raw)
        eligible = cls.legacy_eligible(features)
        training = cls.legacy_eligible(features, model.TRAINING_PRICE_CAP)
        for frame in (eligible, training):
            frame["date"] = pd.to_datetime(frame["date"])
            frame["target_end_date"] = pd.to_datetime(frame["target_end_date"], errors="coerce")
        labeled = training.dropna(subset=["target5_no", "target_end_date"]).copy()
        labeled["future_rank"] = labeled.groupby("date")["target5_no"].rank(pct=True, method="average")
        labeled["y_top025"] = (labeled.future_rank >= .9975).astype(int)
        return eligible, labeled

    @staticmethod
    def source():
        dates = pd.bdate_range("2026-01-05", periods=90)
        rows = []
        for j, symbol in enumerate(("9997", "9998", "9999")):
            close = 100 + j * 15 + np.sin(np.arange(90) / 5) * 8 + np.arange(90) * .2
            rows.append(pd.DataFrame({"date": dates, "symbol": symbol, "open": close * .995,
                "high": close * 1.02, "low": close * .98, "close": close,
                "volume": 20000. + np.arange(90) * 113, "split_ratio": 0.,
                "audit_text": "retained", "audit_number": np.arange(90, dtype=float)}))
        raw = pd.concat(rows, ignore_index=True)
        raw.loc[10, "audit_number"] = np.inf
        raw.loc[110, "audit_number"] = -np.inf
        raw.loc[40, "volume"] = 0
        return raw.sample(frac=1, random_state=7)

    def test_optimized_builder_matches_legacy_exactly_and_leaves_input(self):
        source = self.source()
        before = source.copy(deep=True)
        expected = model.base.build_features(source)
        actual = model.base.build_features(source, memory_efficient=True)
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        pd.testing.assert_frame_equal(source, before, check_exact=True)

    def test_optimized_builder_does_not_merge_or_replace_wide_frame(self):
        source = self.source()
        with patch.object(pd.DataFrame, "merge", side_effect=AssertionError("full feature merge")), \
             patch.object(pd.DataFrame, "replace", side_effect=AssertionError("full feature replace")):
            actual = model.base.build_features(source, memory_efficient=True)
        self.assertEqual(len(actual), len(source))
        self.assertTrue(set(model.base.FEATURES).issubset(actual.columns))

    def test_cloud_quarantine_and_training_match_legacy(self):
        raw = self.source().drop(columns=["audit_number"])
        raw.loc[raw.index[11], "close"] = 999
        build = model.base.build_features
        def legacy(source, **kwargs):
            return build(source)
        with patch.object(model.base, "build_features", side_effect=legacy):
            expected_features = model.build_live_features(raw)
            expected_eligible, expected_labeled = self.legacy_prepare(raw)
        actual_features = model.build_live_features(raw)
        actual_eligible, actual_labeled = model.prepare_live(raw)
        pd.testing.assert_frame_equal(actual_features, expected_features, check_exact=True)
        pd.testing.assert_frame_equal(actual_eligible, expected_eligible, check_exact=True)
        pd.testing.assert_frame_equal(actual_labeled, expected_labeled, check_exact=True)

    def test_existing_market_column_preserves_merge_suffixes(self):
        source = self.source()
        source["med_ret1"] = 123.0
        pd.testing.assert_frame_equal(model.base.build_features(source, memory_efficient=True),
                                      model.base.build_features(source), check_exact=True)

    def test_cloud_prepare_avoids_wide_deep_copies_after_source_validation(self):
        normalized = model.normalize_daily(self.source().drop(columns="audit_number"))
        original_copy = pd.DataFrame.copy
        def guarded_copy(frame, deep=True):
            if deep and len(frame.columns) > 7 and len(frame) > 50:
                raise AssertionError("wide DataFrame deep copy")
            return original_copy(frame, deep=deep)
        with patch.object(model, "normalize_daily", return_value=normalized), \
             patch.object(pd.DataFrame, "copy", guarded_copy), \
             patch.object(pd.DataFrame, "merge", side_effect=AssertionError("wide merge")):
            eligible, labeled = model.prepare_live(normalized)
        self.assertGreater(len(eligible), 0)
        self.assertGreater(len(labeled), 0)

if __name__ == "__main__":
    unittest.main()
