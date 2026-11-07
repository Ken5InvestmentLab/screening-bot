#!/usr/bin/env python3
"""V22 fixed V16 holding-horizon audit (TEST ONLY).

Selection rule is V16 and remains unchanged. This script only asks whether
the same selected Monster candidates are better evaluated/held to 5, 10, 20,
or 40 business-day closes, always entering at next-session open.

No horizon is used to alter candidate selection.
No production writes.
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
    "2023":("2023-01-01","2023-12-31"),
    "2024":("2024-01-01","2024-12-31"),
    "2025":("2025-01-01","2025-12-31"),
    "2026JanAug":("2026-01-01","2026-08-31"),
    "ALL":("2022-07-01","2026-08-31"),
}

def stats(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    if x.empty:return {"n":0}
    y=x.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(x)),
        "mean":float(x.mean()),
        "median":float(x.median()),
        "win_rate":float((x>0).mean()),
        "hit20_rate":float((x>=.20).mean()),
        "hit50_rate":float((x>=.50).mean()),
        "loss10_rate":float((x<=-.10).mean()),
        "max":float(x.max()),
        "min":float(x.min()),
        "top1_removed_mean":float(y.iloc[1:].mean()) if len(y)>1 else None,
    }

def add_horizons(raw,picks):
    groups={s:g.reset_index(drop=True) for s,g in raw.groupby("symbol",sort=False)}
    rows=[]
    for _,r in picks.iterrows():
        sym=str(r["symbol"]); dt=pd.Timestamp(r["date"]); g=groups.get(sym)
        if g is None:continue
        ix=g.index[g["date"]==dt]
        if len(ix)==0:continue
        i=int(ix[0]); rec={"date":dt,"symbol":sym}
        if i+1>=len(g):continue
        entry=float(g.loc[i+1,"open"]); rec["entry_open"]=entry;rec["entry_date"]=g.loc[i+1,"date"]
        for h in [5,10,20,40]:
            if i+h<len(g):
                rec[f"ret{h}"]=float(g.loc[i+h,"close"])/entry-1 if entry else np.nan
                rec[f"end{h}"]=g.loc[i+h,"date"]
            else:
                rec[f"ret{h}"]=np.nan
        rows.append(rec)
    return pd.DataFrame(rows)

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
    trading_dates=pd.Index(pd.to_datetime(raw.date.unique())).sort_values()

    hist=pd.read_csv(a.tail_cache,parse_dates=["date","target_end_date"],dtype={"symbol":str})
    p_hist=v16.select(
        hist[(hist.date>="2023-01-01")&(hist.date<="2025-12-31")],
        trading_dates,
    )

    q=v9.prepare(raw)
    t22=v9.generate_tail_pool(q,"2022-01-01","2022-12-31")
    t26=v9.generate_tail_pool(q,"2026-01-01","2026-08-31")
    p22=v16.select(t22,trading_dates)
    p26=v16.select(t26,trading_dates)

    picks=pd.concat([p22,p_hist,p26],ignore_index=True,sort=False)
    picks=picks.sort_values(["date","symbol"]).drop_duplicates(["date","symbol"])
    hz=add_horizons(raw,picks)

    rows=[]
    for pname,(s,e) in PERIODS.items():
        z=hz[(hz.date>=s)&(hz.date<=e)]
        for h in [5,10,20,40]:
            rows.append({"period":pname,"horizon_bd":h,**stats(z[f"ret{h}"])})
    table=pd.DataFrame(rows)

    report={
        "status":"research_only_no_production_writes",
        "component":"V22 fixed V16 holding-horizon audit",
        "selection_rule_changed":False,
        "entry":"next-session open",
        "exit_horizons_bd":[5,10,20,40],
        "selected_rows":int(len(picks)),
        "results":table.to_dict(orient="records"),
        "production_writes":False,
    }
    OUT.mkdir(parents=True,exist_ok=True)
    table.to_csv(OUT/"v22_v16_horizon_audit.csv",index=False)
    (OUT/"v22_v16_horizon_audit.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
