from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from .evaluation import (
    apply_round_trip_costs,
    build_five_session_labels,
    daily_cohorts,
    label_summary,
    return_metrics,
    weekly_block_bootstrap,
)
from .selection import PolicySpec, apply_selection_policy, rank_candidate_pool
from .session_calendar import SessionCalendar


SESSIONS = pd.DatetimeIndex(pd.to_datetime([
    "2024-01-04", "2024-01-05", "2024-01-09", "2024-01-10",
    "2024-01-11", "2024-01-12", "2024-01-15", "2024-01-16",
    "2024-01-17", "2024-01-18", "2024-01-19", "2024-01-22",
    "2024-01-23", "2024-01-24", "2024-01-25", "2024-01-26",
    "2024-01-29", "2024-01-30", "2024-01-31",
]))
CALENDAR = SessionCalendar(SESSIONS, "synthetic", "unit-test")


def price_bars(symbol: str, *, missing: set[str] | None = None, zero_volume: set[str] | None = None) -> list[dict[str, object]]:
    missing = missing or set()
    zero_volume = zero_volume or set()
    rows = []
    for i, day in enumerate(SESSIONS):
        date = day.strftime("%Y-%m-%d")
        if date in missing:
            continue
        close = 110.0 if date == "2024-01-15" and symbol == "1111" else 100.0
        volume = 0.0 if date in zero_volume else 1000.0
        rows.append({
            "date": date, "symbol": symbol, "open": 100.0, "high": max(100.0, close),
            "low": min(100.0, close), "close": close, "volume": volume,
        })
    return rows


class EvaluationTests(unittest.TestCase):
    def test_target_uses_next_session_open_and_fifth_session_close(self) -> None:
        signals = pd.DataFrame([{
            "date": "2024-01-05", "symbol": "1111", "family": "f",
            "spec_hash": "s", "candidate_id": "f-1",
        }])
        bars = pd.DataFrame(price_bars("1111"))
        labels = build_five_session_labels(bars, signals, CALENDAR)
        row = labels.iloc[0]
        self.assertEqual(row.entry_date, pd.Timestamp("2024-01-09"))
        self.assertEqual(row.exit_date, pd.Timestamp("2024-01-15"))
        self.assertTrue(row.label_resolved)
        self.assertAlmostEqual(row.gross_return, 0.10)
        self.assertEqual(
            row.label_definition,
            "v1_next_xtks_open_to_fifth_close_with_ohlcv_actionability_guards",
        )

    def test_missing_entry_or_exit_and_zero_volume_are_retained_unresolved(self) -> None:
        signals = pd.DataFrame([
            {"date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s"},
            {"date": "2024-01-05", "symbol": "2222", "family": "f", "spec_hash": "s"},
            {"date": "2024-01-05", "symbol": "3333", "family": "f", "spec_hash": "s"},
        ])
        bars = pd.DataFrame(
            price_bars("1111", missing={"2024-01-09"})
            + price_bars("2222", zero_volume={"2024-01-09"})
            + price_bars("3333", missing={"2024-01-15"})
        )
        labels = build_five_session_labels(bars, signals, CALENDAR)
        self.assertEqual(len(labels), 3)
        status_by_symbol = dict(zip(labels.symbol, labels.label_status, strict=True))
        self.assertEqual(status_by_symbol, {
            "1111": "MISSING_ENTRY_BAR",
            "2222": "ENTRY_ZERO_OR_UNKNOWN_VOLUME",
            "3333": "MISSING_EXIT_BAR",
        })
        summary = label_summary(labels)
        self.assertEqual(summary["selected_count"], 3)
        self.assertEqual(summary["resolved_count"], 0)
        self.assertEqual(summary["unresolved_count"], 3)

    def test_invalid_ohlc_and_split_sized_gap_remain_unresolved(self) -> None:
        signals = pd.DataFrame([
            {"date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s"},
            {"date": "2024-01-05", "symbol": "2222", "family": "f", "spec_hash": "s"},
        ])
        first = price_bars("1111")
        first_entry = next(row for row in first if row["date"] == "2024-01-09")
        first_entry["high"] = 90.0
        second = price_bars("2222")
        split_session = next(row for row in second if row["date"] == "2024-01-10")
        split_session.update({"open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0})
        labels = build_five_session_labels(pd.DataFrame(first + second), signals, CALENDAR)
        self.assertEqual(set(labels.label_status), {
            "INVALID_ENTRY_OHLC_RANGE", "POTENTIAL_SPLIT_OR_EXTREME_GAP",
        })
        self.assertFalse(labels.label_resolved.any())

    def test_policy_selection_is_not_replaced_after_missing_label(self) -> None:
        pool = pd.DataFrame([
            {"date": "2024-01-05", "symbol": "1111", "identity_key": "1111", "family": "f", "spec_hash": "s", "score": 10.0},
            {"date": "2024-01-05", "symbol": "2222", "identity_key": "2222", "family": "f", "spec_hash": "s", "score": 9.0},
        ])
        ranked = rank_candidate_pool(
            pool, sessions=SESSIONS, feature_columns=[],
            ranking_terms=[("score", False)],
        )
        chosen = apply_selection_policy(
            ranked, sessions=SESSIONS, policy=PolicySpec("core", 1, "missing-label"),
        ).selected
        bars = pd.DataFrame(
            price_bars("1111", missing={"2024-01-09"}) + price_bars("2222")
        )
        labels = build_five_session_labels(bars, chosen, CALENDAR)
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels.iloc[0].symbol, "1111")
        self.assertEqual(labels.iloc[0].label_status, "MISSING_ENTRY_BAR")

    def test_partial_daily_cohort_is_not_reweighted(self) -> None:
        selections = pd.DataFrame([
            {"date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s",
             "gross_return": 9.9, "label_resolved": True, "label_status": "STALE_SELECTION_COPY"},
            {"date": "2024-01-05", "symbol": "2222", "family": "f", "spec_hash": "s",
             "gross_return": 9.9, "label_resolved": True, "label_status": "STALE_SELECTION_COPY"},
        ])
        signals = selections.copy()
        bars = pd.DataFrame(price_bars("1111") + price_bars("2222", missing={"2024-01-09"}))
        labels = build_five_session_labels(bars, signals, CALENDAR)
        cohorts = daily_cohorts(
            selections, labels, sessions=SESSIONS,
            join_columns=["date", "symbol", "family", "spec_hash"],
        )
        cohort = cohorts.loc[cohorts.date.eq(pd.Timestamp("2024-01-05"))].iloc[0]
        self.assertEqual(cohort.cohort_status, "PARTIAL_UNRESOLVED")
        self.assertEqual(cohort.unresolved_count, 1)
        self.assertTrue(pd.isna(cohort.cohort_return))
        self.assertEqual(cohorts.loc[cohorts.date.eq(pd.Timestamp("2024-01-04")), "cohort_status"].iloc[0], "ABSTAIN")

    def test_costs_draws_and_bootstrap_are_explicit_and_reproducible(self) -> None:
        values = return_metrics(pd.Series([0.0, -0.10, 0.10]))
        self.assertEqual(values["draw_count"], 1)
        self.assertEqual(values["win_rate"], 0.5)
        self.assertEqual(values["plus10_rate"], 1 / 3)

        signal = pd.DataFrame([{
            "date": "2024-01-05", "symbol": "1111", "family": "f", "spec_hash": "s",
        }])
        labels = build_five_session_labels(pd.DataFrame(price_bars("1111")), signal, CALENDAR)
        after_cost = apply_round_trip_costs(labels, costs=(0.005,))
        self.assertAlmostEqual(after_cost.iloc[0]["net_return_cost_0.005"], 0.095)

        daily = pd.DataFrame({
            "date": SESSIONS,
            "selected_count": 1,
            "cohort_status": "COMPLETE",
            "cohort_return": np.linspace(-0.02, 0.03, len(SESSIONS)),
        })
        first = weekly_block_bootstrap(daily, repetitions=300, seed=17)
        second = weekly_block_bootstrap(daily, repetitions=300, seed=17)
        self.assertEqual(first, second)
        self.assertGreater(first["weeks"], 1)

    def test_signal_near_calendar_end_remains_as_unresolved(self) -> None:
        signals = pd.DataFrame([{
            "date": "2024-01-31", "symbol": "1111", "family": "f", "spec_hash": "s",
        }])
        labels = build_five_session_labels(pd.DataFrame(price_bars("1111")), signals, CALENDAR)
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels.iloc[0].label_status, "CALENDAR_HORIZON_NOT_AVAILABLE")


if __name__ == "__main__":
    unittest.main()
