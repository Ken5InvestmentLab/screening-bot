"""Read-only inputs and bounded, locked cache writes for Cloud research."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / '.cache/cloud_full_search_v2_20261001'
OLD = ROOT / '.cache/cloud_cap_corrected_v2_20261001'
DAILY = ROOT / '.cache/weak_early_beta/split_preflight_20261001/normalized_daily.csv'
sys.path.insert(0, str(ROOT))
from weak_early_beta import model as production
FEATURES = production.base.FEATURES
ENDPOINTS = [f'd{d}_{q}' for d in range(1, 11) for q in ('open', 'close')]
SCREEN_MONTHS = ['2023-03', '2023-09', '2024-03', '2024-09']

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def write_json(path, value):
    def clean(x):
        if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [clean(v) for v in x]
        if isinstance(x, np.generic): return clean(x.item())
        if isinstance(x, float) and not np.isfinite(x): return None
        return x
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)

def contract_hashes():
    paths = [HERE/'PROTOCOL.md', *sorted(HERE.glob('*.py')),
             DAILY, OLD/'prepared.json', OLD/'rows.pkl', OLD/'features.npy', OLD/'prices.pkl', OLD/'actions.csv',
             ROOT/'weak_early_beta/model.py', Path(production.base.__file__), Path(production.v7.__file__), Path(production.shadow.__file__),
             *[ROOT/'weak_early_beta'/n for n in ('corporate_actions.py', 'bank_calendar.py', 'trade_basis.py', 'restrictions.py', 'entry_feasibility.py')],
             CACHE/'entry_feasibility_exclusions.csv', CACHE/'restriction_snapshot.json']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}

def verify_contract():
    info = json.loads((CACHE/'prepared.json').read_text(encoding='utf-8'))
    if contract_hashes() != info['hashes']:
        raise RuntimeError('search source/code changed: use a new cache namespace')
    for name, expected in info['output_hashes'].items():
        if sha(CACHE/name) != expected:
            raise RuntimeError(f'prepared array changed: {name}')
    import pandas, sklearn, xgboost
    now = {'python': sys.version, 'numpy': np.__version__, 'pandas': pandas.__version__, 'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__}
    if now != info['versions']:
        raise RuntimeError('runtime changed')
    return info

def lease_ok():
    if (CACHE/'STOP_REQUESTED.json').exists(): return False
    p = CACHE/'usage_lease.json'
    if not p.exists(): return False
    v = json.loads(p.read_text(encoding='utf-8'))
    return (v['primary_used_percent'] < 97 and v['secondary_used_percent'] < 80
            and datetime.now(timezone.utc).timestamp() < v['expires_at_unix'])

@contextmanager
def locked():
    import msvcrt
    CACHE.mkdir(parents=True, exist_ok=True)
    f = (CACHE/'worker.lock').open('a+b')
    if os.fstat(f.fileno()).st_size == 0: f.write(b'0'); f.flush()
    f.seek(0)
    try: msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        raise RuntimeError('another search worker holds the OS lock')
    try: yield
    finally:
        f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1); f.close()

def recipes():
    result = []
    for learner in ('xgb', 'hist', 'extra', 'linear'):
        for size in ('small', 'large'):
            for objective in ('top025', 'win', 'return'):
                for horizon in (5, 10):
                    for features in ('all45', 'price_market', 'augmented'):
                        for cap in (1000, 1500, 2000, 3000, 5000, 0):
                            row = dict(learner=learner, size=size, objective=objective, horizon=horizon, features=features, cap=cap)
                            row['id'] = f'{learner}_{size}_{objective}_h{horizon}_{features}_cap{cap}'
                            result.append(row)
    assert len(result) == 864
    return result
