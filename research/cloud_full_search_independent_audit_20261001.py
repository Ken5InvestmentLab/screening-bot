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

def main():
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
    # Audit the first completed fold from each learner/size/objective/feature
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
        key = (cfg['learner'], cfg['size'], cfg['objective'], cfg['features'])
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
            checks={'n':len(ids),'mean_pct':values.mean()*100,'median_pct':np.median(values)*100,'win_pct':(values>0).mean()*100,
                    'loss10_pct':(values<=-.1).mean()*100,'cash_pl_yen':np.dot(values,cost),
                    'cash_net02_yen':np.dot(values-.002,cost),'top3_ex_mean_pct':np.sort(values)[:-3].mean()*100 if len(values)>3 else None}
            for name, actual in checks.items():
                expected=metric.get(name)
                if actual is None and expected is None: continue
                if not np.isclose(actual,expected,atol=1e-7,rtol=0,equal_nan=True): raise AssertionError(f'final metric mismatch: {name}')
            final_checks.append({'candidate':metric['candidate'],'year':metric['year'],'trade_rows':len(ids)})
    result={'status':'PASS','receipt_count':len(verified),'independent_model_replays':probes,'final_trade_reaggregations':final_checks,
            'audit_script_sha256':digest(Path(__file__)),'limits':'Score/CDF replay sampled by learner/size/objective/features; no proof of fills or profitability; 2026 already viewed.'}
    (HERE/'independent_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','receipts':len(verified),'model_replays':len(probes),'final_reaggregations':len(final_checks)}))

if __name__=='__main__': main()
