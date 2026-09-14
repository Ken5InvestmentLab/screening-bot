#!/usr/bin/env python3
"""Frozen Precision prior-close reclaim evaluator.

Implements PRECISION_PRIOR_CLOSE_RECLAIM_SPEC_20260914.json.

Research-only. First execution opens DEVELOPMENT + INTERNAL_VALIDATION only.
LOCKED_CONFIRMATION may be opened only with --open-locked and only if both
preconfirmation blocks pass all frozen gates.

All daily context and canonical endpoints are derived from the same explicit-
period raw Yahoo 1H archive. No frozen-daily provider fields are used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, cooldown

PRIMARY_COST=0.005
COSTS=[0.0,0.005,0.01]
PERIODS={
    "DEVELOPMENT":("2024-11-01","2025-03-31"),
    "INTERNAL_VALIDATION":("2025-04-01","2025-06-30"),
    "LOCKED_CONFIRMATION":("2025-07-01","2025-12-31"),
}

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

def frozen_gate(primary:dict,min_n:int)->dict:
    checks={
        "min_resolved_n":int(primary.get("n",0))>=min_n,
        "net_mean_gt_0":float(primary.get("mean",-999))>0,
        "net_median_gt_0":float(primary.get("median",-999))>0,
        "net_win_rate_gte_0_60":float(primary.get("win",-999))>=0.60,
        "net_top3_removed_mean_gt_0":(
            primary.get("top3_removed") is not None and float(primary["top3_removed"])>0
        ),
        "gross_loss10_rate_lte_0_08":float(primary.get("gross_le10",999))<=0.08,
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
    for col in ["daily_open","daily_high","daily_low","daily_close","daily_volume"]:
        d["prev_"+col]=g[col].shift(1)
    return d

def prior_close_reclaim_mask(e:pd.DataFrame)->pd.Series:
    return (
        (e["prev_daily_close"] < e["prev_daily_open"])
        & (e["open"] < e["prev_daily_close"])
        & (e["close"] > e["prev_daily_close"])
        & (e["close"] > e["open"])
    )

def make_candidates(raw:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,list[str]]:
    daily=build_daily(raw)
    dates=sorted(daily["date"].dropna().unique().tolist())
    sessions=aggregate(raw,780)
    ctx=daily[[
        "symbol","date",
        "prev_daily_open","prev_daily_high","prev_daily_low",
        "prev_daily_close","prev_daily_volume"
    ]]
    s=sessions.merge(ctx,on=["symbol","date"],how="left",validate="many_to_one")
    eligible=s[
        (s["prev_daily_close"]<=1000)
        & (s["prev_daily_volume"]>=10000)
        & (s["volume"]>=5000)
        & s["prev_daily_open"].notna()
    ].copy()
    selected=cooldown(eligible.loc[prior_close_reclaim_mask(eligible)].copy(),dates,5)
    return selected,daily,dates

def attach_endpoint(candidates:pd.DataFrame,daily:pd.DataFrame,dates:list[str])->pd.DataFrame:
    pos={d:i for i,d in enumerate(dates)}
    entry_map={d:(dates[i+1] if i+1<len(dates) else None) for d,i in pos.items()}
    exit_map={d:(dates[i+5] if i+5<len(dates) else None) for d,i in pos.items()}
    x=candidates.copy()
    x["entry_date"]=x["date"].map(entry_map)
    x["exit_date"]=x["date"].map(exit_map)
    entry=daily[["symbol","date","daily_open"]].rename(columns={"date":"entry_date","daily_open":"entry_open"})
    exit_=daily[["symbol","date","daily_close"]].rename(columns={"date":"exit_date","daily_close":"exit_close"})
    x=x.merge(entry,on=["symbol","entry_date"],how="left",validate="many_to_one")
    x=x.merge(exit_,on=["symbol","exit_date"],how="left",validate="many_to_one")
    resolved=x["entry_open"].notna()&x["exit_close"].notna()&(x["entry_open"]>0)&(x["exit_close"]>0)
    x["endpoint_status"]=np.where(resolved,"RESOLVED","UNRESOLVED_ENDPOINT")
    x["canonical_ret5bd_gross"]=np.where(resolved,x["exit_close"]/x["entry_open"]-1.0,np.nan)
    x["date_dt"]=pd.to_datetime(x["date"],errors="coerce")
    return x

def block_result(x:pd.DataFrame,name:str)->dict:
    start,end=PERIODS[name]
    z=x[(x["date_dt"]>=pd.Timestamp(start))&(x["date_dt"]<=pd.Timestamp(end))].copy()
    resolved=z[z["endpoint_status"]=="RESOLVED"].copy()
    scenarios={f"{c:.3f}":summarize(resolved["canonical_ret5bd_gross"],c) for c in COSTS}
    primary=scenarios[f"{PRIMARY_COST:.3f}"]
    min_n=30 if name=="LOCKED_CONFIRMATION" else 20
    return {
        "period":name,
        "start":start,
        "end":end,
        "selected_n":int(len(z)),
        "resolved_n":int(len(resolved)),
        "unresolved_n":int(len(z)-len(resolved)),
        "cost_scenarios":scenarios,
        "frozen_gate":frozen_gate(primary,min_n),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--open-locked",action="store_true")
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    raw=load(a.inputs)
    candidates,daily,dates=make_candidates(raw)
    labeled=attach_endpoint(candidates,daily,dates)

    dev=block_result(labeled,"DEVELOPMENT")
    val=block_result(labeled,"INTERNAL_VALIDATION")
    prepass=bool(dev["frozen_gate"]["all_pass"] and val["frozen_gate"]["all_pass"])

    result={
        "experiment_id":"PRECISION-PRIOR-CLOSE-RECLAIM-20260914-01",
        "status":"PRECONFIRMATION_ONLY" if not a.open_locked else "LOCKED_CONFIRMATION_REQUESTED",
        "data_source":"explicit-period raw Yahoo 1H only",
        "daily_provider_used":False,
        "session_split_minute":780,
        "same_symbol_cooldown_dates":5,
        "threshold_sweep":False,
        "ranking":"NONE",
        "top_n":"NONE",
        "endpoint":"next observed XTKS date open -> signal date + 5 observed XTKS dates close",
        "primary_round_trip_cost":PRIMARY_COST,
        "periods":{"DEVELOPMENT":dev,"INTERNAL_VALIDATION":val},
        "preconfirmation_pass":prepass,
        "locked_confirmation_opened":False,
        "year_2026_outcomes_opened":False,
        "production_modified":False,
    }

    if a.open_locked:
        if not prepass:
            raise RuntimeError("LOCKED_CONFIRMATION_BLOCKED: preconfirmation gates failed")
        locked=block_result(labeled,"LOCKED_CONFIRMATION")
        result["periods"]["LOCKED_CONFIRMATION"]=locked
        result["locked_confirmation_opened"]=True
        result["locked_confirmation_pass"]=bool(locked["frozen_gate"]["all_pass"])

    rows=[]
    for name,b in result["periods"].items():
        for cost,sm in b["cost_scenarios"].items():
            rows.append({
                "period":name,
                "round_trip_cost":float(cost),
                "selected_n":b["selected_n"],
                "resolved_n":b["resolved_n"],
                "unresolved_n":b["unresolved_n"],
                **sm
            })
    pd.DataFrame(rows).to_csv(out/"precision_prior_close_reclaim_metrics.csv",index=False)

    keep=[
        "symbol","date","session","session_time","open","high","low","close","volume",
        "prev_daily_open","prev_daily_close","prev_daily_volume",
        "entry_date","exit_date","entry_open","exit_close","endpoint_status","canonical_ret5bd_gross"
    ]
    labeled[[c for c in keep if c in labeled.columns]].to_csv(
        out/"precision_prior_close_reclaim_rows.csv",index=False
    )
    (out/"precision_prior_close_reclaim_result.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8"
    )
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=="__main__":
    main()
