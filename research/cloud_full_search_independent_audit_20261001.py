"""Independent saved-model score/CDF and final-trade reaggregation audit."""
from pathlib import Path
import hashlib
import json
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT/'research/cloud_full_search_20261001'
CACHE = ROOT/'.cache/cloud_full_search_v2_20261001'
OLD = ROOT/'.cache/cloud_cap_corrected_v2_20261001'
sys.path.insert(0, str(ROOT))
from weak_early_beta.model import base

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def reaggregate(values, cost, bought, sold):
    """Independent arithmetic, including zero rows and conservative cash use."""
    n = len(values)
    if not n:
        return {'n': 0, **dict.fromkeys(('mean_pct', 'median_pct', 'win_pct', 'loss10_pct', 'top3_ex_mean_pct'))}
    ordered = np.sort(values)
    peak = used = 0.0
    events = [(d, 0, c) for d, c in zip(bought, cost)] + [(d, 1, -c) for d, c in zip(sold, cost)]
    for _, _, change in sorted(events):
        used += change
        peak = max(peak, used)
    return {'n': n, 'mean_pct': np.sum(values)/n*100, 'median_pct': np.median(values)*100,
            'win_pct': np.count_nonzero(values>0)/n*100, 'loss10_pct': np.count_nonzero(values<=-.1)/n*100,
            'top3_ex_mean_pct': np.sum(ordered[:-3])/(n-3)*100 if n>3 else None,
            'net02_mean_pct': np.sum(values)/n*100-.2, 'net05_mean_pct': np.sum(values)/n*100-.5,
            'cash_pl_yen': np.sum(values*cost), 'cash_net02_yen': np.sum((values-.002)*cost),
            'required_capital_yen': peak}

def check_metrics(actual, expected):
    for name, value in actual.items():
        target = expected.get(name)
        if value is None and target is None:
            continue
        if value is None or target is None or not np.isclose(value, target, atol=1e-7, rtol=0):
            raise AssertionError(f'independent metric mismatch: {name}')

def main():
    audit_digest = digest(Path(__file__))
    info = json.loads((CACHE/'prepared.json').read_text(encoding='utf-8'))
    for name, expected in info['hashes'].items():
        if digest(ROOT/name) != expected: raise AssertionError(f'changed source: {name}')
    for name, expected in info['output_hashes'].items():
        if digest(CACHE/name) != expected: raise AssertionError(f'changed outcomes: {name}')
    f = pd.read_pickle(OLD/'rows.pkl')
    x = np.load(OLD/'features.npy', mmap_mode='r')
    aug = np.load(CACHE/'augmented.npy', mmap_mode='r')
    r = np.load(CACHE/'outcomes.npy', mmap_mode='r')
    entry = np.load(CACHE/'entry_prices.npy', mmap_mode='r')
    sessions = np.load(CACHE/'scheduled_sessions.npy', mmap_mode='r')
    which = np.load(CACHE/'session_index.npy', mmap_mode='r')
    def matrix(ix, cfg):
        z = np.asarray(x[ix], dtype=np.float32)
        if cfg['features'] == 'price_market':
            z = z[:, [i for i, k in enumerate(base.FEATURES) if k not in {'volr5','volr10','volr20','volr40','volz20','log_dv'}]]
        elif cfg['features'] == 'augmented': z = np.column_stack([z, aug[ix]])
        return z
    receipts = sorted((CACHE/'fits').glob('*/*.json'))
    verified, probes = [], []
    # Audit the first completed fold from each learner/size/objective/feature/horizon
    # family. Every receipt/file hash is checked; expensive reference replay is
    # sampled, and its exact scope is reported.
    seen = set()
    for path in receipts:
        v = json.loads(path.read_text(encoding='utf-8')); cfg = v['config']
        if v['contract'] != info['hashes']: raise AssertionError('mixed model contracts')
        for suffix, expected in v['files'].items():
            if digest(path.with_suffix('.'+suffix)) != expected: raise AssertionError('changed saved model/predictions')
        if v['max_training_exit'] >= v['month']+'-01': raise AssertionError('future training label')
        verified.append(v['config']['id']+'/'+v['month'])
        key = (cfg['learner'], cfg['size'], cfg['objective'], cfg['features'], cfg['horizon'])
        if key in seen: continue
        seen.add(key)
        with np.load(path.with_suffix('.npz')) as z:
            pred, expected_score, expected_cdf = z['row_id'], z['score'], z['cdf']
        if not len(pred): continue
        pred, expected_score, expected_cdf = pred[:12], expected_score[:12], expected_cdf[:12]
        eligible = (f.source_usable & f.previous_source_usable & f.feature_complete & f.previous_actual_volume.ge(10000) & f.actual_volume.ge(5000) & f.actual_close.ge(20)).to_numpy()
        if cfg['cap']: eligible &= f.previous_actual_close.le(cfg['cap']).to_numpy()
        h = cfg['horizon']-1
        train = np.flatnonzero(eligible & np.isfinite(r[:,2*h+1]) & (sessions[which,h] < np.datetime64(v['month']+'-01')))
        if len(train) != v['train_rows']: raise AssertionError('training count mismatch')
        m = joblib.load(path.with_suffix('.joblib'))
        with threadpool_limits(limits=4):
            tx, px = matrix(train,cfg), matrix(pred,cfg)
            if cfg['objective']=='return': ref, scored=m.predict(tx),m.predict(px)
            else: ref, scored=m.predict_proba(tx)[:,1],m.predict_proba(px)[:,1]
        independently_ranked = np.searchsorted(np.sort(ref.astype(float)), scored.astype(float), side='right')/len(ref)
        if not np.allclose(scored,expected_score,rtol=0,atol=1e-9): raise AssertionError('saved score does not replay')
        if not np.allclose(independently_ranked,expected_cdf,rtol=0,atol=1e-12): raise AssertionError('saved training CDF does not replay')
        probes.append({'config':cfg['id'],'month':v['month'],'scores':len(pred),'training_reference_rows':len(train)})
        del m, tx, px, ref
    # Independently reaggregate each completed DEV winner. Selection uses the
    # frozen policy implementation; this checks arithmetic rather than claiming
    # a second, independent detection algorithm.
    sys.path.insert(0, str(HERE))
    from search import choose
    from common import SCREEN_MONTHS
    from weak_early_beta.restrictions import restricted_mask
    from weak_early_beta.entry_feasibility import performance_eligible
    restriction = json.loads((CACHE/'restriction_snapshot.json').read_text(encoding='utf-8'))['symbols']
    ordinal = {d: i for i, d in enumerate(np.sort(f.date.unique()))}
    dev_checks = []
    for stage in ('screen', 'refined'):
        months = SCREEN_MONTHS if stage=='screen' else [str(m) for m in pd.period_range('2023-01','2024-12',freq='M')]
        for path in sorted((CACHE/stage).glob('*.json')):
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved['contract'] != info['hashes']: raise AssertionError('mixed DEV contract')
            winner = saved['best']
            if winner is None: continue
            parts = []
            for month in months:
                with np.load(CACHE/'fits'/winner['config']['id']/f'{month}.npz') as pred:
                    pool = f.loc[pred['row_id']].copy()
                    pool['row_id'], pool['cdf'], pool['score'] = pred['row_id'], pred['cdf'], pred['score']
                    parts.append(pool)
            pool = pd.concat(parts, ignore_index=True)
            pool = pool[~restricted_mask(pool, restriction)]
            ids = choose(pool, winner['policy'], ordinal)
            ids = ids[np.isfinite(r[ids]).all(axis=1) & (sessions[which[ids],9] <= np.datetime64('2024-12-31'))]
            eligible = f.loc[ids, ['symbol','date']].copy()
            eligible['entry_date'] = sessions[which[ids],0]
            ids = performance_eligible(eligible, CACHE/'entry_feasibility_exclusions.csv').index.to_numpy(np.int64)
            day, quote = winner['endpoint'].split('_'); h = int(day[1:])-1; col = 2*h+(quote=='close')
            check_metrics(reaggregate(np.asarray(r[ids,col]), np.asarray(entry[ids])*100,
                                      sessions[which[ids],0], sessions[which[ids],h]), winner['metrics'])
            if f.loc[ids,'date'].duplicated().any(): raise AssertionError('duplicate DEV policy day')
            dev_checks.append({'stage':stage,'config':winner['config']['id'],'endpoint':winner['endpoint'],'trade_rows':len(ids)})
    final = json.loads((CACHE/'final.json').read_text(encoding='utf-8')) if (CACHE/'final.json').exists() else None
    final_checks = []
    if final:
        for metric in final['candidates']:
            p = CACHE/f"candidate{metric['candidate']}_{metric['year']}_trades.csv"
            trades = pd.read_csv(p,dtype={'symbol':str},parse_dates=['signal_date'])
            ids = trades.row_id.to_numpy(np.int64)
            day, quote = metric['endpoint'].split('_'); col=2*(int(day[1:])-1)+(quote=='close')
            values=np.asarray(r[ids,col]); cost=np.asarray(entry[ids])*100
            if not np.isfinite(r[ids]).all(): raise AssertionError('mixed endpoint cohorts')
            if trades.signal_date.duplicated().any(): raise AssertionError('more than one stock per policy day')
            if not np.array_equal(trades.symbol.to_numpy(), f.loc[ids,'symbol'].astype(str).to_numpy()): raise AssertionError('trade CSV symbol mismatch')
            if not np.array_equal(trades.signal_date.to_numpy(), f.loc[ids,'date'].to_numpy()): raise AssertionError('trade CSV signal date mismatch')
            h = int(day[1:])-1
            checks=reaggregate(values,cost,sessions[which[ids],0],sessions[which[ids],h])
            check_metrics(checks, metric)
            if not np.allclose(trades.gross_return, values, atol=1e-12, rtol=0): raise AssertionError('trade CSV return mismatch')
            if not np.allclose(trades.entry_cost_yen, cost, atol=1e-7, rtol=0): raise AssertionError('trade CSV entry cost mismatch')
            final_checks.append({'candidate':metric['candidate'],'year':metric['year'],'trade_rows':len(ids)})
    if digest(Path(__file__)) != audit_digest: raise AssertionError('audit script changed during execution')
    result={'status':'PASS','receipt_count':len(verified),'independent_model_replays':probes,'dev_winner_reaggregations':dev_checks,'final_trade_reaggregations':final_checks,
            'audit_script_sha256':audit_digest,'limits':'Score/CDF replay sampled by learner/size/objective/features/horizon. DEV winner arithmetic independently reaggregated; selection uses frozen implementation. No proof of fills or profitability; previously viewed periods are reused data.'}
    (HERE/'independent_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','receipts':len(verified),'model_replays':len(probes),'dev_reaggregations':len(dev_checks),'final_reaggregations':len(final_checks)}))

if __name__=='__main__': main()
