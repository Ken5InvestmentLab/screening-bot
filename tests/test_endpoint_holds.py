import unittest
import tempfile
import json
import hashlib
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from tests import test_weak_early_beta_model as fixtures
from weak_early_beta import model, endpoint_holds
from weak_early_beta.corporate_actions import normalize_daily, CorporateActionError

class EndpointHoldTests(unittest.TestCase):
    def fixture(self):
        raw = fixtures.SplitAwareModelTests.daily()
        selected = fixtures.SplitAwareModelTests.selected(raw)
        second = selected.copy()
        second['selector'] = 'body_pct_low'
        entered = model.attach_forward_rows(pd.concat([selected, second], ignore_index=True), fixtures.SplitAwareModelTests.before_split(raw, 3))
        changed = raw[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'split_ratio']].copy()
        for column in ('open', 'high', 'low', 'close'):
            changed.loc[1, column] *= 1.1
        other = changed.copy()
        other['symbol'] = '8888'
        return entered, normalize_daily(pd.concat([changed, other], ignore_index=True))

    def test_symbol_atomic_preserves_all_selectors_and_original_inputs(self):
        ledger, raw = self.fixture()
        before_ledger, before_raw = ledger.copy(deep=True), raw.copy(deep=True)
        held, evidence = endpoint_holds.quarantine(ledger, raw, 'a' * 64)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(len(evidence[0]['conflicts']), 2)
        self.assertFalse(held[held.symbol.eq('9999')].source_usable.any())
        self.assertTrue(held[held.symbol.eq('8888')].source_usable.all())
        result = model.refresh_forward_endpoints(ledger, held, source_sha256='a' * 64)
        # Empty new receipt columns may be initialized, but existing values stay exact.
        pd.testing.assert_frame_equal(result[ledger.columns], ledger)
        pd.testing.assert_frame_equal(raw, before_raw)
        pd.testing.assert_frame_equal(ledger, before_ledger)
        pd.testing.assert_frame_equal(normalize_daily(held), held)

    def test_evidence_tampering_fails_closed(self):
        ledger, raw = self.fixture()
        held, _ = endpoint_holds.quarantine(ledger, raw, 'a' * 64)
        held.loc[held.symbol.eq('9999'), 'volume'] *= 2
        with self.assertRaises(CorporateActionError):
            normalize_daily(held)

    def test_unaffected_symbol_refresh_matches_strict_baseline(self):
        ledger, raw = self.fixture()
        other_raw = raw[raw.symbol.eq('8888')].copy()
        selected = pd.DataFrame([{'date': other_raw.iloc[0].date, 'symbol': '8888', 'selector': 'volr20_low', 'model_period': '2026-09'}])
        other_ledger = model.attach_forward_rows(selected, fixtures.SplitAwareModelTests.before_split(other_raw, 3))
        combined = pd.concat([ledger, other_ledger], ignore_index=True)
        held, _ = endpoint_holds.quarantine(combined, raw, 'a' * 64)
        result = model.refresh_forward_endpoints(combined, held, 'a' * 64)
        baseline = model.refresh_forward_endpoints(other_ledger, other_raw, 'a' * 64)
        # Observed timestamps differ by invocation; all economics match.
        columns = ['entry_date', 'entry_open', 'fifth_xtks_exit_date', 'fifth_xtks_exit_close', 'one_hundred_shares_pl_yen', 'status']
        pd.testing.assert_frame_equal(result[result.symbol.eq('8888')][columns].reset_index(drop=True), baseline[columns].reset_index(drop=True))

    def test_unknown_errors_not_swallowed(self):
        ledger, raw = self.fixture()
        with patch.object(model, 'is_frozen_trade', side_effect=RuntimeError('unknown')):
            with self.assertRaisesRegex(RuntimeError, 'unknown'):
                endpoint_holds.quarantine(ledger, raw, 'a' * 64)

    def test_session_revision_not_price_quarantine(self):
        ledger, raw = self.fixture()
        ledger['entry_date'] = pd.Timestamp('2026-09-03')
        with self.assertRaisesRegex(ValueError, 'entry session revision'):
            endpoint_holds.quarantine(ledger, raw, 'a' * 64)

    def test_no_conflict_keeps_original_frame(self):
        raw = fixtures.SplitAwareModelTests.daily()
        ledger = model.attach_forward_rows(fixtures.SplitAwareModelTests.selected(raw), fixtures.SplitAwareModelTests.before_split(raw, 3))
        result, audit = endpoint_holds.quarantine(ledger, raw, 'a' * 64)
        self.assertIs(result, raw)
        self.assertEqual(audit, [])

    def test_feature_inputs_are_masked_without_dropping_calendar_rows(self):
        ledger, raw = self.fixture()
        held, _ = endpoint_holds.quarantine(ledger, raw, 'a' * 64)
        def inspect(frame, **kwargs):
            self.assertEqual(len(frame), len(raw))
            self.assertTrue(frame.loc[frame.symbol.eq('9999'), ['open', 'high', 'low', 'close', 'volume']].isna().all().all())
            self.assertFalse(frame.loc[frame.symbol.eq('8888'), 'close'].isna().any())
            raise RuntimeError('checked')
        with patch.object(model.base, 'build_features', side_effect=inspect):
            with self.assertRaisesRegex(RuntimeError, 'checked'):
                model.build_live_features(held)

    def test_notification_receipt_same_day_hash_and_ledger_checks(self):
        ledger, raw = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / 'daily.csv'
            raw.to_csv(corpus, index=False)
            sha = model.sha256(corpus)
            _, holds = endpoint_holds.quarantine(ledger, raw, sha)
            audit = root / 'audit.json'
            audit.write_text(json.dumps({'identity': 'CLOUD_ENDPOINT_HOLD_AUDIT_V1', 'daily_sha256': sha, 'holds': holds}), encoding='utf-8')
            receipt = root / 'receipt.json'
            quality = root / 'quality.json'
            quality.write_text(json.dumps({'identity': 'CLOUD_SOURCE_QUALITY_V1', 'daily_sha256': sha}), encoding='utf-8')
            record = {'identity': 'WEAK_EARLY_FIVE_LANE_BETA_V1', 'latest_session': '2026-09-09', 'score_to': '2026-09-09', 'daily_corpus': str(corpus), 'daily_sha256': sha, 'endpoint_holds': holds, 'endpoint_hold_audit': str(audit), 'endpoint_hold_audit_sha256': model.sha256(audit)}
            record['source_quality'] = {'audit_path': str(quality), 'audit_sha256': model.sha256(quality)}
            receipt.write_text(json.dumps(record), encoding='utf-8')
            self.assertEqual(endpoint_holds.notification_holds(receipt, '2026-09-09', ledger), {'9999'})
            with self.assertRaisesRegex(ValueError, 'same-day'):
                endpoint_holds.notification_holds(receipt, '2026-09-10', ledger)
            changed = ledger.copy()
            changed.loc[0, 'entry_open'] += 1
            with self.assertRaisesRegex(ValueError, 'ledger changed'):
                endpoint_holds.notification_holds(receipt, '2026-09-09', changed)
            corpus.write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source identity'):
                endpoint_holds.notification_holds(receipt, '2026-09-09', ledger)

    def test_blocked_pending_does_not_send_or_update_ledger(self):
        from weak_early_beta.notify import notify_pending
        ledger, _ = self.fixture()
        with patch('weak_early_beta.notify._post_webhook') as post:
            result, payloads = notify_pending(ledger, blocked_symbols={'9999'})
            self.assertEqual(payloads, [])
            post.assert_not_called()
            pd.testing.assert_frame_equal(result, ledger)
