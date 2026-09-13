#!/usr/bin/env python3
"""Consumer-side long-horizon overlay audit on a frozen canonical event stream.

Research-only. Does NOT modify/reimplement the canonical V7/V20 event producer.

Input event stream:
- frozen annual candidate detections exported by research/tvfree-canonical-batch02.
- 2025 rows are saved-cache replay.
- 2026 rows are runtime-sensitive same-source reconstruction and are report-only.

Question:
Does putting a fixed event entrance in front of the published Mega40 semantic
overlays materially improve 40BD behavior compared with direct daily application?

Frozen consumers:
- EVENT_ONLY
- EVENT_PLUS_DEEP
- EVENT_PLUS_WICK
- EVENT_PLUS_ANY_LONG_OVERLAY = DEEP OR WICK

Deep / Wick formulas are identical to audit_long_daily_baseline.py.
No threshold, ranking, Top-N, or price-cap search is allowed.

Evaluation:
- signal date = frozen event row signal_date.
- executable entry = next trading day's first raw Yahoo 1H open.
- target = close on 40th global trading date after signal date.
- report 2025H1 / 2025H2 / 2026 matured separately.

This is retrospective role-coverage evidence, not pristine validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load

PERIODS=[
    ("2025H1","2025-01-01","2025-06-30"),
    ("2025H2","2025-07-01","2025-12-31"),
    ("2026_MATURED","2026-01-01","2026-08-31"),
]

def build_daily(raw):
    d=(raw.sort_values("timestamp")
       .groupby(["symbol","date"],as_index=False)
       .agg(
           open=("open","first"),high=("high","max"),low=("low","min"),
           close=("close","last"),volume=("volume","sum"),
           first_ts=("timestamp","first"),last_ts=("timestamp","last"),
       )
       .sort_values(["symbol","date"])
       .copy())
    dates=sorted(d["date"].unique().tolist())
    t40={v:(dates[i+40] if i+40<len(dates) else None) for i,v in enumerate(dates)}
    nextd={v:(dates[i+1] if i+1<len(dates) else None) for i,v in enumerate(dates)}

    outs=[]
    for _,g in d.groupby("symbol",sort=False):
        g=g.sort_values("date").copy()
        c=g["close"].astype(float); o=g["open"].astype(float)
        h=g["high"].astype(float); l=g["low"].astype(float)
        g["prev_close"]=c.shift(1)
        g["prev_volume"]=g["volume"].astype(float).shift(1)

        hi20=h.rolling(20,min_periods=20).max()
        g["drawdown20"]=c/hi20-1.0
        mid=c.rolling(20,min_periods=20).mean()
        sd=c.rolling(20,min_periods=20).std(ddof=0)
        upper=mid+2*sd; lower=mid-2*sd
        g["bbpct20"]=(c-lower)/(upper-lower).replace(0,np.nan)
        g["pre_down3"]=(c.shift(1)<c.shift(2))&(c.shift(2)<c.shift(3))
        g["body_pct"]=(c-o)/o.replace(0,np.nan)

        tp=(h+l+c)/3.0
        ma=tp.rolling(20,min_periods=20).mean()
        mad=tp.rolling(20,min_periods=20).apply(
            lambda x: float(np.mean(np.abs(x-np.mean(x)))), raw=True
        )
        g["cci20"]=(tp-ma)/(0.015*mad.replace(0,np.nan))
        g["lower_wick_ratio"]=(np.minimum(o,c)-l)/(h-l).replace(0,np.nan)
        g["ich_chikou_proxy"]=c>c.shift(26)
        outs.append(g)

    x=pd.concat(outs,ignore_index=True)
    x["target40_date"]=x["date"].map(t40)
    x["next_date"]=x["date"].map(nextd)

    target=x[["symbol","date","close"]].rename(
        columns={"date":"target40_date","close":"target40_close"}
    )
    x=x.merge(target,on=["symbol","target40_date"],how="left")

    nxt=(raw.sort_values("timestamp")
         .groupby(["symbol","date"],as_index=False)
         .agg(next_open=("open","first"),next_open_ts=("timestamp","first"))
         .rename(columns={"date":"next_date"}))
    x=x.merge(nxt,on=["symbol","next_date"],how="left")
    x["ret40_next_open"]=x["target40_close"]/x["next_open"]-1.0

    x["deep_overlay"]=(
        (x["drawdown20"]<=-0.15)
        & x["pre_down3"].fillna(False)
        & (x["bbpct20"]<=0.20)
        & (x["body_pct"]>=0.02)
    )
    x["wick_overlay"]=(
        (x["drawdown20"]<=-0.15)
        & (x["cci20"]<=-100)
        & (x["lower_wick_ratio"]>=0.50)
        & x["ich_chikou_proxy"].fillna(False)
    )
    return x

def metrics(r):
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

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--events",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    raw=load(a.inputs)
    daily=build_daily(raw)

    ev=pd.read_csv(a.events,dtype={"symbol":"string"})
    ev=ev[ev["detection_status"].astype(str)=="DETECTED"].copy()
    ev["symbol"]=ev["symbol"].astype(str).str.replace(".T","",regex=False).str.strip()
    ev["date"]=pd.to_datetime(ev["signal_date"],errors="coerce").dt.strftime("%Y-%m-%d")
    ev["event_year"]=pd.to_numeric(ev["year"],errors="coerce")
    ev=ev[ev["event_year"].isin([2025,2026])].copy()
    ev=ev.drop_duplicates(["symbol","date"],keep="first")

    context_cols=[
        "symbol","date","close","prev_close","prev_volume",
        "drawdown20","bbpct20","pre_down3","body_pct","cci20",
        "lower_wick_ratio","ich_chikou_proxy",
        "next_date","next_open","next_open_ts",
        "target40_date","target40_close","ret40_next_open",
        "deep_overlay","wick_overlay",
    ]
    merged=ev.merge(daily[context_cols],on=["symbol","date"],how="left",indicator=True)
    merged["event_plus_any_long_overlay"]=merged["deep_overlay"].fillna(False)|merged["wick_overlay"].fillna(False)
    merged["date_dt"]=pd.to_datetime(merged["date"],errors="coerce")

    policies={
        "EVENT_ONLY":pd.Series(True,index=merged.index),
        "EVENT_PLUS_DEEP":merged["deep_overlay"].fillna(False),
        "EVENT_PLUS_WICK":merged["wick_overlay"].fillna(False),
        "EVENT_PLUS_ANY_LONG_OVERLAY":merged["event_plus_any_long_overlay"].fillna(False),
    }

    rows=[]
    coverage=[]
    for period,start,end in PERIODS:
        pm=(merged["date_dt"]>=pd.Timestamp(start))&(merged["date_dt"]<=pd.Timestamp(end))
        base=merged[pm].copy()
        coverage.append({
            "period":period,
            "event_rows":int(len(base)),
            "daily_context_matched":int((base["_merge"]=="both").sum()),
            "mature40":int(base["target40_close"].notna().sum()),
            "executable40":int(base["ret40_next_open"].notna().sum()),
            "deep_overlay_n":int(base["deep_overlay"].fillna(False).sum()),
            "wick_overlay_n":int(base["wick_overlay"].fillna(False).sum()),
            "any_overlay_n":int(base["event_plus_any_long_overlay"].fillna(False).sum()),
        })
        for name,mask in policies.items():
            q=merged[pm & mask].copy()
            mature=q[q["ret40_next_open"].notna()].copy()
            rows.append({"period":period,"policy":name,**metrics(mature["ret40_next_open"])})

    metrics_df=pd.DataFrame(rows)
    coverage_df=pd.DataFrame(coverage)
    metrics_df.to_csv(out/"event_long_overlay_metrics.csv",index=False)
    coverage_df.to_csv(out/"event_long_overlay_coverage.csv",index=False)

    keep=[
        "event_year","date","symbol","volr20_first_daily_rank",
        "ret1_signal_time","ret10_signal_time","volr20_signal_time",
        "tail_cdf_signal_time","tail_p_signal_time",
        "previous_session_market_median_ret5",
        "drawdown20","bbpct20","pre_down3","body_pct","cci20",
        "lower_wick_ratio","ich_chikou_proxy","deep_overlay","wick_overlay",
        "next_date","next_open","target40_date","target40_close","ret40_next_open",
        "_merge",
    ]
    merged[[k for k in keep if k in merged.columns]].to_csv(
        out/"event_long_overlay_rows.csv",index=False
    )

    meta={
        "event_source":"canonical annual_candidate_detections_2022_2026.csv",
        "event_source_blob_sha":"06bf7736cdedf16f6c50f4e4ba0d715394c31588",
        "event_spec":"monster_weak_early_volr20_low_canonical_v1",
        "2025_source_status":"saved V7 cache retrospective replay",
        "2026_source_status":"same-source reconstruction with documented runtime sensitivity",
        "consumers":[
            "EVENT_ONLY","EVENT_PLUS_DEEP","EVENT_PLUS_WICK","EVENT_PLUS_ANY_LONG_OVERLAY"
        ],
        "overlay_threshold_changes":False,
        "event_logic_reimplemented":False,
        "production_writes":False,
        "status":"RETROSPECTIVE_CONSUMER_INTEGRATION_AUDIT",
    }
    (out/"event_long_overlay_meta.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8"
    )

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nCOVERAGE")
    print(coverage_df.to_string(index=False))
    print("\nMETRICS")
    print(metrics_df.to_string(index=False))

if __name__=="__main__":
    main()
