#!/usr/bin/env python3
"""Long-horizon role-coverage audit for the fixed Cloud lanes.

Research-only. No signal-rule tuning and no production writes.

Question:
Can the already-fixed Core or short-horizon Monster Watch/Prime lanes also cover
the current Mega40 product role, or is a dedicated long-horizon lane still
missing?

Selection logic is NOT changed:
- Core = fixed reconstructed Core.
- Monster Watch/Prime = fixed expanding walk-forward 5BD ensemble.

Only the evaluation horizon is added:
- 40 business-day close from the signal date.
- evaluate mean/median/win, >=30%, >=50%, <=-20%, top-winner removal.

Current Mega40 report headlines are read from the saved HTML reports only as
descriptive product benchmarks. No thresholds are fitted to match them.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown
from mtf_monster_model import make_candidate_pool
from walkforward_4h_ensemble import (
    FOLDS, TARGET, MIN_TRAIN, MIN_POS, fit_ensemble, score_ensemble
)

KEY=["symbol","date","session"]

def make_core(raw):
    s=aggregate(raw,780)
    s=enrich_session(s)
    s,dates=add_daily_context(s,raw)
    e=s[
        (s["prev_daily_close"]<=1000)
        & (s["prev_daily_volume"]>=10000)
        & (s["volume"]>=5000)
    ].copy()
    g=(
        (e["rsi12"]<45)
        & e["pre_down3"].fillna(False)
        & (e["close"]>e["bb_mid"])
        & (e["atr14_pct"]<0.05)
    )
    q=cooldown(e[g].copy(),dates,5)
    q=q[q["ret5bd"].notna()].copy()
    q["date_dt"]=pd.to_datetime(q["date"],errors="coerce")
    return q

def add_40bd(frame,raw):
    daily=(raw.sort_values("timestamp")
           .groupby(["symbol","date"],as_index=False)
           .agg(daily_close=("close","last"))
           .sort_values(["symbol","date"]))
    dates=sorted(daily["date"].unique().tolist())
    tmap={d:(dates[i+40] if i+40<len(dates) else None) for i,d in enumerate(dates)}
    target=daily.rename(columns={"date":"target40_date","daily_close":"target40_close"})[
        ["symbol","target40_date","target40_close"]
    ]
    x=frame.copy()
    x["target40_date"]=x["date"].map(tmap)
    x=x.merge(target,on=["symbol","target40_date"],how="left")
    x["ret40bd"]=x["target40_close"]/x["close"]-1.0
    return x

def met(r):
    r=pd.Series(r).dropna().astype(float)
    if r.empty: return {"n":0}
    rs=r.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(r)),
        "mean":float(r.mean()),
        "median":float(r.median()),
        "win":float((r>0).mean()),
        "ge30":float((r>=0.30).mean()),
        "ge50":float((r>=0.50).mean()),
        "le20":float((r<=-0.20).mean()),
        "max":float(r.max()),
        "min":float(r.min()),
        "top1_removed":float(rs.iloc[1:].mean()) if len(rs)>1 else None,
        "top3_removed":float(rs.iloc[3:].mean()) if len(rs)>3 else None,
        "top5_removed":float(rs.iloc[5:].mean()) if len(rs)>5 else None,
    }

def parse_pct(s):
    m=re.search(r"([+-]?\d+(?:\.\d+)?)\s*%",s or "")
    return float(m.group(1))/100 if m else None

def parse_mode(path,target):
    soup=BeautifulSoup(path.read_text(encoding="utf-8"),"html.parser")
    labels={}
    summary=soup.find("section",id="summary")
    if summary:
        for m in summary.select(".metric"):
            l=m.select_one(".label"); v=m.select_one(".value")
            if l and v:
                labels=" ".join(l.stripped_strings)
                value=" ".join(v.stripped_strings)
                # workaround local dict shadow
                if not hasattr(parse_mode,"_tmp"): pass
    # redo cleanly
    vals={}
    if summary:
        for m in summary.select(".metric"):
            l=m.select_one(".label"); v=m.select_one(".value")
            if l and v:
                vals[" ".join(l.stripped_strings)]=" ".join(v.stripped_strings)
    n=int(vals.get("確定件数","0") or 0)
    hit=int(vals.get("目標Hit","0") or 0)
    return {
        "n":n,
        "mean":parse_pct(vals.get("確定平均","")),
        "win":parse_pct(vals.get("確定勝率","")),
        "target":target,
        "target_hit":hit,
        "target_hit_rate":hit/n if n else None,
    }

def append_metric(rows,lane,period,frame):
    rows.append({"lane":lane,"period":period,**met(frame["ret40bd"])})

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--repo-root",default=".")
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    root=Path(a.repo_root)

    raw=load(a.inputs)
    core=add_40bd(make_core(raw),raw)

    cand=make_candidate_pool(raw)
    cand=cand[cand["ret5bd"].notna()].copy()
    cand["date_dt"]=pd.to_datetime(cand["date"],errors="coerce")
    cand["target_date_dt"]=pd.to_datetime(cand["target_date"],errors="coerce")
    cand=add_40bd(cand,raw)

    rows=[]
    monster_exports=[]
    fold_meta=[]

    # Core by fixed fold windows.
    for fold,start,end in FOLDS:
        q=core[
            (core["date_dt"]>=pd.Timestamp(start))
            & (core["date_dt"]<=pd.Timestamp(end))
            & core["ret40bd"].notna()
        ]
        append_metric(rows,"Core",fold,q)

    # Fixed Monster selections, evaluated at 40BD only after selection.
    for fold,start,end in FOLDS:
        ts=pd.Timestamp(start)
        train=cand[
            (cand["date_dt"]>=pd.Timestamp("2024-11-01"))
            & (cand["target_date_dt"]<ts)
        ].copy()
        test=cand[
            (cand["date_dt"]>=pd.Timestamp(start))
            & (cand["date_dt"]<=pd.Timestamp(end))
        ].copy()
        pos=int((train["ret5bd"]>=TARGET).sum())
        neg=int(len(train)-pos)
        if len(train)<MIN_TRAIN or pos<MIN_POS or neg<MIN_POS or test.empty:
            fold_meta.append({"fold":fold,"status":"SKIP"})
            continue
        models,wthr,pthr=fit_ensemble(train)
        test=test.copy()
        test["ensemble_score"],test["score_std"]=score_ensemble(models,test)
        watch=test[test["ensemble_score"]>=wthr].copy()
        prime=test[test["ensemble_score"]>=pthr].copy()
        fold_meta.append({
            "fold":fold,"status":"OK",
            "watch_n_selected":int(len(watch)),
            "watch_n_40bd_mature":int(watch["ret40bd"].notna().sum()),
            "prime_n_selected":int(len(prime)),
            "prime_n_40bd_mature":int(prime["ret40bd"].notna().sum()),
        })
        for name,z in [("Monster_Watch",watch),("Monster_Prime",prime)]:
            mature=z[z["ret40bd"].notna()].copy()
            append_metric(rows,name,fold,mature)
            mature["lane"]=name
            mature["fold"]=fold
            monster_exports.append(mature)

    # Aggregate 2026 matured rows for architecture view.
    c26=core[
        (core["date_dt"]>=pd.Timestamp("2026-01-01"))
        & (core["date_dt"]<=pd.Timestamp("2026-08-31"))
        & core["ret40bd"].notna()
    ].copy()
    append_metric(rows,"Core","2026_MATURED",c26)

    if monster_exports:
        me=pd.concat(monster_exports,ignore_index=True,sort=False)
        for lane in ["Monster_Watch","Monster_Prime"]:
            z=me[(me["lane"]==lane)&(pd.to_datetime(me["date"])>=pd.Timestamp("2026-01-01"))].copy()
            z=z.drop_duplicates(KEY)
            append_metric(rows,lane,"2026_MATURED",z)
        keep=["lane","fold","date","session","symbol","ret5bd","ret40bd","target40_date","ensemble_score"]
        me[[k for k in keep if k in me.columns]].to_csv(out/"long_horizon_monster_rows.csv",index=False)

    metrics=pd.DataFrame(rows)
    metrics.to_csv(out/"long_horizon_role_metrics.csv",index=False)
    pd.DataFrame(fold_meta).to_csv(out/"long_horizon_fold_meta.csv",index=False)

    benchmarks=[
        {"mode":"Mega40_Deep",**parse_mode(root/"reports/mega_validation_report_mega40_deep_reversal.html","+30% at 40BD")},
        {"mode":"Mega40_Wick",**parse_mode(root/"reports/mega_validation_report_mega40_wick_recovery.html","+50% at 40BD")},
    ]
    pd.DataFrame(benchmarks).to_csv(out/"long_horizon_current_benchmarks.csv",index=False)

    meta={
        "selection_logic_changes":False,
        "evaluation_horizon_added":"40 business days from signal date",
        "purpose":"determine whether existing fixed Cloud lanes cover Mega40 role",
        "mega_benchmarks":benchmarks,
        "production_writes":False,
        "status":"RETROSPECTIVE_ROLE_COVERAGE_AUDIT",
    }
    (out/"long_horizon_role_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\n40BD METRICS")
    print(metrics.to_string(index=False))
    print("\nFOLD MATURITY")
    print(pd.DataFrame(fold_meta).to_string(index=False))

if __name__=="__main__":
    main()
