from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v12_pine_hybrid as v12
import no_tv_v13_official_daily as d13

PINE=v12.PINE_FEATURES


def fetch_one(code,start,end):
    with ThreadPoolExecutor(max_workers=2) as ex:
        fh=ex.submit(d13.fetch_interval,code,"1h","730d");fd=ex.submit(d13.fetch_interval,code,"1d","730d")
        hc,he=fh.result();dc,de=fd.result()
    if he:return None,"1h_"+str(he)
    if de:return None,"1d_"+str(de)
    hourly=base.parse_1h_chart(hc or {})
    if hourly is None:return None,"hourly_parse_failed"
    sessions=base.synthetic_sessions(hourly).reset_index(drop=True)
    cand=d13.build_issue_candidates_v13(code,hc or {},dc or {},start,end)
    if cand is None:return None,"no_data"
    if cand.empty:return cand,None
    state=v12.pine_state_frame(sessions)
    return cand.merge(state,on=["date","session"],how="left"),None


def build_dataset(a):
    teacher=base.load_teacher(a.teacher);wl,_,wstat=base.load_exact_watchlists(a.watchlist_repo,base.TRAIN_START,base.TEST_END)
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
        fut={ex.submit(fetch_one,c,base.TRAIN_START,base.FETCH_END):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try:fr,err=f.result()
            except Exception as e:fr,err=None,type(e).__name__
            if fr is not None and not fr.empty:frames.append(fr)
            elif err:errors[err]=errors.get(err,0)+1
            if i%100==0:print(f"progress {i}/{len(codes)} frames={len(frames)}",flush=True)
    if not frames:raise RuntimeError("no data")
    d=pd.concat(frames,ignore_index=True);d["monitor_key"]=d.date.astype(str)+"|"+d.symbol.astype(str);d=d[d.monitor_key.isin(mk)&d.date.between(base.TRAIN_START,base.TEST_END)].copy();d["key"]=d.symbol.astype(str)+"|"+d.date.astype(str)+"|"+d.session.astype(int).astype(str);d["label"]=d.key.isin(pos).astype(int)
    return teacher,wstat,d,{"requested":len(codes),"errors":errors}


def feature_cols():return v11.features()+PINE


def fit(train,cols):
    x=train[cols].astype(float);r=train.perf_5bd.to_numpy(float);yw=(r>0).astype(int);yh=(r>=.10).astype(int)
    win=HistGradientBoostingClassifier(learning_rate=.035,max_iter=260,max_leaf_nodes=15,min_samples_leaf=70,l2_regularization=4.0,random_state=141)
    hit=HistGradientBoostingClassifier(learning_rate=.035,max_iter=260,max_leaf_nodes=15,min_samples_leaf=55,l2_regularization=4.5,random_state=142)
    reg=HistGradientBoostingRegressor(learning_rate=.03,max_iter=240,max_leaf_nodes=15,min_samples_leaf=70,l2_regularization=4.5,random_state=143)
    win.fit(x,yw,sample_weight=base.balanced_weights(yw));hit.fit(x,yh,sample_weight=base.balanced_weights(yh));reg.fit(x,np.clip(r,-.20,.30));return win,hit,reg


def attach(df,models,cols):
    win,hit,reg=models;o=df.copy();x=o[cols].astype(float);o["p_win"]=win.predict_proba(x)[:,1];o["p_hit10"]=hit.predict_proba(x)[:,1];o["pred_ret"]=reg.predict(x);o["ret_component"]=.5+.5*np.tanh(o.pred_ret.to_numpy(float)/.08);return o


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v14")
    a=ap.parse_args();teacher,wstat,d,yahoo=build_dataset(a);d=v11.enrich_cross_sectional(d);train=d[d.date.between(base.TRAIN_START,base.TRAIN_END)&d.perf_5bd.notna()].copy();valid=d[d.date.between(base.VALID_START,base.VALID_END)&d.perf_5bd.notna()].copy();test=d[d.date.between(base.TEST_START,base.TEST_END)&d.perf_5bd.notna()].copy();cols=feature_cols();models=fit(train,cols);v=attach(valid,models,cols);t=attach(test,models,cols);policy,trials=risk.choose(v);sel=risk.apply_policy(t,policy)
    result={"scope":"V14 Yahoo-only official daily + Pine state features; direct 5BD outcome learning","teacher":{"rows":len(teacher)},"watchlists":wstat,"yahoo":yahoo,"split":{"train":len(train),"valid":len(valid),"test":len(test)},"policy":policy,"validation_trials":trials[:25],"current_champion":base.CHAMPION,
      "trading_test":{"selected":risk.risk_stats(sel),"all_monitored":risk.risk_stats(t),"pine_bottom_only":risk.risk_stats(t[t.pine_bottom>0]),"actual_bottom":risk.risk_stats(t[t.label==1]),"stable6":risk.risk_stats(t[t.stable_score==6])},
      "selected":sel.sort_values(["date","joint_score"],ascending=[True,False])[["date","session","symbol","joint_score","p_win","p_hit10","pred_ret","pine_bottom","pine_rsi12","stable_score","label","perf_5bd"]].to_dict("records")}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v14_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"policy":policy,"trading_test":result["trading_test"]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
