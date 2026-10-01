"""Cloud acceptance checks for source units, selection and fixed trade economics."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from weak_early_beta import model
from weak_early_beta.cli import _write_daily_cache
from weak_early_beta.corporate_actions import CorporateActionError, normalize_daily
from weak_early_beta.ledger import merge_detections
from weak_early_beta.metrics import required_capital
from weak_early_beta.trade_basis import ECONOMIC_COLUMNS, PRICE_BASIS_VERSION


class SplitAwareModelTests(unittest.TestCase):
    @staticmethod
    def daily(*, later_split=False):
        dates = pd.bdate_range("2026-09-01", periods=9 if later_split else 7)
        # First split is during the five-session trade. A second split, when
        # included, happens only after the trade has already closed.
        actual_prices = [100, 100, 100, 50, 51, 55, 56, 28, 29][:len(dates)]
        factors = ([4, 4, 4, 2, 2, 2, 2, 1, 1] if later_split
                   else [2, 2, 2, 1, 1, 1, 1])
        ratios = [0, 0, 0, 2, 0, 0, 0, 2, 0][:len(dates)]
        prices = [price / factor for price, factor in zip(actual_prices, factors)]
        return normalize_daily(pd.DataFrame({
            "date": dates, "symbol": "9999", "open": prices,
            "high": [price * 1.01 for price in prices],
            "low": [price * .99 for price in prices], "close": prices,
            "volume": [10_000 * factor for factor in factors],
            "split_ratio": ratios,
        }))

    @staticmethod
    def selected(raw):
        return pd.DataFrame([{
            "date": raw.iloc[0]["date"], "symbol": "9999",
            "selector": "volr20_low", "model_period": "2026-09",
        }])

    @staticmethod
    def before_split(raw, count):
        # A contemporaneous pre-event download has no knowledge of a later
        # split and quotes the original session units.
        frame = raw.iloc[:count][["date", "symbol", "split_ratio"]].copy()
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = raw.iloc[:count][f"actual_{column}"].to_numpy()
        return normalize_daily(frame)

    def test_forward_trade_spanning_split_uses_original_lot(self):
        raw = self.daily()
        trade = model.attach_forward_rows(self.selected(raw), raw, source_sha256="test-source").iloc[0]
        self.assertEqual(trade["price_basis"], PRICE_BASIS_VERSION)
        self.assertEqual(trade["signal_close"], 100)
        self.assertEqual(trade["signal_volume"], 10_000)
        self.assertEqual(trade["entry_open"], 100)
        self.assertEqual(trade["exit_shares"], 200)
        self.assertEqual(trade["one_hundred_shares_pl_yen"], 1_000)
        self.assertAlmostEqual(trade["gross_return"], .1)
        self.assertEqual(trade["price_basis_source_sha256"], "test-source")
        self.assertEqual(required_capital(pd.DataFrame([trade])), 10_000)

    def test_later_split_cannot_rewrite_completed_trade_or_merge_receipts(self):
        before = self.daily()
        original = model.attach_forward_rows(self.selected(before), before, source_sha256="original")
        after = self.daily(later_split=True)
        refreshed = model.refresh_forward_endpoints(original, after, source_sha256="later")
        incoming = model.attach_forward_rows(self.selected(after), after, source_sha256="later")
        merged = merge_detections(original, incoming)
        for frame in (refreshed, merged):
            pd.testing.assert_series_equal(
                frame.iloc[0][ECONOMIC_COLUMNS], original.iloc[0][ECONOMIC_COLUMNS],
                check_names=False,
            )
            self.assertEqual(frame.iloc[0]["signal_close"], 100)

    def test_pending_entry_fills_once_and_migrates_verified_legacy_forward(self):
        raw = self.daily()
        pending = model.attach_forward_rows(self.selected(raw), self.before_split(raw, 1))
        pending.loc[:, "price_basis"] = ""
        filled = model.refresh_forward_endpoints(pending, raw, source_sha256="verified")
        self.assertEqual(filled.iloc[0]["status"], "mature")
        self.assertEqual(filled.iloc[0]["price_basis"], PRICE_BASIS_VERSION)
        self.assertEqual(filled.iloc[0]["one_hundred_shares_pl_yen"], 1_000)
        twice = model.refresh_forward_endpoints(filled, raw, source_sha256="same")
        pd.testing.assert_frame_equal(filled, twice)

    def test_entered_cost_revision_requires_review(self):
        raw = self.daily()
        entered = model.attach_forward_rows(self.selected(raw), self.before_split(raw, 3))
        # Revise all price columns together so the source units are internally
        # consistent, but they conflict with the recorded purchase cost.
        changed = raw[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]].copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[1, column] *= 1.1
        changed = normalize_daily(changed)
        with self.assertRaisesRegex(ValueError, "entry price revision"):
            model.refresh_forward_endpoints(entered, changed)

    def test_missing_whole_market_session_does_not_shift_fifth_exit(self):
        raw = self.daily()
        missing = raw[raw.date.ne(pd.Timestamp("2026-09-03"))].copy()
        trade = model.attach_forward_rows(self.selected(raw), missing).iloc[0]
        self.assertEqual(trade["entry_date"], pd.Timestamp("2026-09-02"))
        self.assertEqual(trade["fifth_xtks_exit_date"], pd.Timestamp("2026-09-08"))
        self.assertEqual(trade["one_hundred_shares_pl_yen"], 1_000)

    def test_entered_session_revision_requires_review(self):
        raw = self.daily()
        entered = model.attach_forward_rows(self.selected(raw), self.before_split(raw, 3))
        entered.loc[:, "entry_date"] = pd.Timestamp("2026-09-03")
        with self.assertRaisesRegex(ValueError, "entry session revision"):
            model.refresh_forward_endpoints(entered, raw)

    def test_bad_exit_price_is_quarantined_without_moving_the_exit(self):
        raw = self.daily()[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]].copy()
        raw.loc[5, "close"] = 999
        normalized = normalize_daily(raw)
        trade = model.attach_forward_rows(self.selected(raw), normalized).iloc[0]
        self.assertEqual(trade["status"], "entered")
        self.assertEqual(trade["fifth_xtks_exit_date"], pd.Timestamp("2026-09-08"))
        self.assertTrue(pd.isna(trade["fifth_xtks_exit_close"]))
        self.assertTrue(pd.isna(trade["gross_return"]))

    def test_feature_input_masks_bad_values_but_preserves_sessions_and_actions(self):
        raw = self.daily()[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]].copy()
        raw.loc[3, "close"] = 999
        with patch.object(model.base, "build_features", wraps=model.base.build_features) as build:
            model.build_live_features(raw)
        source = build.call_args.args[0]
        self.assertEqual(len(source), len(raw))
        self.assertEqual(source.loc[3, "date"], raw.loc[3, "date"])
        self.assertEqual(source.loc[3, "split_ratio"], 2)
        self.assertTrue(source.loc[3, ["open", "high", "low", "close", "volume"]].isna().all())

    def test_canonical_history_does_not_migrate_or_recalculate(self):
        raw = self.daily()
        ledger = model.attach_forward_rows(self.selected(raw), raw)
        ledger.loc[:, "source_scope"] = "EXACT_CANONICAL_2023_2026"
        expected = ledger.copy()
        pd.testing.assert_frame_equal(model.refresh_forward_endpoints(ledger, raw), expected)

    def test_future_split_does_not_admit_historically_expensive_stock(self):
        features = pd.DataFrame({name: [0.0, 0.0] for name in model.base.FEATURES})
        features["symbol"] = "9999"
        features["date"] = pd.bdate_range("2026-09-01", periods=2)
        features["close"] = 650  # The latest vendor's split-adjusted history.
        features["actual_close"] = 1300  # Actual price at each historical session.
        features["volume"] = 40_000
        features["actual_volume"] = 20_000
        self.assertTrue(model.eligible_live_rows(features).empty)
        self.assertEqual(len(model.eligible_live_rows(features, price_cap=0)), 1)

    def test_future_split_does_not_inflate_historical_liquidity_gate(self):
        features = pd.DataFrame({name: [0.0, 0.0] for name in model.base.FEATURES})
        features["symbol"] = "9999"
        features["date"] = pd.bdate_range("2026-09-01", periods=2)
        features["actual_close"] = 100
        features["actual_volume"] = 6_000
        features["volume"] = 12_000  # Would have passed the old prior-volume gate.
        self.assertTrue(model.eligible_live_rows(features).empty)

    def test_legacy_corpus_requires_action_aware_refresh(self):
        raw = self.daily()[["date", "symbol", "open", "high", "low", "close", "volume"]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            raw.to_csv(path, index=False)
            with self.assertRaisesRegex(CorporateActionError, "refresh-live"):
                model.read_daily(path)

    def test_failed_cache_write_keeps_previous_price_and_action_evidence(self):
        def interrupted_write(frame, path, **kwargs):
            Path(path).write_text("partial", encoding="utf-8")
            raise OSError("interrupted cache write")

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "daily.csv"
            target.write_text("previous verified evidence", encoding="utf-8")
            with patch.object(pd.DataFrame, "to_csv", interrupted_write):
                with self.assertRaisesRegex(OSError, "interrupted cache write"):
                    _write_daily_cache(self.daily(), target)
            self.assertEqual(target.read_text(encoding="utf-8"), "previous verified evidence")
            self.assertEqual(list(Path(directory).iterdir()), [target])
            _write_daily_cache(self.daily(), target)
            self.assertEqual(len(model.read_daily(target)), 7)


if __name__ == "__main__":
    unittest.main()
