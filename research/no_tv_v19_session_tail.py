from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v14_pine_outcome as v14
import no_tv_v17_unbiased_rolling as v17

FOLDS=v17.FOLDS
SAMPLE_CUTOFF=v17.SAMPLE_CUTOFF
VARIANTS=("v13","v14")
GUARDS=[{"id":"none"},{"id":"sr12","max_session_range":.12},{"id":"strict","max_session_range":.12,"max_abs_session_ret":.10,"max_day_range":12.0,"max_atr":8.0}]
TAIL_WEIGHTS=[0.15,0.25,0.35,0.45]
CONS_Q=[0.0,.90,.95,.97]
COOLDOWNS=[0,3,5]
MIN_VALID=8


def verify_early_sample(watchlist_repo,codes):
    wl,_,_=base.load_exact_watchlists(watchlist_repo,base.TRAIN_START,base.TEST_END)
    early=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=SAMPLE_CUTOFF:early.update(syms)
    bad=[c for c in codes if c not in early]
    if bad:raise RuntimeError(f"future-only symbols leaked: {bad[:10]}")


def cols_for(variant):return v11.features() if variant=="v13" else v14.feature_cols()


def fit_heads(train,cols,seed):
    x=train[cols].astype(float);r=train.perf_5bd.to_numpy(float)
    yw=(r>0).astype(int);yh=(r>=.10).astype(int);yl=(r<=-.10).astype(int)
    kw=dict(learning_rate=.035,max_iter=240,max_leaf_nodes=15,l2_regularization=4.0)
    win=HistGradientBoostingClassifier(**kw,min_samples_leaf=55,random_state=seed+1)
    hit=HistGradientBoostingClassifier(**kw,min_samples_leaf=45,random_state=seed+2)
    loss=HistGradientBoostingClassifier(**kw,min_samples_leaf=45,random_state=seed+3)
    reg=HistGradientBoostingRegressor(learning_rate=.03,max_iter=240,max_leaf_nodes=15,min_samples_leaf=55,l2_regularization=4.5,random_state=seed+4)
    win.fit(x,yw,sample_weight=base.balanced_weights(yw));hit.fit(x,yh,sample_weight=base.balanced_weights(yh));loss.fit(x,yl,sample_weight=base.balanced_weights(yl));reg.fit(x,np.clip(r,-.20,.30))
    return win,hit,loss,reg


def attach_heads(df,models,cols):
    if df.empty:return df.copy()
    win,hit,loss,reg=models;x=df[cols].astype(float);o=df.copy()
    o["p_win"]=win.predict_proba(x)[:,1];o["p_hit10"]=hit.predict_proba(x)[:,1];o["p_loss10"]=loss.predict_proba(x)[:,1];o["pred_ret"]=reg.predict(x)
    return o


def fit_session_models(train,variant):
    cols=cols_for(variant);out={}
    for sess in (9,13):
        z=train[train.session.astype(int)==sess].copy()
        if len(z)<300:raise RuntimeError(f"too few train rows for session {sess}: {len(z)}")
        out[sess]=fit_heads(z,cols,190+sess)
    return out


def attach_session_models(df,models,variant):
    cols=cols_for(variant);parts=[]
    for sess in (9,13):
        z=df[df.session.astype(int)==sess].copy()
        if not z.empty:parts.append(attach_heads(z,models[sess],cols))
    return pd.concat(parts,ignore_index=False).sort_index() if parts else df.iloc[0:0].copy()


def add_relative_scores(df,tail_weight):
    if df.empty:return df.copy()
    o=df.copy();g=["date","session"]
    o["r_win"]=o.groupby(g).p_win.rank(pct=True,method="average")
    o["r_hit"]=o.groupby(g).p_hit10.rank(pct=True,method="average")
    o["r_ret"]=o.groupby(g).pred_ret.rank(pct=True,method="average")
    # lower predicted loss is better
    o["r_safe"]=(-o.p_loss10).groupby([o.date,o.session]).rank(pct=True,method="average")
    o["up_cons"]=o[["r_win","r_hit","r_ret"]].min(axis=1)
    o["all_cons"]=o[["r_win","r_hit","r_ret","r_safe"]].min(axis=1)
    o["utility"]=(1-tail_weight)*(.40*o.r_win+.35*o.r_hit+.25*o.r_ret)+tail_weight*o.r_safe
    return o


def causal_top(df,score,cooldown):
    if df.empty:return df
    d=df.sort_values(["date","session",score],ascending=[True,True,False]);dates=sorted(d.date.unique());di={x:i for i,x in enumerate(dates)};last={};keep=[]
    for (dt,sess),g in d.groupby(["date","session"],sort=True):
        for idx,row in g.iterrows():
            sym=str(row.symbol)
            if cooldown and sym in last and di[dt]-last[sym]<cooldown:continue
            keep.append(idx);last[sym]=di[dt];break
    return d.loc[keep].copy()


def objective(st):
    if st["n"]<MIN_VALID:return -999.
    return .45*st["robust_avg"]+.25*st["avg"]+.15*st["median"]+.015*(st["wr"]-.5)+.02*st["target_rate"]+.20*min(0.,st["p10"])+.04*min(0.,st["min"])-.02*st["loss20"]+.001*np.log1p(st["n"])


def choose(valid):
    best=None;trials=[]
    for tw in TAIL_WEIGHTS:
        s=add_relative_scores(valid,tw)
        for guard in GUARDS:
            g=risk.apply_guard(s,guard)
            for score in ("utility","all_cons"):
                for q in CONS_Q:
                    x=g[g[score]>=q].copy()
                    for sessions in ("both","9","13"):
                        y=x if sessions=="both" else x[x.session.astype(int)==int(sessions)].copy()
                        for cd in COOLDOWNS:
                            sel=causal_top(y,score,cd);st=risk.risk_stats(sel);obj=objective(st)
                            rec={"tail_weight":tw,"guard":guard,"score":score,"threshold":q,"sessions":sessions,"cooldown_days":cd,"objective":float(obj),"stats":st}
                            trials.append(rec)
                            if best is None or (obj,st["n"])>(best["objective"],best["stats"]["n"]):best=rec
    return best,sorted(trials,key=lambda r:(r["objective"],r["stats"]["n"]),reverse=True)


def apply(df,p):
    x=add_relative_scores(df,float(p["tail_weight"]));x=risk.apply_guard(x,p["guard"]);x=x[x[p["score"]]>=float(p["threshold"])].copy()
    if p["sessions"]!="both":x=x[x.session.astype(int)==int(p["sessions"])].copy()
    return causal_top(x,p["score"],int(p["cooldown_days"]))


def evaluate(data,fold,variant):
    train=data[data.date.between(fold["train_start"],fold["train_end"])&data.perf_5bd.notna()].copy();valid=data[data.date.between(fold["valid_start"],fold["valid_end"])&data.perf_5bd.notna()].copy();test=data[data.date.between(fold["test_start"],fold["test_end"])&data.perf_5bd.notna()].copy()
    models=fit_session_models(train,variant);va=attach_session_models(valid,models,variant);te=attach_session_models(test,models,variant);p,tr=choose(va);sel=apply(te,p)
    return {"fold":fold["id"],"variant":variant,"policy":p,"validation":p["stats"],"test":risk.risk_stats(sel),"selected":sel.assign(fold=fold["id"],variant=variant)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v19_session_tail");a=ap.parse_args()
    teacher,wstat,data,yahoo,codes=v17.build_dataset(a);verify_early_sample(a.watchlist_repo,codes);data=v11.enrich_cross_sectional(data);rows=[];parts={"v13":[],"v14":[]}
    for f in FOLDS:
        for variant in VARIANTS:
            print(f"evaluate {f['id']} {variant}",flush=True);r=evaluate(data,f,variant);parts[variant].append(r.pop("selected"));rows.append(r)
    combined={k:risk.risk_stats(pd.concat(v,ignore_index=True)) for k,v in parts.items()}
    result={"scope":"Leakage-free, intraday-causal, session-specific direct outcome models with explicit -10% tail-risk head and relative ranks","sampling":{"cutoff":SAMPLE_CUTOFF,"symbols":codes},"teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,"folds":rows,"combined_test":combined,"current_champion":base.CHAMPION}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v19_session_tail.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"folds":rows,"combined_test":combined},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
