#!/usr/bin/env python3
"""Cluster-risk audit for the fixed reconstructed Core.

Research-only descriptive audit. No signal filtering or threshold tuning.

Fixed, preregistered alert-density buckets:
- 1 signal on signal date
- 2 signals
- 3-4 signals
- 5+ signals

Purpose:
Quantify whether same-day Core bursts behave like correlated risk clusters.
The buckets are operational labels only; they must not be used as a new
performance filter on the already-opened history.

Outputs include candidate-level return stats by density bucket, day-level mean
return stats, and concentration of <=-10% outcomes in burst days.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown
from mtf_monster_model import metrics

TARGET=0.075
PERIODS=[
    ("DEV","2024-11-01","2025-06-30"),
    ("2025H2","2025-07-01","2025-12-31"),
    ("2026_YTD","2026-01-01","2026-08-31"),
]

def make_core(raw):
    s=aggregate(raw,780)
    s=enrich_session(s)
    s,dates=add_daily_context(s,raw)
    e=s[
        (s["prev_daily_close"]<=1000)&
        (s["prev_daily_volume"]>=10000)&
        (s["volume"]>=5000)
    ].copy()
    g=(e["rsi12"]<45)&e["pre_down3"].fillna(False)&(e["close"]>e["bb_mid"])&(e["atr14_pct"]<0.05)
    q=cooldown(e[g].copy(),dates,5)
    q=q[q["ret5bd"].notna()].copy()
    q["date_dt"]=pd.to_datetime(q["date"],errors="coerce")
    return q

def bucket(n):
    if n<=1: return "N1"
    if n==2: return "N2"
    if n<=4: return "N3_4"
    return "N5_PLUS"

def simple(r):
    r=r.dropna().astype(float)
    if r.empty: return {"n":0}
    return {
        "n":int(len(r)),
        "mean":float(r.mean()),
        "median":float(r.median()),
        "win":float((r>0).mean()),
        "ge10":float((r>=0.10).mean()),
        "ge20":float((r>=0.20).mean()),
        "le10":float((r<=-0.10).mean()),
        "min":float(r.min()),
        "max":float(r.max()),
    }

def pmask(x,s,e):
    return (x["date_dt"]>=pd.Timestamp(s))&(x["date_dt"]<=pd.Timestamp(e))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    raw=load(a.inputs)
    core=make_core(raw)

    cand_rows=[]
    day_rows=[]
    concentration=[]

    for period,start,end in PERIODS:
        q=core[pmask(core,start,end)].copy()
        counts=q.groupby("date").size().rename("day_signal_count")
        q=q.merge(counts,on="date",how="left")
        q["density_bucket"]=q["day_signal_count"].map(bucket)

        for b in ["N1","N2","N3_4","N5_PLUS"]:
            z=q[q["density_bucket"]==b]
            cand_rows.append({"period":period,"bucket":b,**simple(z["ret5bd"])})

        d=(q.groupby("date",as_index=False)
           .agg(signal_count=("symbol","size"),
                day_mean_ret=("ret5bd","mean"),
                day_median_ret=("ret5bd","median"),
                day_min_ret=("ret5bd","min"),
                day_max_ret=("ret5bd","max"),
                loss10_count=("ret5bd",lambda s:int((s<=-0.10).sum())),
                win_count=("ret5bd",lambda s:int((s>0).sum()))))
        d["density_bucket"]=d["signal_count"].map(bucket)
        d["period"]=period
        day_rows.append(d)

        total_losses=int((q["ret5bd"]<=-0.10).sum())
        burst=q[q["day_signal_count"]>=5]
        burst_losses=int((burst["ret5bd"]<=-0.10).sum())
        concentration.append({
            "period":period,
            "signals":int(len(q)),
            "signal_days":int(q["date"].nunique()),
            "loss10_total":total_losses,
            "signals_on_5plus_days":int(len(burst)),
            "signals_on_5plus_days_share":float(len(burst)/len(q)) if len(q) else None,
            "loss10_on_5plus_days":burst_losses,
            "loss10_on_5plus_days_share":float(burst_losses/total_losses) if total_losses else None,
            "mean_ret_5plus_days":float(burst["ret5bd"].mean()) if len(burst) else None,
        })

    cand=pd.DataFrame(cand_rows)
    days=pd.concat(day_rows,ignore_index=True)
    conc=pd.DataFrame(concentration)
    cand.to_csv(out/"core_cluster_risk_candidate_buckets.csv",index=False)
    days.to_csv(out/"core_cluster_risk_days.csv",index=False)
    conc.to_csv(out/"core_cluster_risk_concentration.csv",index=False)

    day_summary=(days.groupby(["period","density_bucket"],as_index=False)
                 .agg(days=("date","size"),
                      mean_of_day_means=("day_mean_ret","mean"),
                      median_of_day_means=("day_mean_ret","median"),
                      worst_day_mean=("day_mean_ret","min"),
                      best_day_mean=("day_mean_ret","max"),
                      days_mean_positive=("day_mean_ret",lambda s:float((s>0).mean()))))
    day_summary.to_csv(out/"core_cluster_risk_day_buckets.csv",index=False)

    top=days.sort_values(["period","signal_count","date"],ascending=[True,False,True]).groupby("period",group_keys=False).head(15)
    top.to_csv(out/"core_cluster_risk_top_days.csv",index=False)

    meta={
        "density_buckets":{"N1":"1 signal","N2":"2 signals","N3_4":"3-4 signals","N5_PLUS":"5+ signals"},
        "use":"descriptive cluster-risk annotation only",
        "must_not_be_used_for":"post-hoc filtering or suppression of Core candidates",
        "signal_rule_changes":False,
        "production_writes":False,
    }
    (out/"core_cluster_risk_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nCANDIDATE BUCKETS")
    print(cand.to_string(index=False))
    print("\nDAY BUCKETS")
    print(day_summary.to_string(index=False))
    print("\nCONCENTRATION")
    print(conc.to_string(index=False))
    print("\nTOP BURST DAYS")
    print(top.to_string(index=False))

if __name__=="__main__":
    main()
