#!/usr/bin/env python3
"""V18 five-period single-feature rank audit (TEST ONLY).

Uses only pre-2025 outcomes:
- 2022H2 (where V7 has enough warmup to emit candidates)
- 2023H1
- 2023H2
- 2024H1
- 2024H2

For each existing signal-time feature, test both same-day LOW-rank and HIGH-rank
selection under the fixed market gate med_ret5 <= 0. Tail score is tie-break only.

No 2025/2026 data is read for feature selection.
No production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

import run as base
import v9_conditional_quality_research as v9

OUT = Path("tvfree_screener/out")
PERIODS = {
    "2022H2":("2022-07-01","2022-12-31"),
    "2023H1":("2023-01-01","2023-06-30"),
    "2023H2":("2023-07-01","2023-12-31"),
    "2024H1":("2024-01-01","2024-06-30"),
    "2024H2":("2024-07-01","2024-12-31"),
}

def stats(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    if x.empty:return {"n":0}
    y=x.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(x)),
        "mean":float(x.mean()),
        "hit20":float((x>=.20).mean()),
        "hit50":float((x>=.50).mean()),
        "loss10":float((x<=-.10).mean()),
        "top1_removed_mean":float(y.iloc[1:].mean()) if len(y)>1 else None,
    }

def select(tail,trading_dates,feature,ascending):
    z=tail[tail["med_ret5"]<=0].copy()
    z=z[pd.to_numeric(z[feature],errors="coerce").notna()].copy()
    if z.empty:return z
    z=z.sort_values(
        ["date",feature,"tail_cdf","tail_p"],
        ascending=[True,ascending,False,False],
    )
    top=z.groupby("date",sort=True,as_index=False).head(4)
    date_idx={pd.Timestamp(d):i for i,d in enumerate(trading_dates)}
    rows=[];last_symbol=None;last_idx=None
    for date,day in top.groupby("date",sort=True):
        idx=date_idx.get(pd.Timestamp(date))
        if idx is None:continue
        chosen=None
        for _,row in day.iterrows():
            if (
                last_idx is not None and idx==last_idx+1
                and str(row["symbol"])==last_symbol
            ):
                continue
            chosen=row;break
        if chosen is not None:
            rows.append(chosen)
            last_symbol=str(chosen["symbol"]);last_idx=idx
    return pd.DataFrame(rows).reset_index(drop=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",required=True)
    ap.add_argument("--tail-cache",required=True)
    a=ap.parse_args()

    raw=pd.read_csv(a.cache,parse_dates=["date"],dtype={"symbol":str})
    for c in ["open","high","low","close","volume"]:
        raw[c]=pd.to_numeric(raw[c],errors="coerce")
    raw=raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates=pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    hist=pd.read_csv(
        a.tail_cache,parse_dates=["date","target_end_date"],dtype={"symbol":str}
    )
    hist=hist[(hist.date>="2023-01-01")&(hist.date<="2024-12-31")].copy()

    q=v9.prepare(raw)
    tail22=v9.generate_tail_pool(q,"2022-01-01","2022-12-31")
    tail=pd.concat([tail22,hist],ignore_index=True,sort=False)

    rows=[]
    for feature in base.FEATURES:
        if feature not in tail.columns:
            continue
        for direction,ascending in [("LOW",True),("HIGH",False)]:
            picks=select(tail,trading_dates,feature,ascending)
            per={}
            valid=True
            for name,(s,e) in PERIODS.items():
                st=stats(picks[(picks.date>=s)&(picks.date<=e)]["target5_no"])
                per[name]=st
                if st["n"]<10:
                    valid=False
            pooled=stats(
                picks[(picks.date>="2022-07-01")&(picks.date<="2024-12-31")]["target5_no"]
            )
            means=[per[n]["mean"] for n in PERIODS if per[n]["n"]]
            all_positive=valid and all(x>0 for x in means)
            row={
                "feature":feature,"direction":direction,
                "all_five_positive":bool(all_positive),
                "min_period_mean":float(min(means)) if means else None,
                "pooled_n":pooled["n"],"pooled_mean":pooled["mean"],
                "pooled_hit20":pooled["hit20"],"pooled_hit50":pooled["hit50"],
                "pooled_loss10":pooled["loss10"],
                "pooled_top1_removed_mean":pooled["top1_removed_mean"],
            }
            for name,st in per.items():
                row[f"{name}_n"]=st["n"]
                row[f"{name}_mean"]=st["mean"]
                row[f"{name}_loss10"]=st["loss10"]
            rows.append(row)

    result=pd.DataFrame(rows)
    result=result.sort_values(
        ["all_five_positive","min_period_mean","pooled_mean"],
        ascending=[False,False,False],
    )
    OUT.mkdir(parents=True,exist_ok=True)
    result.to_csv(OUT/"v18_five_period_feature_audit.csv",index=False)

    eligible=result[result.all_five_positive].copy()
    report={
        "status":"research_only_no_production_writes",
        "component":"V18 pre-2025 five-period single-feature rank audit",
        "periods":list(PERIODS.keys()),
        "market_gate":"med_ret5 <= 0",
        "features_tested":int(result.feature.nunique()),
        "directions_per_feature":2,
        "all_five_positive_count":int(len(eligible)),
        "top_candidates":eligible.head(12).to_dict(orient="records"),
        "selection_data_ends":"2024-12-31",
        "production_writes":False,
    }
    (OUT/"v18_five_period_feature_audit.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
