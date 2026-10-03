from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from weak_early_beta.analytics import build_analytics, build_presentation_metrics, validated_unique_detections
from weak_early_beta.config import COMBINED_STACKED_ID, COMBINED_UNIQUE_ID, SELECTOR_ORDER
from weak_early_beta.corporate_actions import normalize_daily
from weak_early_beta.metrics import build_metrics, build_monthly_metrics, required_capital, summarize
from weak_early_beta.model import attach_forward_rows
from weak_early_beta.report_preferences import select_report_view
from weak_early_beta.trade_basis import LEGACY_PRICE_BASIS_VERSION, PRICE_BASIS_VERSION, build_trade_economics


def trade(signal, symbol, entry, exit, cost, cash, selectors=1, **extra):
    rows = []
    for mode in range(selectors):
        rows.append({
            "signal_date": signal, "symbol": symbol, "selector_id": f"selector_{mode}",
            "entry_date": entry, "fifth_xtks_exit_date": exit,
            "entry_open": cost / 100, "entry_shares": 100,
            "entry_cost_yen": cost, "fifth_xtks_exit_close": (cost + cash) / 100,
            "gross_return": cash / cost, "one_hundred_shares_pl_yen": cash,
            "source_scope": "EXACT_CANONICAL_2023_2026", **extra,
        })
    return rows


class AnalyticsTests(unittest.TestCase):
    def example(self):
        return pd.DataFrame([
            *trade("2023-12-25", "9991", "2023-12-26", "2024-01-03", 10000, 1000, 3),
            *trade("2024-01-01", "9991", "2024-01-02", "2024-01-04", 20000, -4000),
            *trade("2024-01-02", "9992", "2024-01-03", "2024-01-05", 5000, 0, 2),
            *trade("2024-01-04", "9993", "2024-01-05", "2024-01-08", 10000, 5000),
            *trade("2024-01-08", "9994", "2024-01-09", "2024-01-10", 10000, -1000),
        ])

    def test_manual_signal_and_lot_statistics_are_different_allocations(self):
        result = build_analytics(self.example(), "2024-01-10")
        unique, stacked = result["strategies"]["unique"], result["strategies"]["stacked"]
        self.assertEqual(unique["resolved_signals"], 5)
        self.assertEqual(stacked["resolved_signals"], 5)
        self.assertEqual(unique["resolved_lots"], 5)
        self.assertEqual(stacked["resolved_lots"], 8)
        self.assertEqual(unique["cash_pl_yen"], 1000)
        self.assertEqual(stacked["cash_pl_yen"], 3000)
        for allocation in [unique, stacked]:
            self.assertAlmostEqual(allocation["signal_mean_pct"], 6)
            self.assertEqual(allocation["signal_median_pct"], 0)
            self.assertEqual(allocation["signal_win_pct"], 40)
        self.assertAlmostEqual(stacked["lot_mean_pct"], 6.25)
        self.assertEqual(stacked["lot_median_pct"], 5)
        self.assertEqual(stacked["lot_win_pct"], 50)
        self.assertEqual(unique["gross_win_cash_pl_yen"], 6000)
        self.assertEqual(stacked["gross_win_cash_pl_yen"], 8000)
        self.assertEqual(unique["average_win_cash_pl_yen"], 3000)
        self.assertEqual(stacked["average_win_cash_pl_yen"], 4000)
        self.assertEqual(unique["average_loss_cash_pl_yen"], -2500)
        self.assertEqual(stacked["average_loss_cash_pl_yen"], -2500)
        self.assertEqual(unique["profit_excluding_best3_signals_yen"], -5000)
        self.assertEqual(stacked["profit_excluding_best3_signals_yen"], -5000)
        self.assertEqual(unique["worst_signal_cash_pl_yen"], -4000)
        self.assertEqual(stacked["worst_return_pct"], -20)
        self.assertEqual(stacked["lot_average_win_pct"], 20)
        self.assertAlmostEqual(stacked["lot_average_loss_pct"], -15)

    def test_date_cashflows_year_crossing_and_same_day_buy_before_sell(self):
        result = build_analytics(self.example())
        unique, stacked = result["strategies"]["unique"], result["strategies"]["stacked"]
        self.assertEqual(unique["minimum_initial_cash_yen"], 35000)
        self.assertEqual(stacked["minimum_initial_cash_yen"], 60000)
        self.assertEqual(unique["peak_open_principal_yen"], 35000)
        self.assertEqual(stacked["peak_open_principal_yen"], 60000)
        self.assertEqual(unique["peak_open_principal_yen"], required_capital(self.example().drop_duplicates(["signal_date", "symbol"])))
        self.assertEqual(unique["max_concurrent_lots"], 3)
        self.assertEqual(stacked["max_concurrent_lots"], 6)
        # Two separately detected 9991 trades still count as one open symbol.
        self.assertEqual(unique["max_concurrent_symbols"], 2)
        self.assertEqual(stacked["max_concurrent_symbols"], 2)
        self.assertEqual(unique["max_drawdown_yen"], 4000)
        self.assertEqual(stacked["max_drawdown_yen"], 4000)
        self.assertEqual(result["cumulative"], [
            {"date": "2023-12-26", "unique": 0, "stacked": 0},
            {"date": "2024-01-03", "unique": 1000, "stacked": 3000},
            {"date": "2024-01-04", "unique": -3000, "stacked": -1000},
            {"date": "2024-01-05", "unique": -3000, "stacked": -1000},
            {"date": "2024-01-08", "unique": 2000, "stacked": 4000},
            {"date": "2024-01-10", "unique": 1000, "stacked": 3000},
        ])
        # Annual bars follow signal year, not the cash-flow settlement year.
        self.assertEqual(result["annual"][0], {"year": 2023, "unique": 1000, "stacked": 3000, "resolved_signals": 1, "resolved_lots": 3, "latest_completed_signal_date": "2023-12-25"})
        self.assertEqual(result["annual"][1]["unique"], 0)
        self.assertEqual(result["annual"][1]["stacked"], 0)

    def test_minimum_cash_reflects_previous_losses_or_gains(self):
        first = trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, -2000)
        later = trade("2024-01-03", "9992", "2024-01-04", "2024-01-05", 10000, 2000)
        summary = build_analytics(pd.DataFrame(first + later))["strategies"]["unique"]
        self.assertEqual(summary["peak_open_principal_yen"], 10000)
        self.assertEqual(summary["minimum_initial_cash_yen"], 12000)
        self.assertEqual(summary["max_drawdown_yen"], 2000)
        same_day = [dict(row, entry_date="2024-01-03") for row in later]
        summary = build_analytics(pd.DataFrame(first + same_day))["strategies"]["unique"]
        self.assertEqual(summary["minimum_initial_cash_yen"], 20000)
        self.assertEqual(summary["peak_open_principal_yen"], 20000)
        winning = trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 5000)
        larger = trade("2024-01-03", "9992", "2024-01-04", "2024-01-05", 12000, 0)
        summary = build_analytics(pd.DataFrame(winning + larger))["strategies"]["unique"]
        self.assertEqual(summary["peak_open_principal_yen"], 12000)
        self.assertEqual(summary["minimum_initial_cash_yen"], 10000)

    def test_same_date_realizations_do_not_invent_intraday_drawdown(self):
        rows = [
            *trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 5000),
            *trade("2024-01-01", "9992", "2024-01-02", "2024-01-03", 10000, -3000),
        ]
        for ordered in [rows, rows[::-1]]:
            summary = build_analytics(pd.DataFrame(ordered))["strategies"]["unique"]
            self.assertEqual(summary["max_drawdown_yen"], 0)

    def test_pending_reference_exclusion_and_coverage(self):
        data = pd.DataFrame([
            *trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 1000, 2),
            *trade("2024-01-04", "9992", "2024-01-05", "2024-01-10", 9000000, 900000, 2, gross_return=float("nan"), source_scope="FORWARD_CAUSAL"),
            *trade("2024-02-08", "7601", "2024-02-09", "2024-02-16", 800000, 400000, 3),
        ])
        before = data.copy(deep=True)
        result = build_analytics(data)
        self.assertEqual(result["counts"], {"display_signals": 3, "display_lots": 7, "eligible_signals": 2, "eligible_lots": 4, "reference_excluded_signals": 1, "reference_excluded_lots": 3, "completed_signals": 1, "completed_lots": 2, "pending_signals": 1, "pending_lots": 2})
        self.assertEqual(result["strategies"]["stacked"]["cash_pl_yen"], 2000)
        self.assertEqual(result["strategies"]["stacked"]["peak_open_principal_yen"], 20000)
        self.assertEqual(result["coverage"]["sources"][1], {"source_scope": "forward", "signals": 1, "resolved_signals": 0, "pending_signals": 1})
        self.assertEqual(result["coverage"]["years"], [{"year": 2024, "historical": 1, "forward": 1, "other": 0}])
        pd.testing.assert_frame_equal(data, before)
        encoded = json.dumps(result, allow_nan=False)
        for forbidden in ["9991", "9992", "7601", "selector_0", "detection_id", "symbol"]:
            self.assertNotIn('"' + forbidden + '"', encoded)

    def test_original_quantities_splits_and_mapped_d6_economics(self):
        split = build_trade_economics("2024-01-02", "2024-01-04", 100, 55, pd.DataFrame([{"effective_date": "2024-01-04", "ratio": 2}]))
        row = {**split, "signal_date": "2024-01-01", "symbol": "9991", "selector_id": "a", "source_scope": "FORWARD_CAUSAL"}
        # This selected D6 row deliberately retains stale D5 share/proceeds
        # columns, just like select_report_view. These must not be consumed.
        row["exit_shares"] = 100
        row["exit_proceeds_yen"] = 1000
        following = trade("2024-01-04", "9992", "2024-01-05", "2024-01-08", 10000, 0)
        result = build_analytics(pd.DataFrame([row, dict(row, selector_id="b"), *following]))
        self.assertEqual(result["strategies"]["unique"]["cash_pl_yen"], 1000)
        self.assertEqual(result["strategies"]["unique"]["minimum_initial_cash_yen"], 10000)
        self.assertEqual(result["strategies"]["stacked"]["minimum_initial_cash_yen"], 20000)
        self.assertEqual(result["strategies"]["unique"]["resolved_lots"], 2)
        self.assertEqual(result["strategies"]["unique"]["total_entry_shares"], 200)
        self.assertEqual(result["strategies"]["unique"]["total_entry_cost_yen"], 20000)

    def test_legacy_cost_is_pinned_entry_price_times_original_lot(self):
        rows = trade("2023-01-01", "9991", "2023-01-02", "2023-01-06", 5000, 500)
        for row in rows:
            row.pop("entry_shares")
            row.pop("entry_cost_yen")
            row["exit_shares"] = 200
        summary = build_analytics(pd.DataFrame(rows))["strategies"]["unique"]
        self.assertEqual(summary["total_entry_shares"], 100)
        self.assertEqual(summary["total_entry_cost_yen"], 5000)
        self.assertEqual(summary["cash_pl_yen"], 500)

    def test_verified_d6_view_uses_actual_entry_while_d5_remains_frozen(self):
        prices = [500, 500, 501, 502, 503, 504, 505]
        daily = normalize_daily(pd.DataFrame({
            "date": pd.bdate_range("2026-09-01", periods=7), "symbol": "9Z9Z",
            "open": prices, "high": [p + 1 for p in prices],
            "low": [p - 1 for p in prices], "close": prices,
            "volume": [20000] * 6 + [10000], "split_ratio": [0] * 6 + [2],
        }))
        selected = pd.DataFrame([{"date": pd.Timestamp("2026-09-01"), "symbol": "9Z9Z", "selector": "volr20_low", "model_period": "2026-09"}])
        source = attach_forward_rows(selected, daily)
        # Historical D5 amounts retain their vendor-adjusted convention while
        # the independent verified D6 receipt uses the actual original lot.
        source["source_scope"] = "EXACT_CANONICAL_2023_2026"
        source["price_basis"] = LEGACY_PRICE_BASIS_VERSION
        source["entry_open"] = 500
        source["entry_cost_yen"] = 50000
        source["gross_return"] = .008
        source["one_hundred_shares_pl_yen"] = 400
        before = source.copy(deep=True)
        d5 = build_analytics(select_report_view(source, None, "d5_close"))["strategies"]["unique"]
        d6 = build_analytics(select_report_view(source, None, "d6_open"))["strategies"]["unique"]
        # This fixture has no independent nominal BASE5 evidence. Its frozen
        # adjusted amounts remain in source, but cannot be shown as actual100.
        self.assertEqual(d5["resolved_signals"], 0)
        self.assertEqual(d5["cash_pl_yen"], 0)
        self.assertEqual(d5["total_entry_cost_yen"], 0)
        self.assertEqual(d6["cash_pl_yen"], 1000)
        self.assertEqual(d6["total_entry_cost_yen"], 100000)
        self.assertEqual(d6["total_entry_shares"], 100)
        self.assertAlmostEqual(d6["lot_mean_pct"], 1)
        pd.testing.assert_frame_equal(source, before)

    def test_stacked_signal_losses_and_best_three_are_grouped_before_ranking(self):
        rows = [
            *trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, -1000, 3),
            *trade("2024-01-04", "9992", "2024-01-05", "2024-01-08", 10000, -2000),
            *trade("2024-01-09", "9993", "2024-01-10", "2024-01-11", 10000, 1000, 5),
            *trade("2024-01-12", "9994", "2024-01-15", "2024-01-16", 100000, 3000),
            *trade("2024-01-17", "9995", "2024-01-18", "2024-01-19", 10000, 2000),
        ]
        result = build_analytics(pd.DataFrame(rows))["strategies"]
        self.assertEqual(result["unique"]["worst_signal_cash_pl_yen"], -2000)
        self.assertEqual(result["stacked"]["worst_signal_cash_pl_yen"], -3000)
        self.assertEqual(result["unique"]["profit_excluding_best3_signals_yen"], -3000)
        self.assertEqual(result["stacked"]["profit_excluding_best3_signals_yen"], -5000)
        self.assertEqual(result["stacked"]["average_loss_cash_pl_yen"], -2500)

    def test_overlap_and_two_distinct_ex_post_normalizations(self):
        result = build_analytics(self.example())
        strata = {row["selector_count"]: row for row in result["overlap"]}
        self.assertEqual(strata[1]["resolved_signals"], 3)
        self.assertEqual(strata[1]["cash_pl_100_yen"], 0)
        self.assertEqual(strata[2]["win_pct"], 0)
        self.assertEqual(strata[3]["cash_pl_100_yen"], 1000)
        normalized = result["normalization"]
        self.assertTrue(normalized["hypothetical_ex_post"])
        self.assertEqual(normalized["share_ratio"], 5 / 8)
        self.assertEqual(normalized["entry_cost_ratio"], 55000 / 80000)
        self.assertEqual(normalized["shares_normalized_stacked_pl_yen"], 1875)
        self.assertEqual(normalized["entry_cost_normalized_stacked_pl_yen"], 2062.5)

    def test_flat_and_empty_values_are_json_safe(self):
        result = build_analytics(pd.DataFrame(trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 0)))
        summary = result["strategies"]["stacked"]
        self.assertEqual(summary["lot_win_pct"], 0)
        self.assertEqual(summary["worst_return_pct"], 0)
        self.assertIsNone(summary["average_win_cash_pl_yen"])
        self.assertIsNone(summary["average_loss_cash_pl_yen"])
        self.assertIsNone(summary["lot_payoff_ratio"])
        empty = build_analytics(pd.DataFrame())
        self.assertEqual(empty["counts"]["completed_signals"], 0)
        self.assertEqual(empty["cumulative"], [])
        self.assertEqual(empty["annual"], [])
        self.assertIsNone(empty["strategies"]["unique"]["signal_mean_pct"])
        self.assertIsNone(empty["strategies"]["unique"]["max_drawdown_yen"])
        self.assertIsNone(empty["normalization"]["share_ratio"])
        json.dumps(empty, allow_nan=False)

    def test_unknown_prices_and_actual_quantities_are_not_invented(self):
        rows = trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 1000, entry_open=float("nan"), entry_cost_yen=float("nan"), entry_shares=float("nan"), price_basis=PRICE_BASIS_VERSION)
        summary = build_analytics(pd.DataFrame(rows))["strategies"]["unique"]
        self.assertEqual(summary["resolved_signals"], 1)
        self.assertEqual(summary["cash_pl_yen"], 1000)
        self.assertIsNone(summary["total_entry_shares"])
        self.assertIsNone(summary["minimum_initial_cash_yen"])
        self.assertIsNone(summary["peak_open_principal_yen"])
        self.assertEqual(summary["max_concurrent_lots"], 1)

    def test_conflicting_overlap_fails_and_duplicate_selector_does_not_inflate(self):
        rows = trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 1000, 2)
        self.assertEqual(build_analytics(pd.DataFrame(rows + [rows[0]]))["counts"]["completed_lots"], 2)
        rows[1]["gross_return"] = float("nan")
        for ordered in [rows, rows[::-1]]:
            with self.assertRaisesRegex(ValueError, "overlapping selectors disagree"):
                build_analytics(pd.DataFrame(ordered))

    def test_contradictory_known_economics_fail_without_recomputing_them(self):
        rows = trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 1000, price_basis=PRICE_BASIS_VERSION)
        with self.assertRaisesRegex(ValueError, "entry cost disagrees"):
            build_analytics(pd.DataFrame([dict(rows[0], entry_cost_yen=20000)]))
        with self.assertRaisesRegex(ValueError, "cash P/L disagrees"):
            build_analytics(pd.DataFrame([dict(rows[0], gross_return=.2)]))

    def test_selected_presentation_metrics_preserve_every_existing_column(self):
        frame = self.example()
        frame["selector_id"] = frame["selector_id"].map({f"selector_{i}": selector_id for i, selector_id in enumerate(SELECTOR_ORDER)})
        day = pd.Timestamp("2024-01-10")
        expected_total = build_metrics(frame, day)
        expected_monthly = build_monthly_metrics(frame, day)
        for selected in (None, [COMBINED_STACKED_ID, COMBINED_UNIQUE_ID], [SELECTOR_ORDER[0]], [SELECTOR_ORDER[-1]]):
            with self.subTest(selectors=selected):
                total, monthly = build_presentation_metrics(frame, day, selected)
                for actual, expected in ((total, expected_total), (monthly, expected_monthly)):
                    if selected is not None:
                        expected = expected.loc[expected["selector_id"].isin(selected)]
                    if actual.empty and expected.empty:
                        continue
                    order = ["selector_id", "period"]
                    pd.testing.assert_frame_equal(actual.sort_values(order).reset_index(drop=True), expected.sort_values(order).reset_index(drop=True))

    def test_presentation_metric_empty_and_invalid_lanes(self):
        total, monthly = build_presentation_metrics(pd.DataFrame())
        self.assertTrue(total.empty)
        self.assertTrue(monthly.empty)
        with self.assertRaisesRegex(ValueError, "unknown presentation metric selector"):
            build_presentation_metrics(self.example(), selector_ids=["unexpected"])

    def test_presentation_metrics_preserve_full_overlap_receipt_validation(self):
        rows = trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 1000, 2)
        rows[0]["selector_id"], rows[1]["selector_id"] = SELECTOR_ORDER[:2]
        for column, first, second in [
            ("fifth_xtks_exit_close", 110, 111),
            ("price_basis_source_sha256", "a" * 64, "b" * 64),
            ("exit_shares", 100, 200),
            ("applied_actions_json", "[]", '[{"effective_date":"2024-01-03","ratio":2}]'),
        ]:
            with self.subTest(column=column):
                conflicting = pd.DataFrame([dict(rows[0], **{column: first}), dict(rows[1], **{column: second})])
                with self.assertRaisesRegex(ValueError, "overlapping selectors disagree"):
                    build_presentation_metrics(conflicting, selector_ids=[COMBINED_UNIQUE_ID])
                with self.assertRaisesRegex(ValueError, "overlapping selectors disagree"):
                    validated_unique_detections(conflicting)

    def test_fast_unique_history_preserves_reference_rows_and_original_unknowns(self):
        frame = pd.DataFrame(trade("2024-02-08", "7601", "2024-02-09", "2024-02-16", 10000, 1000, 3))
        frame["entry_shares"] = float("nan")
        frame["entry_cost_yen"] = float("nan")
        original = frame.copy(deep=True)
        result = validated_unique_detections(frame)
        self.assertEqual(len(result), 1)
        self.assertEqual(list(result.columns), list(frame.columns))
        self.assertTrue(pd.isna(result.iloc[0].entry_shares))
        self.assertTrue(pd.isna(result.iloc[0].entry_cost_yen))
        pd.testing.assert_frame_equal(frame, original)

    def test_summary_cache_reuses_unchanged_months_and_copies_results(self):
        rows = [
            *trade("2024-01-01", "9991", "2024-01-02", "2024-01-03", 10000, 1000),
            *trade("2024-02-01", "9992", "2024-02-02", "2024-02-05", 20000, -2000),
            *trade("2024-03-01", "9993", "2024-03-04", "2024-03-05", 30000, 3000),
        ]
        frame = pd.DataFrame(rows)
        frame["selector_id"] = SELECTOR_ORDER[0]
        cache = {}
        options = {"as_of": "2024-03-06", "selector_ids": [COMBINED_UNIQUE_ID], "_summary_cache": cache}
        with patch("weak_early_beta.analytics.summarize", wraps=summarize) as called:
            first = build_presentation_metrics(frame.iloc[:2], **options)
            self.assertEqual(called.call_count, 4)  # annual, total, January, February
            first[0].loc[:, "cash_pl_100_yen"] = -987654
            again = build_presentation_metrics(frame.iloc[:2].copy(), **options)
            self.assertEqual(called.call_count, 4)
            self.assertNotIn(-987654, again[0].cash_pl_100_yen.tolist())
            growing = build_presentation_metrics(frame, **options)
            self.assertEqual(called.call_count, 7)  # only annual, total, new March
        expected = build_presentation_metrics(frame, "2024-03-06", [COMBINED_UNIQUE_ID])
        for actual, wanted in zip(growing, expected):
            pd.testing.assert_frame_equal(actual, wanted)
        self.assertTrue(all(len(key) == 64 and set(key) <= set("0123456789abcdef") for key in cache))
        # Cached annual period strings were not changed to monthly labels.
        self.assertTrue(all(value["period"] in {"2024", "2024-2024"} for value in cache.values()))

    def test_summary_cache_separates_populations_economics_index_period_and_asof(self):
        frame = self.example()
        frame["selector_id"] = frame["selector_id"].map({f"selector_{i}": selector_id for i, selector_id in enumerate(SELECTOR_ORDER)})
        cache = {}
        variants = [frame, frame.iloc[:3], frame.loc[pd.to_datetime(frame.signal_date).dt.year.eq(2024)]]
        changed = frame.copy(deep=True)
        changed.loc[0:2, "gross_return"] = .2
        changed.loc[0:2, "one_hundred_shares_pl_yen"] = 2000
        variants += [changed, frame.set_axis(range(100, 100 + len(frame))), frame.assign(entry_open=frame.entry_open.astype("float32"))]
        for source in variants:
            for day in ("2024-01-04", "2024-01-10"):
                cached = build_presentation_metrics(source, day, [COMBINED_UNIQUE_ID, COMBINED_STACKED_ID], _summary_cache=cache)
                independent = build_presentation_metrics(source, day, [COMBINED_UNIQUE_ID, COMBINED_STACKED_ID])
                for actual, wanted in zip(cached, independent):
                    pd.testing.assert_frame_equal(actual, wanted)


if __name__ == "__main__":
    unittest.main()
