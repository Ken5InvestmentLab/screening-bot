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
from weak_early_beta.trade_basis import ECONOMIC_COLUMNS
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


if __name__=='__main__':
    unittest.main()
