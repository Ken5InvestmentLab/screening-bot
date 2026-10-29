import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from weak_early_beta.acquisition import AcquisitionArchive, RetainedResponseError
from weak_early_beta.corporate_actions import CorporateActionError, fetch_daily, normalize_daily


class AcquisitionTests(unittest.TestCase):
    context = {"date": "2026-10-29", "period": "5y", "tickers": ["1234.T"], "previousSourceSha256": None}

    @staticmethod
    def response():
        return pd.DataFrame({"Open": [100., 101.], "High": [102., 103.], "Low": [99., 100.],
                             "Close": [101., 102.], "Volume": [1000, 2000], "Stock Splits": [0., 0.]},
                            index=pd.to_datetime(["2026-10-28", "2026-10-29"]))

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
