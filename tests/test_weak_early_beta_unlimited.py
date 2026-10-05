"""Unlimited forward candidates must retain the frozen training universe."""

import unittest
from datetime import timedelta
from unittest.mock import patch

import pandas as pd

from weak_early_beta import model, notify
from weak_early_beta.config import SELECTOR_ORDER
from weak_early_beta.corporate_actions import normalize_daily


class UnlimitedForwardCandidateTests(unittest.TestCase):
    @staticmethod
    def features(prices, dates=None):
        dates = dates if dates is not None else pd.bdate_range("2026-08-31", periods=2)
        records = []
        for symbol, values in prices.items():
            for date, price in zip(dates, values):
                records.append({
                    **{name: 0.0 for name in model.base.FEATURES},
                    "symbol": symbol,
                    "date": date,
                    "actual_close": float(price),
                    "actual_volume": 20_000,
                    "source_usable": True,
                    "target5_no": 0.01,
                    "target_end_date": pd.Timestamp(date.date() + timedelta(days=7)),
                })
        return pd.DataFrame(records)

    def test_prediction_expands_without_changing_training_rows_or_labels(self):
        features = self.features({
            "9991": [100, 100],
            "9992": [1000, 1500],  # Training cap uses the prior quote, inclusive.
            "9993": [1001, 900],  # Falling below the cap today does not qualify.
            "9994": [1_000_000, 1_000_000],
        })
        features.loc[features.symbol.eq("9992"), "target5_no"] = 0.02
        features.loc[features.symbol.eq("9993"), "target5_no"] = 0.03
        features.loc[features.symbol.eq("9994"), "target5_no"] = 0.90

        # This is the old capped preparation, including its daily rank labels.
        legacy = model.eligible_live_rows(features, price_cap=1000.0)
        legacy = legacy.dropna(subset=["target5_no", "target_end_date"]).copy()
        legacy["future_rank"] = legacy.groupby("date")["target5_no"].rank(
            pct=True, method="average"
        )
        legacy["y_top025"] = (legacy["future_rank"] >= 0.9975).astype(int)
        self.assertEqual(set(legacy.symbol), {"9991", "9992"})
        self.assertEqual(legacy.set_index("symbol").loc["9992", "future_rank"], 1.0)

        with patch.object(model, "build_live_features", return_value=features):
            prediction, training = model.prepare_live(pd.DataFrame())

        self.assertEqual(set(prediction.symbol), {"9991", "9992", "9993", "9994"})
        pd.testing.assert_frame_equal(training, legacy)
        # Expensive stocks with an unknown future still remain prediction rows.
        features.loc[features.symbol.eq("9994"), ["target5_no", "target_end_date"]] = (
            float("nan"), pd.NaT
        )
        with patch.object(model, "build_live_features", return_value=features):
            prediction, training = model.prepare_live(pd.DataFrame())
        self.assertIn("9994", set(prediction.symbol))
        pd.testing.assert_frame_equal(training, legacy)

    def test_unlimited_candidates_keep_liquidity_quality_and_lower_price_gates(self):
        features = self.features({
            symbol: [50_000, 50_000] for symbol in (
                "9990", "9991", "9992", "9993", "9994", "9995", "9996", "9997", "9998"
            )
        })
        first, last = features.date.min(), features.date.max()

        def change(symbol, date, column, value):
            features.loc[features.symbol.eq(symbol) & features.date.eq(date), column] = value

        change("9991", first, "actual_volume", 9999)
        change("9992", last, "actual_volume", 4999)
        change("9993", last, "actual_close", 19.99)
        change("9994", last, "source_usable", False)
        change("9995", first, "source_usable", False)
        change("9996", last, model.base.FEATURES[0], float("nan"))
        change("9997", last, "actual_close", float("nan"))
        change("9998", first, "actual_volume", 10_000)
        change("9998", last, "actual_volume", 5_000)
        change("9998", last, "actual_close", 20)

        with patch.object(model, "build_live_features", return_value=features):
            prediction, _ = model.prepare_live(pd.DataFrame())
        self.assertEqual(set(prediction.symbol), {"9990", "9998"})
        self.assertTrue(prediction.date.eq(last).all())

    def test_expensive_selected_stock_reaches_ledger_and_discord_dry_run(self):
        dates = pd.bdate_range("2026-08-31", periods=3)
        features = self.features({"9991": [200] * 3, "9992": [20_000] * 3}, dates)
        features["volr20"] = features.symbol.map({"9991": 2.0, "9992": 0.2})
        features["body_pct"] = features.symbol.map({"9991": 2.0, "9992": 0.2})
        raw = normalize_daily(pd.DataFrame([
            {
                "date": record["date"], "symbol": record["symbol"],
                "open": record["actual_close"], "close": record["actual_close"],
                "high": record["actual_close"] * 1.01,
                "low": record["actual_close"] * 0.99,
                "volume": record["actual_volume"], "split_ratio": 0,
            }
            for record in features.to_dict(orient="records")
        ]))

        def monthly_tail(prediction, training, month):
            self.assertEqual(set(training.symbol), {"9991"})
            self.assertEqual(set(prediction.symbol), {"9991", "9992"})
            tail = prediction[prediction.date.dt.to_period("M").eq(month)].copy()
            return tail.assign(tail_p=0.9, tail_cdf=0.9995, model_period=str(month))

        for method in ("latest", "range"):
            with self.subTest(method=method), \
                 patch.object(model, "build_live_features", return_value=features), \
                 patch.object(model, "causal_tail_for_month", side_effect=monthly_tail):
                if method == "latest":
                    _, selected = model.score_latest(raw, as_of="2026-09-02")
                    expected_dates = {pd.Timestamp("2026-09-02")}
                else:
                    _, selected = model.score_range(raw, "2026-09-01", "2026-09-02")
                    expected_dates = {pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-02")}

                self.assertEqual(set(selected.symbol), {"9992"})
                self.assertEqual(set(selected.selector), set(SELECTOR_ORDER))
                self.assertEqual(set(selected.date), expected_dates)
                ledger = model.attach_forward_rows(
                    selected, raw, company_names={"9992": "High-price example"},
                    source_sha256="synthetic-unlimited-source",
                )
                self.assertTrue(ledger.signal_close.eq(20_000).all())
                self.assertTrue(ledger.source_scope.eq("FORWARD_CAUSAL").all())

                with patch.object(notify, "_post_webhook") as post, \
                     patch.object(notify, "_existing_message") as existing:
                    unchanged, payloads = notify.notify_pending(ledger, dry_run=True)
                post.assert_not_called()
                existing.assert_not_called()
                pd.testing.assert_frame_equal(unchanged, ledger)
                self.assertEqual(len(payloads), len(expected_dates))
                for payload in payloads:
                    embed = payload["embeds"][0]
                    self.assertEqual(embed["title"], "9992 High-price example")
                    fields = {field["name"]: field["value"] for field in embed["fields"]}
                    self.assertEqual(fields["検出時点の終値"], "20,000円")
                    self.assertEqual(fields["該当モード数"], "5モード")


if __name__ == "__main__":
    unittest.main()
