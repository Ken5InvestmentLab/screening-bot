import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from weak_early_beta.acquisition import AcquisitionArchive, RetainedResponseError
from weak_early_beta.corporate_actions import CorporateActionError, fetch_daily, normalize_daily
from weak_early_beta.new_a.source import _target_session_retry_policy, acquire_and_validate


class AcquisitionTests(unittest.TestCase):
    context = {"date": "2026-10-29", "period": "5y", "tickers": ["1234.T"], "previousSourceSha256": None}

    @staticmethod
    def response():
        return pd.DataFrame({"Open": [100., 101.], "High": [102., 103.], "Low": [99., 100.],
                             "Close": [101., 102.], "Volume": [1000, 2000], "Stock Splits": [0., 0.]},
                            index=pd.to_datetime(["2026-10-28", "2026-10-29"]))

    def missing_session(self):
        bars = self.response().astype(float)
        bars.loc["2026-10-29", ["Open", "High", "Low", "Close", "Volume"]] = float("nan")
        return bars

    def mixed_session(self):
        tickers = ["1234.T", "2345.T"]
        return pd.DataFrame({"ticker": tickers}), pd.concat(
            {"1234.T": self.missing_session(), "2345.T": self.response()}, axis=1,
        )

    def test_target_session_retries_only_missing_eligible_ticker_and_replays_identically(self):
        target = self.context["date"]
        context = {**self.context, "tickers": ["1234.T", "2345.T", "3456.T"],
                   "targetSessionRetry": {"version": 1, "session": target, "excludedSymbols": ["3456"]}}
        universe = pd.DataFrame({"ticker": context["tickers"]})
        batch = pd.concat({"1234.T": self.missing_session(), "2345.T": self.response(),
                           "3456.T": self.missing_session()}, axis=1)
        single = self.response()
        single.index = single.index.tz_localize("Asia/Tokyo").tz_convert("UTC")
        options = dict(required_session=target, session_retry_exclusions=frozenset({"3456"}))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            archive = AcquisitionArchive(directory, context)
            with patch("yfinance.download", return_value=batch), patch("yfinance.Ticker") as ticker:
                ticker.return_value.history.return_value = single
                expected = fetch_daily(universe, "5y", archive=archive, **options)
                ticker.assert_called_once_with("1234.T")
            self.assertEqual(archive.sequence, 2)
            receipt = json.loads(next(directory.glob("00002-*.json")).read_text())
            self.assertEqual(receipt["request"]["kind"], "target-session-history")
            self.assertEqual(receipt["request"]["session"], target)
            day = expected[expected["date"].eq(target)]
            self.assertEqual(day["symbol"].tolist(), ["1234", "2345"])
            self.assertEqual(day["actual_close"].tolist(), [102., 102.])

            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            replay = AcquisitionArchive(directory, context, replay=True)
            with patch("yfinance.download", side_effect=AssertionError("no batch network")) as download, \
                 patch("yfinance.Ticker", side_effect=AssertionError("no ticker network")) as ticker:
                actual = fetch_daily(universe, "5y", archive=replay, **options)
                download.assert_not_called()
                ticker.assert_not_called()
            pd.testing.assert_frame_equal(expected, actual)
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_unverified_target_retry_preserves_the_original_missing_session(self):
        universe, batch = self.mixed_session()
        for variant in ("still_missing", "revised_history", "conflicting_split", "invalid_bar", "no_trades", "duplicate_session",
                        "transient_failure"):
            with self.subTest(variant=variant):
                single = self.response()
                if variant == "still_missing":
                    single = self.missing_session()
                elif variant == "revised_history":
                    single.loc["2026-10-28", "Close"] = 100.
                elif variant == "conflicting_split":
                    single.loc["2026-10-29", "Stock Splits"] = 2.
                elif variant == "invalid_bar":
                    single.loc["2026-10-29", "Close"] = 99.
                elif variant == "no_trades":
                    single.loc["2026-10-29", "Volume"] = 0
                elif variant == "duplicate_session":
                    single = pd.concat((single, single.tail(1)))
                with patch("yfinance.download", return_value=batch), patch("yfinance.Ticker") as ticker:
                    ticker.return_value.history.return_value = single
                    if variant == "transient_failure":
                        ticker.return_value.history.side_effect = TimeoutError("provider request timed out")
                    result = fetch_daily(universe, "5y", required_session=self.context["date"])
                    ticker.assert_called_once_with("1234.T")
                incomplete = result.loc[result["symbol"] == "1234"]
                self.assertEqual(incomplete["actual_close"].tolist(), [101.])
                self.assertEqual(incomplete["date"].dt.strftime("%Y-%m-%d").tolist(), ["2026-10-28"])

    def test_optional_provider_failure_retains_original_bar_through_replay(self):
        universe, batch = self.mixed_session()
        date = self.context["date"]
        context = {**self.context, "tickers": universe["ticker"].tolist(),
                   "targetSessionRetry": {"version": 1, "session": date, "excludedSymbols": []}}
        for message in ("HTTP status 403", "SSLError: certificate verify failed"):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                archive = AcquisitionArchive(Path(temporary) / "acquisition", context)
                with patch("yfinance.download", return_value=batch), patch("yfinance.Ticker") as ticker:
                    ticker.return_value.history.side_effect = RuntimeError(message)
                    expected = fetch_daily(universe, "5y", archive=archive, required_session=date)
                    ticker.assert_called_once_with("1234.T")
                self.assertEqual(expected.loc[expected["date"].eq(date), "symbol"].tolist(), ["2345"])
                replay = AcquisitionArchive(archive.directory, context, replay=True)
                with patch("yfinance.download", side_effect=AssertionError("no batch network")), \
                     patch("yfinance.Ticker", side_effect=AssertionError("no ticker network")):
                    actual = fetch_daily(universe, "5y", archive=replay, required_session=date)
                    pd.testing.assert_frame_equal(expected, actual)
                    next(archive.directory.glob("00002-*.json")).unlink()
                    broken = AcquisitionArchive(archive.directory, context, replay=True)
                    with self.assertRaisesRegex(RetainedResponseError, "Missing retained response"):
                        fetch_daily(universe, "5y", archive=broken, required_session=date)

    def test_optional_retry_ignores_untrusted_provider_rows_and_propagates_unexpected_failures(self):
        from yfinance import shared

        universe, batch = self.mixed_session()

        def returns_price_with_certificate_error(**kwargs):
            shared._ERRORS["1234.T"] = "certificate verify failed"
            return self.response()

        with patch.object(shared, "_ERRORS", {}), patch("yfinance.download", return_value=batch), \
             patch("yfinance.Ticker") as ticker:
            ticker.return_value.history.side_effect = returns_price_with_certificate_error
            result = fetch_daily(universe, "5y", required_session=self.context["date"])
            self.assertEqual(result.loc[result["date"].eq(self.context["date"]), "symbol"].tolist(), ["2345"])
            ticker.return_value.history.side_effect = RuntimeError("unexpected response encoder problem")
            with self.assertRaisesRegex(RuntimeError, "unexpected response encoder problem"):
                fetch_daily(universe, "5y", required_session=self.context["date"])

    def test_stale_and_incomplete_target_session_batches_skip_optional_retry(self):
        tickers = [f"{i}.T" for i in range(2000, 2020)]
        universe = pd.DataFrame({"ticker": tickers})
        for first_missing, second_missing in ((10, 10), (2, 9)):
            with self.subTest(first_missing=first_missing, second_missing=second_missing):
                batches = [
                    pd.concat({ticker: self.missing_session() if i < missing else self.response()
                               for i, ticker in enumerate(tickers[offset:offset + 10])}, axis=1)
                    for offset, missing in [(0, first_missing), (10, second_missing)]
                ]
                with patch("yfinance.download", side_effect=batches), patch("yfinance.Ticker") as ticker:
                    result = fetch_daily(universe, "5y", batch=10, required_session=self.context["date"])
                    ticker.assert_not_called()
                self.assertEqual(len(result[result["date"].eq(self.context["date"])]),
                                 len(tickers) - first_missing - second_missing)

    def test_target_session_policy_keeps_old_archives_and_skips_known_restrictions(self):
        date = self.context["date"]
        restrictions = [
            {"code": "1234", "designation_date": date},
            {"code": "2345", "designation_date": "2026-10-28", "relisting_date": date},
            {"code": "3456", "designation_date": "2026-10-30"},
        ]
        tickers = ["1234.T", "2345.T", "3456.T"]
        live = SimpleNamespace(refresh_live=True)
        replay_args = SimpleNamespace(refresh_live=False)
        expected = {"version": 1, "session": date, "excludedSymbols": ["1234"]}
        self.assertEqual(_target_session_retry_policy(live, date, tickers, restrictions, None), expected)
        self.assertIsNone(_target_session_retry_policy(replay_args, date, tickers, restrictions, None))
        self.assertIsNone(_target_session_retry_policy(SimpleNamespace(refresh_live=True, new_a_isolated=True),
                                                       date, tickers, restrictions, None))
        with tempfile.TemporaryDirectory() as temporary:
            old = Path(temporary) / "old"
            new = Path(temporary) / "new"
            AcquisitionArchive(old, self.context)
            AcquisitionArchive(new, {**self.context, "targetSessionRetry": expected})
            self.assertIsNone(_target_session_retry_policy(replay_args, date, tickers, restrictions, old))
            self.assertEqual(_target_session_retry_policy(replay_args, date, tickers, restrictions, new), expected)

            baseline = AcquisitionArchive(Path(temporary) / "before-retry", self.context)
            universe = pd.DataFrame({"ticker": ["1234.T"]})
            with patch("yfinance.download", return_value=self.missing_session()), patch("yfinance.Ticker") as ticker:
                expected_old = fetch_daily(universe, "5y", archive=baseline)
                ticker.assert_not_called()
            with patch("yfinance.download", side_effect=AssertionError("no batch network")), \
                 patch("yfinance.Ticker", side_effect=AssertionError("no unarchived retry")):
                before_retry = AcquisitionArchive(baseline.directory, self.context, replay=True)
                actual_old = fetch_daily(universe, "5y", archive=before_retry)
            pd.testing.assert_frame_equal(expected_old, actual_old)

    def test_new_a_source_pins_the_live_retry_policy_and_keeps_replay_offline(self):
        date = self.context["date"]
        universe = pd.DataFrame({"code": ["1234"], "ticker": ["1234.T"], "name": ["Fixture"]})
        restrictions = [{"code": "1234", "designation_date": date}]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            args = SimpleNamespace(as_of=date, refresh_live=True, period="5y",
                                   daily_corpus=str(Path(temporary) / "daily.csv"))
            # Stop at the mocked acquisition boundary before reading or writing a corpus.
            with patch.dict("os.environ", {"CLOUD_DAILY_ACQUISITION_DIR": str(directory)}), \
                 patch("weak_early_beta.new_a.operational_admission.source_context", return_value=None), \
                 patch("weak_early_beta.model.base.jpx_universe", return_value=universe), \
                 patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", return_value=restrictions), \
                 patch("weak_early_beta.corporate_actions.fetch_daily", side_effect=RuntimeError("mock boundary")) as fetch:
                with self.assertRaisesRegex(RuntimeError, "mock boundary"):
                    acquire_and_validate(args)
                manifest = (directory / "manifest.json").read_bytes()
                replay = SimpleNamespace(**{**vars(args), "refresh_live": False, "retained_acquisition": str(directory)})
                with self.assertRaisesRegex(RuntimeError, "mock boundary"):
                    acquire_and_validate(replay)
            live_call, replay_call = fetch.call_args_list
            for call in (live_call, replay_call):
                self.assertEqual(call.kwargs["required_session"], date)
                self.assertEqual(call.kwargs["session_retry_exclusions"], frozenset({"1234"}))
            self.assertFalse(replay_call.kwargs["archive"].network_fallback_allowed)
            self.assertEqual((directory / "manifest.json").read_bytes(), manifest)
            context = json.loads(manifest)["context"]
            self.assertEqual(context["targetSessionRetry"], {"version": 1, "session": date, "excludedSymbols": ["1234"]})
            self.assertFalse(Path(args.daily_corpus).exists())

    def test_validation_failure_retains_exact_response_and_replays_without_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            archive = AcquisitionArchive(directory, self.context)
            universe = pd.DataFrame({"ticker": ["1234.T"]})
            with patch("yfinance.download", return_value=self.response()) as download, \
                 patch("weak_early_beta.corporate_actions.normalize_daily", side_effect=CorporateActionError("bad basis")):
                with self.assertRaisesRegex(CorporateActionError, "bad basis"):
                    fetch_daily(universe, "5y", archive=archive)
                self.assertEqual(download.call_count, 1)
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            replay = AcquisitionArchive(directory, self.context, replay=True)
            with patch("yfinance.download", side_effect=AssertionError("network must not run")) as download:
                result = fetch_daily(universe, "5y", archive=replay)
                download.assert_not_called()
            self.assertEqual(result["actual_close"].tolist(), [101., 102.])
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_corrupt_or_missing_packet_stops_without_network_fallback(self):
        for damage in ("missing", "changed"):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary) / "acquisition"
                archive = AcquisitionArchive(directory, self.context)
                request = {"kind": "batch", "tickers": ["1234.T"]}
                archive.request(request, self.response, {})
                packet = next(directory.glob("*.pkl"))
                if damage == "missing":
                    packet.unlink()
                else:
                    packet.write_bytes(b"untrusted pickle must never be loaded")
                operation = Mock(side_effect=AssertionError("network fallback"))
                replay = AcquisitionArchive(directory, self.context, replay=True)
                with self.assertRaisesRegex(RetainedResponseError, "SHA-256"):
                    replay.request(request, operation, {})
                operation.assert_not_called()

    def test_incomplete_batch_and_individual_fallback_are_both_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            archive = AcquisitionArchive(directory, self.context)
            universe = pd.DataFrame({"ticker": ["1234.T"]})
            incomplete = self.response().drop(columns=["Stock Splits"])
            with patch("yfinance.download", return_value=incomplete), \
                 patch("yfinance.Ticker") as ticker:
                ticker.return_value.history.return_value = self.response()
                expected = fetch_daily(universe, "5y", archive=archive)
            self.assertEqual(archive.sequence, 2)
            replay = AcquisitionArchive(directory, self.context, replay=True)
            with patch("yfinance.download", side_effect=AssertionError("no batch network")) as download, \
                 patch("yfinance.Ticker", side_effect=AssertionError("no ticker network")) as ticker:
                actual = fetch_daily(universe, "5y", archive=replay)
                download.assert_not_called(); ticker.assert_not_called()
            pd.testing.assert_frame_equal(expected, actual)

    def test_changed_date_period_universe_or_prior_cache_cannot_reuse_responses(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            AcquisitionArchive(directory, self.context)
            for change in ({"date": "2026-10-30"}, {"period": "1y"}, {"tickers": ["5678.T"]}, {"previousSourceSha256": "another"}):
                with self.subTest(change=change), self.assertRaisesRegex(RetainedResponseError, "context differs"):
                    AcquisitionArchive(directory, {**self.context, **change}, replay=True)
            with self.assertRaises(FileExistsError):
                AcquisitionArchive(directory, self.context)

    def test_replay_preserves_provider_partial_batch_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            archive = AcquisitionArchive(directory, self.context)
            errors = {}
            def operation():
                errors["1234.T"] = "ReadTimeout: provider unavailable"
                return self.response()
            request = {"kind": "batch"}
            archive.request(request, operation, errors)
            errors.clear()
            replay = AcquisitionArchive(directory, self.context, replay=True)
            pd.testing.assert_frame_equal(replay.request(request, Mock(), errors), self.response())
            self.assertEqual(errors, {"1234.T": "ReadTimeout: provider unavailable"})

    def test_replaced_yfinance_error_dictionary_preserves_batch_retry_on_replay(self):
        import yfinance as yf

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            archive = AcquisitionArchive(directory, self.context)
            universe = pd.DataFrame({"ticker": ["1234.T"]})
            calls = 0

            def download(*args, **kwargs):
                nonlocal calls
                calls += 1
                yf.shared._ERRORS = {"1234.T": "ReadTimeout: provider unavailable"} if calls == 1 else {}
                return pd.DataFrame() if calls == 1 else self.response()

            with patch.object(yf.shared, "_ERRORS", {}), patch("yfinance.download", side_effect=download), \
                 patch("weak_early_beta.corporate_actions.time.sleep"):
                expected = fetch_daily(universe, "5y", archive=archive)
            self.assertEqual(archive.sequence, 2)
            first_receipt = json.loads(next(directory.glob("00001-*.json")).read_text())
            self.assertEqual(first_receipt["providerErrors"], {"1234.T": "ReadTimeout: provider unavailable"})
            replay = AcquisitionArchive(directory, self.context, replay=True)
            with patch.object(yf.shared, "_ERRORS", {}), \
                 patch("yfinance.download", side_effect=AssertionError("no batch network")) as network, \
                 patch("weak_early_beta.corporate_actions.time.sleep", side_effect=AssertionError("no replay wait")):
                actual = fetch_daily(universe, "5y", archive=replay)
                network.assert_not_called()
            self.assertEqual(replay.sequence, 2)
            pd.testing.assert_frame_equal(expected, actual)

    def test_recorded_transport_failure_keeps_original_bounded_retry_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            archive = AcquisitionArchive(directory, self.context)
            with self.assertRaises(TimeoutError):
                archive.request({"kind": "batch"}, Mock(side_effect=TimeoutError("slow")), {})
            replay = AcquisitionArchive(directory, self.context, replay=True)
            with self.assertRaisesRegex(ConnectionError, "TimeoutError: slow"):
                replay.request({"kind": "batch"}, Mock(side_effect=AssertionError("network")), {})

    def test_replaced_error_dictionary_is_retained_when_provider_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "acquisition"
            archive = AcquisitionArchive(directory, self.context)
            errors = {}

            def operation():
                nonlocal errors
                errors = {"1234.T": "ReadTimeout: provider unavailable"}
                raise TimeoutError("provider timeout")

            with self.assertRaises(TimeoutError):
                archive.request({"kind": "batch"}, operation, lambda: errors)
            errors = {}
            replay = AcquisitionArchive(directory, self.context, replay=True)
            with self.assertRaises(ConnectionError):
                replay.request({"kind": "batch"}, Mock(side_effect=AssertionError("network")), lambda: errors)
            self.assertEqual(errors, {"1234.T": "ReadTimeout: provider unavailable"})

    def test_corrupt_basis_error_identifies_rows_and_nullable_unknowns_fail_closed(self):
        frame = self.response().rename(columns=str.lower).rename(columns={"stock splits": "split_ratio"})
        frame["date"] = frame.index
        frame["symbol"] = "1234"
        normalized = normalize_daily(frame)
        normalized["corporate_actions_version"] = pd.Series(["wrong", pd.NA], dtype="string").to_numpy()
        with self.assertRaisesRegex(CorporateActionError, r"unsupported corporate_actions_version.*invalid_rows=2.*1234"):
            normalize_daily(normalized)


if __name__ == "__main__":
    unittest.main()
