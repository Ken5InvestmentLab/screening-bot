#!/usr/bin/env python3
"""V18 Consensus Monster (research only).

Consensus = V16 and V17 independently select the exact same symbol on the
same date.

V16:
- V7 extreme Tail candidates
- med_ret5 <= 0
- choose lowest volr20 same-day candidate
- one-business-day same-symbol cooldown

V17:
- V7 extreme Tail candidates
- med_ret5 <= 0
- choose lowest average within-day rank of volr20 and ret1
- one-business-day same-symbol cooldown
- suppress selected candidate when range_pct > 0.3040129098415149

No fitted weights, no outcome model, no production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import v9_conditional_quality_research as v9

OUT=Path("tvfree_screener/out")
RMAX=0.3040129098415149

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

def cooldown_pick(z,trading_dates,sort_cols,ascending):
    z=z.sort_values(["date"]+sort_cols,ascending=[True]+ascending)
    top=z.groupby("date",sort=True,as_index=False).head(4)
    date_idx={pd.Timestamp(d):i for i,d in enumerate(trading_dates)}
    rows=[];ls=None;li=None
    for date,day in top.groupby("date",sort=True):
        idx=date_idx.get(pd.Timestamp(date))
        if idx is None:continue
        chosen=None
        for _,row in day.iterrows():
            if li is not None and idx==li+1 and str(row["symbol"])==ls:
                continue
            chosen=row;break
        if chosen is not None:
            rows.append(chosen);ls=str(chosen["symbol"]);li=idx
    return pd.DataFrame(rows).reset_index(drop=True)

def select_v16(tail,trading_dates):
    z=tail[tail["med_ret5"]<=0].copy()
    if z.empty:return z
    return cooldown_pick(
        z,trading_dates,
        ["volr20","tail_cdf","tail_p"],
        [True,False,False],
    )

def select_v17(tail,trading_dates):
    z=tail[tail["med_ret5"]<=0].copy()
    if z.empty:return z
    for c in ["volr20","ret1"]:
        z[f"rank_{c}"]=z.groupby("date")[c].rank(pct=True,method="average",ascending=True)
    z["stable_rank"]=z[["rank_volr20","rank_ret1"]].mean(axis=1)
    p=cooldown_pick(
        z,trading_dates,
        ["stable_rank","tail_cdf","tail_p"],
        [True,False,False],
    )
    return p[p["range_pct"]<=RMAX].copy().reset_index(drop=True)

def consensus(a,b):
    if a.empty or b.empty:return pd.DataFrame()
    keys=b[["date","symbol"]].drop_duplicates()
    return a.merge(keys,on=["date","symbol"],how="inner")

def period_stats(p, periods):
    return {
        n:stats(p[(p.date>=a)&(p.date<=b)]["target5_no"])
        for n,(a,b) in periods.items()
    }

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

    historical=[]
    for yr in [2023,2024,2025]:
        t=hist[(hist.date>=f"{yr}-01-01")&(hist.date<=f"{yr}-12-31")].copy()
        c=consensus(select_v16(t,trading_dates),select_v17(t,trading_dates))
        if not c.empty:
            c["consensus_year"]=yr
            historical.append(c)
    hist_cons=pd.concat(historical,ignore_index=True) if historical else pd.DataFrame()

    q=v9.prepare(raw)
    t26=v9.generate_tail_pool(q,"2026-01-01","2026-08-31")
    c26=consensus(select_v16(t26,trading_dates),select_v17(t26,trading_dates))

    report={
        "status":"research_only_no_production_writes",
        "component":"V18 Consensus Monster",
        "definition":"exact same date+symbol selected independently by V16 and V17",
        "production_writes":False,
        "historical":period_stats(hist_cons,{
            "2023H1":("2023-01-01","2023-06-30"),
            "2023H2":("2023-07-01","2023-12-31"),
            "2024H1":("2024-01-01","2024-06-30"),
            "2024H2":("2024-07-01","2024-12-31"),
            "2025H1":("2025-01-01","2025-06-30"),
            "2025H2":("2025-07-01","2025-12-31"),
        }),
        "historical_pooled_2023_2025":stats(hist_cons["target5_no"]) if not hist_cons.empty else {"n":0},
        "2026":period_stats(c26,{
            "2026H1":("2026-01-01","2026-06-30"),
            "2026_MarAug":("2026-03-01","2026-08-31"),
            "2026_JulAug":("2026-07-01","2026-08-31"),
        }),
        "2026_JanAug":stats(c26["target5_no"]),
        "2026_monthly":{str(m):stats(g["target5_no"]) for m,g in c26.groupby(c26.date.dt.to_period("M"))},
        "warning":"Research-only. Do not tune V18 from 2026 outcomes.",
    }

    OUT.mkdir(parents=True,exist_ok=True)
    hist_cons.to_csv(OUT/"v18_consensus_2023_2025.csv",index=False)
    c26.to_csv(OUT/"v18_consensus_2026.csv",index=False)
    (OUT/"v18_consensus_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
