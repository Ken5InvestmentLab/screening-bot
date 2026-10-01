"""A genuine production raw-to-feature-to-model replay for one frozen month."""
from __future__ import annotations
import gc
import json
import time
import numpy as np
import pandas as pd
from common import CACHE, OLD, DAILY, FEATURES, production, write_json, sha, verify_contract, locked, lease_ok

def replay(month='2025-01'):
    info = verify_contract()
    if not lease_ok(): raise RuntimeError('usage lease missing/expired')
    t = time.time()
    print('parity: production raw-to-feature preparation', flush=True)
    raw = pd.read_csv(DAILY, dtype={'symbol': str}, parse_dates=['date'], low_memory=False)
    # Preserve the entire as-of action declaration during normalization. A
    # later priced event may be needed to validate earlier stored factors.
    # Restrict evaluated quotes/labels AFTER causal features, not the journal.
    eligible, labeled = production.prepare_live(raw)
    eligible = eligible[eligible.date.le('2026-09-30')].copy()
    labeled = labeled[labeled.target_end_date.le('2026-09-30')].copy()
    labeled['future_rank'] = labeled.groupby('date').target5_no.rank(pct=True, method='average')
    labeled['y_top025'] = (labeled.future_rank >= .9975).astype(int)
    del raw; gc.collect()
    f = pd.read_pickle(OLD/'rows.pkl')
    x = np.load(OLD/'features.npy', mmap_mode='r')
    common = f.source_usable & f.previous_source_usable & f.feature_complete & f.previous_actual_volume.ge(10000) & f.actual_volume.ge(5000) & f.actual_close.ge(20) & f.previous_actual_close.le(1000)
    old_ids = pd.MultiIndex.from_frame(f.loc[common, ['symbol', 'date']])
    live_ids = pd.MultiIndex.from_frame(eligible[['symbol', 'date']])
    if not old_ids.equals(live_ids): raise AssertionError('production/cache eligibility differs')
    ix = f.index[common].to_numpy()
    expected = x[ix]
    observed = eligible[FEATURES].to_numpy(dtype=np.float32)
    feature_equal = np.array_equal(expected, observed, equal_nan=True)
    if not feature_equal:
        delta = np.abs(expected.astype(float)-observed)
        write_json(CACHE/'parity_failure.json', {'feature_equal': False, 'differing_cells': int(np.count_nonzero(expected != observed)), 'max_abs': float(np.nanmax(delta)), 'per_feature': dict(zip(FEATURES, np.nanmax(delta, axis=0).tolist()))})
        raise AssertionError('production/cache float32 features differ; diagnose before searching')
    old_lab = f.loc[common & f.target5_no.notna() & f.target_end_date.notna(), ['symbol', 'date', 'target5_no', 'target_end_date']]
    if not old_lab[['symbol', 'date']].reset_index(drop=True).equals(labeled[['symbol', 'date']].reset_index(drop=True)):
        raise AssertionError('labeled identities differ')
    old_y = (old_lab.groupby('date').target5_no.rank(pct=True, method='average') >= .9975).to_numpy()
    if not np.array_equal(old_y, labeled.y_top025.to_numpy(bool)): raise AssertionError('teacher labels differ')
    del expected, observed, f; gc.collect()
    if not lease_ok(): raise RuntimeError('lease expired before fit')
    tail = production.causal_tail_for_month(eligible, labeled, pd.Period(month))
    selected = production.shadow.select_candidates(tail)
    old_selected = pd.read_csv(OLD/f'selected_cap1000_{month}.csv', dtype={'symbol': str}, parse_dates=['date'])
    keys = ['date', 'symbol', 'selector']
    a = selected[keys].sort_values(keys).reset_index(drop=True)
    b = old_selected[keys].sort_values(keys).reset_index(drop=True)
    if not a.equals(b): raise AssertionError('fresh production/cache selected identities differ')
    a.to_csv(CACHE/'parity_selected.csv', index=False, date_format='%Y-%m-%d')
    if verify_contract()['hashes'] != info['hashes']: raise RuntimeError('source changed during parity')
    write_json(CACHE/'parity.json', {'status': 'PASS', 'month': month, 'eligible_rows': len(eligible), 'labeled_rows': len(labeled), 'feature_float32_equal': True, 'teacher_equal': True, 'tail_rows': len(tail), 'selected_rows': len(a), 'selected_sha256': sha(CACHE/'parity_selected.csv'), 'seconds': round(time.time()-t, 2), 'limits': 'One frozen month, same normalized input. Not a replay of the old canonical production lineage or proof of profitability.'})
    print(json.dumps({'parity': 'PASS', 'month': month, 'seconds': round(time.time()-t, 2)}), flush=True)

if __name__ == '__main__':
    with locked(): replay()
