#!/usr/bin/env python3
"""V20 consensus Prime audit using only pre-2025 data (TEST ONLY).

Base Watch:
- V7 extreme Tail
- med_ret5 <= 0
- select lowest volr20

Prime hypotheses use only the second five-period-stable feature, ret1:
- PRIME_HALF: candidate must be in lower half of same-day ret1 ranks.
- PRIME_TOP: candidate must share the minimum ret1 rank for that day.

Both require at least two same-day Tail candidates, so Prime means independent
same-day confirmation rather than a single unopposed candidate.

Selection/evaluation uses only 2022H2, 2023H1/H2, 2024H1/H2.
No 2025/2026 data is read. No production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import numpy as np

import v9_conditional_quality_research as v9
import v16_pre2025_volr20_rank as v16

OUT=Path("tvfree_screener/out")
PERIODS={
    "2022H2":("2022-07-01","2022-12-31"),
    "2023H1":("2023-01-01","2023-06-30"),
    "2023H2":("2023-07-01","2023-12-31"),
    "2024H1":("2024-01-01","2024-06-30"),
    "2024H2":("2024-07-01","2024-12-31"),
}

def select_variant(tail,trading_dates,mode):
    z=tail[tail["med_ret5"]<=0].copy()
    if z.empty:return z
    z["cand_count"]=z.groupby("date")["symbol"].transform("size")
    z["ret1_rank_pct"]=z.groupby("date")["ret1"].rank(
        pct=True,method="min",ascending=True
    )
    z["ret1_rank_min"]=z.groupby("date")["ret1"].rank(
        method="min",ascending=True
    )

    if mode=="PRIME_HALF":
        z=z[(z.cand_count>=2)&(z.ret1_rank_pct<=0.50)].copy()
    elif mode=="PRIME_TOP":
        z=z[(z.cand_count>=2)&(z.ret1_rank_min==1)].copy()
    elif mode!="WATCH":
        raise ValueError(mode)

    z=z.sort_values(
        ["date","volr20","tail_cdf","tail_p"],
        ascending=[True,True,False,False],
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

    report={
        "status":"research_only_no_production_writes",
        "component":"V20 pre-2025 consensus Prime audit",
        "selection_data_ends":"2024-12-31",
        "market_gate":"med_ret5 <= 0",
        "base_rank":"volr20 low",
        "confirmation_feature":"ret1 low",
        "variants":{},
        "production_writes":False,
    }

    for mode in ["WATCH","PRIME_HALF","PRIME_TOP"]:
        picks=select_variant(tail,trading_dates,mode)
        per={}
        for name,(s,e) in PERIODS.items():
            per[name]=v16.stats(
                picks[(picks.date>=s)&(picks.date<=e)]["target5_no"]
            )
        pooled=v16.stats(
            picks[(picks.date>="2022-07-01")&(picks.date<="2024-12-31")]["target5_no"]
        )
        report["variants"][mode]={
            "periods":per,
            "pooled":pooled,
            "all_five_positive":all(
                per[n].get("n",0)>=5 and per[n].get("mean",-999)>0
                for n in PERIODS
            ),
        }

    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"v20_consensus_prime_audit.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
