from __future__ import annotations

import unittest

import pandas as pd

from .selection import PolicySpec, apply_selection_policy, rank_candidate_pool


def sessions(*days: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(days))


def pool(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": date,
                "symbol": symbol,
                "identity_key": symbol,
                "family": "test-family",
                "spec_hash": "spec-a",
                "score": score,
                "ret5": score / 10,
                "future_return": float(symbol) / 100,
                "target5_no": score,
            }
            for date, symbol, score in rows
        ]
    )


def ranked(rows: list[tuple[str, str, float]], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    return rank_candidate_pool(
        pool(rows),
        sessions=calendar,
        feature_columns=["ret5"],
        ranking_terms=[("score", False)],
    )


class SelectionTests(unittest.TestCase):
    def test_full_pool_is_ranked_and_every_allowed_top_n_can_select_multiple(self) -> None:
        calendar = sessions("2024-01-04", "2024-01-05", "2024-01-09")
        candidates = ranked([
            ("2024-01-04", "1111", 9),
            ("2024-01-04", "2222", 8),
            ("2024-01-04", "3333", 7),
            ("2024-01-05", "1111", 10),
            ("2024-01-05", "4444", 6),
            ("2024-01-05", "5555", 5),
            ("2024-01-09", "1111", 4),
            ("2024-01-09", "2222", 3),
            ("2024-01-09", "3333", 2),
        ], calendar)
        self.assertEqual(len(candidates), 9)
        self.assertNotIn("future_return", candidates.columns)
        self.assertNotIn("target5_no", candidates.columns)
        self.assertEqual(candidates.loc[candidates.date.eq(pd.Timestamp("2024-01-04")), "raw_rank"].tolist(), [1, 2, 3])

        top1 = apply_selection_policy(
            candidates, sessions=calendar,
            policy=PolicySpec("core", 1, "core-top1"),
        )
        top3 = apply_selection_policy(
            candidates, sessions=calendar,
            policy=PolicySpec("core", 3, "core-top3"),
        )
        self.assertEqual(top1.selected.groupby("date").size().max(), 1)
        self.assertEqual(top3.selected.groupby("date").size().max(), 3)
        self.assertEqual(set(top3.selected.loc[top3.selected.date.eq(pd.Timestamp("2024-01-04")), "symbol"]), {"1111", "2222", "3333"})
        jan5 = top1.selected.loc[top1.selected.date.eq(pd.Timestamp("2024-01-05"))].iloc[0]
        self.assertEqual(jan5.symbol, "4444")
        self.assertEqual(int(jan5.raw_rank), 2)
        self.assertEqual(int(jan5.policy_rank), 1)
        self.assertEqual(top1.daily.loc[top1.daily.date.eq(pd.Timestamp("2024-01-09")), "selected_count"].iloc[0], 1)

        top5 = apply_selection_policy(
            candidates, sessions=calendar,
            policy=PolicySpec("monster", 5, "monster-top5"),
        )
        self.assertGreater(top5.daily["selected_count"].max(), 1)
        self.assertEqual(top5.selected.iloc[0].lane, "monster")

    def test_no_candidate_session_clears_one_business_session_cooldown(self) -> None:
        calendar = sessions("2022-12-30", "2023-01-04", "2023-01-05")
        candidates = ranked([
            ("2022-12-30", "1111", 9),
            ("2023-01-05", "1111", 8),
        ], calendar)
        result = apply_selection_policy(
            candidates, sessions=calendar,
            policy=PolicySpec("core", 1, "year-edge"),
        )
        self.assertEqual(result.selected["date"].tolist(), [
            pd.Timestamp("2022-12-30"), pd.Timestamp("2023-01-05")
        ])
        self.assertEqual(result.daily.loc[result.daily.date.eq(pd.Timestamp("2023-01-04")), "abstain_reason"].iloc[0], "NO_CANDIDATES")

    def test_cooldown_state_carries_across_year_boundary(self) -> None:
        calendar = sessions("2022-12-29", "2022-12-30", "2023-01-04")
        candidates = ranked([
            ("2022-12-30", "1111", 9),
            ("2023-01-04", "1111", 8),
        ], calendar)
        result = apply_selection_policy(
            candidates, sessions=calendar,
            policy=PolicySpec("core", 1, "carry-year"),
        )
        self.assertEqual(result.selected["date"].tolist(), [pd.Timestamp("2022-12-30")])
        self.assertEqual(result.daily.iloc[-1]["cooldown_blocked_count"], 1)

    def test_lane_policies_are_independent_and_hash_ignores_future_values(self) -> None:
        calendar = sessions("2024-01-04", "2024-01-05")
        first_input = pool([
            ("2024-01-04", "1111", 9),
            ("2024-01-05", "2222", 8),
        ])
        changed = first_input.copy()
        changed["future_return"] = [5000, -5000]
        changed["target5_no"] = [-1e9, 1e9]
        first_rank = rank_candidate_pool(
            first_input, sessions=calendar, feature_columns=["ret5"],
            ranking_terms=[("score", False)],
        )
        second_rank = rank_candidate_pool(
            changed, sessions=calendar, feature_columns=["ret5"],
            ranking_terms=[("score", False)],
        )
        core = apply_selection_policy(
            first_rank, sessions=calendar, policy=PolicySpec("core", 1, "core"),
        )
        same_policy = apply_selection_policy(
            second_rank, sessions=calendar, policy=PolicySpec("core", 1, "core"),
        )
        monster = apply_selection_policy(
            second_rank, sessions=calendar, policy=PolicySpec("monster", 1, "monster"),
        )
        self.assertEqual(core.selection_sha256, same_policy.selection_sha256)
        self.assertEqual(core.selected["symbol"].tolist(), monster.selected["symbol"].tolist())
        self.assertEqual(core.selected["lane"].tolist(), ["core", "core"])
        self.assertEqual(monster.selected["lane"].tolist(), ["monster", "monster"])

    def test_calendar_rejects_holiday_candidate_and_bad_input(self) -> None:
        calendar = sessions("2024-01-04", "2024-01-05", "2024-01-09")
        with self.assertRaisesRegex(ValueError, "official session calendar"):
            ranked([("2024-01-08", "1111", 9)], calendar)
        duplicate = pool([
            ("2024-01-04", "1111", 9),
            ("2024-01-04", "1111", 8),
        ])
        with self.assertRaisesRegex(ValueError, "duplicate family/spec/symbol"):
            rank_candidate_pool(
                duplicate, sessions=calendar, feature_columns=["ret5"],
                ranking_terms=[("score", False)],
            )
        with self.assertRaisesRegex(ValueError, "one of"):
            PolicySpec("core", 4, "unsupported")

    def test_raw_rank_tie_break_is_symbol_ascending(self) -> None:
        calendar = sessions("2024-01-04")
        candidates = ranked([
            ("2024-01-04", "2222", 1),
            ("2024-01-04", "1111", 1),
        ], calendar)
        self.assertEqual(candidates["symbol"].tolist(), ["1111", "2222"])
        self.assertEqual(candidates["raw_rank"].tolist(), [1, 2])

    def test_two_symbols_cannot_duplicate_the_same_instrument_identity(self) -> None:
        calendar = sessions("2024-01-04")
        candidates = pool([
            ("2024-01-04", "1111", 2),
            ("2024-01-04", "2222", 1),
        ])
        candidates["identity_key"] = "same-issuer-security"
        with self.assertRaisesRegex(ValueError, "duplicate instrument identity"):
            rank_candidate_pool(
                candidates, sessions=calendar, feature_columns=["ret5"],
                ranking_terms=[("score", False)],
            )


if __name__ == "__main__":
    unittest.main()
