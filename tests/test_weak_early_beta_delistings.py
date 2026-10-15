"""Official delisting acquisition gates retain verified causal history."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import requests

from weak_early_beta.corporate_actions import CorporateActionError, normalize_daily
from weak_early_beta.restrictions import (
    JPX_DELISTINGS_URL, JPX_RESTRICTIONS_URL, JPX_NEW_LISTINGS_URL, exclude_delisted_universe,
    fetch_jpx_restricted_symbols, parse_jpx_delisted_symbols,
    parse_jpx_new_listings, preserve_delisted_history, restricted_mask, quarantine_restricted_detections,
)


class DelistingTests(unittest.TestCase):
    @staticmethod
    def document(rows, *, archives=False):
        options = ""
        if archives:
            options = '<select class="backnumber">' + "".join(
                f'<option value="{JPX_DELISTINGS_URL if year == 2026 else f"/listing/stocks/delisted/archives-{2026-year:02d}.html"}">{year}年</option>'
                for year in range(2020, 2027)
            ) + '</select>'
        header = '<tr><th>上場廃止日</th><th>銘柄名</th><th>コード</th><th>市場区分</th><th>上場廃止理由</th></tr>'
        body = "".join('<tr>' + "".join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows)
        return (options + '<table>' + header + body + '</table>').encode('utf-8')

    @staticmethod
    def restrictions(date='2026-10-09'):
        return [{"code": "7183", "company_name": "あんしん保証",
                 "designation_date": "2026-08-01", "delisting_date": date,
                 "delisting_source_url": JPX_DELISTINGS_URL}]

    @staticmethod
    def prices(symbol='7183'):
        return normalize_daily(pd.DataFrame({
            "symbol": [symbol, symbol], "date": pd.to_datetime(['2026-10-07', '2026-10-08']),
            "open": [50., 50.], "high": [51., 51.], "low": [49., 49.],
            "close": [50., 50.], "volume": [10000., 10000.], "split_ratio": [0., 2.],
        }))

    def test_parser_inclusive_boundary_and_future_dates(self):
        document = self.document([
            ['2026/10/09', '保証', ' 7183 ', 'スタンダード', '株式併合'],
            ['2026/10/19', '将来', '5484', 'スタンダード', '株式併合'],
            ['2026/10/08', '英字', ' 123a ', 'グロース', '株式併合'],
        ])
        before = parse_jpx_delisted_symbols(document, '2026-10-08')
        today = parse_jpx_delisted_symbols(document, '2026-10-09')
        self.assertEqual([row['code'] for row in before], ['123A'])
        self.assertEqual([row['code'] for row in today], ['123A', '7183'])

    def test_parser_rejects_missing_header_empty_and_malformed_rows(self):
        valid = self.document([['2026/10/09', '保証', '7183', '市場', '理由']])
        documents = [b'<html>unavailable</html>', self.document([]),
                     valid.replace('上場廃止日'.encode(), '別の日'.encode()),
                     self.document([['2026/99/09', '保証', '7183', '市場', '理由']]),
                     self.document([['2026/10/09', '保証', '71830', '市場', '理由']]),
                     self.document([['2026/10/09', '保証', '7183', '市場']]),
                     valid.replace(b'</table>', b'')]
        for document in documents:
            with self.subTest(document=document), self.assertRaises(ValueError):
                parse_jpx_delisted_symbols(document, '2026-10-09')

    def responses(self):
        supervision = ('<table><tr><th>指定年月日</th><th>銘柄名</th><th>コード</th><th>市場</th><th>解除</th><th>内容</th></tr>'
                       '<tr><td>2026/08/01</td><td>保証</td><td>7183</td>'
                       '<td>市場</td><td>-</td><td>上場廃止の決定・整理銘柄指定</td></tr></table>').encode()
        pages = {JPX_RESTRICTIONS_URL: supervision,
                 JPX_DELISTINGS_URL: self.document([
                     ['2026/10/09', '保証', '7183', '市場', '理由'],
                     ['2026/10/19', '将来', '5484', '市場', '理由'],
                 ], archives=True)}
        pages.update({f'https://www.jpx.co.jp/listing/stocks/delisted/archives-{2026-year:02d}.html':
                      self.document([[f'{year}/10/09', '過去', str(year), '市場', '理由']])
                      for year in range(2020, 2026)})
        pages[JPX_NEW_LISTINGS_URL] = self.listing_document('2026/10/01', '600A', archives=True)
        pages.update({f'https://www.jpx.co.jp/listing/stocks/new/00-archives-{2026-year:02d}.html':
                      self.listing_document(f'{year}/10/09', f'{year-2000:03d}A')
                      for year in range(2022, 2026)})
        return pages

    @staticmethod
    def listing_document(date, code, *, archives=False, approval='2025/10/01'):
        options = ''
        if archives:
            options = '<select class="backnumber">' + ''.join(
                f'<option value="{JPX_NEW_LISTINGS_URL if year == 2026 else f"/listing/stocks/new/00-archives-{2026-year:02d}.html"}">{year}年</option>'
                for year in range(2022, 2027)) + '</select>'
        first = ['上場日（上場承認日）', '会社名（注3）', 'コード', '会社概要', '確認書', '仮条件', '公募', '売買単位']
        second = ['市場区分', 'Iの部', 'CG報告書', '公募価格', '売出', '決算短信']
        primary = [f'{date} （{approval}）', '銀行', code, '', '', '-', '-', '100']
        secondary = ['プライム', '', '', '-', '-', '']
        rows = [first, second, primary, secondary]
        return (options + '<table>' + ''.join('<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
                                            for row in rows) + '</table>').encode()

    def test_fetch_combines_designation_and_yearly_hash_evidence(self):
        pages = self.responses()
        def get(url, **kwargs):
            return SimpleNamespace(content=pages[url], url=url, raise_for_status=lambda: None)
        with tempfile.TemporaryDirectory() as temporary, patch('weak_early_beta.restrictions.requests.get', side_effect=get):
            path = Path(temporary) / 'snapshot.json'
            rows = fetch_jpx_restricted_symbols('2026-10-09', path)
            payload = json.loads(path.read_text(encoding='utf-8'))
        today = next(row for row in rows if row['code'] == '7183')
        self.assertEqual(today['designation_date'], '2026-08-01')
        self.assertEqual(today['delisting_date'], '2026-10-09')
        self.assertNotIn('5484', {row['code'] for row in rows})
        self.assertEqual(payload['version'], 2)
        self.assertEqual([row['year'] for row in payload['delisting_sources']], list(range(2021, 2027)))
        self.assertTrue(all(len(row['source_sha256']) == 64 for row in payload['delisting_sources']))
        past = next(row for row in rows if row['code'] == '2021')
        self.assertEqual(past['designation_date'], past['delisting_date'])
        self.assertEqual(restricted_mask(pd.DataFrame({'symbol': ['2021', '2021'],
            'date': ['2021-10-08', '2021-10-09']}), [past]).tolist(), [False, True])

    def test_fetch_failure_never_uses_or_overwrites_saved_snapshot(self):
        for failure in ('http', 'malformed', 'unsafe_archive', 'missing_year', 'new_http', 'new_malformed', 'supervision'):
            pages = self.responses()
            if failure == 'unsafe_archive':
                pages[JPX_DELISTINGS_URL] = pages[JPX_DELISTINGS_URL].replace(
                    b'/listing/stocks/delisted/archives-01.html', b'https://evil.test/archives-01.html')
            elif failure == 'missing_year':
                pages[JPX_DELISTINGS_URL] = pages[JPX_DELISTINGS_URL].replace(b'2021', b'2020')
            elif failure == 'supervision':
                pages[JPX_RESTRICTIONS_URL] = b'<html>503</html>'
            def get(url, **kwargs):
                if url == JPX_NEW_LISTINGS_URL:
                    if failure == 'new_http':
                        raise requests.HTTPError('503')
                    if failure == 'new_malformed':
                        return SimpleNamespace(content=b'<html>error</html>', url=url, raise_for_status=lambda: None)
                if url.endswith('archives-01.html'):
                    if failure == 'http':
                        raise requests.HTTPError('503')
                    if failure == 'malformed':
                        return SimpleNamespace(content=b'<html>error</html>', url=url, raise_for_status=lambda: None)
                return SimpleNamespace(content=pages[url], url=url, raise_for_status=lambda: None)
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary, \
                    patch('weak_early_beta.restrictions.requests.get', side_effect=get):
                path = Path(temporary) / 'snapshot.json'
                path.write_bytes(b'prior evidence')
                with self.assertRaises((ValueError, requests.HTTPError)):
                    fetch_jpx_restricted_symbols('2026-10-09', path)
                self.assertEqual(path.read_bytes(), b'prior evidence')

    def test_universe_excludes_completed_only_and_preserves_tickers(self):
        universe = pd.DataFrame({'code': ['7183', '5484', '9999'],
                                 'name': ['保証', '将来', '現役'], 'ticker': ['7183.T', '5484.T', '9999.T']})
        restrictions = self.restrictions() + [{**self.restrictions()[0], 'code': '5484', 'delisting_date': '2026-10-19'}]
        before, _ = exclude_delisted_universe(universe, restrictions, '2026-10-08')
        active, excluded = exclude_delisted_universe(universe, restrictions, '2026-10-09')
        pd.testing.assert_frame_equal(before, universe)
        self.assertEqual(active.ticker.tolist(), ['5484.T', '9999.T'])
        self.assertEqual(excluded.code.tolist(), ['7183'])
        minimal, _ = exclude_delisted_universe(universe[['code', 'name']], restrictions, '2026-10-09')
        self.assertEqual(minimal.code.tolist(), ['5484', '9999'])

    def test_preserved_history_retains_units_basis_and_source_attrs(self):
        previous, current = self.prices(), self.prices('9999')
        previous.attrs['source_sha256'] = 'a' * 64
        current.attrs['source_revision_receipt'] = {'checked': True}
        combined, receipt = preserve_delisted_history(previous, current, self.restrictions(), '2026-10-09', 'a' * 64)
        pd.testing.assert_frame_equal(combined[combined.symbol.eq('7183')].reset_index(drop=True), previous)
        self.assertEqual(combined.attrs, current.attrs)
        self.assertEqual(receipt['retained_rows'], 2)
        self.assertEqual(receipt['retained_symbols'][0]['latest_session'], '2026-10-08')
        self.assertEqual(len(receipt['retained_symbols'][0]['rows_sha256']), 64)
        self.assertEqual(receipt['previous_source_sha256'], 'a' * 64)

    def test_history_rejects_bad_source_sha_and_post_delisting_prices(self):
        for bad in ('sha', 'mismatch', 'legacy', 'bad_source', 'after_delisting', 'live_delisted'):
            previous, current = self.prices(), self.prices('9999')
            digest = 'a' * 64
            if bad == 'sha': digest = 'invalid'
            if bad == 'mismatch': previous.attrs['source_sha256'] = 'b' * 64
            if bad == 'legacy': previous = previous.drop(columns='corporate_actions_version')
            if bad == 'bad_source': previous.loc[0, 'split_factor'] = -1
            if bad == 'after_delisting': previous.loc[1, 'date'] = pd.Timestamp('2026-10-09')
            if bad == 'live_delisted': current = self.prices()
            with self.subTest(bad=bad), self.assertRaises((ValueError, CorporateActionError)):
                preserve_delisted_history(previous, current, self.restrictions(), '2026-10-09', digest)

    def test_history_first_run_and_no_delisted_rows_need_no_hash(self):
        current = self.prices('9999')
        for previous, restrictions in ((None, self.restrictions()), (current, self.restrictions()),
                                       (current, []), (current, self.restrictions('2026-10-19'))):
            combined, receipt = preserve_delisted_history(previous, current, restrictions, '2026-10-09', None)
            pd.testing.assert_frame_equal(combined, current)
            self.assertEqual(receipt['retained_rows'], 0)

    def test_retention_does_not_extend_current_rolling_history(self):
        previous, current = self.prices(), self.prices('9999')
        previous.loc[0, 'date'] = pd.Timestamp('2020-10-07')
        current.loc[0, 'date'] = pd.Timestamp('2021-10-07')
        combined, receipt = preserve_delisted_history(previous, current, self.restrictions(), '2026-10-09', 'a' * 64)
        expected = previous.iloc[1:].reset_index(drop=True)
        pd.testing.assert_frame_equal(combined[combined.symbol.eq('7183')].reset_index(drop=True), expected)
        self.assertEqual(receipt['outside_current_window_rows'], 1)
        self.assertEqual(receipt['retained_rows'], 1)
        self.assertEqual(combined.date.min(), current.date.min())

    def test_same_code_relisting_releases_only_on_actual_listing_day(self):
        for as_of, should_exclude in [('2025-12-16', True), ('2025-12-17', False), ('2026-10-09', False)]:
            pages = self.responses()
            pages['https://www.jpx.co.jp/listing/stocks/delisted/archives-03.html'] = self.document([
                ['2023/09/28', '旧銀行', '8303', '市場', '理由']])
            pages['https://www.jpx.co.jp/listing/stocks/new/00-archives-01.html'] = self.listing_document('2025/12/17', '8303')
            def get(url, **kwargs):
                return SimpleNamespace(content=pages[url], url=url, raise_for_status=lambda: None)
            with self.subTest(as_of=as_of), tempfile.TemporaryDirectory() as temporary, \
                    patch('weak_early_beta.restrictions.requests.get', side_effect=get):
                path = Path(temporary) / 'snapshot.json'
                restrictions = fetch_jpx_restricted_symbols(as_of, path)
                active, _ = exclude_delisted_universe(pd.DataFrame({'code': ['8303']}), restrictions, as_of)
                self.assertEqual(active.empty, should_exclude)
                bank = next(row for row in restrictions if row['code'] == '8303')
                if not should_exclude:
                    self.assertEqual(bank['relisting_date'], '2025-12-17')
                    self.assertEqual(restricted_mask(pd.DataFrame({'symbol': ['8303'] * 3,
                        'date': ['2023-09-27', '2023-09-28', '2025-12-17']}), [bank]).tolist(), [False, True, False])
                    self.assertTrue(json.loads(path.read_text(encoding='utf-8'))['relisted_symbols'])

    def test_new_listing_parser_future_and_malformed_fail_closed(self):
        document = self.listing_document('2026/10/19', '5484', approval='2026/09/01')
        self.assertEqual(parse_jpx_new_listings(document, '2026-10-09'), [])
        self.assertEqual(parse_jpx_new_listings(document, '2026-10-19')[0]['listing_date'], '2026-10-19')
        for bad in (document.replace('上場日'.encode(), '承認日'.encode()), b'<html>503</html>',
                    document.replace(b'5484', b'invalid'), document.replace(b'2026/10/19', b'2026/99/19')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_jpx_new_listings(bad, '2026-10-09')

    def test_relisting_then_new_delisting_still_excludes_latest_event(self):
        older = {**self.restrictions('2023-09-28')[0], 'code': '8303', 'relisting_date': '2025-12-17'}
        latest = {**self.restrictions()[0], 'code': '8303'}
        active, _ = exclude_delisted_universe(pd.DataFrame({'code': ['8303']}), [older, latest], '2026-10-09')
        self.assertTrue(active.empty)

    def test_multiple_delisting_events_keep_matching_historical_audit(self):
        old = {**self.restrictions('2023-09-28')[0], 'code': '8303', 'designation_date': '2023-09-28',
               'relisting_date': '2025-12-17', 'source_url': 'https://www.jpx.co.jp/old-event'}
        new = {**self.restrictions()[0], 'code': '8303', 'source_url': 'https://www.jpx.co.jp/new-event'}
        ledger = pd.DataFrame({'symbol': ['8303'] * 3, 'signal_date': ['2024-01-01', '2025-12-17', '2026-10-09'],
                               'source_scope': ['FORWARD_CAUSAL'] * 3, 'detection_id': ['old', 'relisted', 'new']})
        with tempfile.TemporaryDirectory() as temporary:
            active, audit = quarantine_restricted_detections(ledger, [old, new], Path(temporary) / 'audit.csv')
        self.assertEqual(active.detection_id.tolist(), ['relisted'])
        self.assertEqual(audit.restriction_source_url.tolist(), [old['source_url'], new['source_url']])
        self.assertEqual(audit.restriction_designation_date.tolist(), ['2023-09-28', '2026-08-01'])

    def test_older_universe_code_with_missing_relisting_coverage_stops(self):
        old = {**self.restrictions('2021-09-28')[0], 'relisting_coverage_start_year': 2022}
        with self.assertRaisesRegex(ValueError, 'coverage'):
            exclude_delisted_universe(pd.DataFrame({'code': ['7183']}), [old], '2026-10-09')

    def test_preserved_string_basis_round_trips_with_current_timestamp_basis(self):
        previous, current = self.prices(), self.prices('9999')
        previous['basis_asof'] = previous['basis_asof'].dt.strftime('%Y-%m-%d')
        combined, _ = preserve_delisted_history(previous, current, self.restrictions(), '2026-10-09', 'a' * 64)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'daily.csv'
            combined.to_csv(path, index=False)
            roundtrip = normalize_daily(pd.read_csv(path, parse_dates=['date'], dtype={'symbol': str}))
        self.assertEqual(set(roundtrip.basis_asof), {pd.Timestamp('2026-10-08')})
        self.assertEqual(roundtrip[roundtrip.symbol.eq('7183')].actual_close.tolist(), [100., 50.])


    @patch('weak_early_beta.network.time.sleep')
    def test_transient_archive_failure_retries_only_that_page(self, sleep):
        pages = self.responses()
        failed_url = 'https://www.jpx.co.jp/listing/stocks/delisted/archives-05.html'
        seen = []

        def get(url, **kwargs):
            seen.append(url)
            if url == failed_url and seen.count(url) == 1:
                raise requests.ConnectionError('[WinError 10048] socket exhaustion')
            return SimpleNamespace(content=pages[url], url=url, raise_for_status=lambda: None)

        with tempfile.TemporaryDirectory() as temporary, patch('weak_early_beta.restrictions.requests.get', side_effect=get):
            path = Path(temporary) / 'snapshot.json'
            rows = fetch_jpx_restricted_symbols('2026-10-09', path)
            self.assertTrue(rows)
            self.assertTrue(path.exists())
        self.assertEqual(seen.count(JPX_RESTRICTIONS_URL), 1)
        self.assertEqual(seen.count(JPX_DELISTINGS_URL), 1)
        self.assertEqual(seen.count(failed_url), 2)
        sleep.assert_called_once_with(1)

    @patch('weak_early_beta.network.time.sleep')
    def test_transport_exhaustion_retains_previous_snapshot(self, sleep):
        failure = requests.ConnectionError('[WinError 10048] socket exhaustion')
        with tempfile.TemporaryDirectory() as temporary, patch('weak_early_beta.restrictions.requests.get', side_effect=failure) as get:
            path = Path(temporary) / 'snapshot.json'
            path.write_text('original evidence', encoding='utf-8')
            with self.assertRaises(requests.ConnectionError) as caught:
                fetch_jpx_restricted_symbols('2026-10-09', path)
            self.assertIs(caught.exception, failure)
            self.assertEqual(path.read_text(encoding='utf-8'), 'original evidence')
        self.assertEqual(get.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == '__main__':
    unittest.main()
