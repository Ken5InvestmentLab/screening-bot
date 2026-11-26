"""Explicit source-vintage acceptance; historical monitor decisions stay immutable."""
import json
import math
from pathlib import Path
import pandas as pd
from .files import atomic_write, digest, file_sha, read, encode

SYMBOLS = ('2978','4826','4888','5271','5537','6276','8303','8746','9256')
MISSING = ('3600','446A','4563','5918','5969','6612','6898','7031','7434','7634','7677','7916','9214','9367','9476')
BASELINE_DAY = '2026-11-25'
ACTIVATION_DAY = '2026-11-26'
NOMINAL = ('actual_open','actual_high','actual_low','actual_close','actual_volume')
ACCEPTED_ISSUES = {'unresolved_jpx_historical_revision','ambiguous_provider_repair_basis',
                   'ambiguous_security_identity_after_consolidation'}


def decisions(value):
    if not isinstance(value,dict):
        return set()
    return {digest(row) for row in value.get('decisions', [])} | decisions(value.get('parent_audit'))


def make_review(frame, source_hash):
    result = {}
    for symbol in SYMBOLS:
        group = frame.loc[frame.symbol.eq(symbol) & (frame.date <= pd.Timestamp(BASELINE_DAY))]
        if symbol == '8303':
            group = group.loc[group.date >= pd.Timestamp('2025-12-17')]
        rows = {}
        known_decisions = set()
        for row in group.to_dict('records'):
            values = [float(row[k]) for k in NOMINAL]
            if not all(math.isfinite(v) and v >= 0 for v in values):
                raise ValueError('baseline contains invalid nominal values')
            rows[row['date'].date().isoformat()] = values
            raw = row.get('jpx_symbol_hold_evidence')
            if isinstance(raw,str) and raw:
                known_decisions |= decisions(json.loads(raw))
        if not rows or max(rows) != BASELINE_DAY:
            raise ValueError('baseline lacks the confirmed latest session')
        result[symbol] = dict(rows=rows, accepted_decisions=sorted(known_decisions))
    return dict(schema='NEW_A_OWNER_ACCEPTED_SOURCE_BASELINE_V1', baseline_day=BASELINE_DAY,
                activation_day=ACTIVATION_DAY, source_sha256=source_hash, symbols=result,
                acknowledged_missing=list(MISSING), backfill=False)


def register(pipeline, review_file, review_sha, current_source_sha):
    if file_sha(review_file) != review_sha:
        raise ValueError('source baseline reviewed bytes changed')
    review = read(review_file)
    if (review.get('schema') != 'NEW_A_OWNER_ACCEPTED_SOURCE_BASELINE_V1'
            or review.get('baseline_day') != BASELINE_DAY or review.get('activation_day') != ACTIVATION_DAY
            or review.get('source_sha256') != current_source_sha or review.get('backfill') is not False
            or set(review.get('symbols', {})) != set(SYMBOLS) or review.get('acknowledged_missing') != list(MISSING)):
        raise ValueError('source baseline scope differs from owner instruction')
    db = pipeline.db
    db.execute('CREATE TABLE IF NOT EXISTS accepted_source_baseline (id INTEGER PRIMARY KEY CHECK(id=1),review_sha TEXT NOT NULL)')
    saved = db.execute('SELECT review_sha FROM accepted_source_baseline WHERE id=1').fetchone()
    if saved and saved[0] != review_sha:
        raise ValueError('source baseline already pinned to different bytes')
    destination = pipeline.private_directory/'accepted-source-baseline.json'
    if destination.exists() and read(destination) != review:
        raise ValueError('source baseline file changed')
    states = {}
    for symbol in SYMBOLS:
        state = pipeline.read(symbol)
        if not state or state['active'] or state['watches']:
            raise ValueError('source baseline would change an active monitor')
        if state['calendar'][state['cursor']] > BASELINE_DAY:
            raise ValueError('source baseline must precede the next daily')
        states[symbol] = state
    atomic_write(destination, review)
    if not saved:
        with db:
            for symbol,state in states.items():
                state['cursor'] = state['calendar'].index(BASELINE_DAY)
                state['previous'].pop(symbol, None)
                db.execute('UPDATE symbol_heads SET state_json=?,state_hash=? WHERE symbol=?',
                           (encode(state),digest(state),symbol))
                db.execute("DELETE FROM held WHERE symbol=? AND reason='SOURCE_QUARANTINED'", (symbol,))
            for symbol in MISSING:
                # Persist the original skipped decision before acknowledging its display.
                db.execute("INSERT OR IGNORE INTO missing_quote_days SELECT symbol,day FROM held WHERE symbol=? AND reason='MISSING_SOURCE'", (symbol,))
                db.execute("DELETE FROM held WHERE symbol=? AND reason='MISSING_SOURCE'", (symbol,))
            db.execute('INSERT INTO accepted_source_baseline VALUES(1,?)', (review_sha,))
    return dict(schema='NEW_A_ACCEPTED_SOURCE_BASELINE_RECEIPT_V1',review_sha256=review_sha,
                baseline_day=BASELINE_DAY,symbols=list(SYMBOLS),acknowledged_missing=list(MISSING),
                historical_events_rewritten=False, historical_quotes_rewritten=False,notifications_sent=0)


def apply(source, pipeline, as_of):
    table = pipeline.db.execute("SELECT 1 FROM sqlite_master WHERE name='accepted_source_baseline'").fetchone()
    saved = pipeline.db.execute('SELECT review_sha FROM accepted_source_baseline WHERE id=1').fetchone() if table else None
    if not saved or as_of < ACTIVATION_DAY:
        return source
    path = pipeline.private_directory/'accepted-source-baseline.json'
    if file_sha(path) != saved[0]:
        raise ValueError('accepted baseline bytes changed')
    review = read(path)
    frame = source['frame'].copy(deep=False)
    # Only these two metadata columns are changed in the New A view, never the raw cache.
    frame['source_usable'] = frame['source_usable'].copy()
    frame['source_issue'] = frame['source_issue'].copy()
    audit = []
    for symbol, accepted in review['symbols'].items():
        group = frame.loc[frame.symbol.eq(symbol)]
        if symbol == '8303':
            group = group.loc[group.date >= pd.Timestamp('2025-12-17')]
        changed = []
        known = set(accepted['accepted_decisions'])
        for row in group.to_dict('records'):
            day = row['date'].date().isoformat()
            if day in accepted['rows'] and any(not math.isclose(float(row[k]),v,rel_tol=1e-9,abs_tol=1e-7) for k,v in zip(NOMINAL,accepted['rows'][day])):
                changed.append(day)
            raw = row.get('jpx_symbol_hold_evidence')
            if isinstance(raw,str) and raw and not decisions(json.loads(raw)) <= known:
                changed.append(day)
        if not changed:
            mask = group.index[group.source_issue.fillna('').isin(ACCEPTED_ISSUES)]
            # Basic OHLC validity remains mandatory even when accepting a source vintage.
            valid = (frame.loc[mask,'low']>0) & (frame.loc[mask,'low']<=frame.loc[mask,['open','close']].min(axis=1)) & (frame.loc[mask,['open','close']].max(axis=1)<=frame.loc[mask,'high'])
            mask = mask[valid]
            frame.loc[mask,'source_usable'] = True
            frame.loc[mask,'source_issue'] = ''
        audit.append(dict(symbol=symbol,status='REVISION_RECURRED' if changed else 'ACCEPTED_BASELINE',changed_dates=sorted(set(changed))))
    folder = pipeline.private_directory/'source-baseline-observations'
    value = dict(schema='NEW_A_SOURCE_BASELINE_OBSERVATION_V1',as_of=as_of,source_sha256=source['source_hash'],baseline_sha256=saved[0],symbols=audit)
    target = folder/(as_of+'-'+source['source_hash']+'.json')
    if target.exists() and read(target)!=value:
        raise ValueError('baseline observation changed')
    if not target.exists():
        atomic_write(target,value)
    return {**source,'frame':frame,'source_revision':{**source.get('source_revision',{}),'ownerAcceptedBaseline':value}}
