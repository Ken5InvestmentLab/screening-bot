from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v11_independent_selector as v11
import no_tv_stage2_selector as s2
import no_tv_v10_standalone as base

GUARDS = [
    {"id":"none"},
    {"id":"sr12","max_session_range":.12},
    {"id":"sr16","max_session_range":.16},
    {"id":"sr20","max_session_range":.20},
    {"id":"ret10","max_abs_session_ret":.10},
    {"id":"ret15","max_abs_session_ret":.15},
    {"id":"day12","max_day_range":12.0},
    {"id":"day16","max_day_range":16.0},
    {"id":"atr8","max_atr":8.0},
    {"id":"atr10","max_atr":10.0},
    {"id":"moderate","max_session_range":.16,"max_abs_session_ret":.12,"max_day_range":16.0,"max_atr":10.0},
    {"id":"strict","max_session_range":.12,"max_abs_session_ret":.10,"max_day_range":12.0,"max_atr":8.0},
]
COOLDOWNS = [0, 3, 5, 10]
TOPN = [1, 2, 3]


def apply_guard(df,g):
    m=pd.Series(True,index=df.index)
    if "max_session_range" in g:m &= pd.to_numeric(df.session_range_pct,errors="coerce") <= float(g["max_session_range"])
    if "max_abs_session_ret" in g:m &= pd.to_numeric(df.session_ret,errors="coerce").abs() <= float(g["max_abs_session_ret"])
    if "max_day_range" in g:m &= pd.to_numeric(df.day_range_pct,errors="coerce") <= float(g["max_day_range"])
    if "max_atr" in g:m &= pd.to_numeric(df.atr14_pct,errors="coerce") <= float(g["max_atr"])
    return df[m].copy()


def select_with_cooldown(df,score,n,cooldown):
    if df.empty:return df
    d=df.sort_values(["date",score],ascending=[True,False]).copy()
    dates=sorted(d.date.unique()); date_ix={x:i for i,x in enumerate(dates)}; last={}; keep=[]
    for dt,g in d.groupby("date",sort=True):
        taken=0;di=date_ix[dt]
        for idx,row in g.iterrows():
            sym=str(row.symbol)
            if cooldown and sym in last and di-last[sym] < cooldown:continue
            keep.append(idx);last[sym]=di;taken+=1
            if taken>=n:break
    return d.loc[keep].copy()


def risk_stats(df):
    st=base.trade_stats(df)
    x=pd.to_numeric(df.perf_5bd,errors="coerce").dropna().to_numpy(float) if not df.empty else np.array([])
    st["min"]=float(np.min(x)) if len(x) else 0.0
    st["p10"]=float(np.quantile(x,.10)) if len(x) else 0.0
    st["loss20"]=int(np.sum(x<=-.20)) if len(x) else 0
    return st


def objective(st):
    if st["n"]<20:return -999.0
    # prioritize repeatable return and explicitly penalize tail losses
    tail_penalty=.20*min(0.0,st["p10"])+.03*min(0.0,st["min"])-.01*st["loss20"]
    return .45*st["robust_avg"]+.25*st["avg"]+.15*st["median"]+.01*(st["wr"]-.5)+.015*st["target_rate"]+tail_penalty


def attach_joint(df,w):
    o=df.copy();o["joint_score"]=w[0]*o.p_win+w[1]*o.p_hit10+w[2]*o.ret_component
    return o


def choose(valid):
    trials=[];best=None
    for w in v11.WEIGHT_SETS:
        scored=attach_joint(valid,w)
        for g in GUARDS:
            guarded=apply_guard(scored,g)
            for cd in COOLDOWNS:
                for n in TOPN:
                    sel=select_with_cooldown(guarded,"joint_score",n,cd);st=risk_stats(sel);obj=objective(st)
                    rec={"weights":list(w),"guard":g,"cooldown_days":cd,"topn":n,"objective":float(obj),"stats":st}
                    trials.append(rec)
                    if best is None or (obj,best_tiebreak(rec))>(best["objective"],best_tiebreak(best)):best=rec
    return best,sorted(trials,key=lambda r:(r["objective"],best_tiebreak(r)),reverse=True)


def best_tiebreak(r):
    st=r.get("stats",{});g=r.get("guard",{})
    # on exact/near ties prefer lower tail risk, then simpler guard
    complexity=max(0,len(g)-1)+(1 if r.get("cooldown_days",0) else 0)
    return (st.get("p10",0),st.get("min",0),-complexity)


def apply_policy(df,p):
    scored=attach_joint(df,p["weights"]);guarded=apply_guard(scored,p["guard"])
    return select_with_cooldown(guarded,"joint_score",int(p["topn"]),int(p["cooldown_days"]))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int);ap.add_argument("--max-workers",type=int,default=20);ap.add_argument("--output-dir",default="research_artifacts/v11_1_risk")
    a=ap.parse_args();_,wl_stats,data,_,_,_,yahoo=s2.build_dataset(a);data=v11.enrich_cross_sectional(data)
    train=data[data.date.between(base.TRAIN_START,base.TRAIN_END)&data.perf_5bd.notna()].copy();valid=data[data.date.between(base.VALID_START,base.VALID_END)&data.perf_5bd.notna()].copy();test=data[data.date.between(base.TEST_START,base.TEST_END)&data.perf_5bd.notna()].copy()
    fcols=v11.features();models=v11.fit_models(train,fcols);v=v11.attach(valid,models,fcols);t=v11.attach(test,models,fcols);policy,trials=choose(v);selected=apply_policy(t,policy)
    # fixed sensitivity rows are diagnostic only; promotion decision must use validation-selected policy above
    sensitivity={}
    base_policy={"weights":policy["weights"],"topn":policy["topn"],"cooldown_days":0}
    for g in GUARDS:
        p={**base_policy,"guard":g};sensitivity[g["id"]]=risk_stats(apply_policy(t,p))
    result={"scope":"V11.1 independent Yahoo-only with validation-selected tail-risk guard","watchlists":wl_stats,"yahoo":yahoo,"policy":policy,"validation_trials":trials[:25],"current_champion":base.CHAMPION,
      "trading_test":{"selected":risk_stats(selected),"actual_bottom":risk_stats(t[t.label==1]),"reconstructed_stable6":risk_stats(t[t.stable_score==6])},"test_guard_sensitivity_diagnostic_only":sensitivity,
      "selected":selected.sort_values(["date","joint_score"],ascending=[True,False])[["date","session","symbol","joint_score","p_win","p_hit10","pred_ret","session_ret","session_range_pct","day_range_pct","atr14_pct","stable_score","label","perf_5bd"]].to_dict("records")}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v11_1_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"policy":policy,"trading_test":result["trading_test"],"sensitivity":sensitivity},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
