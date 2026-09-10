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
Q=[0.0,.70,.80,.85,.90,.95]
COOLDOWNS=[0,3,5]
MIN_VALID=6


def verify_early_sample(repo,codes):
    wl,_,_=base.load_exact_watchlists(repo,base.TRAIN_START,base.TEST_END);early=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=SAMPLE_CUTOFF:early.update(syms)
    bad=[c for c in codes if c not in early]
    if bad:raise RuntimeError(f"future-only symbols leaked: {bad[:10]}")


def cols_for(variant):return v11.features() if variant=="v13" else v14.feature_cols()


def fit_models(train,variant):
    cols=cols_for(variant);x=train[cols].astype(float);r=train.perf_5bd.to_numpy(float);yw=(r>0).astype(int);yh=(r>=.10).astype(int);yl=(r<=-.10).astype(int)
    def clf(seed,leaf):
        return HistGradientBoostingClassifier(learning_rate=.035,max_iter=220,max_leaf_nodes=11,min_samples_leaf=leaf,l2_regularization=4.0,random_state=seed)
    win=clf(211,18);hit=clf(212,15);loss=clf(213,15);reg=HistGradientBoostingRegressor(learning_rate=.03,max_iter=220,max_leaf_nodes=11,min_samples_leaf=18,l2_regularization=4.0,random_state=214)
    win.fit(x,yw,sample_weight=base.balanced_weights(yw));hit.fit(x,yh,sample_weight=base.balanced_weights(yh));loss.fit(x,yl,sample_weight=base.balanced_weights(yl));reg.fit(x,np.clip(r,-.20,.30));return win,hit,loss,reg


def attach(df,models,variant):
    if df.empty:return df.copy()
    cols=cols_for(variant);win,hit,loss,reg=models;x=df[cols].astype(float);o=df.copy();o["p_win"]=win.predict_proba(x)[:,1];o["p_hit10"]=hit.predict_proba(x)[:,1];o["p_loss10"]=loss.predict_proba(x)[:,1];o["pred_ret"]=reg.predict(x)
    g=["date","session"];o["r_win"]=o.groupby(g).p_win.rank(pct=True);o["r_hit"]=o.groupby(g).p_hit10.rank(pct=True);o["r_ret"]=o.groupby(g).pred_ret.rank(pct=True);o["r_safe"]=(-o.p_loss10).groupby([o.date,o.session]).rank(pct=True)
    o["score"]=(o.r_win*o.r_hit*o.r_ret*o.r_safe).pow(.25);o["score_min"]=o[["r_win","r_hit","r_ret","r_safe"]].min(axis=1);return o


def causal_top(df,col,cd):
    if df.empty:return df
    d=df.sort_values(["date","session",col],ascending=[True,True,False]);dates=sorted(d.date.unique());ix={x:i for i,x in enumerate(dates)};last={};keep=[]
    for (dt,sess),g in d.groupby(["date","session"],sort=True):
        for idx,row in g.iterrows():
            sym=str(row.symbol)
            if cd and sym in last and ix[dt]-last[sym]<cd:continue
            keep.append(idx);last[sym]=ix[dt];break
    return d.loc[keep].copy()


def obj(st):
    if st["n"]<MIN_VALID:return -999.
    return .45*st["robust_avg"]+.25*st["avg"]+.15*st["median"]+.015*(st["wr"]-.5)+.02*st["target_rate"]+.20*min(0.,st["p10"])+.04*min(0.,st["min"])-.02*st["loss20"]+.001*np.log1p(st["n"])


def choose(valid):
    best=None;tr=[]
    for guard in GUARDS:
        z=risk.apply_guard(valid,guard)
        for score in ("score","score_min"):
            for q in Q:
                x=z[z[score]>=q].copy()
                for sessions in ("both","9","13"):
                    y=x if sessions=="both" else x[x.session.astype(int)==int(sessions)].copy()
                    for cd in COOLDOWNS:
                        s=causal_top(y,score,cd);st=risk.risk_stats(s);o=obj(st);r={"guard":guard,"score":score,"threshold":q,"sessions":sessions,"cooldown_days":cd,"objective":float(o),"stats":st};tr.append(r)
                        if best is None or (o,st["n"])>(best["objective"],best["stats"]["n"]):best=r
    return best,sorted(tr,key=lambda x:(x["objective"],x["stats"]["n"]),reverse=True)


def apply(df,p):
    x=risk.apply_guard(df,p["guard"]);x=x[x[p["score"]]>=float(p["threshold"])].copy()
    if p["sessions"]!="both":x=x[x.session.astype(int)==int(p["sessions"])].copy()
    return causal_top(x,p["score"],int(p["cooldown_days"]))


def evaluate(data,fold,variant):
    # Critical design: train, validation and test all live in the SAME Yahoo-Pine candidate distribution.
    pine=data[data.pine_bottom>0].copy()
    train=pine[pine.date.between(fold["train_start"],fold["train_end"])&pine.perf_5bd.notna()].copy();valid=pine[pine.date.between(fold["valid_start"],fold["valid_end"])&pine.perf_5bd.notna()].copy();test=pine[pine.date.between(fold["test_start"],fold["test_end"])&pine.perf_5bd.notna()].copy()
    if min(len(train),len(valid),len(test))<20:raise RuntimeError(f"too few Pine rows {fold['id']}: {len(train)}/{len(valid)}/{len(test)}")
    models=fit_models(train,variant);va=attach(valid,models,variant);te=attach(test,models,variant);p,tr=choose(va);sel=apply(te,p)
    return {"fold":fold["id"],"variant":variant,"sizes":{"train":len(train),"valid":len(valid),"test":len(test)},"policy":p,"validation":p["stats"],"test":risk.risk_stats(sel),"pine_all_test":risk.risk_stats(test),"selected":sel.assign(fold=fold["id"],variant=variant)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v21_pine_gated");a=ap.parse_args()
    teacher,wstat,data,yahoo,codes=v17.build_dataset(a);verify_early_sample(a.watchlist_repo,codes);data=v11.enrich_cross_sectional(data);rows=[];parts={"v13":[],"v14":[]}
    for f in FOLDS:
        for variant in VARIANTS:
            print(f"evaluate {f['id']} {variant}",flush=True);r=evaluate(data,f,variant);parts[variant].append(r.pop("selected"));rows.append(r)
    combined={k:risk.risk_stats(pd.concat(v,ignore_index=True)) for k,v in parts.items()};result={"scope":"Leakage-free, intraday-causal Yahoo-Pine-gated outcome model. Training and runtime candidate distributions match; TradingView labels are evaluation-only.","sampling":{"cutoff":SAMPLE_CUTOFF,"symbols":codes},"teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,"folds":rows,"combined_test":combined,"current_champion":base.CHAMPION}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v21_pine_gated.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"folds":rows,"combined_test":combined},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
