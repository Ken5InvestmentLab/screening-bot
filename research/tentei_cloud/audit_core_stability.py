#!/usr/bin/env python3
"""Stability and uncertainty audit for the fixed reconstructed Core baseline.

Research-only. No rule selection, threshold tuning, or production writes.

This audit does not change Core. It quantifies:
- monthly return stability;
- concentration (top winner removals);
- week-clustered moving-block style bootstrap uncertainty;
- leave-one-month-out sensitivity.

Fixed periods are descriptive:
- DEV: 2024-11-01..2025-06-30
- 2025H2: 2025-07-01..2025-12-31
- 2026_YTD: 2026-01-01..2026-08-31

Bootstrap samples whole ISO-week clusters with replacement to preserve same-week
cross-sectional clustering. The random seed and repetitions are fixed here.
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
BOOTSTRAP_REPS=5000
SEED=20260914

PERIODS=[
    ("DEV","2024-11-01","2025-06-30"),
    ("2025H2","2025-07-01","2025-12-31"),
    ("2026_YTD","2026-01-01","2026-08-31"),
]


def make_core_pool(raw: pd.DataFrame) -> pd.DataFrame:
    s=aggregate(raw,780)
    s=enrich_session(s)
    s,dates=add_daily_context(s,raw)
    eligible=s[
        (s["prev_daily_close"]<=1000)
        & (s["prev_daily_volume"]>=10000)
        & (s["volume"]>=5000)
    ].copy()
    gate=(
        (eligible["rsi12"]<45)
        & eligible["pre_down3"].fillna(False)
        & (eligible["close"]>eligible["bb_mid"])
        & (eligible["atr14_pct"]<0.05)
    )
    q=cooldown(eligible[gate].copy(),dates,5)
    q=q[q["ret5bd"].notna()].copy()
    q["date_dt"]=pd.to_datetime(q["date"],errors="coerce")
    iso=q["date_dt"].dt.isocalendar()
    q["iso_week"]=iso["year"].astype(str)+"-W"+iso["week"].astype(str).str.zfill(2)
    q["month"]=q["date_dt"].dt.to_period("M").astype(str)
    return q


def period_mask(x,start,end):
    return (x["date_dt"]>=pd.Timestamp(start))&(x["date_dt"]<=pd.Timestamp(end))


def summarize_returns(r: pd.Series) -> dict:
    r=r.dropna().astype(float)
    if r.empty:
        return {"n":0}
    rs=r.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(r)),
        "mean":float(r.mean()),
        "median":float(r.median()),
        "win":float((r>0).mean()),
        "ge10":float((r>=0.10).mean()),
        "ge20":float((r>=0.20).mean()),
        "le10":float((r<=-0.10).mean()),
        "max":float(r.max()),
        "min":float(r.min()),
        "top1_removed":float(rs.iloc[1:].mean()) if len(rs)>1 else None,
        "top3_removed":float(rs.iloc[3:].mean()) if len(rs)>3 else None,
        "top5_removed":float(rs.iloc[5:].mean()) if len(rs)>5 else None,
    }


def weekly_block_bootstrap(q: pd.DataFrame, reps: int, seed: int) -> dict:
    groups=[g["ret5bd"].dropna().astype(float).to_numpy() for _,g in q.groupby("iso_week",sort=True)]
    groups=[g for g in groups if len(g)]
    if not groups:
        return {}
    rng=np.random.default_rng(seed)
    nblocks=len(groups)
    means=np.empty(reps)
    medians=np.empty(reps)
    le10=np.empty(reps)
    wins=np.empty(reps)
    for i in range(reps):
        idx=rng.integers(0,nblocks,size=nblocks)
        arr=np.concatenate([groups[j] for j in idx])
        means[i]=arr.mean()
        medians[i]=np.median(arr)
        le10[i]=(arr<=-0.10).mean()
        wins[i]=(arr>0).mean()

    def ci(a):
        return [float(np.quantile(a,0.025)),float(np.quantile(a,0.975))]

    return {
        "week_blocks":nblocks,
        "reps":reps,
        "mean_ci95":ci(means),
        "median_ci95":ci(medians),
        "win_ci95":ci(wins),
        "le10_ci95":ci(le10),
        "prob_mean_gt_0":float((means>0).mean()),
        "prob_median_gt_0":float((medians>0).mean()),
        "bootstrap_mean_of_mean":float(means.mean()),
    }


def monthly_table(q: pd.DataFrame, period: str) -> list[dict]:
    rows=[]
    for month,g in q.groupby("month",sort=True):
        m=summarize_returns(g["ret5bd"])
        rows.append({"period":period,"month":month,**m})
    return rows


def leave_one_month_out(q: pd.DataFrame, period: str) -> list[dict]:
    rows=[]
    months=sorted(q["month"].dropna().unique())
    for month in months:
        z=q[q["month"]!=month]
        m=summarize_returns(z["ret5bd"])
        rows.append({
            "period":period,
            "left_out_month":month,
            **m,
        })
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    raw=load(a.inputs)
    core=make_core_pool(raw)

    baseline=[]
    monthly=[]
    lomo=[]
    uncertainty={}

    for i,(name,start,end) in enumerate(PERIODS):
        q=core[period_mask(core,start,end)].copy()
        baseline.append({
            "period":name,
            **summarize_returns(q["ret5bd"]),
            "months":int(q["month"].nunique()),
            "weeks":int(q["iso_week"].nunique()),
        })
        monthly.extend(monthly_table(q,name))
        lomo.extend(leave_one_month_out(q,name))
        uncertainty[name]=weekly_block_bootstrap(q,BOOTSTRAP_REPS,SEED+i)

    baseline_df=pd.DataFrame(baseline)
    monthly_df=pd.DataFrame(monthly)
    lomo_df=pd.DataFrame(lomo)
    baseline_df.to_csv(out/"core_stability_baseline.csv",index=False)
    monthly_df.to_csv(out/"core_stability_monthly.csv",index=False)
    lomo_df.to_csv(out/"core_stability_leave_one_month_out.csv",index=False)

    # Compact robustness summary derived without any selection.
    robustness=[]
    for name,_,_ in PERIODS:
        m=monthly_df[monthly_df["period"]==name]
        l=lomo_df[lomo_df["period"]==name]
        robustness.append({
            "period":name,
            "positive_months":int((m["mean"]>0).sum()) if len(m) else 0,
            "total_months":int(len(m)),
            "monthly_mean_median":float(m["mean"].median()) if len(m) else None,
            "worst_month_mean":float(m["mean"].min()) if len(m) else None,
            "best_month_mean":float(m["mean"].max()) if len(m) else None,
            "lomo_mean_min":float(l["mean"].min()) if len(l) else None,
            "lomo_mean_max":float(l["mean"].max()) if len(l) else None,
            "all_lomo_mean_positive":bool((l["mean"]>0).all()) if len(l) else False,
            "bootstrap_prob_mean_gt_0":uncertainty[name].get("prob_mean_gt_0"),
            "bootstrap_mean_ci95_low":uncertainty[name].get("mean_ci95",[None,None])[0],
            "bootstrap_mean_ci95_high":uncertainty[name].get("mean_ci95",[None,None])[1],
        })
    pd.DataFrame(robustness).to_csv(out/"core_stability_robustness.csv",index=False)

    meta={
        "raw_start":str(raw["date"].min()),
        "raw_end":str(raw["date"].max()),
        "core_pool_n":int(len(core)),
        "periods":PERIODS,
        "bootstrap":{
            "method":"sample whole ISO-week clusters with replacement",
            "reps":BOOTSTRAP_REPS,
            "seed":SEED,
        },
        "selection_changes":False,
        "threshold_tuning":False,
        "production_writes":False,
        "status":"DESCRIPTIVE_STABILITY_AUDIT",
    }
    payload={"meta":meta,"uncertainty":uncertainty}
    (out/"core_stability_meta.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(payload,ensure_ascii=False,indent=2))
    print("\nBASELINE")
    print(baseline_df.to_string(index=False))
    print("\nROBUSTNESS")
    print(pd.DataFrame(robustness).to_string(index=False))
    print("\nMONTHLY")
    print(monthly_df.to_string(index=False))
    print("\nLEAVE ONE MONTH OUT")
    print(lomo_df.to_string(index=False))


if __name__=="__main__":
    main()
