from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v14_pine_outcome as v14

GUARDS=[
 {"id":"none"},
 {"id":"sr12","max_session_range":.12},
 {"id":"day12","max_day_range":12.0},
 {"id":"atr10","max_atr":10.0},
 {"id":"moderate","max_session_range":.16,"max_abs_session_ret":.12,"max_day_range":16.0,"max_atr":10.0},
 {"id":"strict","max_session_range":.12,"max_abs_session_ret":.10,"max_day_range":12.0,"max_atr":8.0},
]
COOLDOWNS=[0,3,5]
MIN_VALID_N=8


def add_score(df,w):
    o=df.copy();o["joint_score"]=w[0]*o.p_win+w[1]*o.p_hit10+w[2]*o.ret_component;return o


def candidate_thresholds(scored,g):
    x=risk.apply_guard(scored,g)
    if x.empty:return []
    top=x.sort_values(["date","joint_score"],ascending=[True,False]).groupby("date",sort=False).head(1)
    vals=top.joint_score.to_numpy(float)
    qs=[0,.10,.20,.30,.40,.50,.60,.65]
    return sorted(set(float(np.quantile(vals,q)) for q in qs))


def select(df,w,g,cooldown,threshold):
    x=risk.apply_guard(add_score(df,w),g)
    x=x[x.joint_score>=threshold].copy()
    return risk.select_with_cooldown(x,"joint_score",1,cooldown)


def objective(st):
    if st["n"]<MIN_VALID_N:return -999.0
    # reward repeatable average/median while penalizing left-tail; light n term avoids 8-row lottery winning ties
    tail=.25*min(0.0,st["p10"])+.05*min(0.0,st["min"])-.015*st["loss20"]
    return .50*st["robust_avg"]+.25*st["avg"]+.15*st["median"]+.015*(st["wr"]-.5)+.02*st["target_rate"]+tail+.001*np.log1p(st["n"])


def choose(valid):
    best=None;trials=[]
    for w in v11.WEIGHT_SETS:
        scored=add_score(valid,w)
        for g in GUARDS:
            for th in candidate_thresholds(scored,g):
                for cd in COOLDOWNS:
                    sel=select(valid,w,g,cd,th);st=risk.risk_stats(sel);obj=objective(st)
                    rec={"weights":list(w),"guard":g,"cooldown_days":cd,"threshold":float(th),"objective":float(obj),"stats":st}
                    trials.append(rec)
                    if best is None or (obj,st["n"])>(best["objective"],best["stats"]["n"]):best=rec
    return best,sorted(trials,key=lambda r:(r["objective"],r["stats"]["n"]),reverse=True)


def apply(df,p):return select(df,p["weights"],p["guard"],int(p["cooldown_days"]),float(p["threshold"]))


def run_variant(data,variant):
    train=data[data.date.between(base.TRAIN_START,base.TRAIN_END)&data.perf_5bd.notna()].copy();valid=data[data.date.between(base.VALID_START,base.VALID_END)&data.perf_5bd.notna()].copy();test=data[data.date.between(base.TEST_START,base.TEST_END)&data.perf_5bd.notna()].copy()
    cols=v11.features() if variant=="v13" else v14.feature_cols();models=v11.fit_models(train,cols) if variant=="v13" else v14.fit(train,cols);v=v11.attach(valid,models,cols) if variant=="v13" else v14.attach(valid,models,cols);t=v11.attach(test,models,cols) if variant=="v13" else v14.attach(test,models,cols);p,tr=choose(v);sel=apply(t,p)
    return {"policy":p,"trials":tr[:25],"test":risk.risk_stats(sel),"selected":sel}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v16")
    a=ap.parse_args();teacher,wstat,d,yahoo=v14.build_dataset(a);d=v11.enrich_cross_sectional(d);res={}
    for variant in ("v13","v14"):
        r=run_variant(d,variant);sel=r.pop("selected");r["selected_rows"]=sel.sort_values(["date","joint_score"],ascending=[True,False])[["date","session","symbol","joint_score","p_win","p_hit10","pred_ret","pine_bottom","stable_score","label","perf_5bd"]].to_dict("records");res[variant]=r
    result={"scope":"Selective Yahoo-only outcome policy with validation-chosen abstention threshold","teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,"current_champion":base.CHAMPION,"variants":res}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v16_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({k:{"policy":v["policy"],"test":v["test"]} for k,v in res.items()},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
