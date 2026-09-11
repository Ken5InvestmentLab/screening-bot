#!/usr/bin/env python3
"""V17 pre-2025 stable Tail rank + 2023-derived extreme-range veto.

Selection logic:
- V7 extreme Tail candidates (cdf >= 0.999)
- market gate: med_ret5 <= 0
- same-day rank: average of lower volr20 and lower ret1 percentiles
- select one candidate/day with one-business-day same-symbol cooldown
- AFTER selection, suppress notification if range_pct > 0.3040129098415149

The range threshold is the 90th percentile of selected V14 candidates in 2023.
It was then checked on 2024 only before this 2025/2026 reporting runner:
- 2024H1 mean improved from ~+5.29% to ~+6.30%
- 2024H2 mean improved from ~+1.56% to ~+1.93%

No production writes. 2025/2026 are reporting only.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import v9_conditional_quality_research as v9

OUT=Path("tvfree_screener/out")
RANGE_MAX=0.3040129098415149

def stats(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    if x.empty:return {"n":0}
    y=x.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(x)),"mean":float(x.mean()),"median":float(x.median()),
        "win_rate":float((x>0).mean()),"hit10_rate":float((x>=.10).mean()),
        "hit20_rate":float((x>=.20).mean()),"hit50_rate":float((x>=.50).mean()),
        "hit100_rate":float((x>=1).mean()),"loss10_rate":float((x<=-.10).mean()),
        "loss20_rate":float((x<=-.20).mean()),"max":float(x.max()),"min":float(x.min()),
        "top1_removed_mean":float(y.iloc[1:].mean()) if len(y)>1 else None,
        "top3_removed_mean":float(y.iloc[3:].mean()) if len(y)>3 else None,
    }

def select_v14(tail,trading_dates):
    z=tail[tail["med_ret5"]<=0].copy()
    if z.empty:return z
    for c in ["volr20","ret1"]:
        z[f"rank_{c}"]=z.groupby("date")[c].rank(pct=True,method="average",ascending=True)
    z["stable_rank"]=z[["rank_volr20","rank_ret1"]].mean(axis=1)
    z=z.sort_values(["date","stable_rank","tail_cdf","tail_p"],ascending=[True,True,False,False])
    top=z.groupby("date",sort=True,as_index=False).head(4)
    date_idx={pd.Timestamp(d):i for i,d in enumerate(trading_dates)}
    rows=[];last_symbol=None;last_idx=None
    for date,day in top.groupby("date",sort=True):
        idx=date_idx.get(pd.Timestamp(date))
        if idx is None:continue
        chosen=None
        for _,row in day.iterrows():
            if last_idx is not None and idx==last_idx+1 and str(row["symbol"])==last_symbol:
                continue
            chosen=row;break
        if chosen is not None:
            rows.append(chosen);last_symbol=str(chosen["symbol"]);last_idx=idx
    return pd.DataFrame(rows).reset_index(drop=True)

def apply_veto(p):
    if p.empty:return p.copy()
    return p[p["range_pct"]<=RANGE_MAX].copy().reset_index(drop=True)

def pstats(p,periods):
    return {n:stats(p[(p.date>=a)&(p.date<=b)]["target5_no"]) for n,(a,b) in periods.items()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",required=True)
    ap.add_argument("--tail-cache",required=True)
    a=ap.parse_args()

    raw=pd.read_csv(a.cache,parse_dates=["date"],dtype={"symbol":str})
    for c in ["open","high","low","close","volume"]:
        raw[c]=pd.to_numeric(raw[c],errors="coerce")
    raw=raw.dropna(subset=["date","symbol","open","high","low","close","volume"]).sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates=pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    hist=pd.read_csv(a.tail_cache,parse_dates=["date","target_end_date"],dtype={"symbol":str})
    t25=hist[(hist.date>="2025-01-01")&(hist.date<="2025-12-31")].copy()
    p25_base=select_v14(t25,trading_dates)
    p25=apply_veto(p25_base)

    q=v9.prepare(raw)
    t26=v9.generate_tail_pool(q,"2026-01-01","2026-08-31")
    p26_base=select_v14(t26,trading_dates)
    p26=apply_veto(p26_base)

    report={
        "status":"research_only_no_production_writes",
        "component":"V17 V14 stable rank + pre-2025 extreme-range veto",
        "range_veto":{
            "feature":"range_pct",
            "threshold":RANGE_MAX,
            "source":"2023 selected V14 candidates q90",
            "action":"suppress selected notification; do not substitute second candidate",
        },
        "pre2025_validation":{
            "2024H1_mean_after_veto":0.06304782989415174,
            "2024H2_mean_after_veto":0.019321379736267956,
        },
        "2025":pstats(p25,{
            "2025H1":("2025-01-01","2025-06-30"),
            "2025H2":("2025-07-01","2025-12-31"),
        }),
        "2025_pooled":stats(p25["target5_no"]),
        "2025_suppressed":int(len(p25_base)-len(p25)),
        "2026":pstats(p26,{
            "2026H1":("2026-01-01","2026-06-30"),
            "2026_JulAug":("2026-07-01","2026-08-31"),
            "2026_MarAug":("2026-03-01","2026-08-31"),
        }),
        "2026_JanAug":stats(p26["target5_no"]),
        "2026_suppressed":int(len(p26_base)-len(p26)),
        "2026_monthly":{str(m):stats(g["target5_no"]) for m,g in p26.groupby(p26.date.dt.to_period("M"))},
        "production_writes":False,
        "warning":"2025/2026 are reporting only; do not tune V17 from these results.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    p25.to_csv(OUT/"v17_rangeveto_2025_picks.csv",index=False)
    p26.to_csv(OUT/"v17_rangeveto_2026_picks.csv",index=False)
    (OUT/"v17_rangeveto_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
