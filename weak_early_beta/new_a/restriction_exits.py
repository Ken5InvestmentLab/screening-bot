"""Exit at the next verified market open after an official delisting decision."""
import datetime
import json
import math
from .files import digest, encode

EFFECTIVE_FROM = '2026-11-26'


def observe(pipeline, rows, calendar, as_of, *, live):
    db = pipeline.db
    db.execute('''CREATE TABLE IF NOT EXISTS restriction_exit_decisions (
        symbol TEXT NOT NULL, confirmed_on TEXT NOT NULL, receipt_json TEXT NOT NULL,
        receipt_hash TEXT NOT NULL, PRIMARY KEY(symbol,confirmed_on))''')
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
    if live and as_of == today and as_of >= EFFECTIVE_FROM:
        due = next((day for day in calendar if day > as_of), None)
        if not due:
            raise ValueError('next verified market session required for restriction exit')
        with db:
            for row in rows:
                designation = row.get('designation', '')
                restricted = '整理銘柄指定' in designation and '上場廃止の決定' in designation
                delisting = row.get('delisting_date')
                if not restricted and not delisting:
                    continue
                if row.get('relisting_date') and row['relisting_date'] <= as_of:
                    continue
                if restricted and row.get('designation_date', '') > as_of:
                    continue
                if delisting and delisting <= as_of:
                    continue  # No invented open after a security has already stopped trading.
                symbol = str(row['code'])
                if db.execute('SELECT 1 FROM restriction_exit_decisions WHERE symbol=?', (symbol,)).fetchone():
                    continue
                value = dict(symbol=symbol, confirmed_on=as_of, exit_date=due,
                             reason='整理銘柄入り' if restricted else '上場廃止決定',
                             source_url=row.get('source_url') or row.get('delisting_source_url'))
                db.execute('INSERT INTO restriction_exit_decisions VALUES (?,?,?,?)',
                           (symbol, as_of, encode(value), digest(value)))
    result = []
    for raw, sha in db.execute('SELECT receipt_json,receipt_hash FROM restriction_exit_decisions WHERE confirmed_on<=? ORDER BY confirmed_on,symbol', (as_of,)):
        value = json.loads(raw)
        if digest(value) != sha:
            raise ValueError('restriction exit receipt changed')
        result.append(value)
    return result


def settlement_quotes(pipeline, frame, rules, calendar, as_of, source_hash):
    """Settlement-only prices; never introduce a restricted monitoring observation."""
    if not rules or frame is None:
        return {}
    db=pipeline.db
    db.execute('''CREATE TABLE IF NOT EXISTS restriction_exit_quotes (
        symbol TEXT NOT NULL,day TEXT NOT NULL,observed_after TEXT NOT NULL,
        receipt_json TEXT NOT NULL,receipt_hash TEXT NOT NULL,PRIMARY KEY(symbol,day))''')
    retained={}
    for symbol,day,raw,sha in db.execute('SELECT symbol,day,receipt_json,receipt_hash FROM restriction_exit_quotes WHERE observed_after<=?',(as_of,)):
        value=json.loads(raw)
        if digest(value)!=sha:raise ValueError('restriction settlement quote changed')
        retained[symbol,day]=value['quote']
    observed = pipeline.observed_quotes()
    symbols = {r['symbol'] for r in rules}
    source = {(str(row.pop('symbol')), row.pop('date').date().isoformat()): row
              for row in frame.loc[frame.symbol.isin(symbols)].to_dict('records')}
    output = dict(retained)
    allowed = {'unresolved_jpx_restriction', 'jpx_restricted', 'verified_restricted', 'jpx_symbol_hold'}
    for rule in rules:
        symbol = rule['symbol']
        anchors = sorted((day, row) for (code, day), row in observed.items()
                         if code == symbol and day < rule['confirmed_on'])
        if not anchors:
            continue
        anchor_day, old = anchors[-1]
        current = source.get((symbol, anchor_day))
        if not current or not math.isclose(old['actual_close'], current['actual_close'], abs_tol=1e-8, rel_tol=0):
            continue
        scale = old['close'] / current['close']
        for day in calendar:
            key = (symbol, day)
            if not rule['confirmed_on'] <= day <= min(as_of, rule['exit_date']) or key in observed or key in output:
                continue
            row = source.get(key)
            if not row:
                continue
            issues = str(row.get('source_issue', '') or '')
            flags = {part for part in issues.split(';') if part and part != 'nan'}
            if flags - allowed:
                continue
            if str(row.get('source_usable')).lower() not in ('true','1') and not flags:
                continue
            values = [row.get(k) for k in ('open','high','low','close','actual_close','volume','actual_volume')]
            if not all(isinstance(x,(int,float)) and math.isfinite(x) and x > 0 for x in values):
                continue
            if not row['low'] <= min(row['open'],row['close']) <= max(row['open'],row['close']) <= row['high'] or row['high'] == row['low']:
                continue
            output[key] = {**{k: row[k]*scale for k in ('open','high','low','close')},
                           'volume':row['volume']/scale, 'split_factor':row['close']*scale/row['actual_close'],
                           'actual_close':row['actual_close'],'actual_volume':row['actual_volume'],
                           'source_usable':True}
            value={'quote':output[key],'source_sha256':source_hash,'observed_after':as_of}
            with db:
                db.execute('INSERT INTO restriction_exit_quotes VALUES(?,?,?,?,?)',
                           (symbol,day,as_of,encode(value),digest(value)))
    return output
