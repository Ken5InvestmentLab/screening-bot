from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v14_pine_outcome as v14
import no_tv_v16_selective as selective

FOLDS=[
 {"id":"F1","train_start":"2026-03-05","train_end":"2026-04-30","valid_start":"2026-05-01","valid_end":"2026-05-31","test_start":"2026-06-01","test_end":"2026-06-30"},
 {"id":"F2","train_start":"2026-03-05","train_end":"2026-05-31","valid_start":"2026-06-01","valid_end":"2026-06-30","test_start":"2026-07-01","test_end":"2026-07-31"},
 {"id":"F3","train_start":"2026-03-05","train_end":"2026-06-30","valid_start":"2026-07-01","valid_end":"2026-07-31","test_start":"2026-08-01","test_end":"2026-08-31"},
]
SAMPLE_CUTOFF="2026-04-30"


def build_dataset(a):
    teacher=base.load_teacher(a.teacher);wl,_,wstat=base.load_exact_watchlists(a.watchlist_repo,base.TRAIN_START,base.TEST_END)
    union=set();monitor_keys=set();early_freq={}
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=base.TEST_END:
            union.update(syms);monitor_keys.update(f"{d}|{s}" for s in syms)
        if base.TRAIN_START<=d<=SAMPLE_CUTOFF:
            for s in syms:early_freq[s]=early_freq.get(s,0)+1
    if a.max_symbols:
        # No labels, returns, May-Aug watchlist frequency, or future outcomes are used here.
        codes=sorted(union,key=lambda s:(-early_freq.get(s,0),s))[:a.max_symbols]
        universe=set(codes);monitor_keys={k for k in monitor_keys if k.split("|",1)[1] in universe}
    else:
        codes=sorted(union);universe=set(codes)
    teacher["monitor_key"]=teacher.signal_date+"|"+teacher.symbol_code;teacher_mon=teacher[teacher.monitor_key.isin(monitor_keys)&teacher.signal_date.between(base.TRAIN_START,base.TEST_END)].copy();positive_keys=set(teacher_mon.key)
    frames=[];errors={};ok=0
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(v14.fetch_one,c,base.TRAIN_START,base.FETCH_END):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try:fr,err=f.result()
            except Exception as e:fr,err=None,type(e).__name__
            if fr is not None:
                ok+=1
                if not fr.empty:frames.append(fr)
            elif err:errors[err]=errors.get(err,0)+1
            if i%100==0:print(f"progress {i}/{len(codes)} frames={len(frames)}",flush=True)
    if not frames:raise RuntimeError("no data")
    d=pd.concat(frames,ignore_index=True);d["monitor_key"]=d.date.astype(str)+"|"+d.symbol.astype(str);d=d[d.monitor_key.isin(monitor_keys)&d.date.between(base.TRAIN_START,base.TEST_END)].copy();d["key"]=d.symbol.astype(str)+"|"+d.date.astype(str)+"|"+d.session.astype(int).astype(str);d["label"]=d.key.isin(positive_keys).astype(int)
    return teacher,wstat,d,{"requested":len(codes),"ok":ok,"errors":errors},codes


def fit_attach(train,valid,test,variant):
    cols=v11.features() if variant=="v13" else v14.feature_cols();models=v11.fit_models(train,cols) if variant=="v13" else v14.fit(train,cols);v=v11.attach(valid,models,cols) if variant=="v13" else v14.attach(valid,models,cols);t=v11.attach(test,models,cols) if variant=="v13" else v14.attach(test,models,cols);return v,t


def evaluate(data,fold,variant):
    train=data[data.date.between(fold["train_start"],fold["train_end"])&data.perf_5bd.notna()].copy();valid=data[data.date.between(fold["valid_start"],fold["valid_end"])&data.perf_5bd.notna()].copy();test=data[data.date.between(fold["test_start"],fold["test_end"])&data.perf_5bd.notna()].copy();v,t=fit_attach(train,valid,test,variant);policy,trials=selective.choose(v);sel=selective.apply(t,policy)
    return {"fold":fold["id"],"variant":variant,"sizes":{"train":len(train),"valid":len(valid),"test":len(test)},"policy":policy,"validation":policy["stats"],"test":risk.risk_stats(sel),"selected":sel.assign(fold=fold["id"],variant=variant)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v17_unbiased_rolling")
    a=ap.parse_args();teacher,wstat,data,yahoo,codes=build_dataset(a);data=v11.enrich_cross_sectional(data);rows=[];parts={"v13":[],"v14":[]}
    for fold in FOLDS:
        for variant in ("v13","v14"):
            print(f"evaluate {fold['id']} {variant}",flush=True);r=evaluate(data,fold,variant);parts[variant].append(r.pop("selected"));rows.append(r)
    combined={k:risk.risk_stats(pd.concat(v,ignore_index=True)) for k,v in parts.items()}
    result={"scope":"Leakage-free smoke: 350 symbols chosen only from Mar05-Apr30 watchlist frequency; rolling policies use prior validation month only","sampling":{"cutoff":SAMPLE_CUTOFF,"max_symbols":a.max_symbols,"symbols":codes},"teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,"folds":rows,"combined_test":combined,"current_champion":base.CHAMPION}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v17_unbiased_rolling.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"folds":rows,"combined_test":combined},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
