from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v13_official_daily as core


def build_dataset(a):
    teacher=base.load_teacher(a.teacher);wl,_,wl_stats=base.load_exact_watchlists(a.watchlist_repo,base.TRAIN_START,base.TEST_END)
    monitor_keys=set();union=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=base.TEST_END:
            union.update(syms);monitor_keys.update(f"{d}|{s}" for s in syms)
    teacher["monitor_key"]=teacher.signal_date+"|"+teacher.symbol_code
    tm=teacher[teacher.monitor_key.isin(monitor_keys)&teacher.signal_date.between(base.TRAIN_START,base.TEST_END)].copy();pos=set(tm.key)
    if a.max_symbols:
        freq={s:0 for s in union}
        for syms in wl.values():
            for s in syms:
                if s in freq:freq[s]+=1
        must=set(tm.loc[tm.signal_date.between(base.TEST_START,base.TEST_END),"symbol_code"])
        ordered=sorted(union,key=lambda s:(s not in must,-freq[s],s))[:a.max_symbols];union=set(ordered)
        monitor_keys={k for k in monitor_keys if k.split("|",1)[1] in union};pos={k for k in pos if k.split("|",1)[0] in union}
    frames=[];errors={};ok=0;codes=sorted(union)
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(core.fetch_one,c,base.TRAIN_START,base.FETCH_END):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try:fr,err=f.result()
            except Exception as e:fr,err=None,type(e).__name__
            if fr is not None:
                ok+=1
                if not fr.empty:frames.append(fr)
            elif err:errors[err]=errors.get(err,0)+1
            if i%100==0:print(f"progress {i}/{len(codes)} frames={len(frames)}",flush=True)
    if not frames:raise RuntimeError("no candidate rows")
    data=pd.concat(frames,ignore_index=True);data["monitor_key"]=data.date.astype(str)+"|"+data.symbol.astype(str)
    data=data[data.monitor_key.isin(monitor_keys)&data.date.between(base.TRAIN_START,base.TEST_END)].copy()
    data["key"]=data.symbol.astype(str)+"|"+data.date.astype(str)+"|"+data.session.astype(int).astype(str);data["label"]=data.key.isin(pos).astype(int)
    return teacher,wl_stats,data,{"requested":len(codes),"ok":ok,"errors":errors}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v13_independent")
    a=ap.parse_args();teacher,wl_stats,data,yahoo=build_dataset(a);data=v11.enrich_cross_sectional(data)
    train=data[data.date.between(base.TRAIN_START,base.TRAIN_END)&data.perf_5bd.notna()].copy();valid=data[data.date.between(base.VALID_START,base.VALID_END)&data.perf_5bd.notna()].copy();test=data[data.date.between(base.TEST_START,base.TEST_END)&data.perf_5bd.notna()].copy()
    fcols=v11.features();models=v11.fit_models(train,fcols);v=v11.attach(valid,models,fcols);t=v11.attach(test,models,fcols)
    policy,trials=risk.choose(v);selected=risk.apply_policy(t,policy)
    result={"scope":"V13 fully independent Yahoo-only; official 1D completed history + 1H partial current day","teacher":{"rows":len(teacher)},"watchlists":wl_stats,"yahoo":yahoo,
      "split":{"train":len(train),"valid":len(valid),"test":len(test)},"policy":policy,"validation_trials":trials[:25],"current_champion":base.CHAMPION,
      "trading_test":{"all_monitored":risk.risk_stats(t),"v13_selected":risk.risk_stats(selected),"actual_bottom":risk.risk_stats(t[t.label==1]),"reconstructed_stable6":risk.risk_stats(t[t.stable_score==6])},
      "selected":selected.sort_values(["date","joint_score"],ascending=[True,False])[["date","session","symbol","joint_score","p_win","p_hit10","pred_ret","stable_score","label","perf_5bd"]].to_dict("records")}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v13_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"policy":policy,"trading_test":result["trading_test"]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
