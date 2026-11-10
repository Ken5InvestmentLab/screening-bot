"""End-to-end revision stage. Official evidence loader is explicit.
Called only from the historical numeric-revision failure path.
"""
from .corporate_actions import normalize_daily,validate_source_revision,CorporateActionError
from .jpx_decisions import decide
from .jpx_holds import apply,audit

def resolve(previous,current,*,evidence,previous_source_sha256,archive):
    if 'corporate_actions_version' not in previous:
        raise CorporateActionError('JPX resolver requires previously verified share basis')
    original=normalize_daily(current)
    proposed=validate_source_revision(previous,original,previous_source_sha256=previous_source_sha256,collect_unexplained=True)
    cells=proposed.get('unexplainedCells',[])
    if not cells:return original,proposed
    if archive is None:raise CorporateActionError('JPX resolver requires retained response archive')
    info=archive.verified_revision_info()
    decisions=[decide(**cell,evidence=evidence.get((cell['symbol'],cell['session'],cell['field']))) for cell in cells]
    held={d['symbol'] for d in decisions if d['held']}
    corrected=original.copy();confirmations={}
    for d in decisions:
        symbol,date,field=d['symbol'],d['date'],d['field']
        if symbol in held:continue
        if d['decision']=='accept_new':confirmations[(symbol,date,field)]=evidence[(symbol,date,field)]
        elif d['decision']=='keep_old':
            mask=corrected.symbol.eq(symbol)&corrected.date.eq(date)
            if int(mask.sum())!=1:raise CorporateActionError('JPX restore identity missing/duplicate')
            factor=corrected.loc[mask,'split_factor'];value=float(d['selected'])
            corrected.loc[mask,field]=value*factor if field=='volume' else value/factor
            corrected.loc[mask,'actual_'+field]=value
    corrected=normalize_daily(corrected)
    for symbol in sorted(held):
        corrected=apply(corrected,symbol,[d for d in decisions if d['symbol']==symbol and d['held']],previous_source_sha256=previous_source_sha256,acquisition_manifest_sha256=info['manifestSha256'],acquisition_inventory_sha256=info['responseInventorySha256'])
    corrected=normalize_daily(corrected)
    # Original previous + original SHA preserve existing reviewed registry contract.
    receipt=validate_source_revision(previous,corrected,previous_source_sha256=previous_source_sha256,confirmed_new=confirmations)
    receipt['jpxDecisions']=decisions;receipt['jpxHolds']=audit(corrected)
    receipt['jpxAcquisition']=info
    return corrected,receipt

