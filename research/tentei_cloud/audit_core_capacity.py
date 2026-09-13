#!/usr/bin/env python3
"""Concurrent-position/capital-capacity audit for fixed reconstructed Core.

Research-only. No signal-rule, sizing, or production changes.

Entry proxy:
- first raw Yahoo 1H bar strictly after the completed signal session;
- use that bar's date as executable entry date.

Exit proxy:
- existing five-business-day target_date at that day's close.

Concurrency:
- a trade consumes one position slot from entry_date through target_date
  inclusive (exit occurs at target-day close).

This deliberately does not optimize capital allocation or choose which signals to
skip when capacity is exceeded. It only quantifies unconstrained slot demand.
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

def make_core_pool(raw):
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
    q["target_date_dt"]=pd.to_datetime(q["target_date"],errors="coerce")
    return q,dates

def attach_exec_date(core,raw):
    by_symbol={}
    for sym,g in raw.sort_values("timestamp").groupby("symbol",sort=False):
        by_symbol[str(sym)]=g[["timestamp","open"]].reset_index(drop=True)

    rows=[]
    for _,r in core.iterrows():
        g=by_symbol.get(str(r["symbol"]))
        if g is None or g.empty or pd.isna(r["last_ts"]):
            rows.append({"exec_ts":pd.NaT,"exec_date":None})
            continue
        needle=pd.Timestamp(r["last_ts"])
        j=int(g["timestamp"].searchsorted(needle,side="right"))
        if j>=len(g):
            rows.append({"exec_ts":pd.NaT,"exec_date":None})
            continue
        ts=pd.Timestamp(g.iloc[j]["timestamp"])
        rows.append({"exec_ts":ts,"exec_date":ts.date().isoformat()})
    x=pd.concat([core.reset_index(drop=True),pd.DataFrame(rows)],axis=1)
    x["exec_date_dt"]=pd.to_datetime(x["exec_date"],errors="coerce")
    return x

def qv(s,p):
    return float(s.quantile(p)) if len(s) else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    raw=load(a.inputs)
    core,dates=make_core_pool(raw)
    x=attach_exec_date(core,raw)
    match=float(x["exec_date_dt"].notna().mean()) if len(x) else 0
    if match<0.90:
        raise RuntimeError(f"execution-date coverage guard failed: {match:.4f}")

    trading_dates=pd.to_datetime(pd.Series(sorted(set(dates))),errors="coerce").dropna().sort_values()

    summary=[]
    daily_all=[]
    trade_rows=[]

    for period,start,end in PERIODS:
        ps=pd.Timestamp(start); pe=pd.Timestamp(end)
        q=x[(x["date_dt"]>=ps)&(x["date_dt"]<=pe)].copy()

        # Capacity horizon includes target dates even if they extend beyond signal-period end.
        if q.empty:
            summary.append({"period":period,"signals":0})
            continue

        cal=trading_dates[
            (trading_dates>=q["exec_date_dt"].min())
            & (trading_dates<=q["target_date_dt"].max())
        ].copy()

        rows=[]
        for d in cal:
            opened=q[(q["exec_date_dt"]==d)]
            closing=q[(q["target_date_dt"]==d)]
            active=q[(q["exec_date_dt"]<=d)&(q["target_date_dt"]>=d)]
            rows.append({
                "period":period,
                "date":d.date().isoformat(),
                "open_positions":int(len(active)),
                "new_entries":int(len(opened)),
                "exits_at_close":int(len(closing)),
                "unique_active_symbols":int(active["symbol"].nunique()),
            })
        daily=pd.DataFrame(rows)
        daily_all.append(daily)

        peak=int(daily["open_positions"].max())
        peak_rows=daily[daily["open_positions"]==peak]
        first_peak=peak_rows.iloc[0]["date"] if len(peak_rows) else None

        summary.append({
            "period":period,
            "signals":int(len(q)),
            "exec_coverage":float(q["exec_date_dt"].notna().mean()),
            "calendar_trading_days":int(len(daily)),
            "concurrent_mean":float(daily["open_positions"].mean()),
            "concurrent_median":float(daily["open_positions"].median()),
            "concurrent_p90":qv(daily["open_positions"],0.90),
            "concurrent_p95":qv(daily["open_positions"],0.95),
            "concurrent_max":peak,
            "first_peak_date":first_peak,
            "days_concurrent_5plus":int((daily["open_positions"]>=5).sum()),
            "days_concurrent_10plus":int((daily["open_positions"]>=10).sum()),
            "days_concurrent_15plus":int((daily["open_positions"]>=15).sum()),
            "new_entries_max":int(daily["new_entries"].max()),
            "new_entries_p95":qv(daily["new_entries"],0.95),
        })

        tr=q[[
            "symbol","date","session","exec_date","target_date","ret5bd"
        ]].copy()
        tr["period"]=period
        trade_rows.append(tr)

    summary_df=pd.DataFrame(summary)
    daily_df=pd.concat(daily_all,ignore_index=True) if daily_all else pd.DataFrame()
    trades_df=pd.concat(trade_rows,ignore_index=True) if trade_rows else pd.DataFrame()

    summary_df.to_csv(out/"core_capacity_summary.csv",index=False)
    daily_df.to_csv(out/"core_capacity_daily.csv",index=False)
    trades_df.to_csv(out/"core_capacity_trades.csv",index=False)

    top=(daily_df.sort_values(["period","open_positions","date"],ascending=[True,False,True])
         .groupby("period",as_index=False,group_keys=False).head(15)) if len(daily_df) else pd.DataFrame()
    top.to_csv(out/"core_capacity_top_days.csv",index=False)

    meta={
        "entry_proxy":"first raw Yahoo 1H bar after completed signal session; slot starts on its date",
        "exit_proxy":"existing 5BD target_date close; target date counted as occupied through close",
        "position_unit":"one slot per Core signal; no sizing assumptions",
        "capacity_filtering":False,
        "signal_rule_changes":False,
        "production_writes":False,
        "status":"DESCRIPTIVE_CAPITAL_CAPACITY_AUDIT",
    }
    (out/"core_capacity_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nSUMMARY")
    print(summary_df.to_string(index=False))
    print("\nTOP CAPACITY DAYS")
    print(top.to_string(index=False))

if __name__=="__main__":
    main()
