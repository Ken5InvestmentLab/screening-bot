#!/usr/bin/env python3
"""Operational-load audit for the fixed reconstructed Core.

Research-only. No signal-rule changes, no threshold tuning, no production writes.

Quantifies what an operator/user would experience if every fixed Core candidate
were surfaced:
- signals per trading day;
- AM/PM session burst sizes;
- exact signal-session last-bar timestamp burst sizes;
- weekly alert load;
- active-day frequency;
- symbol recurrence under the already-fixed 5BD cooldown.

This is descriptive capacity/UX evidence only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown

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
    q["last_ts"]=pd.to_datetime(q["last_ts"],errors="coerce")
    iso=q["date_dt"].dt.isocalendar()
    q["iso_week"]=iso["year"].astype(str)+"-W"+iso["week"].astype(str).str.zfill(2)
    q["signal_clock"]=q["last_ts"].dt.strftime("%H:%M")
    return q

def pmask(x,start,end):
    return (x["date_dt"]>=pd.Timestamp(start))&(x["date_dt"]<=pd.Timestamp(end))

def qv(s: pd.Series,p: float) -> float|None:
    if s.empty:
        return None
    return float(s.quantile(p))

def summarize_period(q: pd.DataFrame, period: str) -> dict:
    if q.empty:
        return {"period":period,"n":0}

    # Only dates on which at least one signal appeared.
    day=q.groupby("date").size().rename("signals")
    sess=q.groupby(["date","session"]).size().rename("signals")
    exact=q.groupby(["date","last_ts"]).size().rename("signals")
    week=q.groupby("iso_week").size().rename("signals")

    symbol_counts=q.groupby("symbol").size().rename("signals")

    return {
        "period":period,
        "n":int(len(q)),
        "unique_symbols":int(q["symbol"].nunique()),
        "active_days":int(day.size),
        "active_weeks":int(week.size),
        "am_n":int((q["session"]=="AM").sum()),
        "pm_n":int((q["session"]=="PM").sum()),
        "am_share":float((q["session"]=="AM").mean()),
        "signals_per_active_day_mean":float(day.mean()),
        "signals_per_active_day_median":float(day.median()),
        "signals_per_active_day_p90":qv(day,0.90),
        "signals_per_active_day_p95":qv(day,0.95),
        "signals_per_active_day_max":int(day.max()),
        "days_with_1_signal":int((day==1).sum()),
        "days_with_2_signals":int((day==2).sum()),
        "days_with_3plus_signals":int((day>=3).sum()),
        "days_with_5plus_signals":int((day>=5).sum()),
        "session_burst_mean":float(sess.mean()),
        "session_burst_p95":qv(sess,0.95),
        "session_burst_max":int(sess.max()),
        "exact_timestamp_burst_max":int(exact.max()),
        "weekly_signals_mean_active_weeks":float(week.mean()),
        "weekly_signals_p95_active_weeks":qv(week,0.95),
        "weekly_signals_max":int(week.max()),
        "symbols_seen_once":int((symbol_counts==1).sum()),
        "symbols_seen_2plus":int((symbol_counts>=2).sum()),
        "max_signals_same_symbol":int(symbol_counts.max()),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir)
    out.mkdir(parents=True,exist_ok=True)

    raw=load(a.inputs)
    core=make_core_pool(raw)

    summaries=[]
    daily_rows=[]
    session_rows=[]
    weekly_rows=[]
    clock_rows=[]
    recurrence_rows=[]

    for period,start,end in PERIODS:
        q=core[pmask(core,start,end)].copy()
        summaries.append(summarize_period(q,period))

        d=(q.groupby("date",as_index=False)
           .agg(signals=("symbol","size"),
                unique_symbols=("symbol","nunique"),
                am_signals=("session",lambda s:int((s=="AM").sum())),
                pm_signals=("session",lambda s:int((s=="PM").sum()))))
        d["period"]=period
        daily_rows.append(d)

        ss=(q.groupby(["date","session"],as_index=False)
            .agg(signals=("symbol","size"),unique_symbols=("symbol","nunique")))
        ss["period"]=period
        session_rows.append(ss)

        w=(q.groupby("iso_week",as_index=False)
           .agg(signals=("symbol","size"),active_days=("date","nunique"),unique_symbols=("symbol","nunique")))
        w["period"]=period
        weekly_rows.append(w)

        c=(q.groupby(["signal_clock","session"],as_index=False)
           .agg(signals=("symbol","size"),active_dates=("date","nunique")))
        c["period"]=period
        clock_rows.append(c)

        rec=(q.groupby("symbol",as_index=False)
             .agg(signals=("date","size"),first_date=("date","min"),last_date=("date","max")))
        rec["period"]=period
        recurrence_rows.append(rec)

    summary=pd.DataFrame(summaries)
    daily=pd.concat(daily_rows,ignore_index=True) if daily_rows else pd.DataFrame()
    session=pd.concat(session_rows,ignore_index=True) if session_rows else pd.DataFrame()
    weekly=pd.concat(weekly_rows,ignore_index=True) if weekly_rows else pd.DataFrame()
    clocks=pd.concat(clock_rows,ignore_index=True) if clock_rows else pd.DataFrame()
    recurrence=pd.concat(recurrence_rows,ignore_index=True) if recurrence_rows else pd.DataFrame()

    summary.to_csv(out/"core_operational_load_summary.csv",index=False)
    daily.to_csv(out/"core_operational_load_daily.csv",index=False)
    session.to_csv(out/"core_operational_load_session.csv",index=False)
    weekly.to_csv(out/"core_operational_load_weekly.csv",index=False)
    clocks.to_csv(out/"core_operational_load_clocks.csv",index=False)
    recurrence.to_csv(out/"core_operational_load_symbol_recurrence.csv",index=False)

    # Top bursts for direct operational inspection.
    top_daily=(daily.sort_values(["period","signals","date"],ascending=[True,False,True])
               .groupby("period",as_index=False,group_keys=False).head(10))
    top_session=(session.sort_values(["period","signals","date"],ascending=[True,False,True])
                 .groupby("period",as_index=False,group_keys=False).head(10))
    top_daily.to_csv(out/"core_operational_load_top_daily.csv",index=False)
    top_session.to_csv(out/"core_operational_load_top_session.csv",index=False)

    meta={
        "raw_start":str(raw["date"].min()),
        "raw_end":str(raw["date"].max()),
        "core_rule":"unchanged fixed reconstructed Core",
        "periods":PERIODS,
        "scope":"notification/operational load only",
        "threshold_tuning":False,
        "signal_rule_changes":False,
        "production_writes":False,
        "status":"DESCRIPTIVE_OPERATIONAL_LOAD_AUDIT",
    }
    (out/"core_operational_load_meta.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8"
    )

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nSUMMARY")
    print(summary.to_string(index=False))
    print("\nTOP DAILY BURSTS")
    print(top_daily.to_string(index=False))
    print("\nTOP SESSION BURSTS")
    print(top_session.to_string(index=False))
    print("\nCLOCK DISTRIBUTION")
    print(clocks.to_string(index=False))

if __name__=="__main__":
    main()
