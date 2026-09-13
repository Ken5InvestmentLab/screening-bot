#!/usr/bin/env python3
"""TV-free long-horizon daily baseline from current Mega40 semantics.

Research-only. No production writes.

This is NOT an attempt to reproduce the current TradingView/BOTTOM-dependent
Mega40 candidates exactly. It asks whether the published Mega40 semantic rules
have useful 40BD behavior when applied directly to a TV-free daily TSE universe.

Frozen mode semantics:

DEEP:
- 20-day high drawdown >= 15%
- previous three completed daily closes descending
- Bollinger(20,2) position <= 20%
- bullish candle body >= 2%

WICK:
- 20-day high drawdown >= 15%
- CCI(20) <= -100
- lower wick >= 50% of candle range
- current close > close 26 sessions ago

Two fixed universe variants:
- CAP1000: previous close <= 1000 JPY, previous volume >= 10k,
  current volume >= 5k.
- NO_PRICE_CAP: same liquidity rules, no price cap.

All formulas and variants are declared before result inspection.
Same-symbol cooldown = 5 business dates, matching existing research convention.

Primary executable entry:
- next trading day's first raw 1H bar OPEN after the daily signal is complete.

40BD target:
- close on the 40th global trading date after signal date.

Periods:
- DEV: 2025-01-01..2025-06-30
- VALID: 2025-07-01..2025-12-31
- 2026_MATURED: 2026 signals whose 40BD target exists in the fetched history.

No result-dependent threshold sweep is allowed in this script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load

PERIODS=[
    ("DEV","2025-01-01","2025-06-30"),
    ("VALID","2025-07-01","2025-12-31"),
    ("2026_MATURED","2026-01-01","2026-08-31"),
]

def build_daily(raw):
    d=(raw.sort_values("timestamp")
       .groupby(["symbol","date"],as_index=False)
       .agg(
           open=("open","first"),
           high=("high","max"),
           low=("low","min"),
           close=("close","last"),
           volume=("volume","sum"),
           first_ts=("timestamp","first"),
           last_ts=("timestamp","last"),
       )
       .sort_values(["symbol","date"])
       .copy())
    dates=sorted(d["date"].unique().tolist())
    date_pos={v:i for i,v in enumerate(dates)}
    t40={v:(dates[i+40] if i+40<len(dates) else None) for i,v in enumerate(dates)}
    nextd={v:(dates[i+1] if i+1<len(dates) else None) for i,v in enumerate(dates)}

    outs=[]
    for _,g in d.groupby("symbol",sort=False):
        g=g.sort_values("date").copy()
        c=g["close"].astype(float)
        o=g["open"].astype(float)
        h=g["high"].astype(float)
        l=g["low"].astype(float)
        v=g["volume"].astype(float)

        g["prev_close"]=c.shift(1)
        g["prev_volume"]=v.shift(1)

        hi20=h.rolling(20,min_periods=20).max()
        g["drawdown20"]=c/hi20-1.0

        mid=c.rolling(20,min_periods=20).mean()
        sd=c.rolling(20,min_periods=20).std(ddof=0)
        upper=mid+2*sd
        lower=mid-2*sd
        width=(upper-lower).replace(0,np.nan)
        g["bbpct20"]=(c-lower)/width

        g["pre_down3"]=(c.shift(1)<c.shift(2))&(c.shift(2)<c.shift(3))
        g["body_pct"]=(c-o)/o.replace(0,np.nan)

        tp=(h+l+c)/3.0
        tp_ma=tp.rolling(20,min_periods=20).mean()
        mad=tp.rolling(20,min_periods=20).apply(
            lambda x: float(np.mean(np.abs(x-np.mean(x)))),raw=True
        )
        g["cci20"]=(tp-tp_ma)/(0.015*mad.replace(0,np.nan))

        rng=(h-l).replace(0,np.nan)
        lower_wick=np.minimum(o,c)-l
        g["lower_wick_ratio"]=lower_wick/rng
        g["ich_chikou_proxy"]=c>c.shift(26)

        outs.append(g)

    x=pd.concat(outs,ignore_index=True)
    x["target40_date"]=x["date"].map(t40)
    x["next_date"]=x["date"].map(nextd)

    target=x[["symbol","date","close"]].rename(
        columns={"date":"target40_date","close":"target40_close"}
    )
    x=x.merge(target,on=["symbol","target40_date"],how="left")
    x["ret40_close_entry"]=x["target40_close"]/x["close"]-1.0
    x["date_dt"]=pd.to_datetime(x["date"],errors="coerce")
    return x,dates,date_pos

def attach_next_open(x,raw):
    # first raw 1H bar on the next global trading date for the same symbol
    first=(raw.sort_values("timestamp")
           .groupby(["symbol","date"],as_index=False)
           .agg(next_open=("open","first"),next_open_ts=("timestamp","first"))
           .rename(columns={"date":"next_date"}))
    y=x.merge(first,on=["symbol","next_date"],how="left")
    y["ret40_next_open"]=y["target40_close"]/y["next_open"]-1.0
    return y

def cooldown(q,date_pos,n=5):
    keep=[]
    last={}
    for idx,r in q.sort_values(["date","symbol"]).iterrows():
        di=date_pos.get(str(r["date"]))
        if di is None:
            continue
        s=str(r["symbol"])
        p=last.get(s)
        if p is None or di-p>=n:
            keep.append(idx)
            last[s]=di
    return q.loc[keep].sort_values(["date","symbol"]).copy()

def metrics(r):
    r=pd.Series(r).dropna().astype(float)
    if r.empty:
        return {"n":0}
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

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    raw=load(a.inputs)
    x,dates,date_pos=build_daily(raw)
    x=attach_next_open(x,raw)

    base_liq=(x["prev_volume"]>=10000)&(x["volume"]>=5000)
    universes={
        "CAP1000":base_liq&(x["prev_close"]<=1000),
        "NO_PRICE_CAP":base_liq,
    }

    deep=(
        (x["drawdown20"]<=-0.15)
        & x["pre_down3"].fillna(False)
        & (x["bbpct20"]<=0.20)
        & (x["body_pct"]>=0.02)
    )
    wick=(
        (x["drawdown20"]<=-0.15)
        & (x["cci20"]<=-100)
        & (x["lower_wick_ratio"]>=0.50)
        & x["ich_chikou_proxy"].fillna(False)
    )
    modes={"DEEP":deep,"WICK":wick}

    rows=[]
    counts=[]
    exports=[]

    for uname,umask in universes.items():
        for mname,mmask in modes.items():
            rawcand=x[umask&mmask].copy()
            selected=cooldown(rawcand,date_pos,5)
            selected["universe"]=uname
            selected["mode"]=mname
            exports.append(selected)

            for period,start,end in PERIODS:
                q=selected[
                    (selected["date_dt"]>=pd.Timestamp(start))
                    & (selected["date_dt"]<=pd.Timestamp(end))
                ].copy()
                mature=q[q["target40_close"].notna()].copy()
                executable=mature[mature["next_open"].notna()].copy()

                counts.append({
                    "universe":uname,
                    "mode":mname,
                    "period":period,
                    "selected_n":int(len(q)),
                    "mature40_n":int(len(mature)),
                    "exec_entry_n":int(len(executable)),
                })

                for entry,col in [
                    ("SIGNAL_CLOSE","ret40_close_entry"),
                    ("NEXT_DAY_OPEN","ret40_next_open"),
                ]:
                    rows.append({
                        "universe":uname,
                        "mode":mname,
                        "period":period,
                        "entry":entry,
                        **metrics(executable[col] if entry=="NEXT_DAY_OPEN" else mature[col]),
                    })

    metrics_df=pd.DataFrame(rows)
    counts_df=pd.DataFrame(counts)
    metrics_df.to_csv(out/"long_daily_baseline_metrics.csv",index=False)
    counts_df.to_csv(out/"long_daily_baseline_counts.csv",index=False)

    allsel=pd.concat(exports,ignore_index=True,sort=False)
    keep=[
        "universe","mode","date","symbol","open","high","low","close","volume",
        "prev_close","prev_volume","drawdown20","bbpct20","pre_down3","body_pct",
        "cci20","lower_wick_ratio","ich_chikou_proxy","next_date","next_open",
        "target40_date","target40_close","ret40_close_entry","ret40_next_open",
    ]
    allsel[[k for k in keep if k in allsel.columns]].to_csv(
        out/"long_daily_baseline_candidates.csv",index=False
    )

    meta={
        "formulas":{
            "pre_decline15":"close / rolling20 daily high - 1 <= -0.15",
            "pre_down3":"previous 3 completed daily closes strictly descending",
            "bb_lower":"BB(20,2) normalized position <= 0.20",
            "body2":"(close-open)/open >= 0.02",
            "cci_os":"standard CCI(20) <= -100 using typical price and mean absolute deviation",
            "lower_wick50":"(min(open,close)-low)/(high-low) >= 0.50",
            "ich_chikou":"current close > close 26 sessions ago",
        },
        "universe_variants":{
            "CAP1000":"prev close <=1000, prev volume >=10000, current daily volume >=5000",
            "NO_PRICE_CAP":"prev volume >=10000, current daily volume >=5000",
        },
        "cooldown_business_dates":5,
        "primary_entry":"next trading day first raw Yahoo 1H bar open",
        "target":"40th global trading date close after signal date",
        "periods":PERIODS,
        "threshold_sweep":False,
        "production_writes":False,
        "status":"EXPLORATORY_FIXED_SEMANTIC_BASELINE",
    }
    (out/"long_daily_baseline_meta.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8"
    )

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nCOUNTS")
    print(counts_df.to_string(index=False))
    print("\nMETRICS")
    print(metrics_df.to_string(index=False))

if __name__=="__main__":
    main()
