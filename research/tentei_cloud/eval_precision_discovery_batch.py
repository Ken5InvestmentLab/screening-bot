#!/usr/bin/env python3
"""Frozen three-family Precision discovery batch evaluator.

Implements PRECISION_DISCOVERY_BATCH_SPEC_20260914.json.

This first-stage evaluator opens DEVELOPMENT outcomes only.
It does not calculate INTERNAL_VALIDATION, 2025H2, or 2026 returns.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, cooldown

PRIMARY_COST=0.005
DEV_START="2024-11-01"
DEV_END="2025-03-31"

FAMILIES=[
    "PRIOR_HIGH_BREAKOUT",
    "TWO_DAY_PULLBACK_RECLAIM",
    "INSIDE_RANGE_STRENGTH",
]

def summarize(gross:pd.Series,cost:float)->dict:
    r=gross.dropna().astype(float)
    if r.empty:
        return {"n":0}
    net=r-cost
    rs=net.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(net)),
        "mean":float(net.mean()),
        "median":float(net.median()),
        "win":float((net>0).mean()),
        "gross_ge10":float((r>=0.10).mean()),
        "gross_ge20":float((r>=0.20).mean()),
        "gross_le10":float((r<=-0.10).mean()),
        "max":float(net.max()),
        "min":float(net.min()),
        "top1_removed":float(rs.iloc[1:].mean()) if len(rs)>1 else None,
        "top3_removed":float(rs.iloc[3:].mean()) if len(rs)>3 else None,
        "top5_removed":float(rs.iloc[5:].mean()) if len(rs)>5 else None,
    }

def gate(sm:dict)->dict:
    checks={
        "min_resolved_n":int(sm.get("n",0))>=50,
        "net_mean_gt_0":float(sm.get("mean",-999))>0,
        "net_median_gt_0":float(sm.get("median",-999))>0,
        "net_win_rate_gte_0_60":float(sm.get("win",-999))>=0.60,
        "net_top3_removed_mean_gt_0":(
            sm.get("top3_removed") is not None and float(sm["top3_removed"])>0
        ),
        "gross_loss10_rate_lte_0_08":float(sm.get("gross_le10",999))<=0.08,
    }
    checks["all_pass"]=all(checks.values())
    return checks

def build_daily(raw:pd.DataFrame)->pd.DataFrame:
    d=(raw.sort_values("timestamp")
       .groupby(["symbol","date"],as_index=False)
       .agg(
           daily_open=("open","first"),
           daily_high=("high","max"),
           daily_low=("low","min"),
           daily_close=("close","last"),
           daily_volume=("volume","sum"),
       )
       .sort_values(["symbol","date"])
       .reset_index(drop=True))
    g=d.groupby("symbol",sort=False)
    d["prev_daily_open"]=g["daily_open"].shift(1)
    d["prev_daily_high"]=g["daily_high"].shift(1)
    d["prev_daily_low"]=g["daily_low"].shift(1)
    d["prev_daily_close"]=g["daily_close"].shift(1)
    d["prev_daily_volume"]=g["daily_volume"].shift(1)
    d["prev2_daily_close"]=g["daily_close"].shift(2)
    return d

def family_mask(e:pd.DataFrame,name:str)->pd.Series:
    if name=="PRIOR_HIGH_BREAKOUT":
        return (
            (e["open"]<=e["prev_daily_high"])
            & (e["close"]>e["prev_daily_high"])
            & (e["close"]>e["open"])
        )
    if name=="TWO_DAY_PULLBACK_RECLAIM":
        return (
            (e["prev_daily_close"]<e["prev2_daily_close"])
            & (e["close"]>e["prev_daily_close"])
            & (e["close"]>e["open"])
        )
    if name=="INSIDE_RANGE_STRENGTH":
        mid=(e["prev_daily_high"]+e["prev_daily_low"])/2.0
        return (
            (e["low"]>=e["prev_daily_low"])
            & (e["high"]<=e["prev_daily_high"])
            & (e["close"]>mid)
            & (e["close"]>e["open"])
        )
    raise KeyError(name)

def attach_dev_endpoint(candidates:pd.DataFrame,daily:pd.DataFrame,dates:list[str])->pd.DataFrame:
    x=candidates[
        pd.to_datetime(candidates["date"]).between(pd.Timestamp(DEV_START),pd.Timestamp(DEV_END))
    ].copy()
    pos={d:i for i,d in enumerate(dates)}
    entry_map={d:(dates[i+1] if i+1<len(dates) else None) for d,i in pos.items()}
    exit_map={d:(dates[i+5] if i+5<len(dates) else None) for d,i in pos.items()}
    x["entry_date"]=x["date"].map(entry_map)
    x["exit_date"]=x["date"].map(exit_map)
    entry=daily[["symbol","date","daily_open"]].rename(columns={"date":"entry_date","daily_open":"entry_open"})
    exit_=daily[["symbol","date","daily_close"]].rename(columns={"date":"exit_date","daily_close":"exit_close"})
    x=x.merge(entry,on=["symbol","entry_date"],how="left",validate="many_to_one")
    x=x.merge(exit_,on=["symbol","exit_date"],how="left",validate="many_to_one")
    resolved=x["entry_open"].notna()&x["exit_close"].notna()&(x["entry_open"]>0)&(x["exit_close"]>0)
    x["endpoint_status"]=np.where(resolved,"RESOLVED","UNRESOLVED_ENDPOINT")
    x["gross_ret5bd"]=np.where(resolved,x["exit_close"]/x["entry_open"]-1.0,np.nan)
    return x

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    raw=load(a.inputs)
    daily=build_daily(raw)
    dates=sorted(daily["date"].dropna().unique().tolist())
    sessions=aggregate(raw,780)
    ctx=daily[[
        "symbol","date","prev_daily_open","prev_daily_high","prev_daily_low",
        "prev_daily_close","prev_daily_volume","prev2_daily_close"
    ]]
    s=sessions.merge(ctx,on=["symbol","date"],how="left",validate="many_to_one")
    eligible=s[
        (s["prev_daily_close"]<=1000)
        & (s["prev_daily_volume"]>=10000)
        & (s["volume"]>=5000)
        & s["prev_daily_open"].notna()
        & s["prev2_daily_close"].notna()
    ].copy()

    results=[]
    exports=[]
    for name in FAMILIES:
        selected=cooldown(eligible.loc[family_mask(eligible,name)].copy(),dates,5)
        dev=attach_dev_endpoint(selected,daily,dates)
        resolved=dev[dev["endpoint_status"]=="RESOLVED"].copy()
        sm=summarize(resolved["gross_ret5bd"],PRIMARY_COST)
        g=gate(sm)
        results.append({
            "family":name,
            "selected_n":int(len(dev)),
            "resolved_n":int(len(resolved)),
            "unresolved_n":int(len(dev)-len(resolved)),
            "primary_cost":PRIMARY_COST,
            "metrics":sm,
            "gate":g,
        })
        ex=dev.copy()
        ex["family"]=name
        exports.append(ex)

    eligible_results=[r for r in results if r["gate"]["all_pass"]]
    eligible_results=sorted(
        eligible_results,
        key=lambda r:(
            -r["metrics"]["win"],
            -r["metrics"]["median"],
            -r["metrics"]["mean"],
            r["family"],
        )
    )
    winner=eligible_results[0]["family"] if eligible_results else None

    result={
        "experiment_id":"PRECISION-BATCH-20260914-01",
        "status":"DEVELOPMENT_SELECTION_ONLY",
        "development_period":[DEV_START,DEV_END],
        "families_preregistered":FAMILIES,
        "family_results":results,
        "eligible_family_count":len(eligible_results),
        "selected_winner":winner,
        "internal_validation_opened":False,
        "locked_confirmation_opened":False,
        "year_2026_outcomes_opened":False,
        "production_modified":False,
    }

    (out/"precision_discovery_batch_result.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8"
    )
    if exports:
        z=pd.concat(exports,ignore_index=True,sort=False)
        keep=[
            "family","symbol","date","session","session_time","open","high","low","close","volume",
            "prev_daily_high","prev_daily_low","prev_daily_close","prev_daily_volume","prev2_daily_close",
            "entry_date","exit_date","entry_open","exit_close","endpoint_status","gross_ret5bd"
        ]
        z[[c for c in keep if c in z.columns]].to_csv(out/"precision_discovery_batch_dev_rows.csv",index=False)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=="__main__":
    main()
