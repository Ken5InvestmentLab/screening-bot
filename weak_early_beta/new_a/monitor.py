"""隔離研究専用。日次確定バーから監視イベントを作る。通信・発注機能なし。"""
import copy
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def valid(r, nominal=False):
    if not r:
        return False
    fields = ['open', 'high', 'low', 'close'] + (['actual_close', 'split_factor', 'volume', 'actual_volume'] if nominal else [])
    if not all(isinstance(r.get(k), (int, float)) and math.isfinite(r[k]) for k in fields):
        return False
    o, h, l, c = (r[k] for k in ['open', 'high', 'low', 'close'])
    return (min(o, h, l, c) > 0 and l <= min(o, c) <= max(o, c) <= h
            and str(r.get('source_usable')).lower() in ['true', '1']
            and (not nominal or (r['actual_close'] > 0 and r['split_factor'] > 0)))


def base_key(e):
    return e['candidate_date'], -e['priority_score'], e['symbol'], e['episode_id']


def initial(calendar, symbols, contract):
    if sorted(set(calendar)) != calendar or not calendar or len(set(symbols)) != len(symbols):
        raise ValueError('sorted unique calendar / symbols required')
    for day in calendar:
        if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
            raise ValueError('invalid session')
    return dict(version=1, contract=contract, calendar=calendar, symbols=sorted(symbols), cursor=-1,
                active={}, watches={}, sequence={}, previous={}, identities={}, bases={}, pending=[], events=[])


def advance(state, day, rows, observed_at):
    """全universeの日次一括更新。欠損銘柄もキーを持ち値Noneで渡す。"""
    s = copy.deepcopy(state)
    i = s['cursor'] + 1
    if i >= len(s['calendar']) or s['calendar'][i] != day:
        raise ValueError('calendar gap, reorder or exhausted calendar')
    if sorted(rows) != s['symbols']:
        raise ValueError('incomplete universe; missing must be explicit null')
    obs = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    close = datetime.fromisoformat(day + 'T15:30:00+09:00')
    if obs.tzinfo is None or obs < close or obs > datetime.now(timezone.utc):
        raise ValueError('observation must follow completed close and not be future')
    emitted = []

    def event(kind, e, **extra):
        value = dict(kind=kind, session=day, observed_at=observed_at,
                     symbol=e['symbol'], episode_id=e['episode_id'], candidate_date=e['candidate_date'], **extra)
        value['event_id'] = digest([s['contract'], kind, day, e['symbol'], e['episode_id']])
        emitted.append(value)

    # 予定日を過ぎても価格未確認を後日の始値へ振り替えない。
    for p in s['pending']:
        if p['entry_index'] == i:
            r = rows[p['symbol']]
            sym = p['symbol']
            same_identity = sym not in s['identities'] or (r and r.get('security_id') == s['identities'][sym])
            same_basis = sym not in s['bases'] or (r and r.get('price_basis_id') == s['bases'][sym])
            if same_identity and same_basis and valid(r, True) and r['volume'] > 0 and r['actual_volume'] > 0 and r['high'] != r['low']:
                p['reference_open'] = r['open'] * r['actual_close'] / r['close']
                p['price_status'] = 'HISTORICAL_REFERENCE_ONLY'
            else:
                p['price_status'] = 'UNRESOLVED_OPEN'
            event('REFERENCE_OPEN', p, price_status=p['price_status'], reference_open=p.get('reference_open'), execution_status='NOT_EXECUTED')
    for sym in s['symbols']:
        r = rows[sym]
        identity = r.get('security_id') if r else None
        changed = sym in s['identities'] and s['identities'][sym] != identity
        basis = r.get('price_basis_id') if r else None
        basis_changed = sym in s['bases'] and s['bases'][sym] != basis
        if identity:
            s['identities'][sym] = identity
        if basis:
            s['bases'][sym] = basis
        old = s['active'].get(sym)
        # episode resetとwatch terminalは別state。保存コードと同じ1本離脱。
        reset = old and (not valid(r) or changed or basis_changed or r['close'] < old['support'] * .98 or r['close'] > old['resistance'] * 1.02)
        if reset:
            reason = 'IDENTITY_CHANGED' if changed else ('BASIS_CHANGED' if basis_changed else ('DATA_GAP' if not valid(r) else ('DOWN_INVALIDATED' if r['close'] < old['support'] * .98 else 'UP_ESCAPED')))
            event('MONITOR_RESET', old, reason=reason)
            del s['active'][sym]
        for key, w in list(s['watches'].items()):
            e = w['episode']
            if e['symbol'] != sym:
                continue
            L, H = e['support'], e['resistance']
            status = None
            if changed:
                status = 'IDENTITY_CHANGED'
            elif basis_changed:
                status = 'BASIS_CHANGED'
            elif not valid(r, True):
                status = 'DATA_GAP'
            elif r['close'] < L * .98:
                status = 'DOWN_INVALIDATED'
            elif r['close'] > H * 1.02:
                status = 'UP_ESCAPED'
            else:
                prev = s['previous'].get(sym)
                c = r['close']
                if (r['low'] >= L * .98 and r['low'] <= L * 1.03 and c >= L * 1.03
                        and c > r['open'] and prev is not None and c > prev['close']
                        and r['high'] > r['low'] and (c-r['low'])/(r['high']-r['low']) >= .60):
                    status = 'TRIGGERED'
                    entry = i+1
                    exit_i = i+20
                    p = dict(e, trigger_date=day, entry_index=entry, reference_exit_index=exit_i,
                             reference_entry_date=s['calendar'][entry] if entry < len(s['calendar']) else None,
                             reference_exit_date=s['calendar'][exit_i] if exit_i < len(s['calendar']) else None,
                             price_status='UNCONFIRMED_NEXT_OPEN', execution_status='NOT_EXECUTED')
                    s['pending'].append(p)
                    event('ENTRY_CANDIDATE', e, **{k:p[k] for k in ['trigger_date','reference_entry_date','reference_exit_date','price_status','execution_status']})
            if status is None and i == w['start_index'] + 20:
                status = 'EXPIRED'
            if status:
                event('WATCH_TERMINAL', e, reason=status)
                del s['watches'][key]
        if not reset and r and r.get('candidate') is True:
            if sym not in s['active']:
                if not valid(r, True) or not all(isinstance(r.get(k), (float, int)) and math.isfinite(r[k]) and r[k] > 0 for k in ['low20','high20','median_turnover20']):
                    raise ValueError('invalid candidate features')
                seq = s['sequence'].get(sym, 0) + 1
                s['sequence'][sym] = seq
                e = dict(symbol=sym, candidate_date=day, episode_id=seq, support=r['low20'], resistance=r['high20'], priority_score=r['median_turnover20'], detection_count=1)
                s['active'][sym] = e
                s['watches'][sym + '|' + str(seq)] = dict(episode=copy.deepcopy(e), start_index=i)
                event('WATCH_STARTED', e, support=e['support'], resistance=e['resistance'], priority_score=e['priority_score'])
            else:
                s['active'][sym]['detection_count'] += 1
        # 欠損前終値を前営業日の価格として使わない。
        s['previous'][sym] = r if valid(r) else None
    s['cursor'] = i
    s['events'].extend(emitted)
    return s, emitted


class Store:
    """SQLiteの単一transactionと世代照合。再開・同日重複・古いwriterを検証。"""
    def __init__(self, path, seed):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS head (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, state TEXT NOT NULL, state_hash TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS days (day TEXT PRIMARY KEY, hash TEXT NOT NULL)')
        self.db.execute('INSERT OR IGNORE INTO head VALUES (1,0,?,?)', (encode(seed),digest(seed)))
        self.db.commit()
        existing = self.read()[1]
        if any(existing[k] != seed[k] for k in ['contract', 'calendar', 'symbols']):
            raise ValueError('state contract mismatch')

    def read(self):
        version, raw, h = self.db.execute('SELECT version,state,state_hash FROM head WHERE id=1').fetchone()
        state = json.loads(raw)
        if digest(state) != h or version != state['cursor']+1 or self.db.execute('SELECT count(*) FROM days').fetchone()[0] != version:
            raise ValueError('corrupt durable head')
        return version, state

    def ingest(self, day, rows, observed_at, expected_version):
        h = digest(rows)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            version, state = self.read()
            prior = self.db.execute('SELECT hash FROM days WHERE day=?', (day,)).fetchone()
            if prior:
                if prior[0] != h:
                    raise ValueError('conflicting same-day revision')
                return version, []
            if version != expected_version:
                raise ValueError('stale writer')
            new, events = advance(state, day, rows, observed_at)
            self.db.execute('UPDATE head SET version=?,state=?,state_hash=? WHERE id=1', (version+1, encode(new), digest(new)))
            self.db.execute('INSERT INTO days VALUES (?,?)', (day,h))
            return version+1, events
