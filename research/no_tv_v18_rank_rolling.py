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
import no_tv_v17_unbiased_rolling as v17

FOLDS=v17.FOLDS
SAMPLE_CUTOFF=v17.SAMPLE_CUTOFF
GUARDS=[{"id":"none"},{"id":"sr12","max_session_range":.12},{"id":"strict","max_session_range":.12,"max_abs_session_ret":.10,"max_day_range":12.0,"max_atr":8.0}]
SESSIONS=["both","9","13"]
COOLDOWNS=[0,3,5]
CONSENSUS_THRESHOLDS=[0.0,.90,.95,.97,.98]
MIN_VALID=8


def verify_early_sample(watchlist_repo,codes):
    wl,_,_=base.load_exact_watchlists(watchlist_repo,base.TRAIN_START,base.TEST_END)
    early=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=SAMPLE_CUTOFF: early.update(syms)
    missing=[c for c in codes if c not in early]
    if missing: raise RuntimeError(f"future-only symbols leaked into sample: {missing[:10]}")


def fit_attach(train,valid,test,variant):
    cols=v11.features() if variant=="v13" else v14.feature_cols()
    models=v11.fit_models(train,cols) if variant=="v13" else v14.fit(train,cols)
    va=v11.attach(valid,models,cols) if variant=="v13" else v14.attach(valid,models,cols)
    te=v11.attach(test,models,cols) if variant=="v13" else v14.attach(test,models,cols)
    return va,te


def session_filter(df,mode):
    if mode=="9": return df[df.session.astype(int)==9].copy()
    if mode=="13": return df[df.session.astype(int)==13].copy()
    return df.copy()


def causal_top(df,score_col,cooldown=0):
    if df.empty: return df
    d=df.sort_values(["date","session",score_col],ascending=[True,True,False]).copy()
    days=sorted(d.date.unique()); day_ix={x:i for i,x in enumerate(days)}; last={}; keep=[]
    for (dt,sess),g in d.groupby(["date","session"],sort=True):
        di=day_ix[dt]
        for idx,row in g.iterrows():
            sym=str(row.symbol)
            if cooldown and sym in last and di-last[sym] < cooldown: continue
            keep.append(idx); last[sym]=di; break
    return d.loc[keep].copy()


def obj(st,min_n=MIN_VALID):
    if st["n"]<min_n: return -999.0
    tail=.20*min(0.0,st["p10"])+.04*min(0.0,st["min"])-.015*st["loss20"]
    return .45*st["robust_avg"]+.25*st["avg"]+.15*st["median"]+.015*(st["wr"]-.5)+.02*st["target_rate"]+tail+.001*np.log1p(st["n"])


def choose_weighted(valid):
    best=None; trials=[]
    for w in v11.WEIGHT_SETS:
        scored=valid.copy(); scored["score"]=w[0]*scored.p_win+w[1]*scored.p_hit10+w[2]*scored.ret_component
        for g in GUARDS:
            guarded=risk.apply_guard(scored,g)
            for sm in SESSIONS:
                sf=session_filter(guarded,sm)
                for cd in COOLDOWNS:
                    sel=causal_top(sf,"score",cd); st=risk.risk_stats(sel); o=obj(st)
                    rec={"type":"weighted","weights":list(w),"guard":g,"sessions":sm,"cooldown_days":cd,"objective":float(o),"stats":st}
                    trials.append(rec)
                    if best is None or (o,st["n"])>(best["objective"],best["stats"]["n"]): best=rec
    return best,sorted(trials,key=lambda r:(r["objective"],r["stats"]["n"]),reverse=True)


def apply_weighted(df,p):
    w=p["weights"]; x=df.copy(); x["score"]=w[0]*x.p_win+w[1]*x.p_hit10+w[2]*x.ret_component
    x=risk.apply_guard(x,p["guard"]); x=session_filter(x,p["sessions"])
    return causal_top(x,"score",int(p["cooldown_days"]))


def consensus_scores(df,guard):
    x=risk.apply_guard(df,guard)
    if x.empty:return x
    grp=["date","session"]
    x["r_win"]=x.groupby(grp).p_win.rank(pct=True,method="average")
    x["r_hit"]=x.groupby(grp).p_hit10.rank(pct=True,method="average")
    x["r_ret"]=x.groupby(grp).pred_ret.rank(pct=True,method="average")
    x["cons_min"]=x[["r_win","r_hit","r_ret"]].min(axis=1)
    x["cons_geo"]=(x.r_win*x.r_hit*x.r_ret).pow(1/3)
    return x


def choose_consensus(valid):
    best=None;trials=[]
    for g in GUARDS:
        scored=consensus_scores(valid,g)
        for mode,col in (("min","cons_min"),("geo","cons_geo")):
            for th in CONSENSUS_THRESHOLDS:
                q=scored[scored[col]>=th].copy()
                for sm in SESSIONS:
                    sf=session_filter(q,sm)
                    for cd in COOLDOWNS:
                        sel=causal_top(sf,col,cd);st=risk.risk_stats(sel);o=obj(st)
                        rec={"type":"consensus","mode":mode,"threshold":th,"guard":g,"sessions":sm,"cooldown_days":cd,"objective":float(o),"stats":st}
                        trials.append(rec)
                        if best is None or (o,st["n"])>(best["objective"],best["stats"]["n"]):best=rec
    return best,sorted(trials,key=lambda r:(r["objective"],r["stats"]["n"]),reverse=True)


def apply_consensus(df,p):
    col="cons_min" if p["mode"]=="min" else "cons_geo"
    x=consensus_scores(df,p["guard"]);x=x[x[col]>=float(p["threshold"])].copy();x=session_filter(x,p["sessions"])
    return causal_top(x,col,int(p["cooldown_days"]))


def evaluate(data,fold,variant):
    train=data[data.date.between(fold["train_start"],fold["train_end"])&data.perf_5bd.notna()].copy()
    valid=data[data.date.between(fold["valid_start"],fold["valid_end"])&data.perf_5bd.notna()].copy()
    test=data[data.date.between(fold["test_start"],fold["test_end"])&data.perf_5bd.notna()].copy()
    va,te=fit_attach(train,valid,test,variant)
    pw,tw=choose_weighted(va);pc,tc=choose_consensus(va)
    sw=apply_weighted(te,pw);sc=apply_consensus(te,pc)
    return {
      "fold":fold["id"],"variant":variant,"sizes":{"train":len(train),"valid":len(valid),"test":len(test)},
      "weighted":{"policy":pw,"test":risk.risk_stats(sw)},"consensus":{"policy":pc,"test":risk.risk_stats(sc)},
      "selected_weighted":sw.assign(fold=fold["id"],variant=variant),"selected_consensus":sc.assign(fold=fold["id"],variant=variant)
    }


def fixed_baselines(data):
    tests=[]
    for fold in FOLDS:
        x=data[data.date.between(fold["test_start"],fold["test_end"])&data.perf_5bd.notna()].copy();x["fold"]=fold["id"];tests.append(x)
    t=pd.concat(tests,ignore_index=True)
    rules={"pine_bottom_all":t.pine_bottom>0,"pine_stable_ge4":(t.pine_bottom>0)&(t.stable_score>=4),"pine_stable_ge5":(t.pine_bottom>0)&(t.stable_score>=5),"pine_stable_6":(t.pine_bottom>0)&(t.stable_score==6),"actual_bottom_stable6_eval_only":(t.label==1)&(t.stable_score==6)}
    return {k:risk.risk_stats(t[m].copy()) for k,m in rules.items()}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v18_rank_rolling");a=ap.parse_args()
    teacher,wstat,data,yahoo,codes=v17.build_dataset(a);verify_early_sample(a.watchlist_repo,codes);data=v11.enrich_cross_sectional(data)
    rows=[];parts={"v13_weighted":[],"v13_consensus":[],"v14_weighted":[],"v14_consensus":[]}
    for fold in FOLDS:
        for variant in ("v13","v14"):
            print(f"evaluate causal {fold['id']} {variant}",flush=True);r=evaluate(data,fold,variant)
            parts[f"{variant}_weighted"].append(r.pop("selected_weighted"));parts[f"{variant}_consensus"].append(r.pop("selected_consensus"));rows.append(r)
    combined={k:risk.risk_stats(pd.concat(v,ignore_index=True)) for k,v in parts.items()}
    baselines=fixed_baselines(data)
    result={"scope":"Leakage-free AND intraday-causal rolling evaluation. 09:00 never sees 13:00 candidates. Cross-sectional rank/consensus avoids absolute probability-scale drift.","sampling":{"cutoff":SAMPLE_CUTOFF,"max_symbols":a.max_symbols,"symbols":codes},"teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,"folds":rows,"combined_test":combined,"fixed_baselines":baselines,"current_champion":base.CHAMPION}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v18_rank_rolling.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"folds":rows,"combined_test":combined,"fixed_baselines":baselines},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
