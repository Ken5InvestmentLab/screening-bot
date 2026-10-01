import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from weak_early_beta.ledger import LEDGER_COLUMNS, merge_detections, read_ledger, write_ledger
from weak_early_beta.metrics import combined_detections, required_capital
from weak_early_beta.trade_basis import (
    ECONOMIC_COLUMNS,
    LEGACY_PRICE_BASIS_VERSION,
    PRICE_BASIS_VERSION,
    UnsupportedFractionalShares,
    build_trade_economics,
    is_frozen_trade,
    preserve_completed_economics,
)


class TradeBasisTests(unittest.TestCase):
    def actions(self, *pairs):
        return pd.DataFrame([
            {"symbol": "9999", "effective_date": date, "ratio": ratio}
            for date, ratio in pairs
        ], columns=["symbol", "effective_date", "ratio"])

    def trade(self, actions=None, **overrides):
        kwargs = {
            "entry_date": "2026-09-24", "exit_date": "2026-09-30",
            "actual_entry_open": 100, "actual_exit_close": 110,
            "actions": actions, "symbol": "9999", "basis_date": "2026-09-30",
            "source_sha256": "pinned-source",
        }
        kwargs.update(overrides)
        return build_trade_economics(**kwargs)

    def row(self, economics):
        return {
            **dict.fromkeys(LEDGER_COLUMNS, ""), **economics,
            "detection_id": "2026-09-23|9999|volr20_low",
            "signal_date": pd.Timestamp("2026-09-23"), "symbol": "9999",
            "selector_id": "volr20_low", "source_scope": "FORWARD_CAUSAL",
            "signal_close": 99, "signal_volume": 10000,
            "signal_discord_url": "https://example.test/original-receipt",
        }

    def test_split_keeps_original_purchase_cost_and_changes_exit_quantity(self):
        trade = self.trade(self.actions(("2026-09-28", 2)), actual_exit_close=55)
        self.assertEqual(trade["entry_open"], 100)
        self.assertEqual(trade["exit_shares"], 200)
        self.assertEqual(trade["entry_cost_yen"], 10000)
        self.assertEqual(trade["exit_proceeds_yen"], 11000)
        self.assertEqual(trade["one_hundred_shares_pl_yen"], 1000)
        self.assertAlmostEqual(trade["gross_return"], .1)

    def test_consolidation_changes_quantity_without_a_phantom_gain(self):
        trade = self.trade(self.actions(("2026-09-28", .1)), actual_exit_close=1100)
        self.assertEqual(trade["exit_shares"], 10)
        self.assertAlmostEqual(trade["holding_action_factor"], .1)
        self.assertEqual(trade["one_hundred_shares_pl_yen"], 1000)
        self.assertAlmostEqual(trade["gross_return"], .1)

    def test_action_on_entry_session_does_not_multiply_already_new_basis_lot(self):
        trade = self.trade(
            self.actions(("2026-09-24", 2)),
            actual_entry_open=50, actual_exit_close=55,
        )
        self.assertEqual(trade["exit_shares"], 100)
        self.assertEqual(trade["holding_action_factor"], 1)
        self.assertEqual(trade["one_hundred_shares_pl_yen"], 500)
        self.assertAlmostEqual(trade["gross_return"], .1)

    def test_action_on_exit_session_is_included_but_later_actions_are_not(self):
        trade = self.trade(
            self.actions(("2026-09-30", 2), ("2026-10-01", 10)), actual_exit_close=55,
        )
        self.assertEqual(trade["exit_shares"], 200)
        self.assertEqual(json.loads(trade["applied_actions_json"]), [
            {"effective_date": "2026-09-30", "ratio": 2.0},
        ])

    def test_multiple_actions_and_other_symbol_are_handled_in_date_order(self):
        actions = self.actions(("2026-09-29", .5), ("2026-09-28", 2))
        other = pd.DataFrame([{"symbol": "8888", "effective_date": "2026-09-28", "ratio": 10}])
        trade = self.trade(pd.concat([actions, other], ignore_index=True))
        self.assertEqual(trade["exit_shares"], 100)
        self.assertEqual(trade["one_hundred_shares_pl_yen"], 1000)

    def test_fractional_shares_stop_even_if_a_later_split_would_restore_whole_shares(self):
        with self.assertRaisesRegex(UnsupportedFractionalShares, "cash-in-lieu"):
            self.trade(self.actions(("2026-09-28", .003), ("2026-09-29", 10)))
        with self.assertRaises(UnsupportedFractionalShares):
            self.trade(self.actions(("2026-09-28", 1e-12)))

    def test_conflicting_actions_and_multi_symbol_without_filter_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.trade(self.actions(("2026-09-28", 2), ("2026-09-28", 3)))
        actions = self.actions(("2026-09-28", 2))
        actions.loc[1] = {"symbol": "8888", "effective_date": "2026-09-28", "ratio": 3}
        with self.assertRaisesRegex(ValueError, "symbol is required"):
            self.trade(actions, symbol=None)

    def test_missing_endpoints_remain_unfrozen(self):
        entered = self.row(self.trade(actual_exit_close=None))
        self.assertEqual(entered["status"], "entered")
        self.assertTrue(pd.isna(entered["gross_return"]))
        self.assertFalse(is_frozen_trade(entered))
        pending = self.trade(entry_date=None, exit_date=None, actual_entry_open=None, actual_exit_close=None)
        self.assertEqual(pending["status"], "pending_entry")

    def test_completed_economics_cannot_be_rebased_by_future_action_or_rerun(self):
        original = self.row(self.trade())
        rebased = self.row(self.trade(actual_entry_open=50, actual_exit_close=55, basis_date="2026-10-01"))
        preserved = preserve_completed_economics(original, rebased)
        self.assertTrue(is_frozen_trade(preserved))
        for column in ECONOMIC_COLUMNS:
            self.assertEqual(preserved[column], original[column], column)
        self.assertEqual(preserve_completed_economics(preserved, rebased), preserved)
        merged = merge_detections(pd.DataFrame([original]), pd.DataFrame([rebased]))
        self.assertEqual(merged.iloc[0]["entry_open"], 100)
        self.assertEqual(merged.iloc[0]["one_hundred_shares_pl_yen"], 1000)
        self.assertEqual(merged.iloc[0]["signal_close"], 99)
        self.assertEqual(required_capital(merged), 10000)

    def test_corrupt_marked_snapshot_fails_instead_of_being_silently_recomputed(self):
        original = self.row(self.trade())
        original["one_hundred_shares_pl_yen"] = 500
        with self.assertRaisesRegex(ValueError, "corrupt frozen"):
            preserve_completed_economics(original, self.row(self.trade()))

    def test_action_receipt_and_basis_date_must_support_frozen_amounts(self):
        trade = self.row(self.trade(self.actions(("2026-09-28", 2)), actual_exit_close=55))
        trade["applied_actions_json"] = "[]"
        with self.assertRaisesRegex(ValueError, "action receipts"):
            is_frozen_trade(trade)
        with self.assertRaisesRegex(ValueError, "precedes"):
            self.trade(basis_date="2026-09-25")

    def test_frozen_basis_requires_a_real_date_not_nan_or_an_epoch_number(self):
        for basis in (float("nan"), "NaN", pd.NaT, None, 9_000_000_000_000_000_000, "2026-09-29"):
            with self.subTest(basis=basis):
                trade = self.row(self.trade())
                trade["price_basis_date"] = basis
                with self.assertRaisesRegex(ValueError, "corrupt frozen"):
                    is_frozen_trade(trade)

    def test_frozen_endpoints_reject_nonfinite_prices(self):
        for column in ("entry_open", "fifth_xtks_exit_close"):
            for price in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(column=column, price=price):
                    trade = self.row(self.trade())
                    trade[column] = price
                    with self.assertRaisesRegex(ValueError, "corrupt frozen"):
                        is_frozen_trade(trade)

    def test_missing_or_corrected_action_receipt_cannot_preserve_obsolete_economics(self):
        original = self.row(self.trade(self.actions(("2026-09-28", 2)), actual_exit_close=55))
        missing = dict(original)
        del missing["applied_actions_json"]
        with self.assertRaisesRegex(ValueError, "corrupt frozen"):
            is_frozen_trade(missing)
        corrected = dict(original, applied_actions_json='[{"effective_date":"2026-09-28","ratio":3}]')
        with self.assertRaisesRegex(ValueError, "action receipts"):
            preserve_completed_economics(corrected, original)

    def test_frozen_action_json_rejects_ambiguous_or_invalid_receipts(self):
        invalid = (
            "null", "{}", "[null]",
            '[{"effective_date":"2026-09-28","ratio":true}]',
            '[{"effective_date":"2026-09-28","ratio":"2"}]',
            '[{"effective_date":"2026-09-28","ratio":NaN}]',
            '[{"effective_date":"2026-09-28","ratio":2,"ratio":2}]',
            '[{"effective_date":"2026-09-24","ratio":2}]',
            '[{"effective_date":"2026-10-01","ratio":2}]',
            '[{"effective_date":"2026-09-28T00:00:00","ratio":2}]',
            '[{"effective_date":"2026-09-28","ratio":2},{"effective_date":"2026-09-28","ratio":1}]',
            '[{"effective_date":"2026-09-29","ratio":1},{"effective_date":"2026-09-28","ratio":2}]',
            '[{"effective_date":"2026-09-28","ratio":0.003},{"effective_date":"2026-09-29","ratio":10}]',
        )
        for receipt in invalid:
            with self.subTest(receipt=receipt):
                trade = self.row(self.trade(self.actions(("2026-09-28", 2)), actual_exit_close=55))
                trade["applied_actions_json"] = receipt
                with self.assertRaisesRegex(ValueError, "corrupt frozen"):
                    is_frozen_trade(trade)

    def test_verified_legacy_forward_endpoints_can_migrate_without_rebasing_canonical_rows(self):
        legacy = self.row(self.trade(actual_entry_open=50, actual_exit_close=55))
        legacy["price_basis"] = ""
        migrated = self.row(self.trade(self.actions(("2026-09-28", 2)), actual_exit_close=55))
        merged = merge_detections(pd.DataFrame([legacy]), pd.DataFrame([migrated]))
        self.assertEqual(merged.iloc[0]["entry_open"], 100)
        self.assertEqual(merged.iloc[0]["one_hundred_shares_pl_yen"], 1000)
        self.assertEqual(merged.iloc[0]["price_basis"], PRICE_BASIS_VERSION)
        self.assertTrue(is_frozen_trade(merged.iloc[0]))

    def test_forward_catchup_cannot_replace_a_pinned_canonical_detection(self):
        canonical = self.row(self.trade(actual_entry_open=50, actual_exit_close=55))
        canonical.update({
            "source_scope": "EXACT_CANONICAL_2023_2026",
            "price_basis": LEGACY_PRICE_BASIS_VERSION,
            "fundamental_status": "not_requested_historical",
        })
        incoming = self.row(self.trade(self.actions(("2026-09-28", 2)), actual_exit_close=55))
        merged = merge_detections(pd.DataFrame([canonical]), pd.DataFrame([incoming]))
        for column in LEDGER_COLUMNS:
            self.assertEqual(merged.iloc[0][column], canonical[column], column)

    def test_csv_roundtrip_keeps_frozen_share_basis_and_legacy_amounts(self):
        original = self.row(self.trade(self.actions(("2026-09-28", 2)), actual_exit_close=55))
        legacy = dict(original, detection_id="2023-01-01|9999|volr20_low", source_scope="EXACT_CANONICAL_2023_2026")
        legacy.update({"price_basis": "", "entry_open": 50, "fifth_xtks_exit_close": 55,
                       "gross_return": .1, "one_hundred_shares_pl_yen": 500})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            write_ledger(pd.DataFrame([original, legacy]), path)
            restored = read_ledger(path).set_index("detection_id")
        self.assertTrue(is_frozen_trade(restored.loc[original["detection_id"]]))
        old = restored.loc[legacy["detection_id"]]
        self.assertEqual(old["price_basis"], LEGACY_PRICE_BASIS_VERSION)
        self.assertEqual(old["one_hundred_shares_pl_yen"], 500)
        self.assertFalse(is_frozen_trade(old))

    def test_capital_uses_original_entry_shares_and_overlap_requires_same_basis(self):
        original = self.row(self.trade(entry_shares=200))
        self.assertEqual(required_capital(pd.DataFrame([original])), 20000)
        other = dict(original, detection_id="2026-09-23|9999|body_pct_low", selector_id="body_pct_low")
        other["entry_shares"] = 100
        with self.assertRaisesRegex(RuntimeError, "entry_shares"):
            combined_detections(pd.DataFrame([original, other]))


if __name__ == "__main__":
    unittest.main()
