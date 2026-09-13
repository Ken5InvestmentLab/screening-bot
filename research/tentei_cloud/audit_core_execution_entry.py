#!/usr/bin/env python3
"""Executable-entry audit for the fixed reconstructed 4H Core.

Research-only. No production writes and no signal-rule changes.

Problem:
The standard research label ret5bd uses the reconstructed signal-session CLOSE as
the entry price. A real alert can only be acted on after that session is complete.

This audit therefore attaches, for each fixed Core candidate, the first raw Yahoo
1H bar strictly AFTER the signal session's last raw timestamp and uses that bar's
OPEN as a causal executable-entry proxy.

Examples under the fixed 13:00 split:
- AM signal: first next bar is normally the 13:00 JST bar.
- PM signal: first next bar is normally the next trading day's opening bar.

The target remains the same pre-existing 5-business-day target close so this is
an entry-timing sensitivity test, not a horizon redefinition.

Matched comparisons use only candidates with an observed next bar so the
signal-close and next-open returns are compared on the same rows.

2025H2/2026 aggregate outcomes have already been inspected; results are
retrospective causal evidence, not pristine OOS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown

BOOTSTRAP_REPS=5000
SEED=20260914
COSTS=[0.0,0.005,0.01]

PERIODS=[
    ("DEV","2024-11-01","2025-06-30"),
    ("2025H2","2025-07-01","2025-12-31"),
    ("2026_YTD","2026-01-01","2026-08-31"),
    ("2026_01_02","2026-01-01","2026-02-28"),
    ("2026_03_04","2026-03-01","2026-04-30"),
    ("2026_05_06","2026-05-01","2026-06-30"),
    ("2026_07_08","2026-07-01","2026-08-31"),
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
    return q


def attach_next_bar(core: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    # Raw is already normalized to JST in load().
    by_symbol={}
    for sym,g in raw.sort_values("timestamp").groupby("symbol",sort=False):
        by_symbol[str(sym)]=g[["timestamp","open","close","volume"]].reset_index(drop=True)

    rows=[]
    for _,r in core.iterrows():
        sym=str(r["symbol"])
        g=by_symbol.get(sym)
        if g is None or g.empty or pd.isna(r["last_ts"]):
            rows.append({
                "exec_ts":pd.NaT,"exec_open":np.nan,"exec_bar_close":np.nan,
                "exec_volume":np.nan,"entry_delay_hours":np.nan,
            })
            continue
        needle=pd.Timestamp(r["last_ts"])
        # Keep both operands in pandas' timezone-aware datetime dtype.
        # Do not compare raw integer epochs: pandas 3 may store datetime64 in
        # microseconds while Timestamp.value is nanoseconds.
        j=int(g["timestamp"].searchsorted(needle, side="right"))
        if j>=len(g):
            rows.append({
                "exec_ts":pd.NaT,"exec_open":np.nan,"exec_bar_close":np.nan,
                "exec_volume":np.nan,"entry_delay_hours":np.nan,
            })
            continue
        z=g.iloc[j]
        exec_ts=pd.Timestamp(z["timestamp"])
        rows.append({
            "exec_ts":exec_ts,
            "exec_open":float(z["open"]),
            "exec_bar_close":float(z["close"]),
            "exec_volume":float(z["volume"]),
            "entry_delay_hours":float((exec_ts-needle).total_seconds()/3600.0),
        })

    x=pd.concat([core.reset_index(drop=True),pd.DataFrame(rows)],axis=1)
    x["ret5bd_next_open"]=x["target_close"]/x["exec_open"]-1.0
    x["entry_gap_vs_signal_close"]=x["exec_open"]/x["close"]-1.0
    x["matched"]=x["exec_open"].notna()&x["target_close"].notna()
    return x


def summarize(r: pd.Series) -> dict:
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


def week_bootstrap(q: pd.DataFrame, col: str, cost: float, seed: int) -> dict:
    groups=[
        (g[col].dropna().astype(float)-cost).to_numpy()
        for _,g in q.groupby("iso_week",sort=True)
    ]
    groups=[a for a in groups if len(a)]
    if not groups:
        return {}
    rng=np.random.default_rng(seed)
    n=len(groups)
    means=np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        idx=rng.integers(0,n,size=n)
        a=np.concatenate([groups[j] for j in idx])
        means[i]=a.mean()
    return {
        "week_blocks":n,
        "prob_mean_gt_0":float((means>0).mean()),
        "mean_ci95_low":float(np.quantile(means,0.025)),
        "mean_ci95_high":float(np.quantile(means,0.975)),
    }


def pmask(x,start,end):
    return (x["date_dt"]>=pd.Timestamp(start))&(x["date_dt"]<=pd.Timestamp(end))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    raw=load(a.inputs)
    core=make_core_pool(raw)
    x=attach_next_bar(core,raw)
    matched_rate=float(x["matched"].mean()) if len(x) else 0.0
    if matched_rate < 0.90:
        raise RuntimeError(
            f"executable-entry coverage guard failed: matched_rate={matched_rate:.4f} < 0.90"
        )

    coverage=[]
    compare=[]
    cost_rows=[]

    for pi,(name,start,end) in enumerate(PERIODS):
        q=x[pmask(x,start,end)].copy()
        matched=q[q["matched"]].copy()

        coverage.append({
            "period":name,
            "core_n":int(len(q)),
            "matched_n":int(len(matched)),
            "matched_rate":float(len(matched)/len(q)) if len(q) else None,
            "am_n":int((matched["session"]=="AM").sum()),
            "pm_n":int((matched["session"]=="PM").sum()),
            "entry_gap_mean":float(matched["entry_gap_vs_signal_close"].mean()) if len(matched) else None,
            "entry_gap_median":float(matched["entry_gap_vs_signal_close"].median()) if len(matched) else None,
            "entry_delay_hours_median":float(matched["entry_delay_hours"].median()) if len(matched) else None,
        })

        for scope,sub in [
            ("ALL",matched),
            ("AM",matched[matched["session"]=="AM"]),
            ("PM",matched[matched["session"]=="PM"]),
        ]:
            sig=summarize(sub["ret5bd"])
            exe=summarize(sub["ret5bd_next_open"])
            compare.append({
                "period":name,
                "scope":scope,
                "matched_n":int(len(sub)),
                "signal_close_mean":sig.get("mean"),
                "next_open_mean":exe.get("mean"),
                "mean_delta_next_open_minus_signal":(
                    exe.get("mean")-sig.get("mean")
                    if exe.get("mean") is not None and sig.get("mean") is not None else None
                ),
                "signal_close_median":sig.get("median"),
                "next_open_median":exe.get("median"),
                "signal_close_win":sig.get("win"),
                "next_open_win":exe.get("win"),
                "signal_close_le10":sig.get("le10"),
                "next_open_le10":exe.get("le10"),
                "next_open_top3_removed":exe.get("top3_removed"),
            })

        for ci,cost in enumerate(COSTS):
            r=matched["ret5bd_next_open"]-cost
            sm=summarize(r)
            boot=week_bootstrap(matched,"ret5bd_next_open",cost,SEED+pi*10+ci)
            cost_rows.append({
                "period":name,
                "round_trip_cost":cost,
                **sm,
                **boot,
            })

    cov=pd.DataFrame(coverage)
    cmp=pd.DataFrame(compare)
    costs=pd.DataFrame(cost_rows)

    cov.to_csv(out/"core_execution_coverage.csv",index=False)
    cmp.to_csv(out/"core_execution_matched_compare.csv",index=False)
    costs.to_csv(out/"core_execution_cost_sensitivity.csv",index=False)

    keep=[
        "date","session","session_time","last_ts","symbol","close","target_date","target_close",
        "ret5bd","exec_ts","exec_open","exec_bar_close","entry_delay_hours",
        "entry_gap_vs_signal_close","ret5bd_next_open","matched",
    ]
    x[[k for k in keep if k in x.columns]].to_csv(out/"core_execution_rows.csv",index=False)

    meta={
        "raw_start":str(raw["date"].min()),
        "raw_end":str(raw["date"].max()),
        "core_pool_n":int(len(x)),
        "entry_proxy":"first raw Yahoo 1H bar strictly after signal session last_ts; use its OPEN",
        "target":"unchanged existing five-business-day target close",
        "matched_comparison":True,
        "cost_scenarios":COSTS,
        "bootstrap":"5000 whole-ISO-week cluster resamples",
        "signal_rule_changes":False,
        "production_writes":False,
        "status":"RETROSPECTIVE_CAUSAL_EXECUTION_SENSITIVITY",
    }
    (out/"core_execution_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nCOVERAGE")
    print(cov.to_string(index=False))
    print("\nMATCHED COMPARE")
    print(cmp.to_string(index=False))
    print("\nEXECUTION COST SENSITIVITY")
    print(costs.to_string(index=False))


if __name__=="__main__":
    main()
