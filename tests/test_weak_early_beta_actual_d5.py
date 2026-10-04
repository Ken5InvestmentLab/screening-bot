"""Actual D5/D6 economics use one acquired lot; canonical values stay intact."""
import copy
import hashlib
import json
import re
import unittest
from decimal import Decimal
from pathlib import Path

import pandas as pd

from weak_early_beta.ledger import DEFAULT_LEDGER, read_ledger
from weak_early_beta.reviewed_endpoint_overlay import apply_reviewed_endpoint_overlay
from weak_early_beta.reviewed_d5_overlay import (
    DEFAULT_OVERLAY, DEFAULT_OVERLAY_SHA256, RECEIPT_COLUMN,
    actual_d5_economics, apply_reviewed_d5_overlay,
)
from weak_early_beta.report_preferences import select_report_view, released_history
from weak_early_beta.report import _detection_rows
from weak_early_beta.analytics import build_analytics
from weak_early_beta.trade_basis import ECONOMIC_COLUMNS, LEGACY_PRICE_BASIS_VERSION, build_trade_economics
from tests.test_weak_early_beta_report_preferences import actual_trade


class ActualD5PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = read_ledger(DEFAULT_LEDGER)
        cls.source_sha = hashlib.sha256(DEFAULT_LEDGER.read_bytes()).hexdigest()
        cls.package = json.loads(DEFAULT_OVERLAY.read_bytes())
        cls.d6, _ = apply_reviewed_endpoint_overlay(cls.raw)
        cls.joined, cls.audit = apply_reviewed_d5_overlay(cls.d6)

    def test_pinned_sidecar_and_all_canonical_columns_are_preserved(self):
        self.assertEqual(hashlib.sha256(DEFAULT_OVERLAY.read_bytes()).hexdigest(), DEFAULT_OVERLAY_SHA256)
        self.assertEqual(len(self.package['records']),253)
        self.assertEqual(self.audit['applied_mode_rows'],967)
        pd.testing.assert_frame_equal(self.joined[self.d6.columns],self.d6)
        for endpoint in ('d5_close','d6_open'):
            view=select_report_view(self.joined,None,endpoint)
            for column in ECONOMIC_COLUMNS:
                if column in self.joined:
                    pd.testing.assert_series_equal(view['raw_d5_'+column],self.joined[column],check_names=False)
        self.assertEqual(hashlib.sha256(DEFAULT_LEDGER.read_bytes()).hexdigest(),self.source_sha)

    def test_all253_prices_shares_profit_returns_and_acquired_lots_match_independent_arithmetic(self):
        d5=select_report_view(self.joined,None,'d5_close')
        d6=select_report_view(self.joined,None,'d6_open')
        for index,row in d5[d5.display_d5_verified].iterrows():
            record=self.package['records'][f'{row.signal_date:%Y-%m-%d}|{row.symbol}']['receipt']['record']
            cost=Decimal(str(record['entry_price']))*100
            shares=Decimal(100)
            for action in record['applied_actions']:
                shares*=Decimal(str(action['ratio']))
            proceeds=Decimal(str(record['exit_price']))*shares
            self.assertAlmostEqual(row.entry_cost_yen,float(cost),places=6)
            self.assertAlmostEqual(row.exit_shares,float(shares),places=6)
            self.assertAlmostEqual(row.exit_proceeds_yen,float(proceeds),places=6)
            self.assertAlmostEqual(row.one_hundred_shares_pl_yen,float(proceeds-cost),places=6)
            self.assertAlmostEqual(row.gross_return,float(proceeds/cost-1),places=9)
            self.assertEqual(row.entry_shares,100)
            for column in ('entry_open','entry_shares','entry_cost_yen'):
                self.assertAlmostEqual(row[column],d6.loc[index,column],places=6)

    def test_split_consolidation_history_and_csv_attributes_are_actual_d5_in_both_selected_views(self):
        subset=self.joined[self.joined.symbol.isin(['8894','3997','6085'])]
        d5=select_report_view(subset,None,'d5_close')
        rows=_detection_rows(subset)
        nested=_detection_rows(select_report_view(subset,None,'d6_open'))
        self.assertEqual(rows,nested)
        for (signal,symbol),group in d5.groupby(['signal_date','symbol']):
            row=group.iloc[0]
            match=re.search(r'<tr\b(?=[^>]*data-date="'+signal.strftime('%Y-%m-%d')+r'")(?=[^>]*data-symbol="'+symbol+r'")[^>]*>',rows)
            self.assertIsNotNone(match)
            self.assertIn(f'data-entry-open="{row.entry_open}"',match[0])
            self.assertIn(f'data-d5-close="{row.fifth_xtks_exit_close}"',match[0])
            self.assertIn(f'data-d5-return="{row.gross_return}"',match[0])
        self.assertTrue(d5.display_d5_verified.all())
        self.assertNotIn('保存時の調整価格参考値',rows)

    def test_no_d5_receipt_never_reuses_legacy_d5_or_d6_prices(self):
        source=self.d6.iloc[:1].copy()
        view=select_report_view(source,None,'d5_close')
        for column in ('entry_open','fifth_xtks_exit_close','gross_return','one_hundred_shares_pl_yen','entry_cost_yen','exit_shares'):
            self.assertTrue(pd.isna(view.iloc[0][column]),column)
        self.assertFalse(view.iloc[0].display_d5_verified)
        self.assertTrue(pd.notna(source.iloc[0].sixth_entry_open))

    def test_tampered_price_action_date_hash_and_scope_are_unavailable(self):
        row=self.joined.iloc[0].copy()
        original=json.loads(row[RECEIPT_COLUMN])
        for field,value in [('record_sha256','0'*64),('source_input_sha256','0'*64),('cost_yen',1),('raw_market_refetched',True),('identity','2023-01-04|9999')]:
            with self.subTest(field=field):
                candidate=copy.deepcopy(original);candidate[field]=value
                row[RECEIPT_COLUMN]=json.dumps(candidate)
                self.assertIsNone(actual_d5_economics(row))
        for field,value in [('exit_price',12345),('exit_date','2023-01-13'),('applied_actions',[{'effective_date':'2023-01-10','ratio':2}])]:
            candidate=copy.deepcopy(original);candidate['record'][field]=value
            row[RECEIPT_COLUMN]=json.dumps(candidate)
            self.assertIsNone(actual_d5_economics(row))

    def test_baseline_changes_are_rejected_and_unlisted_modes_stay_unavailable(self):
        source=self.d6.iloc[:1].copy();source.loc[source.index[0],'entry_open']=12345
        with self.assertRaisesRegex(ValueError,'baseline changed'):
            apply_reviewed_d5_overlay(source)
        source=self.d6.iloc[:1].copy();source['detection_id']='not-reviewed';source['selector_id']='not-reviewed'
        result,audit=apply_reviewed_d5_overlay(source)
        self.assertEqual(audit['applied_mode_rows'],0)
        self.assertEqual(result.iloc[0][RECEIPT_COLUMN],'')

    def test_reapplication_and_nested_d5_d6_selection_are_idempotent(self):
        repeated,_=apply_reviewed_d5_overlay(self.joined)
        pd.testing.assert_frame_equal(repeated,self.joined)
        source=self.joined.iloc[:15].copy()
        first=select_report_view(source,None,'d5_close')
        repeated=select_report_view(select_report_view(source,None,'d6_open'),None,'d5_close')
        pd.testing.assert_frame_equal(first[list(ECONOMIC_COLUMNS)],repeated[list(ECONOMIC_COLUMNS)])

    def test_free_unreleased_identifier_and_forward_actual_snapshot_are_preserved(self):
        free=released_history(self.joined)
        self.assertEqual(len(free),967)
        rows=_detection_rows(self.joined,mask_pending=True)
        self.assertIsNone(re.search(r'<tr\b(?=[^>]*data-date="2026-09-30")(?=[^>]*data-symbol="4052")[^>]*>',rows))
        frame=actual_trade('F001',900)
        original=frame.copy(deep=True)
        result=select_report_view(frame,None,'d5_close')
        self.assertTrue(result.display_d5_verified.all())
        self.assertAlmostEqual(result.iloc[0].one_hundred_shares_pl_yen,400)
        pd.testing.assert_frame_equal(frame,original)


class ForwardPendingPresentationTests(unittest.TestCase):
    @staticmethod
    def forward(symbol, entry, exit_price):
        frame = actual_trade(symbol, 900)
        row = frame.iloc[0]
        economics = build_trade_economics(
            row.entry_date, row.fifth_xtks_exit_date, entry, exit_price, None,
            basis_date=row.entry_date if pd.isna(exit_price) else row.fifth_xtks_exit_date,
            source_sha256=str(row.price_basis_source_sha256),
        )
        for column, value in economics.items():
            frame[column] = value
        # Neither incomplete entry/exit fixture has a confirmed D6 receipt.
        frame['sixth_xtks_exit_status'] = 'pending'
        frame['sixth_economics_status'] = 'pending'
        return frame

    def test_entered_lot_is_preserved_without_confirming_d5_or_d6(self):
        frame = self.forward('P001', 900, float('nan'))
        original = frame.copy(deep=True)
        for endpoint in ('d5_close', 'd6_open'):
            with self.subTest(endpoint=endpoint):
                view = select_report_view(frame, None, endpoint).iloc[0]
                self.assertEqual(view.status, 'entered')
                self.assertEqual(view.entry_open, 900)
                self.assertEqual(view.entry_shares, 100)
                self.assertEqual(view.entry_cost_yen, 90000)
                self.assertEqual(view.entry_date, frame.iloc[0].entry_date)
                self.assertFalse(view.display_d5_verified)
                for column in ('fifth_xtks_exit_close', 'gross_return', 'one_hundred_shares_pl_yen', 'exit_proceeds_yen', 'exit_shares'):
                    self.assertTrue(pd.isna(view[column]), column)
                repeated = select_report_view(select_report_view(frame, None, 'd6_open'), None, endpoint).iloc[0]
                for column in ('status', 'entry_open', 'entry_shares', 'entry_cost_yen'):
                    self.assertEqual(view[column], repeated[column])
                self.assertEqual(build_analytics(select_report_view(frame, None, endpoint))['counts']['completed_signals'], 0)
        pd.testing.assert_frame_equal(frame, original)

    def test_entry_before_purchase_and_unverified_legacy_remain_unavailable(self):
        pending = self.forward('P002', float('nan'), float('nan'))
        legacy = self.forward('P003', 900, float('nan'))
        legacy['source_scope'] = 'EXACT_CANONICAL_HISTORY'
        legacy['price_basis'] = LEGACY_PRICE_BASIS_VERSION
        for frame in (pending, legacy):
            for endpoint in ('d5_close', 'd6_open'):
                row = select_report_view(frame, None, endpoint).iloc[0]
                self.assertEqual(row.status, 'pending_entry')
                self.assertFalse(row.display_d5_verified)
                for column in ('entry_open', 'entry_shares', 'entry_cost_yen', 'gross_return'):
                    self.assertTrue(pd.isna(row[column]), column)

    def test_mature_forward_stays_confirmed_at_9000_yen(self):
        frame = self.forward('P004', 900, 990)
        row = select_report_view(frame, None, 'd5_close').iloc[0]
        self.assertEqual(row.status, 'mature')
        self.assertTrue(row.display_d5_verified)
        self.assertEqual(row.entry_open, 900)
        self.assertEqual(row.one_hundred_shares_pl_yen, 9000)

    def test_history_and_csv_entry_attributes_distinguish_all_four_states(self):
        entered = self.forward('P001', 900, float('nan'))
        pending = self.forward('P002', float('nan'), float('nan'))
        legacy = self.forward('P003', 900, float('nan'))
        legacy['source_scope'] = 'EXACT_CANONICAL_HISTORY'
        legacy['price_basis'] = LEGACY_PRICE_BASIS_VERSION
        mature = self.forward('P004', 900, 990)
        frame = pd.concat([entered, pending, legacy, mature], ignore_index=True)
        rows = _detection_rows(frame)
        for symbol, label, bought, completed in (
            ('P001', '保有中', True, False), ('P002', '寄付待ち', False, False),
            ('P003', '寄付待ち', False, False), ('P004', '結果あり', True, True),
        ):
            row = re.search(r'<tr\b(?=[^>]*data-symbol="'+symbol+r'")[\s\S]*?</tr>', rows)[0]
            self.assertIn(label, row)
            for attribute in ('data-entry-open="900.0"', 'data-d6-entry-open="900.0"'):
                self.assertEqual(attribute in row, bought)
            self.assertEqual('data-d5-close="990.0"' in row, completed)
            if not completed:
                self.assertNotIn('data-d5-return=', row)
                self.assertNotIn('data-d6-return=', row)
        self.assertEqual(rows, _detection_rows(select_report_view(frame, None, 'd6_open')))
        free = _detection_rows(frame, mask_pending=True)
        for symbol in ('P001', 'P002', 'P003', 'P004'):
            self.assertNotIn(symbol, free)

    def test_corrupt_acquired_cost_and_rejected_receipt_do_not_restore_entry(self):
        frame = self.forward('P001', 900, float('nan'))
        for column, value in (('entry_cost_yen', 1), ('entry_shares', 0.5), (RECEIPT_COLUMN, '{"invalid":true}')):
            with self.subTest(column=column):
                bad = frame.copy(deep=True)
                bad[column] = value
                row = select_report_view(bad, None, 'd5_close').iloc[0]
                self.assertEqual(row.status, 'pending_entry')
                self.assertTrue(pd.isna(row.entry_open))
                self.assertFalse(row.display_d5_verified)


if __name__=='__main__':
    unittest.main()
