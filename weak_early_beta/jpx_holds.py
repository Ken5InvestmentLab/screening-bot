"""Versioned whole-symbol hold evidence.
Original OHLCV/date/action rows are never removed.
"""
import hashlib,json,re
import pandas as pd
COLUMN='jpx_symbol_hold_evidence'
ISSUE='unresolved_jpx_historical_revision'
def digest(group):
    columns=['symbol','date','open','high','low','close','volume','split_ratio','provider_repaired','off_session_actions']
    g=group.copy()
    if 'off_session_actions' not in g:g['off_session_actions']=''
    g['off_session_actions']=g['off_session_actions'].fillna('')
    g['date']=pd.to_datetime(g['date']).dt.strftime('%Y-%m-%d')
    for k in ('open','high','low','close','volume','split_ratio'):g[k]=g[k].astype(float)
    g['provider_repaired']=g['provider_repaired'].astype(str).str.lower()
    return hashlib.sha256(g.sort_values('date')[columns].to_json(orient='records',double_precision=15).encode()).hexdigest()
def verify(group):
    if COLUMN not in group:return None
    values=group[COLUMN].fillna('').astype(str); entries=values[values.ne('')]
    if entries.empty:return None
    if len(entries)!=1:raise ValueError('hold requires one symbol anchor')
    e=json.loads(entries.iloc[0])
    if e.get('identity')!='CLOUD_JPX_SYMBOL_HOLD_V1' or e.get('symbol')!=str(group.symbol.iloc[0]) or e.get('current_rows_sha256')!=digest(group):raise ValueError('hold evidence identity/current row mismatch')
    for k in ('previous_source_sha256','acquisition_manifest_sha256','acquisition_inventory_sha256'):
        if not re.fullmatch('[a-f0-9]{64}',e.get(k,'')):raise ValueError('hold missing source identity')
    if not e.get('decisions') and not e.get('carried_from_sha256'):raise ValueError('hold has no unresolved decision or lineage')
    if e.get('carried_from_sha256'):
        parent=e.get('parent_audit')
        if not re.fullmatch('[a-f0-9]{64}',e['carried_from_sha256']) or not isinstance(parent,dict) or hashlib.sha256(json.dumps(parent,sort_keys=True).encode()).hexdigest()!=e['carried_from_sha256']:
            raise ValueError('invalid durable hold parent audit/hash')
    for r in e.get('decisions',[]):
        if r.get('symbol')!=e['symbol'] or r.get('held') is not True or r.get('decision')!='hold_symbol':raise ValueError('hold not supported by unresolved decision')
    return e

def apply(frame,symbol,decisions,*,previous_source_sha256,acquisition_manifest_sha256,acquisition_inventory_sha256,carried=None):
    out=frame.copy()
    if COLUMN not in out:out[COLUMN]=''
    group=out[out.symbol.eq(symbol)]
    if group.empty:raise ValueError('cannot hold absent symbol')
    e={'identity':'CLOUD_JPX_SYMBOL_HOLD_V1','symbol':symbol,'current_rows_sha256':digest(group),'previous_source_sha256':previous_source_sha256,'acquisition_manifest_sha256':acquisition_manifest_sha256,'acquisition_inventory_sha256':acquisition_inventory_sha256,'decisions':decisions}
    if carried:
        e['carried_from_sha256']=hashlib.sha256(json.dumps(carried,sort_keys=True).encode()).hexdigest()
        e['parent_audit']=carried
    out.loc[group.index,COLUMN]=''
    out.at[group.index[-1],COLUMN]=json.dumps(e,sort_keys=True,separators=(',',':'))
    verify(out.loc[group.index])
    usable=out.loc[group.index,'source_usable'].astype(bool)
    out.loc[group.index[usable],'source_issue']=ISSUE
    out.loc[group.index,'source_usable']=False
    return out

def audit(frame):
    return [e for _,g in frame.groupby('symbol',sort=False) if (e:=verify(g))]

def carry(previous,current,*,archive):
    """Carry only CSV-hash/quality-receipt verified holds; never implicit release."""
    prior=audit(previous)
    if not prior:return current
    lineage=previous.attrs.get('jpx_hold_lineage')
    if not lineage or lineage.get('dailySha256')!=previous.attrs.get('source_sha256') or lineage.get('holds')!=prior:
        raise ValueError('prior JPX hold has no matching CSV/quality lineage')
    if archive is None:raise ValueError('JPX hold carry requires retained acquisition identity')
    info=archive.verified_revision_info()
    out=current
    for e in prior:
        if not out.symbol.eq(e['symbol']).any():
            raise ValueError('held symbol absent in new acquisition; explicit resolution required')
        out=apply(out,e['symbol'],[],previous_source_sha256=lineage['dailySha256'],acquisition_manifest_sha256=info['manifestSha256'],acquisition_inventory_sha256=info['responseInventorySha256'],carried=e)
    return out
def verify_cached_lineage(frame,quality,sha):
    holds=audit(frame)
    if holds and (quality.get('identity')!='CLOUD_SOURCE_QUALITY_V1' or quality.get('daily_sha256')!=sha or quality.get('source_revision',{}).get('jpxHolds')!=holds):
        raise ValueError('cached JPX holds require matching CSV/quality evidence; cannot recreate lineage')
    return holds

