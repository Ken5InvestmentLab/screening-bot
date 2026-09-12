from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from .core_moderate_ridge import (
    FAMILY_SPEC,
    FAMILY_SPEC_SHA256,
    FEATURES,
    cap_training_target,
    fit_ridge,
    predict_ridge,
    signal_quality_mask,
)
from .core_moderate_ridge_audit import (
    _read_bars, build_labels_for_eligible_signals, iter_symbol_feature_batches,
    required_label_signals, score_by_quarter,
)
from .artifact_store import sha256_file
from .feature_panel import build_feature_panel
from .session_calendar import SessionCalendar


class CoreModerateRidgeTests(unittest.TestCase):
    def test_registered_spec_keeps_full_pool_and_multiple_names(self) -> None:
        self.assertTrue(FAMILY_SPEC_SHA256)
        self.assertEqual(FAMILY_SPEC["selection_study"]["top_n"], [1, 2, 3, 5])
        self.assertTrue(FAMILY_SPEC["selection_study"]["multiple_names_per_day"])
        self.assertIn("ret40", FEATURES)
        self.assertIn("volr20_prevavg", FEATURES)
        self.assertNotIn("volr20_inclusive", FEATURES)
        self.assertEqual(FAMILY_SPEC["training"]["alpha"], 10.0)

    def test_target_caps_positive_tail_and_preserves_negative_values(self) -> None:
        result = cap_training_target([-0.7, -0.1, 0.1, 0.5])
        np.testing.assert_allclose(result, [-0.7, -0.1, 0.1, 0.3])

    def test_ridge_is_deterministic_and_train_scaling_is_stored(self) -> None:
        rng = np.random.default_rng(901)
        x = rng.normal(size=(700, len(FEATURES)))
        y = -0.01 + 0.03 * x[:, 0] - 0.02 * x[:, 3] + rng.normal(0, 0.01, 700)
        y[-1] = 0.8
        first = fit_ridge(x, y)
        second = fit_ridge(x, y)
        self.assertEqual(first["n_train"], 700)
        self.assertTrue(np.all(first["upper"] >= first["lower"]))
        np.testing.assert_allclose(first["coefficient"], second["coefficient"])
        prediction = predict_ridge(first, x[:10])
        np.testing.assert_allclose(prediction, predict_ridge(second, x[:10]))
        self.assertLess(float(first["target_mean"]), 0.3)

    def test_feature_quality_requires_registered_finite_features_and_clean_bar(self) -> None:
        row = {name: 0.1 for name in FEATURES}
        row.update(open=100.0, high=102.0, low=99.0, close=101.0, volume=1000.0)
        frame = pd.DataFrame([row, {**row, "close": 103.0}, {**row, "ret5": np.nan}])
        self.assertEqual(signal_quality_mask(frame).tolist(), [True, False, False])

    def test_ridge_fails_closed_on_small_or_nonfinite_fit(self) -> None:
        x = np.ones((499, len(FEATURES)))
        y = np.zeros(499)
        with self.assertRaisesRegex(ValueError, "at least 500"):
            fit_ridge(x, y)
        x = np.ones((500, len(FEATURES)))
        with self.assertRaisesRegex(ValueError, "zero-variance"):
            fit_ridge(x, np.zeros(500))

    def test_vectorized_labels_match_next_open_to_fifth_close_definition(self) -> None:
        days = pd.date_range("2024-01-04", periods=7, freq="D")
        calendar = SessionCalendar(days, "fixture", "synthetic-test")
        prices = pd.DataFrame({
            "date": days,
            "symbol": "1111",
            "open": [100, 101, 102, 103, 104, 105, 106],
            "high": [102, 103, 104, 105, 106, 107, 108],
            "low": [99, 100, 101, 102, 103, 104, 105],
            "close": [101, 102, 103, 104, 105, 106, 107],
            "volume": 1000,
        })
        signals = pd.DataFrame({"date": [days[0]], "symbol": ["1111"], "close": [101.0]})
        result = build_labels_for_eligible_signals(prices, signals, calendar).iloc[0]
        self.assertEqual(result.label_status, "RESOLVED")
        self.assertEqual(result.entry_date, days[1])
        self.assertEqual(result.exit_date, days[5])
        self.assertAlmostEqual(result.gross_return, 106 / 101 - 1)

    def test_vectorized_labels_keep_missing_future_bar_unresolved(self) -> None:
        days = pd.date_range("2024-01-04", periods=7, freq="D")
        calendar = SessionCalendar(days, "fixture", "synthetic-test")
        prices = pd.DataFrame({
            "date": days.delete(2),
            "symbol": "1111",
            "open": [100, 101, 103, 104, 105, 106],
            "high": [102, 103, 105, 106, 107, 108],
            "low": [99, 100, 102, 103, 104, 105],
            "close": [101, 102, 104, 105, 106, 107],
            "volume": 1000,
        })
        signals = pd.DataFrame({"date": [days[0]], "symbol": ["1111"], "close": [101.0]})
        result = build_labels_for_eligible_signals(prices, signals, calendar).iloc[0]
        self.assertFalse(bool(result.label_resolved))
        self.assertEqual(result.label_status, "MISSING_HOLDING_SESSION_BAR")
        self.assertTrue(pd.isna(result.gross_return))

    def test_streamed_label_groups_preserve_missing_symbol_alignment(self) -> None:
        days = pd.date_range("2024-01-04", periods=7, freq="D")
        calendar = SessionCalendar(days, "fixture", "synthetic-test")
        prices = pd.concat([
            pd.DataFrame({
                "date": days, "symbol": symbol,
                "open": np.arange(100, 107, dtype=float),
                "high": np.arange(102, 109, dtype=float),
                "low": np.arange(99, 106, dtype=float),
                "close": np.arange(101, 108, dtype=float),
                "volume": 1000,
            })
            for symbol in ("1111", "3333")
        ], ignore_index=True)
        signals = pd.DataFrame({
            "date": [days[0], days[0], days[0]],
            "symbol": ["1111", "2222", "3333"],
            "close": [101.0, 101.0, 101.0],
        })
        labels = build_labels_for_eligible_signals(prices, signals, calendar)
        status = dict(zip(labels.symbol.astype(str), labels.label_status, strict=True))
        self.assertEqual(status["1111"], "RESOLVED")
        self.assertEqual(status["2222"], "MISSING_ENTRY_BAR")
        self.assertEqual(status["3333"], "RESOLVED")

    def test_required_labels_are_only_sampled_training_plus_full_score_pool(self) -> None:
        prepared = pd.DataFrame({
            "date": pd.to_datetime([
                "2022-01-04", "2022-01-05", "2022-07-01", "2022-07-04", "2022-07-05",
            ]),
            "symbol": ["1111", "1111", "1111", "1111", "1111"],
            "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "session_index": [0, 1, 5, 6, 7],
        })
        result = required_label_signals(
            prepared,
            score_start=pd.Timestamp("2022-07-01"),
            score_end=pd.Timestamp("2022-07-05"),
        )
        self.assertEqual(
            result["date"].dt.strftime("%Y-%m-%d").tolist(),
            ["2022-01-04", "2022-07-01", "2022-07-04", "2022-07-05"],
        )
        self.assertEqual(list(result.columns), ["date", "symbol", "close"])

    def test_quarter_fit_accepts_only_strictly_matured_training_labels(self) -> None:
        days = pd.DatetimeIndex(["2022-06-30", "2022-07-01", "2022-07-04"])
        calendar = SessionCalendar(days, "fixture", "synthetic-test")
        rng = np.random.default_rng(20260913)
        train = pd.DataFrame(rng.normal(size=(600, len(FEATURES))), columns=FEATURES)
        train["date"] = days[0]
        train["symbol"] = [f"T{i:04d}" for i in range(600)]
        train["session_index"] = 0
        live = pd.DataFrame(rng.normal(size=(1, len(FEATURES))), columns=FEATURES)
        live["date"] = days[1]
        live["symbol"] = "LIVE"
        live["session_index"] = 1
        panel = pd.concat([train, live], ignore_index=True)
        labels = pd.DataFrame({
            "date": days[0],
            "symbol": train["symbol"],
            "gross_return": np.linspace(-0.2, 0.2, 600),
            "label_resolved": True,
            "label_available_at": days[0],
        })
        scored, receipts, _models = score_by_quarter(
            panel, labels, calendar,
            score_start=days[1], score_end=days[2],
        )
        self.assertEqual(len(scored), 1)
        self.assertEqual(receipts[0]["latest_label_available_at"], days[0].date().isoformat())

    def test_quarter_fit_rejects_label_that_matures_on_the_prediction_date(self) -> None:
        days = pd.DatetimeIndex(["2022-06-30", "2022-07-01", "2022-07-04"])
        calendar = SessionCalendar(days, "fixture", "synthetic-test")
        rng = np.random.default_rng(88)
        train = pd.DataFrame(rng.normal(size=(600, len(FEATURES))), columns=FEATURES)
        train["date"] = days[0]
        train["symbol"] = [f"T{i:04d}" for i in range(600)]
        train["session_index"] = 0
        live = pd.DataFrame(rng.normal(size=(1, len(FEATURES))), columns=FEATURES)
        live["date"] = days[1]
        live["symbol"] = "LIVE"
        live["session_index"] = 1
        panel = pd.concat([train, live], ignore_index=True)
        labels = pd.DataFrame({
            "date": days[0],
            "symbol": train["symbol"],
            "gross_return": np.linspace(-0.2, 0.2, 600),
            "label_resolved": True,
            "label_available_at": days[1],
        })
        with self.assertRaisesRegex(ValueError, "fewer than 500 mature"):
            score_by_quarter(
                panel, labels, calendar,
                score_start=days[1], score_end=days[2],
            )

    def test_streamed_features_match_full_reference_and_keep_all_symbols(self) -> None:
        days = pd.date_range("2022-01-04", periods=75, freq="D")
        calendar = SessionCalendar(days, "fixture", "synthetic-test")
        records = []
        for symbol_index, symbol in enumerate(("1111", "2222", "3333")):
            symbol_days = days.delete(42) if symbol == "1111" else days
            for index, day in enumerate(symbol_days):
                close = 100.0 + symbol_index * 20 + index * (0.1 + symbol_index * 0.01)
                open_ = close - 0.2
                records.append({
                    "date": day, "symbol": symbol,
                    "open": open_, "high": close + 0.8, "low": open_ - 0.8,
                    "close": close, "volume": 1000.0 + index * 5,
                })
        bars = pd.DataFrame.from_records(records)
        streamed_batches = list(iter_symbol_feature_batches(bars, calendar.sessions, symbols_per_batch=2))
        streamed = pd.concat(streamed_batches, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
        reference = build_feature_panel(bars, sessions=calendar.sessions)
        reference["symbol"] = reference["symbol"].astype("string")
        reference = reference.loc[:, streamed.columns]
        reference = reference.sort_values(["date", "symbol"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(
            streamed, reference, check_dtype=False, check_exact=False,
            rtol=1e-6, atol=1e-7,
        )
        self.assertEqual(len(streamed), len(bars))
        self.assertEqual(streamed["symbol"].nunique(), 3)
        self.assertEqual(len(streamed_batches), 2)

    def test_cutoff_reader_does_not_parse_later_numeric_ohlcv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "daily.csv"
            source.write_text(
                "date,open,high,low,close,volume,symbol\n"
                "2023-12-28,100,102,99,101,1000,1111\n"
                "2025-01-06,not-a-price,not-a-price,not-a-price,not-a-price,not-a-volume,1111\n",
                encoding="utf-8",
            )
            with patch("tvfree_screener.batch01.core_moderate_ridge_audit.SOURCE_PATH", source), patch(
                "tvfree_screener.batch01.core_moderate_ridge_audit._expected_source_hash",
                lambda: sha256_file(source),
            ):
                bars = _read_bars(pd.Timestamp("2023-12-31"))
            self.assertEqual(len(bars), 1)
            self.assertEqual(bars.iloc[0]["date"], pd.Timestamp("2023-12-28"))
            self.assertEqual(bars.iloc[0]["close"], 101.0)


if __name__ == "__main__":
    unittest.main()
