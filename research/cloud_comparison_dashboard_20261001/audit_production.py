"""Read-only comparison with a frozen local/public production snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from weak_early_beta.entry_feasibility import performance_eligible
from weak_early_beta.ledger import read_ledger
from weak_early_beta.metrics import build_metrics, combined_detections


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', action='store_true', required=True,
                        help='Explicitly capture a new read-only production reference')
    parser.parse_args()
    paths = [ROOT / 'weak_early_beta/state/detections.csv', ROOT / 'weak_early_beta/state/metrics.csv',
             ROOT / 'weak_early_beta/state/entry_feasibility_exclusions.csv']
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    ledger = read_ledger()
    saved = pd.read_csv(paths[1])
    computed = build_metrics(ledger, as_of=pd.Timestamp('2026-10-01'))
    key = ['selector_id', 'period']
    saved = saved.set_index(key).sort_index()
    computed = computed.set_index(key).sort_index()
    if not saved.index.equals(computed.index):
        raise ValueError('Production metric keys differ from read-only ledger aggregation')
    numeric = ['n', 'pending', 'mean_pct', 'median_pct', 'win_pct', 'minus10_pct',
               'top3_ex_mean_pct', 'cash_pl_100_yen', 'required_capital_yen']
    for column in numeric:
        if not saved[column].isna().equals(computed[column].isna()) or not ((saved[column] - computed[column]).abs().fillna(0) < 1e-6).all():
            raise ValueError(f'Production metrics disagree: {column}')
    public = json.loads((HERE / 'production_public_snapshot.json').read_text(encoding='utf-8'))
    for field, selector in [('uniqueRows', 'all_conditions_unique'), ('stackedRows', 'all_conditions_stacked')]:
        for row in public[field][1:]:
            period = '2023-2026' if '合計' in row[0] else row[0]
            local = saved.loc[(selector, period)]
            if int(row[1]) != int(local['n']) or int(row[2]) != int(local['pending']):
                raise ValueError('Live public table disagrees with saved production metrics')
            for column, index in [('cash_pl_100_yen', 3), ('required_capital_yen', 4), ('capital_return_pct', 5),
                                  ('simple_annualized_pct', 6), ('mean_pct', 7), ('median_pct', 8), ('win_pct', 9),
                                  ('plus10_pct', 10), ('plus20_pct', 11), ('minus10_pct', 12), ('minus20_pct', 13),
                                  ('max_up_pct', 14), ('max_down_pct', 15)]:
                displayed = float(row[index].replace('¥', '').replace(',', '').strip('%+'))
                tolerance = .5001 if column in ('cash_pl_100_yen', 'required_capital_yen') else .0051
                if abs(displayed - local[column]) > tolerance:
                    raise ValueError(f'Live public value disagrees: {selector}/{period}/{column}')
    research_path = ROOT / '.cache/cloud_cap_corrected_v2_20261001/trades_cap1000.csv'
    research = pd.read_csv(research_path, dtype={'symbol': str})
    summary = json.loads((ROOT / 'research/cloud_cap_comparison_20261001/summary.json').read_text(encoding='utf-8'))
    research = performance_eligible(research)
    research = research[~research.comparison_restricted]
    research = research[~pd.to_datetime(research.signal_date).dt.strftime('%Y-%m-%d').isin(summary['common_day_excluded_calendar'])]
    research = combined_detections(research)
    research = research[research.gross_return.notna()]
    production = combined_detections(performance_eligible(ledger))
    production = production[production.gross_return.notna()]
    identities = lambda frame: set(zip(pd.to_datetime(frame.signal_date).dt.strftime('%Y-%m-%d'), frame.symbol.astype(str)))
    pids, rids = identities(production), identities(research)
    if len(pids) != 248 or len(rids) != 252:
        raise ValueError('Unexpected compared cohort size')
    pmap = dict(zip(zip(pd.to_datetime(production.signal_date).dt.strftime('%Y-%m-%d'), production.symbol.astype(str)), production.gross_return))
    rmap = dict(zip(zip(pd.to_datetime(research.signal_date).dt.strftime('%Y-%m-%d'), research.symbol.astype(str)), research.gross_return))
    rows = []
    for (mode, period), row in saved.iterrows():
        rows.append({'mode': mode, 'period': 'ALL' if period == '2023-2026' else period,
                     **{column: int(row[column]) if column in ('n', 'pending') else float(row[column]) for column in numeric}})
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    if before != after:
        raise ValueError('Production files changed during read-only comparison')
    output = {'status': 'PASS', 'verified_date_jst': '2026-10-01', 'public_updated_label': public['updated'],
              'public_url': public['url'], 'production_sources_sha256': before,
              'public_snapshot_sha256': sha(HERE / 'production_public_snapshot.json'),
              'research_trades_sha256': sha(research_path), 'metrics': rows,
              'completed_unique_identities': {'production': len(pids), 'research': len(rids), 'shared': len(pids & rids),
                  'production_only': len(pids - rids), 'research_only': len(rids - pids),
                  'shared_returns_differ': sum(abs(pmap[k] - rmap[k]) > 1e-8 for k in pids & rids)},
              'source_scope_rows': ledger.source_scope.value_counts().to_dict(),
              'same_production_baseline': False, 'no_production_mutations': True,
              'checks': ['35 metrics recalculated read-only from saved ledger', 'live public unique/stacked tables match saved metrics',
                         'production file hashes unchanged', 'actual detection identity overlap counted'],
              'interpretation': 'This corrected retraining comparison is not a reproduction of the frozen published production history. Differences are not attributed to the price cap alone.'}
    (HERE / 'production_reference.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'PASS', 'identities': output['completed_unique_identities']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
