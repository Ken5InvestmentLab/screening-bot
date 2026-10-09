"""Cloud acceptance checks for source units, selection and fixed trade economics."""

import json
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from weak_early_beta import model
from weak_early_beta.cli import _write_daily_cache, command_daily
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

    def test_cached_and_refreshed_daily_use_same_serialized_verified_input(self):
        class InputReached(Exception):
            pass

        for refresh_live, refresh_universe in ((False, False), (False, True), (True, False)):
            with self.subTest(refresh_live=refresh_live, refresh_universe=refresh_universe), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "daily.csv"
                _write_daily_cache(self.daily(), path)
                expected = model.read_daily(path)
                expected_hash = model.sha256(path)
                original_read = model.read_daily
                universe = pd.DataFrame({"code": ["9999"], "name": ["Example"]})

                def capture_input(ledger, raw, source_sha256=""):
                    pd.testing.assert_frame_equal(raw, expected)
                    self.assertEqual(source_sha256, expected_hash)
                    raise InputReached

                args = Namespace(
                    ledger=str(Path(temporary) / "ledger.csv"), daily_corpus=str(path),
                    refresh_live=refresh_live, refresh_universe=refresh_universe, period="5y",
                )
                with patch("weak_early_beta.cli._load_or_bootstrap", return_value=pd.DataFrame()), \
                     patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", return_value=[]), \
                     patch.object(model, "read_daily", wraps=original_read) as reads, \
                     patch.object(model.base, "jpx_universe", return_value=universe), \
                     patch("weak_early_beta.corporate_actions.fetch_daily", return_value=self.daily()), \
                     patch.object(model, "refresh_forward_endpoints", side_effect=capture_input), \
                     redirect_stderr(StringIO()) as progress:
                    with self.assertRaises(InputReached):
                        command_daily(args)
                    self.assertEqual(reads.call_count, 1)
                    records = [json.loads(line) for line in progress.getvalue().splitlines()
                               if line.startswith('{"identity": "CLOUD_DAILY_PHASE_V1"')]
                    live = [(r["stage"], r["event"]) for r in records
                            if r["stage"] in {"live-acquisition", "source-cache-write"}]
                    self.assertEqual(live, [
                        ("live-acquisition", "started"), ("live-acquisition", "finished"),
                        ("source-cache-write", "started"), ("source-cache-write", "finished"),
                    ] if refresh_live else [])

    def test_live_phase_failure_preserves_cache_and_does_not_retry(self):
        for failed_stage in ("live-acquisition", "source-cache-write"):
            with self.subTest(failed_stage=failed_stage), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "daily.csv"
                _write_daily_cache(self.daily(), path)
                original = path.read_bytes()
                args = Namespace(ledger=str(Path(temporary) / "ledger.csv"),
                                 daily_corpus=str(path), refresh_live=True, period="5y")
                failure = CorporateActionError("blocked source") if failed_stage == "live-acquisition" else OSError("disk full")
                with patch("weak_early_beta.cli._load_or_bootstrap", return_value=pd.DataFrame()), \
                     patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", return_value=[]), \
                     patch.object(model.base, "jpx_universe", return_value=pd.DataFrame({"code": ["9999"], "name": ["Example"]})), \
                     patch("weak_early_beta.corporate_actions.fetch_daily", return_value=self.daily(),
                           side_effect=failure if failed_stage == "live-acquisition" else None) as fetch, \
                     patch("weak_early_beta.cli._write_daily_cache", side_effect=failure if failed_stage == "source-cache-write" else None) as write, \
                     patch.object(model, "read_daily") as read, \
                     redirect_stderr(StringIO()) as progress:
                    with self.assertRaises(type(failure)) as raised:
                        command_daily(args)
                    self.assertIs(raised.exception, failure)
                    self.assertEqual(fetch.call_count, 1)
                    self.assertEqual(write.call_count, int(failed_stage == "source-cache-write"))
                    read.assert_not_called()
                self.assertEqual(path.read_bytes(), original)
                self.assertFalse(path.with_suffix(".source-quality.json").exists())
                records = [json.loads(line) for line in progress.getvalue().splitlines()
                           if line.startswith('{"identity": "CLOUD_DAILY_PHASE_V1"')]
                self.assertEqual(records[-1]["stage"], failed_stage)
                self.assertEqual(records[-1]["event"], "failed")

    def test_delisting_lookup_failure_stops_before_vendor_or_cache_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "daily.csv"
            _write_daily_cache(self.daily(), path)
            before = path.read_bytes()
            args = Namespace(refresh_live=True, as_of="2026-10-09",
                             ledger=str(Path(temporary) / "ledger.csv"), daily_corpus=str(path))
            with patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", side_effect=RuntimeError("JPX unavailable")), \
                 patch("weak_early_beta.corporate_actions.fetch_daily") as vendor, \
                 patch("weak_early_beta.cli._write_daily_cache") as write, \
                 patch.object(model, "refresh_forward_endpoints") as endpoints, redirect_stderr(StringIO()):
                with self.assertRaisesRegex(RuntimeError, "JPX unavailable"):
                    command_daily(args)
                vendor.assert_not_called()
                write.assert_not_called()
                endpoints.assert_not_called()
            self.assertEqual(path.read_bytes(), before)

    def test_delisted_ticker_is_not_fetched_and_verified_history_is_retained(self):
        class InputReached(Exception):
            pass
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "daily.csv"
            old = self.daily().copy()
            old["symbol"] = "7183"
            _write_daily_cache(old, path)
            prior = model.read_daily(path)
            path.with_suffix(".source-quality.json").write_text(json.dumps({
                "identity": "CLOUD_SOURCE_QUALITY_V1", "daily_sha256": model.sha256(path),
            }), encoding="utf-8")
            universe = pd.DataFrame({"code": ["7183", "9999"], "name": ["Delisted", "Active"]})
            restrictions = [{"code": "7183", "designation_date": "2026-09-10", "delisting_date": "2026-10-09",
                             "delisting_source_url": "https://www.jpx.co.jp/listing/stocks/delisted/index.html"}]
            def capture(ledger, raw, source_sha256=""):
                pd.testing.assert_frame_equal(raw.loc[raw.symbol.eq("7183")].reset_index(drop=True), prior)
                self.assertIn("9999", set(raw.symbol))
                raise InputReached
            args = Namespace(refresh_live=True, as_of="2026-10-09", period="5y",
                             ledger=str(Path(temporary) / "ledger.csv"), daily_corpus=str(path))
            with patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", return_value=restrictions), \
                 patch("weak_early_beta.cli._load_or_bootstrap", return_value=pd.DataFrame()), \
                 patch.object(model.base, "jpx_universe", return_value=universe), \
                 patch("weak_early_beta.corporate_actions.fetch_daily", return_value=self.daily()) as vendor, \
                 patch.object(model, "refresh_forward_endpoints", side_effect=capture), redirect_stderr(StringIO()):
                with self.assertRaises(InputReached):
                    command_daily(args)
                self.assertEqual(vendor.call_args.args[0]["code"].tolist(), ["9999"])
            quality = json.loads(path.with_suffix(".source-quality.json").read_text(encoding="utf-8"))
            self.assertEqual(quality["acquisition_exclusions"]["excluded_universe_symbols"], ["7183"])

    def test_delisted_history_with_wrong_quality_hash_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "daily.csv"
            old = self.daily().copy()
            old["symbol"] = "7183"
            _write_daily_cache(old, path)
            before = path.read_bytes()
            path.with_suffix(".source-quality.json").write_text(json.dumps({
                "identity": "CLOUD_SOURCE_QUALITY_V1", "daily_sha256": "0" * 64,
            }), encoding="utf-8")
            args = Namespace(refresh_live=True, as_of="2026-10-09", period="5y",
                             ledger=str(Path(temporary) / "ledger.csv"), daily_corpus=str(path))
            with patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", return_value=[{
                     "code": "7183", "designation_date": "2026-10-09", "delisting_date": "2026-10-09",
                     "delisting_source_url": "https://www.jpx.co.jp/listing/stocks/delisted/index.html"}]), \
                 patch("weak_early_beta.cli._load_or_bootstrap", return_value=pd.DataFrame()), \
                 patch.object(model.base, "jpx_universe", return_value=pd.DataFrame({"code": ["7183", "9999"]})), \
                 patch("weak_early_beta.corporate_actions.fetch_daily") as vendor, redirect_stderr(StringIO()):
                with self.assertRaisesRegex(RuntimeError, "matching source-quality receipt"):
                    command_daily(args)
                vendor.assert_not_called()
            self.assertEqual(path.read_bytes(), before)

    def test_cached_predictions_drop_delisted_rows_without_changing_training(self):
        eligible = pd.DataFrame({"symbol": ["7183", "7183", "9999"],
                                 "date": pd.to_datetime(["2026-10-08", "2026-10-09", "2026-10-09"])})
        labeled = eligible.assign(future_rank=[.1, .7, 1], y_top025=[0, 0, 1])
        expected_training = labeled.copy(deep=True)
        delistings = [{"code": "7183", "delisting_date": "2026-10-09"}]
        def tail_for_month(prediction, training, month):
            pd.testing.assert_frame_equal(training, expected_training)
            self.assertEqual(prediction.loc[prediction.symbol.eq("7183"), "date"].tolist(), [pd.Timestamp("2026-10-08")])
            return prediction.copy()
        for mode in ("latest", "range"):
            with self.subTest(mode=mode), patch.object(model, "prepare_live", return_value=(eligible.copy(), labeled.copy())), \
                 patch.object(model, "causal_tail_for_month", side_effect=tail_for_month), \
                 patch.object(model.shadow, "select_candidates", side_effect=lambda frame: frame.copy()):
                if mode == "latest":
                    tail, selected = model.score_latest(pd.DataFrame(), "2026-10-09", delistings=delistings)
                    self.assertEqual(selected.symbol.tolist(), ["9999"])
                else:
                    tail, selected = model.score_range(pd.DataFrame(), "2026-10-08", "2026-10-09", delistings=delistings)
                    self.assertEqual(selected.symbol.tolist(), ["7183", "9999"])
        pd.testing.assert_frame_equal(labeled, expected_training)

    def test_all_delisted_predictions_and_empty_months_are_zero_candidates(self):
        eligible = pd.DataFrame({"symbol": ["7183"], "date": [pd.Timestamp("2026-10-09")]})
        restrictions = [{"code": "7183", "delisting_date": "2026-10-09"}]
        for mode in ("latest", "range"):
            for blocked in (False, True):
                with self.subTest(mode=mode, blocked=blocked), \
                     patch.object(model, "prepare_live", return_value=(eligible.copy(), pd.DataFrame())), \
                     patch.object(model, "causal_tail_for_month", return_value=pd.DataFrame()) as monthly:
                    if mode == "latest":
                        tail, selected = model.score_latest(pd.DataFrame(), "2026-10-09", delistings=restrictions if blocked else [])
                    else:
                        tail, selected = model.score_range(pd.DataFrame(), "2026-10-09", "2026-10-09", delistings=restrictions if blocked else [])
                    self.assertTrue(tail.empty)
                    self.assertTrue(selected.empty)
                    if blocked:
                        monthly.assert_not_called()

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

    def test_quarantined_quotes_do_not_vote_against_market_breadth(self):
        dates = pd.bdate_range("2026-08-03", periods=35)
        raw = pd.concat([
            pd.DataFrame({"date": dates, "symbol": symbol, "open": range(100, 135),
                          "high": range(102, 137), "low": range(99, 134),
                          "close": range(101, 136), "volume": 20_000, "split_ratio": 0})
            for symbol in ("9997", "9998", "9999")
        ], ignore_index=True)
        # Every quote for one symbol is invalid; the two valid rising series
        # must retain a 100% breadth rather than become artificially 66.7%.
        raw.loc[raw.symbol.eq("9999"), "close"] = 999
        result = model.build_live_features(raw)
        valid = result[result.symbol.ne("9999") & result.date.eq(dates[-1])]
        self.assertTrue(valid.breadth_ret1_pos.eq(1).all())
        self.assertTrue(valid.breadth_ma20.eq(1).all())
        first = result[result.date.eq(dates[0])]
        self.assertTrue(first.breadth_ret1_pos.isna().all())

    def test_replayed_missing_entry_cannot_erase_original_purchase(self):
        raw = self.daily()
        original = model.attach_forward_rows(self.selected(raw), self.before_split(raw, 3))
        missing = self.before_split(raw, 3)
        missing = missing[missing.date.ne(pd.Timestamp("2026-09-02"))].copy()
        incoming = model.attach_forward_rows(self.selected(raw), missing)
        self.assertEqual(incoming.iloc[0]["status"], "pending_entry")
        merged = merge_detections(original, incoming)
        for column in ECONOMIC_COLUMNS:
            left, right = merged.iloc[0][column], original.iloc[0][column]
            if pd.isna(right):
                self.assertTrue(pd.isna(left), column)
            else:
                self.assertEqual(left, right, column)
        completed = model.refresh_forward_endpoints(merged, raw)
        self.assertEqual(completed.iloc[0]["status"], "mature")
        self.assertEqual(completed.iloc[0]["entry_cost_yen"], 10_000)

    def test_merge_rejects_conflicting_purchase_but_accepts_completion(self):
        raw = self.daily()
        original = model.attach_forward_rows(self.selected(raw), self.before_split(raw, 3))
        completed = model.attach_forward_rows(self.selected(raw), raw)
        self.assertEqual(merge_detections(original, completed).iloc[0]["status"], "mature")
        revised = completed.copy()
        revised.loc[:, "entry_open"] = 101
        with self.assertRaisesRegex(ValueError, "entry price revision"):
            merge_detections(original, revised)
        revised = completed.copy()
        revised.loc[:, "entry_shares"] = 200
        with self.assertRaisesRegex(ValueError, "entry shares revision"):
            merge_detections(original, revised)

    def test_future_split_does_not_admit_expensive_stock_to_training(self):
        features = pd.DataFrame({name: [0.0, 0.0] for name in model.base.FEATURES})
        features["symbol"] = "9999"
        features["date"] = pd.bdate_range("2026-09-01", periods=2)
        features["close"] = 650  # The latest vendor's split-adjusted history.
        features["actual_close"] = 1300  # Actual price at each historical session.
        features["volume"] = 40_000
        features["actual_volume"] = 20_000
        self.assertTrue(model.eligible_live_rows(features, price_cap=model.TRAINING_PRICE_CAP).empty)
        self.assertEqual(len(model.eligible_live_rows(features)), 1)

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
