"""Prepare scheduled actual-lot outcomes without rebuilding completed fits."""
from __future__ import annotations
import json
import sys
import time
import numpy as np
import pandas as pd
from common import CACHE, OLD, ROOT, DAILY, FEATURES, ENDPOINTS, contract_hashes, write_json, sha, locked, recipes
from weak_early_beta.bank_calendar import add_bank_business_days
from weak_early_beta.trade_basis import build_trade_economics, UnsupportedFractionalShares

def scheduled_outcomes(p, actions):
    if p.duplicated(['symbol', 'date']).any(): raise ValueError('duplicate quote identities')
    dates = np.sort(p.date.unique())
    sessions = np.array([[np.datetime64(add_bank_business_days(pd.Timestamp(day).date(), h)) for h in range(1, 11)] for day in dates])
    which = np.searchsorted(dates, p.date.to_numpy())
    idx = pd.MultiIndex.from_frame(p[['symbol', 'date']])
    n = len(p)
    target_indices = np.full((n, 10), -1, dtype=np.int32)
    for h in range(10):
        target_indices[:, h] = idx.get_indexer(pd.MultiIndex.from_arrays([p.symbol, sessions[which, h]]))
    entry = target_indices[:, 0]
    good_entry = entry >= 0
    entry_price = np.full(n, np.nan)
    entry_factor = np.full(n, np.nan)
    aopen = p.actual_open.to_numpy(float)
    aclose = p.actual_close.to_numpy(float)
    sf = p.split_factor.to_numpy(float)
    source = p.source_usable.to_numpy(bool)
    good_entry[good_entry] &= source[entry[good_entry]]
    entry_price[good_entry] = aopen[entry[good_entry]]
    entry_factor[good_entry] = sf[entry[good_entry]]
    out = np.full((n, 20), np.nan)
    earliest_fraction = np.full(n, np.datetime64('2260-01-01'), dtype='datetime64[ns]')
    symbol_rows = p.groupby('symbol', sort=False).indices
    # Check every intermediate event, including off-session journal events.
    for symbol, events in actions.groupby('symbol', sort=False):
        rows = symbol_rows.get(symbol, np.array([], dtype=np.int64))
        es = sessions[which[rows], 0]
        held = np.full(len(rows), 100.0)
        for ev in events.sort_values('effective_date').itertuples(index=False):
            day = np.datetime64(ev.effective_date)
            inside = (es < day) & (sessions[which[rows], 9] >= day)
            held[inside] *= ev.ratio
            invalid = inside & ((held <= 0) | (np.abs(held - np.round(held)) > 1e-8))
            bad = rows[invalid]
            earliest_fraction[bad] = np.minimum(earliest_fraction[bad], day)
    for h in range(10):
        exit_rows = target_indices[:, h]
        valid = good_entry & (exit_rows >= 0)
        valid[valid] &= source[exit_rows[valid]]
        valid &= sessions[which, h] < earliest_fraction
        quantity = np.full(n, np.nan)
        quantity[valid] = 100 * entry_factor[valid] / sf[exit_rows[valid]]
        valid &= np.isfinite(quantity) & (quantity > 0) & (np.abs(quantity - np.round(quantity)) < 1e-8)
        for q, values in enumerate((aopen, aclose)):
            out[valid, 2*h+q] = values[exit_rows[valid]] * quantity[valid] / (entry_price[valid]*100) - 1
    out[np.abs(out) < 1e-12] = 0
    return out, entry_price, sessions, which, target_indices

def augmented(x):
    at = {name: i for i, name in enumerate(FEATURES)}
    a = lambda name: x[:, at[name]].astype(np.float64)
    eps = 1e-4
    values = [a('ret5')/np.maximum(a('atr14p'), eps),
              a('body_pct')/np.maximum(a('range_pct'), eps),
              a('lower_wick')/np.maximum(a('range_pct'), eps),
              a('ret10')-a('ret40'), a('ma5_gap')-a('ma20_gap'),
              a('dd20')/np.maximum(a('atr14p'), eps),
              a('ret5')-a('med_ret5'), np.log1p(np.maximum(a('volr20'), 0))]
    return np.column_stack([np.nan_to_num(np.clip(v, -100, 100), nan=0) for v in values]).astype(np.float32)

def prepare():
    if (CACHE/'prepared.json').exists():
        from common import verify_contract
        verify_contract(); print('prepare already verified', flush=True); return
    t = time.time()
    old = json.loads((OLD/'prepared.json').read_text(encoding='utf-8'))
    if old['source_sha256'] != sha(DAILY): raise RuntimeError('changed normalized corpus')
    origins = {}
    for source, name in ((ROOT/'weak_early_beta/state/entry_feasibility_exclusions.csv', 'entry_feasibility_exclusions.csv'),
                         (ROOT/'weak_early_beta/state/jpx_restricted_symbols_latest.json', 'restriction_snapshot.json')):
        destination = CACHE/name
        # Preserve a captured snapshot even if initial preparation was interrupted.
        if not destination.exists(): destination.write_bytes(source.read_bytes())
        origins[name] = {'captured_from': source.relative_to(ROOT).as_posix(), 'captured_sha256': sha(destination)}
    hashes = contract_hashes()
    print('prepare: load immutable metadata/quotes', flush=True)
    f = pd.read_pickle(OLD/'rows.pkl')
    p = pd.read_pickle(OLD/'prices.pkl')
    if not f[['symbol', 'date']].equals(p[['symbol', 'date']]): raise RuntimeError('feature/price row order mismatch')
    actions = pd.read_csv(OLD/'actions.csv', dtype={'symbol': str}, parse_dates=['effective_date'])
    if actions.duplicated(['symbol', 'effective_date']).any() or not np.isfinite(actions.ratio).all() or actions.ratio.le(0).any():
        raise ValueError('invalid action journal')
    print('prepare: scheduled outcomes and intermediate action quantities', flush=True)
    outcomes, entry, dates, which, positions = scheduled_outcomes(p, actions)
    print('prepare: save arrays and independently audit economics', flush=True)
    np.save(CACHE/'outcomes.npy', outcomes)
    np.save(CACHE/'entry_prices.npy', entry)
    np.save(CACHE/'scheduled_sessions.npy', dates)
    np.save(CACHE/'session_index.npy', which)
    x = np.load(OLD/'features.npy', mmap_mode='r')
    np.save(CACHE/'augmented.npy', augmented(x))
    # Independent scalar trade calculator comparison, weighted toward actions.
    impacted = f.index[f.symbol.isin(actions.symbol.unique())]
    valid = np.flatnonzero(np.isfinite(outcomes).all(axis=1))
    probes = np.unique(np.concatenate([valid[::max(len(valid)//120, 1)][:120],
                                      impacted[::max(len(impacted)//120, 1)][:120]]))
    checked = 0
    for i in probes:
        if positions[i, 0] < 0: continue
        symbol = str(f.iloc[i].symbol)
        events = actions[actions.symbol.eq(symbol)]
        for h in (1, 5, 10):
            j = positions[i, h-1]
            if j < 0 or not p.iloc[j].source_usable: continue
            ep, ex = pd.Timestamp(dates[which[i], 0]), pd.Timestamp(dates[which[i], h-1])
            for q in ('open', 'close'):
                col = 2*(h-1)+(q == 'close')
                try:
                    result = build_trade_economics(ep, ex, entry[i], p.iloc[j][f'actual_{q}'], events, symbol=symbol)
                except UnsupportedFractionalShares:
                    if np.isfinite(outcomes[i, col]): raise AssertionError('fractional outcome accepted')
                    continue
                expected = result['gross_return']
                if not np.isclose(expected, outcomes[i, col], equal_nan=True, atol=1e-10, rtol=0):
                    raise AssertionError(f'outcome scalar mismatch: {i}/{h}/{q}')
                checked += 1
    if contract_hashes() != hashes: raise RuntimeError('inputs changed during preparation')
    import sklearn, xgboost
    write_json(CACHE/'prepared.json', dict(identity='CLOUD_FULL_SEARCH_V1', hashes=hashes,
               versions=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__, sklearn=sklearn.__version__, xgboost=xgboost.__version__),
               rows=len(f), configurations=recipes(), independent_scalar_probes=checked, frozen_policy_origins=origins,
               complete_20_endpoints=int(np.isfinite(outcomes).all(axis=1).sum()), seconds=round(time.time()-t, 2),
               output_hashes={n: sha(CACHE/n) for n in ('outcomes.npy', 'entry_prices.npy', 'scheduled_sessions.npy', 'session_index.npy', 'augmented.npy')}))
    print(json.dumps({'prepared_rows': len(f), 'scalar_probes': checked, 'seconds': round(time.time()-t, 2)}), flush=True)

if __name__ == '__main__':
    with locked(): prepare()
