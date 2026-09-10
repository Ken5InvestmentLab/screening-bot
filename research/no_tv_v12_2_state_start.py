from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v12_pine_hybrid as v12

STARTS=["full","2024-09-01","2025-01-01","2025-04-01","2025-07-01","2025-10-01","2025-12-01","2026-01-01","2026-02-01"]


def state_variant(sessions,start):
    z=sessions.copy() if start=="full" else sessions[sessions.date>=start].copy()
    if z.empty:return pd.DataFrame(columns=["date","session",f"pine_{start}"])
    st=v12.pine_state_frame(z.reset_index(drop=True))[["date","session","pine_bottom"]].copy();st=st.rename(columns={"pine_bottom":f"pine_{start}"});return st


def fetch_code(code,start_date,end_date):
    chart,err=base.fetch_chart(code)
    if err:return None,err
    hourly=base.parse_1h_chart(chart or {})
    if hourly is None:return None,"parse_failed"
    sessions=base.synthetic_sessions(hourly).reset_index(drop=True)
    cand=base.build_issue_candidates(code,chart or {},start_date,end_date)
    if cand is None:return None,"no_data"
    if cand.empty:return cand,None
    out=cand
    for s in STARTS:out=out.merge(state_variant(sessions,s),on=["date","session"],how="left")
    return out,None


def metrics(df,col):return v12.class_from_binary(df,col)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=20);ap.add_argument("--output-dir",default="research_artifacts/v12_2_state_start")
    a=ap.parse_args();teacher=base.load_teacher(a.teacher);wl,_,wstat=base.load_exact_watchlists(a.watchlist_repo,base.TRAIN_START,base.TEST_END)
    mk=set();union=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=base.TEST_END:union.update(syms);mk.update(f"{d}|{s}" for s in syms)
    teacher["monitor_key"]=teacher.signal_date+"|"+teacher.symbol_code;tm=teacher[teacher.monitor_key.isin(mk)&teacher.signal_date.between(base.TRAIN_START,base.TEST_END)].copy();pos=set(tm.key)
    if a.max_symbols:
        freq={s:0 for s in union}
        for syms in wl.values():
            for s in syms:
                if s in freq:freq[s]+=1
        must=set(tm.loc[tm.signal_date.between(base.TEST_START,base.TEST_END),"symbol_code"]);union=set(sorted(union,key=lambda s:(s not in must,-freq[s],s))[:a.max_symbols]);mk={k for k in mk if k.split("|",1)[1] in union};pos={k for k in pos if k.split("|",1)[0] in union}
    frames=[];errors={};codes=sorted(union)
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(fetch_code,c,base.TRAIN_START,base.FETCH_END):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try:fr,err=f.result()
            except Exception as e:fr,err=None,type(e).__name__
            if fr is not None and not fr.empty:frames.append(fr)
            elif err:errors[err]=errors.get(err,0)+1
            if i%100==0:print(f"progress {i}/{len(codes)}",flush=True)
    d=pd.concat(frames,ignore_index=True);d["monitor_key"]=d.date.astype(str)+"|"+d.symbol.astype(str);d=d[d.monitor_key.isin(mk)&d.date.between(base.TRAIN_START,base.TEST_END)].copy();d["key"]=d.symbol.astype(str)+"|"+d.date.astype(str)+"|"+d.session.astype(int).astype(str);d["label"]=d.key.isin(pos).astype(int)
    valid=d[d.date.between(base.VALID_START,base.VALID_END)].copy();test=d[d.date.between(base.TEST_START,base.TEST_END)].copy();rows=[]
    for s in STARTS:
        col=f"pine_{s}";vm=metrics(valid,col);tmx=metrics(test,col);rows.append({"start":s,"validation":vm,"test":tmx})
    chosen=max(rows,key=lambda r:(r["validation"]["f1"],r["validation"]["recall"],r["validation"]["precision"]))
    result={"scope":"Pine state initialization sensitivity; July selects start, August untouched","watchlists":wstat,"errors":errors,"rows":len(d),"starts":rows,"chosen_by_july":chosen}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v12_2_state_start.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
