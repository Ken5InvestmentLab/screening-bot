"""Causal, resumable staged model and policy search. No production writes."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gc
import itertools
import json
from pathlib import Path
import time
import joblib
import numpy as np
import pandas as pd
from common import CACHE, OLD, HERE, ROOT, FEATURES, ENDPOINTS, SCREEN_MONTHS, production, recipes, write_json, sha, verify_contract, locked, lease_ok
from weak_early_beta.restrictions import restricted_mask
from weak_early_beta.entry_feasibility import performance_eligible

def policies(full=False):
    gates = (.90, .95, .99, .995, .999) if full else (.95, .99, .999)
    ranks = ('score', 'volume', 'body', 'blend', 'fusion') if full else ('score', 'volume', 'body')
    for gate, rank, market, retmax, medmin, vol, cooldown in itertools.product(
            gates, ranks, (None, 0, -.01) if full else (None, 0),
            (None, 0, .2, .5735294117647058) if full else (None,),
            (None, -.01) if full else (None,), (1, 2) if full else (1,), (0, 5) if full else (0,)):
        yield dict(gate=gate, rank=rank, market=market, retmax=retmax, medmin=medmin, vol=vol, cooldown=cooldown)

def stats(values, costs=None, entry=None, exit=None):
    r = np.asarray(values, dtype=float)
    if not len(r): return dict(n=0, mean_pct=None, median_pct=None, win_pct=None, loss10_pct=None, top3_ex_mean_pct=None, utility=-1e30)
    mean, median, win, loss = r.mean()*100, np.median(r)*100, (r>0).mean()*100, (r<=-.1).mean()*100
    top3 = np.sort(r)[:-3].mean()*100 if len(r)>3 else np.nan
    result = dict(n=len(r), mean_pct=mean, median_pct=median, win_pct=win, loss10_pct=loss,
                  top3_ex_mean_pct=top3, min_pct=r.min()*100, net02_mean_pct=mean-.2, net05_mean_pct=mean-.5,
                  utility=top3+.25*median+.05*(win-50)-.1*loss)
    if costs is not None:
        result['cash_pl_yen'] = float(np.dot(r, costs))
        result['cash_net02_yen'] = float(np.dot(r-.002, costs))
        # Conservative capital: an opening buy needs funds before a same-day sell.
        events = [(d, 0, c) for d, c in zip(entry, costs)] + [(d, 1, -c) for d, c in zip(exit, costs)]
        level = peak = 0
        for _, _, change in sorted(events): level += change; peak = max(peak, level)
        result['required_capital_yen'] = float(peak)
    return result

def robust(m):
    return (m['n'] >= 40 and m.get('n2023', 0) >= 15 and m.get('n2024', 0) >= 15
            and m['top3_ex_mean_pct'] is not None and m['top3_ex_mean_pct'] > 0
            and m['median_pct'] >= 0 and m['loss10_pct'] <= 30 and m['net02_mean_pct'] > 0)

def choose_one(day, rank):
    if day.empty: return None
    if rank == 'score': cols, ascending = ['cdf', 'score'], [False, False]
    elif rank == 'volume': cols, ascending = ['volr20', 'cdf', 'score'], [True, False, False]
    elif rank == 'body': cols, ascending = ['body_pct', 'cdf', 'score'], [True, False, False]
    elif rank == 'blend':
        day = day.copy()
        day['blend'] = (day.volr20.rank(pct=True)+day.body_pct.rank(pct=True))/2
        cols, ascending = ['blend', 'cdf', 'score'], [True, False, False]
    elif rank == 'fusion':
        a, b = choose_one(day, 'volume'), choose_one(day, 'body')
        return a if a is not None and a == b else None
    else: raise ValueError(rank)
    ordered = day.sort_values(cols, ascending=ascending, kind='mergesort')
    first = ordered.iloc[0]
    if (ordered[cols].eq(first[cols]).all(axis=1)).sum() != 1: return None
    return int(first.row_id)

def choose(pool, policy, session_ordinals):
    z = pool[pool.cdf.ge(policy['gate'])].copy()
    if policy['market'] is not None: z = z[z.med_ret5.le(policy['market'])]
    if policy['retmax'] is not None: z = z[z.ret10.le(policy['retmax'])]
    if policy['medmin'] is not None: z = z[z.med_ret1.ge(policy['medmin'])]
    z = z[z.actual_volume.ge(5000*policy['vol']) & z.previous_actual_volume.ge(10000*policy['vol'])]
    last, selected = {}, []
    for day, group in z.groupby('date', sort=True):
        ordinal = session_ordinals[np.datetime64(day, 'ns')]
        if policy['cooldown']:
            group = group[group.symbol.map(lambda s: ordinal-last.get(s, -100000) > policy['cooldown'])]
        picked = choose_one(group, policy['rank'])
        if picked is not None:
            selected.append(picked)
            last[str(group.loc[group.row_id.eq(picked), 'symbol'].iloc[0])] = ordinal
    return np.array(selected, dtype=np.int64)

class Data:
    def __init__(self):
        self.info = verify_contract()
        self.f = pd.read_pickle(OLD/'rows.pkl')
        self.x = np.load(OLD/'features.npy', mmap_mode='r')
        self.a = np.load(CACHE/'augmented.npy', mmap_mode='r')
        self.outcomes = np.load(CACHE/'outcomes.npy', mmap_mode='r')
        self.entry = np.load(CACHE/'entry_prices.npy', mmap_mode='r')
        self.sessions = np.load(CACHE/'scheduled_sessions.npy', mmap_mode='r')
        self.which = np.load(CACHE/'session_index.npy', mmap_mode='r')
        f = self.f
        self.common = (f.source_usable & f.previous_source_usable & f.feature_complete & f.previous_actual_volume.ge(10000) & f.actual_volume.ge(5000) & f.actual_close.ge(20)).to_numpy()
        restrictions = json.loads((CACHE/'restriction_snapshot.json').read_text(encoding='utf-8'))['symbols']
        self.restricted = restricted_mask(f, restrictions).to_numpy()
        dates = np.sort(f.date.unique())
        self.ordinal = {d: i for i, d in enumerate(dates)}
        self.labels = {}

    def population(self, cfg):
        mask = self.common.copy()
        if cfg['cap'] > 0: mask &= self.f.previous_actual_close.le(cfg['cap']).to_numpy()
        return mask

    def label(self, cfg):
        key = (cfg['cap'], cfg['horizon'], cfg['objective'])
        if key not in self.labels:
            valid = self.population(cfg) & np.isfinite(self.outcomes[:, 2*(cfg['horizon']-1)+1])
            ix = np.flatnonzero(valid)
            r = np.asarray(self.outcomes[ix, 2*(cfg['horizon']-1)+1])
            if cfg['objective'] == 'top025':
                y = (pd.Series(r, index=ix).groupby(self.f.loc[ix, 'date']).rank(pct=True, method='average') >= .9975).to_numpy(np.int8)
            elif cfg['objective'] == 'win': y = (r > .002).astype(np.int8)
            else: y = np.clip(r, -.5, .5).astype(np.float32)
            self.labels[key] = (ix, y)
        return self.labels[key]

    def matrix(self, ix, group):
        z = np.asarray(self.x[ix], dtype=np.float32)
        if group == 'price_market':
            keep = [i for i, n in enumerate(FEATURES) if n not in ('volr5', 'volr10', 'volr20', 'volr40', 'volz20', 'log_dv')]
            z = z[:, keep]
        elif group == 'augmented': z = np.column_stack([z, self.a[ix]])
        return z

    def fit(self, cfg, month):
        import sklearn.ensemble as e
        from sklearn.linear_model import SGDClassifier, SGDRegressor
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from xgboost import XGBClassifier, XGBRegressor
        p = pd.Period(month)
        ix, y = self.label(cfg)
        mature = self.sessions[self.which[ix], cfg['horizon']-1] < p.start_time.to_datetime64()
        train = ix[mature]; y = y[mature]
        pred = np.flatnonzero(self.population(cfg) & self.f.date.between(p.start_time, p.end_time.normalize()).to_numpy())
        if len(train) < 30000 or not len(pred): raise RuntimeError('insufficient causal month')
        reg, large = cfg['objective'] == 'return', cfg['size'] == 'large'
        weight = min((len(y)-y.sum())/max(y.sum(), 1), 80) if not reg else None
        if not reg and len(np.unique(y)) != 2: raise RuntimeError('degenerate classifier')
        if cfg['learner'] == 'xgb':
            args = dict(n_estimators=240 if large else 160, max_depth=5 if large else 3,
                        learning_rate=.04, subsample=.8, colsample_bytree=.8,
                        min_child_weight=50 if large else 18, reg_lambda=10 if large else 6,
                        reg_alpha=.3, n_jobs=4, random_state=42)
            m = XGBRegressor(objective='reg:squarederror', **args) if reg else XGBClassifier(objective='binary:logistic', eval_metric='logloss', scale_pos_weight=weight, **args)
        elif cfg['learner'] == 'hist':
            args = dict(max_iter=240 if large else 160, learning_rate=.04, max_depth=5 if large else 3,
                        max_leaf_nodes=31 if large else 7, min_samples_leaf=200 if large else 100,
                        l2_regularization=10, early_stopping=False, random_state=42)
            m = e.HistGradientBoostingRegressor(**args) if reg else e.HistGradientBoostingClassifier(class_weight={0: 1, 1: weight}, **args)
        elif cfg['learner'] == 'extra':
            args = dict(n_estimators=192 if large else 128, max_depth=10 if large else 6,
                        min_samples_leaf=400 if large else 200, max_features=.8, n_jobs=4, random_state=42)
            m = e.ExtraTreesRegressor(**args) if reg else e.ExtraTreesClassifier(class_weight={0: 1, 1: weight}, **args)
        else:
            args = dict(alpha=.001 if large else .0001, penalty='elasticnet', l1_ratio=.15,
                        max_iter=30, tol=1e-4, random_state=42, shuffle=True)
            core = SGDRegressor(loss='huber', **args) if reg else SGDClassifier(loss='log_loss', class_weight={0: 1, 1: weight}, **args)
            m = make_pipeline(StandardScaler(), core)
        tx = self.matrix(train, cfg['features']); px = self.matrix(pred, cfg['features'])
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=4):
            m.fit(tx, y)
            reference = m.predict(tx) if reg else m.predict_proba(tx)[:, 1]
            prediction = m.predict(px) if reg else m.predict_proba(px)[:, 1]
        cdf = production.v7.cdf(reference, prediction)
        retain = cdf >= .90
        folder = CACHE/'fits'/cfg['id']; folder.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(folder/f'{month}.npz', row_id=pred[retain], cdf=cdf[retain], score=prediction[retain])
        joblib.dump(m, folder/f'{month}.joblib', compress=3)
        receipt = dict(config=cfg, month=month, train_rows=len(train), prediction_rows=len(pred), retained_rows=int(retain.sum()),
                       max_training_exit=str(pd.Timestamp(self.sessions[self.which[train], cfg['horizon']-1].max()).date()),
                       contract=self.info['hashes'], files={suffix: sha(folder/f'{month}.{suffix}') for suffix in ('npz', 'joblib')})
        if receipt['max_training_exit'] >= f'{month}-01': raise AssertionError('future teacher leaked')
        write_json(folder/f'{month}.json', receipt)
        del tx, px, m, reference, prediction; gc.collect()
        return receipt

    def pool(self, cfg, months):
        chunks = []
        for month in months:
            path = CACHE/'fits'/cfg['id']/f'{month}.npz'
            with np.load(path) as saved:
                ids = saved['row_id']
                z = self.f.loc[ids].copy()
                z['row_id'], z['cdf'], z['score'] = ids, saved['cdf'], saved['score']
                chunks.append(z)
        pool = pd.concat(chunks, ignore_index=True)
        # JPX designation known at signal time is a detection gate.
        return pool[~self.restricted[pool.row_id.to_numpy()]].copy()

    def measured(self, ids, period):
        if not len(ids): return ids
        all_prices = np.isfinite(self.outcomes[ids]).all(axis=1)
        if period == 'DEV':
            all_prices &= self.sessions[self.which[ids], 9] <= np.datetime64('2024-12-31')
        ids = ids[all_prices]
        if not len(ids): return ids
        frame = self.f.loc[ids, ['symbol', 'date']].copy()
        frame['entry_date'] = self.sessions[self.which[ids], 0]
        allowed = performance_eligible(frame, CACHE/'entry_feasibility_exclusions.csv')
        return allowed.index.to_numpy(np.int64)

    def metrics(self, ids, endpoint):
        col = ENDPOINTS.index(endpoint)
        h = int(endpoint.split('_')[0][1:])-1
        m = stats(self.outcomes[ids, col], self.entry[ids]*100,
                  self.sessions[self.which[ids], 0], self.sessions[self.which[ids], h])
        years = self.f.loc[ids, 'date'].dt.year.to_numpy()
        for y in (2023, 2024, 2025, 2026):
            mask = years == y
            m[f'n{y}'] = int(mask.sum())
            if mask.any():
                r = self.outcomes[ids[mask], col]
                m[f'mean{y}_pct'] = float(r.mean()*100)
                m[f'win{y}_pct'] = float((r > 0).mean()*100)
                m[f'median{y}_pct'] = float(np.median(r)*100)
                m[f'loss10_{y}_pct'] = float((r <= -.1).mean()*100)
        return m

    def best_policy(self, cfg, months, full=False):
        pool = self.pool(cfg, months)
        namespace = 'refined' if full else 'screen'
        pending = CACHE/'policy_progress'/f"{namespace}_{cfg['id']}.json"
        saved = json.loads(pending.read_text(encoding='utf-8')) if pending.exists() else {}
        if saved and saved['contract'] != self.info['hashes']: raise RuntimeError('mixed policy checkpoint')
        best = saved.get('best')
        tested, passed, cursor = saved.get('tested', 0), saved.get('passed', 0), saved.get('cursor', 0)
        for number, policy in enumerate(policies(full)):
            if number < cursor: continue
            if not lease_ok():
                write_json(pending, dict(contract=self.info['hashes'], best=best, tested=tested, passed=passed, cursor=number))
                return None
            ids = self.measured(choose(pool, policy, self.ordinal), 'DEV')
            for endpoint in ENDPOINTS:
                m = self.metrics(ids, endpoint); tested += 1
                if not robust(m): continue
                passed += 1
                candidate = dict(config=cfg, policy=policy, endpoint=endpoint, metrics=m)
                if best is None or m['utility'] > best['metrics']['utility']: best = candidate
            if number % 20 == 19:
                write_json(pending, dict(contract=self.info['hashes'], best=best, tested=tested, passed=passed, cursor=number+1))
        result = dict(contract=self.info['hashes'], config=cfg, tested_policies_endpoints=tested, qualifying=passed, best=best)
        write_json(CACHE/namespace/f"{cfg['id']}.json", result)
        return result

def complete(cfg, month, info):
    folder = CACHE/'fits'/cfg['id']
    p = folder/f'{month}.json'
    if not p.exists(): return False
    v = json.loads(p.read_text(encoding='utf-8'))
    if v['contract'] != info['hashes'] or v['config'] != cfg: raise RuntimeError('mixed fitted checkpoints')
    if any(sha(folder/f'{month}.{s}') != h for s, h in v['files'].items()): raise RuntimeError('changed fit artifact')
    return True

def baseline(data, year):
    selection = pd.concat([pd.read_csv(OLD/f'selected_cap1000_{month}.csv', dtype={'symbol': str}, parse_dates=['date'])
                           for month in pd.period_range(f'{year}-01', f'{year}-12' if year < 2026 else '2026-09', freq='M')], ignore_index=True)
    keys = selection[['symbol', 'date']].drop_duplicates()
    idx = pd.MultiIndex.from_frame(data.f[['symbol', 'date']])
    ids = idx.get_indexer(pd.MultiIndex.from_frame(keys))
    if (ids < 0).any(): raise RuntimeError('baseline signal missing from source')
    return data.metrics(data.measured(ids, str(year)), 'd5_close')

def publish_final(data, frozen):
    rows, baseline_metrics = [], {str(y): baseline(data, y) for y in (2025, 2026)}
    for j, candidate in enumerate(frozen['candidates']):
        cfg = candidate['config']
        for year in (2025, 2026):
            months = [str(m) for m in pd.period_range(f'{year}-01', f'{year}-12' if year == 2025 else '2026-09', freq='M')]
            pool = data.pool(cfg, months)
            ids = data.measured(choose(pool, candidate['policy'], data.ordinal), str(year))
            m = data.metrics(ids, candidate['endpoint']); b = baseline_metrics[str(year)]
            current_pass = (m['n'] >= max(50, .7*b['n']) and m['mean_pct'] is not None
                            and m['mean_pct'] >= b['mean_pct'] and m['win_pct'] >= b['win_pct']
                            and m['median_pct'] >= b['median_pct'] and m['loss10_pct'] <= b['loss10_pct']
                            and m['top3_ex_mean_pct'] >= b['top3_ex_mean_pct'] and m['net05_mean_pct'] > 0)
            public_pass = (m['mean_pct'] is not None and m['mean_pct'] >= 5.49422506939 and m['win_pct'] >= 49.1935483871
                           and m['median_pct'] >= 0 and m['loss10_pct'] <= 29.0322580645)
            rows.append(dict(candidate=j, config=cfg['id'], year=year, endpoint=candidate['endpoint'], comparable_baseline_pass=current_pass, published_reference_screen_pass=public_pass, **m))
            pd.DataFrame({'row_id': ids, 'signal_date': data.f.loc[ids, 'date'].to_numpy(), 'symbol': data.f.loc[ids, 'symbol'].to_numpy(),
                          'gross_return': data.outcomes[ids, ENDPOINTS.index(candidate['endpoint'])], 'entry_cost_yen': data.entry[ids]*100}).to_csv(CACHE/f'candidate{j}_{year}_trades.csv', index=False)
    result = dict(status='COMPLETE', baseline=baseline_metrics, candidates=rows,
                  adoption='UNCONFIRMED: no production changes. Canonical historical lineage differs; 2026 already viewed.')
    write_json(CACHE/'final.json', result)
    write_json(HERE/'RESULTS.json', result)
    pd.DataFrame(rows).to_csv(HERE/'validation.csv', index=False)

def run(max_fits, max_seconds):
    if not lease_ok(): raise RuntimeError('usage lease missing/expired or STOP requested')
    parity = json.loads((CACHE/'parity.json').read_text(encoding='utf-8'))
    if parity['status'] != 'PASS': raise RuntimeError('production replay must pass before new search')
    data = Data(); began = time.time(); fits = 0
    all_cfg = recipes()
    screen = CACHE/'screen'; screen.mkdir(exist_ok=True)
    shortlist_path = CACHE/'shortlist.json'
    if not shortlist_path.exists():
        for cfg in all_cfg:
            result = screen/f"{cfg['id']}.json"
            if result.exists():
                if json.loads(result.read_text(encoding='utf-8'))['contract'] != data.info['hashes']:
                    raise RuntimeError('changed screening contract')
                continue
            for month in SCREEN_MONTHS:
                if complete(cfg, month, data.info): continue
                if fits >= max_fits or time.time()-began >= max_seconds or not lease_ok():
                    write_json(CACHE/'progress.json', dict(phase='SCREEN', next_config=cfg['id'], next_month=month, screen_complete=len(list(screen.glob('*.json'))), total_configs=len(all_cfg), reason='bounded batch or usage guard'))
                    return
                t = time.time(); receipt = data.fit(cfg, month); fits += 1
                print(json.dumps({'fit': cfg['id'], 'month': month, 'train': receipt['train_rows'], 'retained': receipt['retained_rows'], 'seconds': round(time.time()-t, 2)}), flush=True)
            if not lease_ok(): return
            result = data.best_policy(cfg, SCREEN_MONTHS)
            if result is None: return
            print(json.dumps({'screen_complete': cfg['id'], 'qualifying': result['qualifying']}), flush=True)
        results = [json.loads(p.read_text(encoding='utf-8')) for p in screen.glob('*.json')]
        picked = []
        for learner, objective in itertools.product(('xgb', 'hist', 'extra', 'linear'), ('top025', 'win', 'return')):
            group = [r['best'] for r in results if r['best'] and r['config']['learner'] == learner and r['config']['objective'] == objective]
            if group: picked.append(max(group, key=lambda r: r['metrics']['utility'])['config'])
        write_json(shortlist_path, {'contract': data.info['hashes'], 'configs': picked, 'all_screen_configs': len(results), 'selected_before_2025': True})
    shortlist_record = json.loads(shortlist_path.read_text(encoding='utf-8'))
    if shortlist_record['contract'] != data.info['hashes']: raise RuntimeError('changed shortlist contract')
    shortlist = shortlist_record['configs']
    dev_months = [str(m) for m in pd.period_range('2023-01', '2024-12', freq='M')]
    refined = CACHE/'refined'; refined.mkdir(exist_ok=True)
    for cfg in shortlist:
        result_path = refined/f"{cfg['id']}.json"
        if result_path.exists():
            if json.loads(result_path.read_text(encoding='utf-8'))['contract'] != data.info['hashes']:
                raise RuntimeError('changed refinement contract')
            continue
        for month in dev_months:
            if complete(cfg, month, data.info): continue
            if fits >= max_fits or time.time()-began >= max_seconds or not lease_ok():
                write_json(CACHE/'progress.json', {'phase': 'DEV_REFINE', 'next_config': cfg['id'], 'next_month': month}); return
            t = time.time(); data.fit(cfg, month); fits += 1
            print(json.dumps({'refine_fit': cfg['id'], 'month': month, 'seconds': round(time.time()-t, 2)}), flush=True)
        if not lease_ok(): return
        if data.best_policy(cfg, dev_months, full=True) is None: return
    frozen_path = CACHE/'frozen_candidates.json'
    if not frozen_path.exists():
        winners = [json.loads(p.read_text(encoding='utf-8'))['best'] for p in refined.glob('*.json')]
        winners = sorted([v for v in winners if v], key=lambda r: r['metrics']['utility'], reverse=True)[:8]
        write_json(frozen_path, {'contract': data.info['hashes'], 'selected_before_2025': True, 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'candidates': winners})
        write_json(HERE/'frozen_candidates.json', json.loads(frozen_path.read_text(encoding='utf-8')))
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    if frozen['contract'] != data.info['hashes']: raise RuntimeError('changed fixed validation contract')
    for candidate in frozen['candidates']:
        cfg = candidate['config']
        for month in [str(m) for m in pd.period_range('2025-01', '2026-09', freq='M')]:
            if complete(cfg, month, data.info): continue
            if fits >= max_fits or time.time()-began >= max_seconds or not lease_ok():
                write_json(CACHE/'progress.json', {'phase': 'FIXED_VALIDATION', 'next_config': cfg['id'], 'next_month': month, 'frozen_sha256': sha(frozen_path)}); return
            t = time.time(); data.fit(cfg, month); fits += 1
            print(json.dumps({'fixed_fit': cfg['id'], 'month': month, 'seconds': round(time.time()-t, 2)}), flush=True)
    if not lease_ok(): return
    publish_final(data, frozen)
    write_json(CACHE/'progress.json', {'phase': 'COMPLETE', 'adoption': 'UNCONFIRMED'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-fits', type=int, default=8)
    parser.add_argument('--max-seconds', type=int, default=480)
    args = parser.parse_args()
    with locked(): run(args.max_fits, args.max_seconds)
