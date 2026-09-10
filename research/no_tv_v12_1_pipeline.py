from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

import no_tv_v10_standalone as base
import no_tv_v12_pine_hybrid as v12
import no_tv_stage2_selector as s2


def build_dataset(a):
    teacher=base.load_teacher(a.teacher)
    wl,_,wl_stats=base.load_exact_watchlists(a.watchlist_repo,base.TRAIN_START,base.TEST_END)
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
    frames=[];errors={};codes=sorted(union)
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(v12.fetch_v12,c,base.TRAIN_START,base.FETCH_END):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try:fr,err=f.result()
            except Exception as e:fr,err=None,type(e).__name__
            if fr is not None and not fr.empty:frames.append(fr)
            elif err:errors[err]=errors.get(err,0)+1
            if i%100==0:print(f"progress {i}/{len(codes)} frames={len(frames)}",flush=True)
    if not frames:raise RuntimeError("no rows")
    data=pd.concat(frames,ignore_index=True);data["monitor_key"]=data.date.astype(str)+"|"+data.symbol.astype(str)
    data=data[data.monitor_key.isin(monitor_keys)&data.date.between(base.TRAIN_START,base.TEST_END)].copy()
    data["key"]=data.symbol.astype(str)+"|"+data.date.astype(str)+"|"+data.session.astype(int).astype(str);data["label"]=data.key.isin(pos).astype(int)
    return teacher,wl_stats,data,{"requested":len(codes),"errors":errors}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int);ap.add_argument("--max-workers",type=int,default=20);ap.add_argument("--output-dir",default="research_artifacts/v12_1_pipeline")
    a=ap.parse_args();teacher,wl_stats,data,yahoo=build_dataset(a)
    train=data[data.date.between(base.TRAIN_START,base.TRAIN_END)].copy();valid=data[data.date.between(base.VALID_START,base.VALID_END)].copy();test=data[data.date.between(base.TEST_START,base.TEST_END)].copy()
    # Stage 1A: exact Pine-state candidate generator.
    valid_exact=valid[valid.pine_bottom>0].copy();test_exact=test[test.pine_bottom>0].copy()
    # Stage 1B: Pine-aware hybrid probability model. July alone fixes the threshold.
    h=HistGradientBoostingClassifier(learning_rate=.04,max_iter=220,max_leaf_nodes=15,min_samples_leaf=35,l2_regularization=2.0,random_state=121)
    ytr=train.label.to_numpy(int);h.fit(train[v12.HYBRID_FEATURES].astype(float),ytr,sample_weight=base.balanced_weights(ytr))
    pv=h.predict_proba(valid[v12.HYBRID_FEATURES].astype(float))[:,1];th=base.choose_threshold(valid.label.to_numpy(int),pv);pt=h.predict_proba(test[v12.HYBRID_FEATURES].astype(float))[:,1]
    valid["p_bottom_hybrid"]=pv;test["p_bottom_hybrid"]=pt;valid_hybrid=valid[valid.p_bottom_hybrid>=th["threshold"]].copy();test_hybrid=test[test.p_bottom_hybrid>=th["threshold"]].copy()
    # Stage 2: outcomes are learned ONLY from actual historical Tenchi BOTTOMs.
    train_bottom=train[(train.label==1)&train.perf_5bd.notna()].copy();valid_bottom=valid[(valid.label==1)&valid.perf_5bd.notna()].copy();test_bottom=test[(test.label==1)&test.perf_5bd.notna()].copy()
    if min(len(train_bottom),len(valid_bottom),len(test_bottom))<20:raise RuntimeError("too few actual BOTTOM rows")
    win,hit,reg=s2.outcome_models(train_bottom)
    valid_bottom=s2.attach_outcome_scores(valid_bottom,win,hit,reg);test_bottom=s2.attach_outcome_scores(test_bottom,win,hit,reg)
    valid_exact=s2.attach_outcome_scores(valid_exact,win,hit,reg);test_exact=s2.attach_outcome_scores(test_exact,win,hit,reg)
    valid_hybrid=s2.attach_outcome_scores(valid_hybrid,win,hit,reg);test_hybrid=s2.attach_outcome_scores(test_hybrid,win,hit,reg)
    policy,trials=s2.choose_policy(valid_bottom)
    selected_actual=s2.score_with_policy(test_bottom,policy);selected_exact=s2.score_with_policy(test_exact,policy);selected_hybrid=s2.score_with_policy(test_hybrid,policy)
    result={"scope":"V12.1 Yahoo-only Pine-state candidate generation + Stage2 outcome selector","teacher":{"rows":len(teacher),"date_min":teacher.signal_date.min(),"date_max":teacher.signal_date.max()},"watchlists":wl_stats,"yahoo":yahoo,
      "split":{"train":{"n":len(train),"bottom":int(train.label.sum())},"valid":{"n":len(valid),"bottom":int(valid.label.sum()),"exact":len(valid_exact),"hybrid":len(valid_hybrid)},"test":{"n":len(test),"bottom":int(test.label.sum()),"exact":len(test_exact),"hybrid":len(test_hybrid)}},
      "stage1":{"exact_validation":v12.class_from_binary(valid,"pine_bottom"),"exact_test":v12.class_from_binary(test,"pine_bottom"),"hybrid_threshold":th,"hybrid_validation":base.class_stats(valid,pv,th["threshold"]),"hybrid_test":base.class_stats(test,pt,th["threshold"])},
      "stage2_policy":policy,"validation_policy_trials":sorted(trials,key=lambda x:x["objective"],reverse=True)[:12],"current_champion":base.CHAMPION,
      "trading_test":{"actual_bottom_all":base.trade_stats(test_bottom),"stage2_actual_bottom":base.trade_stats(selected_actual),"exact_pine_all":base.trade_stats(test_exact),"stage2_exact_pine":base.trade_stats(selected_exact),"hybrid_all":base.trade_stats(test_hybrid),"stage2_hybrid":base.trade_stats(selected_hybrid)},
      "selected_exact":selected_exact.sort_values(["date","outcome_score"],ascending=[True,False])[["date","session","symbol","outcome_score","p_win","p_hit10","pred_ret","stable_score","label","perf_5bd"]].to_dict("records"),
      "selected_hybrid":selected_hybrid.sort_values(["date","outcome_score"],ascending=[True,False])[["date","session","symbol","p_bottom_hybrid","outcome_score","p_win","p_hit10","pred_ret","stable_score","label","perf_5bd"]].to_dict("records")}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v12_1_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"split":result["split"],"stage1":result["stage1"],"stage2_policy":policy,"trading_test":result["trading_test"]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
