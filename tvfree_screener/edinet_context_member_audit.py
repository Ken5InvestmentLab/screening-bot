#!/usr/bin/env python3
"""Outcome-blind audit of candidate EDINET CSV contexts for Class-B documents.

Reads only the already-frozen pre-parser type=5 ZIP bytes. It does not choose a
fact, mutate parser aliases, emit accounting values, or inspect strategy returns.
"""
from __future__ import annotations
import argparse, io, json, hashlib
from pathlib import Path
import zipfile
import pandas as pd
from edinet_fundamental_collector import CSV_COLUMN_ALIASES, FACT_SPECS

CLASS_B_DOCS=("S100QF0X","S100RWZI","S100UXL5")
FIELDS=("assets","equity","operating_income","net_income")

def _col(df, logical):
    return next((n for n in CSV_COLUMN_ALIASES[logical] if n in df.columns),None)

def _read_csvs(zip_bytes):
    out=[]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in sorted(zf.namelist()):
            if not name.lower().endswith('.csv'): continue
            raw=zf.read(name); df=None
            for enc in ('utf-16','utf-8-sig','cp932'):
                try:
                    # EDINET XBRL-to-CSV files are tab-delimited despite .csv suffix.
                    df=pd.read_csv(io.BytesIO(raw),encoding=enc,sep='\t',dtype=str,keep_default_na=False)
                    break
                except Exception: pass
            if df is not None: out.append((name,df))
    return out

def audit_doc(path,doc_id):
    raw_zip=path.read_bytes(); records=[]; distinct_values={f:set() for f in FIELDS}
    for filename,df in _read_csvs(raw_zip):
        ec=_col(df,'element_id')
        if ec is None: continue
        cc,rc,oc,pc,vc=(_col(df,x) for x in ('context_id','relative_year','consolidated','period_type','value'))
        for field in FIELDS:
            hit=df[df[ec].isin(FACT_SPECS[field]['elements'])]
            for _,row in hit.iterrows():
                relative=str(row.get(rc,'')) if rc else ''
                value=str(row.get(vc,'')) if vc else ''
                if relative in ('当期','当期末','CurrentYear') and value.strip(): distinct_values[field].add(value)
                records.append({'field':field,'kind':FACT_SPECS[field]['kind'],'element_id':str(row.get(ec,'')),'context_id':str(row.get(cc,'')) if cc else '','relative_year':relative,'consolidated':str(row.get(oc,'')) if oc else '','period_type':str(row.get(pc,'')) if pc else '','value_present':bool(value.strip()),'source_csv':filename})
    records.sort(key=lambda x:(x['field'],x['element_id'],x['context_id'],x['source_csv']))
    by={f:[r for r in records if r['field']==f] for f in FIELDS}
    current={f:[r for r in by[f] if r['relative_year'] in ('当期','当期末','CurrentYear')] for f in FIELDS}
    return {'doc_id':doc_id,'frozen_zip_sha256':hashlib.sha256(raw_zip).hexdigest(),'status':'CONTEXT_CANDIDATES_ENUMERATED' if records else 'NO_MAPPED_CANDIDATES_FAIL_CLOSED','strategy_outcomes_opened':False,'performance_opened':False,'fact_values_emitted':False,'candidate_count_by_field':{f:len(by[f]) for f in FIELDS},'current_candidate_count_by_field':{f:len(current[f]) for f in FIELDS},'current_distinct_value_count_by_field':{f:len(distinct_values[f]) for f in FIELDS},'mapped_source_csv_count':len({r['source_csv'] for r in records}),'candidate_contexts':by}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--zip-root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    root,out=Path(a.zip_root),Path(a.out); out.mkdir(parents=True,exist_ok=True); docs=[]
    for doc_id in CLASS_B_DOCS:
        p=root/f'{doc_id}.zip'
        if not p.is_file(): raise SystemExit(f'FAIL_CLOSED missing frozen ZIP: {doc_id}')
        rec=audit_doc(p,doc_id); (out/f'{doc_id}_contexts.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2,sort_keys=True)+'\n'); docs.append(rec)
    collision=all(all(d['current_candidate_count_by_field'][f]>1 and d['current_distinct_value_count_by_field'][f]>1 for f in FIELDS) for d in docs)
    summary={'status':'CLASS_B_MULTI_SOURCE_COLLISION_CONFIRMED' if collision else 'CLASS_B_CONTEXT_AUDIT_COMPLETE_UNRESOLVED','documents':len(docs),'doc_ids':list(CLASS_B_DOCS),'strategy_outcomes_opened':False,'performance_opened':False,'fact_values_emitted':False,'cross_field_collision_confirmed':collision,'rule':'Enumerate frozen candidates only; distinct-value counts may prove ambiguity but accounting values are never emitted or selected.'}
    (out/'class_b_context_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n'); print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
    if any(d['status']!='CONTEXT_CANDIDATES_ENUMERATED' for d in docs): raise SystemExit(2)
if __name__=='__main__': main()
