"""Finite retained-input recovery; all identities and market data are synthetic."""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

import pandas as pd

from weak_early_beta import corporate_actions as ca, jpx_reports, model
from weak_early_beta.acquisition import AcquisitionArchive, RetainedResponseError
from weak_early_beta.new_a import source


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FixedSourceRecovery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name).resolve()
        self.private = self.repo / '.cache/weak_early_beta'
        self.private.mkdir(parents=True)
        self.previous = self.private / 'daily.csv'
        raw = pd.DataFrame({'date': pd.to_datetime(['2026-11-16']), 'symbol': ['1234'],
                            'open': [100.], 'high': [103.], 'low': [99.],
                            'close': [101.], 'volume': [10000.], 'split_ratio': [0.]})
        self.previous_frame = ca.normalize_daily(raw)
        self.previous_frame.to_csv(self.previous, index=False, date_format='%Y-%m-%d')
        self.quality = self.previous.with_suffix('.source-quality.json')
        self.quality.write_text(json.dumps({**ca.source_quality_receipt(self.previous_frame),
                    'daily_sha256': sha(self.previous), 'source_revision': {}, 'acquisition_exclusions': {}}))
        context = {'date': '2026-11-17', 'period': '5y', 'tickers': ['1234.T'],
                   'previousSourceSha256': sha(self.previous)}
        self.original = self.private / 'original'
        archive = AcquisitionArchive(self.original, context)
        kwargs = dict(period='5y', interval='1d', group_by='ticker', auto_adjust=False,
                      actions=True, repair=True, threads=True, progress=False, timeout=30)
        response = pd.DataFrame({'Open': [100., 101.], 'High': [103., 104.], 'Low': [99., 100.],
                                 'Close': [101., 102.], 'Volume': [10000., 11000.],
                                 'Stock Splits': [0., 0.]}, index=pd.to_datetime(['2026-11-16', '2026-11-17']))
        archive.request({'kind': 'batch', 'tickers': ['1234.T'], 'kwargs': kwargs}, lambda: response, {})
        inventory = archive.verified_revision_info()
        evidence = self.original / 'jpx-evidence'
        evidence.mkdir()
        (evidence / 'stq_20261109.pdf').write_bytes(b'%PDF-synthetic-not-extracted')
        (evidence / 'stq_20261109.source.json').write_text('{}')
        self.replay = self.private / 'execution-copy'
        shutil.copytree(self.original, self.replay)
        self.workbook = self.private / 'pre-run.xlsx'
        self.labels = pd.DataFrame({'日付': [20261031, 20261031], 'コード': ['1234', '5678'],
                                    '銘柄名': ['Synthetic A', 'Synthetic delisted'],
                                    '市場・商品区分': ['プライム（内国株式）', 'スタンダード（内国株式）']})
        self.labels.to_excel(self.workbook, index=False)
        self.restrictions = self.private / 'original-restrictions.json'
        self.restriction_rows = [{'code': '5678', 'designation_date': '2026-11-16',
                                 'delisting_date': '2026-11-16', 'delisting_source_url': 'https://synthetic.invalid',
                                 'relisting_coverage_start_year': 2021}]
        self.restrictions.write_text(json.dumps({'version': 2, 'as_of': '2026-11-17',
                                                'symbols': self.restriction_rows}))
        self.context = {'schema': 'NEW_A_FIXED_SOURCE_RECOVERY_V1', 'target_date': '2026-11-17', 'period': '5y',
                        'archive': {'path': str(self.original.relative_to(self.repo)),
                                    'manifest_sha256': sha(self.original / 'manifest.json'),
                                    'inventory_sha256': inventory['responseInventorySha256'], 'request_count': 1,
                                    'independent_evidence': [{'path': str(f.relative_to(self.original)), 'sha256': sha(f)}
                                                             for f in sorted(evidence.iterdir())]},
                        'previous_corpus': self.ref(self.previous), 'previous_quality': self.ref(self.quality),
                        'restriction_snapshot': self.ref(self.restrictions),
                        'official_workbook': self.ref(self.workbook), 'completed_cache': None}
        self.args = SimpleNamespace(as_of='2026-11-17', period='5y', refresh_live=False,
                                    refresh_universe=True, new_a_isolated=False,
                                    daily_corpus=str(self.previous), retained_acquisition=str(self.replay))

    def ref(self, path):
        return {'path': str(path.relative_to(self.repo)), 'sha256': sha(path)}

    def fixed(self):
        return source._fixed_source_inputs(self.repo, self.args, self.context)

    def execute(self):
        # This patch represents an explicitly synthetic finite host record. All
        # file, corporate-action, normalization and quality gates run for real.
        with patch('weak_early_beta.new_a.operational_admission.source_context', return_value=self.context), \
             patch.object(source, '__file__', str(self.repo / 'weak_early_beta/new_a/source.py')), \
             patch('weak_early_beta.restrictions.fetch_jpx_restricted_symbols', side_effect=AssertionError('no JPX fetch')), \
             patch.object(model.base, 'jpx_universe', side_effect=AssertionError('no universe fetch')), \
             patch('yfinance.download', side_effect=AssertionError('no price fetch')), \
             patch('yfinance.Ticker', side_effect=AssertionError('no history fetch')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('no independent fetch')):
            return source.acquire_and_validate(self.args)

    def test_finite_replay_retains_source_rules_and_never_fetches_prices_or_jpx(self):
        original = {str(f.relative_to(self.original)): f.read_bytes() for f in self.original.rglob('*') if f.is_file()}
        result = self.execute()
        self.assertEqual(result['frame'].date.max(), pd.Timestamp('2026-11-17'))
        self.assertEqual(result['frame'].actual_close.tolist(), [101., 102.])
        self.assertEqual(result['company_names'], {'1234': 'Synthetic A'})
        self.assertEqual(result['restrictions'], self.restriction_rows)
        self.assertEqual(result['acquisition_exclusions']['excluded_universe_symbols'], ['5678'])
        self.assertEqual(result['fixed_input_reference']['kind'], 'PRE_RUN_OFFICIAL_MONTH_END_REFERENCE')
        self.assertFalse(result['fixed_input_reference']['original_response_bytes_equal_claimed'])
        self.assertEqual(result['acquisition_evidence']['requests'], 1)
        self.assertTrue(result['acquisition_evidence']['replayed'])
        self.assertEqual(original, {str(f.relative_to(self.original)): f.read_bytes()
                                    for f in self.original.rglob('*') if f.is_file()})
        self.assertEqual(json.loads(self.quality.read_text())['daily_sha256'], sha(self.previous))

    def test_all_pinned_inputs_and_packets_are_verified_before_deserialization(self):
        paths = [self.previous, self.quality, self.workbook, self.restrictions,
                 next(self.original.glob('*.pkl')), next(self.replay.glob('*.pkl')),
                 self.original / 'jpx-evidence/stq_20261109.pdf',
                 self.replay / 'jpx-evidence/stq_20261109.source.json']
        for path in paths:
            with self.subTest(path=path.name):
                saved = path.read_bytes()
                path.write_bytes(saved + b'changed')
                try:
                    with patch('pickle.load', side_effect=AssertionError('must not deserialize')):
                        with self.assertRaises((ValueError, RetainedResponseError)):
                            self.fixed()
                finally:
                    path.write_bytes(saved)

    def test_missing_packet_or_independent_evidence_stops_without_fallback(self):
        for path in [next(self.replay.glob('*.pkl')), self.replay / 'jpx-evidence/stq_20261109.pdf']:
            with self.subTest(path=path.name):
                saved = path.read_bytes(); path.unlink()
                try:
                    with self.assertRaises((ValueError, RetainedResponseError)):
                        self.fixed()
                finally:
                    path.write_bytes(saved)

    def test_live_new_date_isolated_or_period_changes_cannot_enter_fixed_path(self):
        for key, value in [('as_of', '2026-11-18'), ('period', '1y'), ('refresh_live', True), ('new_a_isolated', True)]:
            with self.subTest(key=key):
                saved = getattr(self.args, key); setattr(self.args, key, value)
                try:
                    with self.assertRaisesRegex(ValueError, 'target or live acquisition'):
                        self.fixed()
                finally:
                    setattr(self.args, key, saved)

    def test_reference_population_is_compared_even_when_new_reference_hash_is_supplied(self):
        self.labels.loc[0, 'コード'] = '9999'
        self.labels.to_excel(self.workbook, index=False)
        self.context['official_workbook'] = self.ref(self.workbook)
        with self.assertRaisesRegex(ValueError, 'original ticker sequence'):
            self.fixed()

    def test_private_path_escape_and_original_archive_reuse_are_rejected(self):
        bad = copy.deepcopy(self.context)
        bad['official_workbook']['path'] = '../pre-run.xlsx'
        with self.assertRaisesRegex(ValueError, 'escapes private'):
            source._fixed_source_inputs(self.repo, self.args, bad)
        self.args.retained_acquisition = str(self.original)
        with self.assertRaisesRegex(ValueError, 'separate execution'):
            self.fixed()

    def completed(self, day='2026-11-17'):
        corpus = self.private / 'completed.csv'
        frame = self.previous_frame.copy()
        frame['date'] = pd.to_datetime([day]); frame['basis_asof'] = pd.to_datetime([day])
        frame.to_csv(corpus, index=False, date_format='%Y-%m-%d')
        frame = model.read_daily(corpus)
        quality = corpus.with_suffix('.source-quality.json')
        quality.write_text(json.dumps({**ca.source_quality_receipt(frame), 'daily_sha256': sha(corpus),
                                       'source_revision': {}, 'acquisition_exclusions': {}}))
        self.context['completed_cache'] = {'corpus': self.ref(corpus), 'quality': self.ref(quality),
                    'original_manifest_sha256': self.context['archive']['manifest_sha256'],
                    'original_inventory_sha256': self.context['archive']['inventory_sha256'],
                    'previous_source_sha256': self.context['previous_corpus']['sha256']}
        self.args.daily_corpus = str(corpus)
        return corpus, quality

    def test_completed_cache_reuses_matching_quality_without_replaying_or_writing(self):
        corpus, quality = self.completed()
        before = (corpus.read_bytes(), quality.read_bytes())
        with patch.object(ca, 'fetch_daily', side_effect=AssertionError('no replay')), \
             patch.object(source, '_write_receipt', side_effect=AssertionError('no quality overwrite')):
            result = self.execute()
        self.assertEqual(result['frame'].date.max(), pd.Timestamp('2026-11-17'))
        self.assertEqual(before, (corpus.read_bytes(), quality.read_bytes()))

    def test_previous_day_cache_cannot_be_counted_as_completed_target_source(self):
        corpus, quality = self.completed(day='2026-11-16')
        before = (corpus.read_bytes(), quality.read_bytes())
        with self.assertRaisesRegex(ValueError, 'did not reach the target session'):
            self.execute()
        self.assertEqual(before, (corpus.read_bytes(), quality.read_bytes()))

    def test_completed_quality_is_recomputed_and_lineage_is_required(self):
        corpus, quality = self.completed()
        value = json.loads(quality.read_text()); value['sourceRows'] += 1
        quality.write_text(json.dumps(value)); self.context['completed_cache']['quality'] = self.ref(quality)
        with self.assertRaisesRegex(ValueError, 'quality does not match'):
            self.execute()
        self.context['completed_cache']['original_inventory_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'completed cache lineage'):
            self.fixed()

    def test_no_finite_record_preserves_normal_jpx_and_universe_refresh(self):
        self.args.retained_acquisition = None
        with patch('weak_early_beta.new_a.operational_admission.source_context', return_value=None), \
             patch('weak_early_beta.restrictions.fetch_jpx_restricted_symbols', return_value=[]) as restrictions, \
             patch.object(model.base, 'jpx_universe', return_value=pd.DataFrame({'code': ['1234'], 'name': ['ordinary']})) as universe:
            result = source.acquire_and_validate(self.args)
        restrictions.assert_called_once(); universe.assert_called_once()
        self.assertEqual(result['company_names'], {'1234': 'ordinary'})
        self.assertNotIn('fixed_input_reference', result)


class IndependentNetworkBoundary(unittest.TestCase):
    def test_finite_archive_flag_blocks_missing_pdf_network_and_preserves_explicit_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = SimpleNamespace(directory=Path(temporary), network_fallback_allowed=False)
            with patch('urllib.request.urlopen', side_effect=AssertionError('no network')) as request:
                evidence, failures = jpx_reports.load([{'session': '2026-11-09', 'symbol': '1234'}], archive)
            request.assert_not_called()
            self.assertEqual(evidence, {})
            self.assertIn('network disabled', failures['2026-11-09'])

    def test_normal_archive_keeps_existing_network_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = SimpleNamespace(directory=Path(temporary))
            with patch('urllib.request.urlopen', side_effect=URLError('synthetic unavailable')) as request:
                _, failures = jpx_reports.load([{'session': '2026-11-09', 'symbol': '1234'}], archive)
            request.assert_called_once()
            self.assertIn('official source unavailable', failures['2026-11-09'])


if __name__ == '__main__':
    unittest.main()
