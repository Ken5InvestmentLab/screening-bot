#!/usr/bin/env python3
"""V12 Pre-Exhaustion rank for causal V7 Tail candidates (TEST ONLY).

No new outcome model. Among same-day V7 extreme-Tail candidates, prefer the
candidate that is relatively less mature/overextended:
- lower 20D return,
- lower close-vs-20D-MA gap,
- lower 20D volume ratio.

The three within-day percentile ranks are averaged; lower is better.

Two fixed diagnostic lanes:
- PREX3_ALL: use every Tail day.
- PREX3_MED5_NONPOS: use only days where cross-sectional median 5D return <= 0.

2024 is development, 2025 is reporting/validation. 2026 is intentionally not
opened in this runner. No production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

PERIODS = {
    "2024H1": ("2024-01-01","2024-06-30"),
    "2024H2": ("2024-07-01","2024-12-31"),
    "2025H1": ("2025-01-01","2025-06-30"),
    "2025H2": ("2025-07-01","2025-12-31"),
}

def stats(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    if x.empty:return {"n":0}
    return {
        "n":int(len(x)),"mean":float(x.mean()),"median":float(x.median()),
        "win_rate":float((x>0).mean()),"hit10_rate":float((x>=.10).mean()),
        "hit20_rate":float((x>=.20).mean()),"hit50_rate":float((x>=.50).mean()),
        "hit100_rate":float((x>=1).mean()),"loss10_rate":float((x<=-.10).mean()),
        "max":float(x.max()),"min":float(x.min()),
    }

def select(cache, market_gate):
    z=cache.copy()
    if market_gate:
        z=z[z["med_ret5"]<=0].copy()
    if z.empty:return z
    for c in ["ret20","ma20_gap","volr20"]:
        z[f"rank_{c}"]=z.groupby("date")[c].rank(
            pct=True,method="average",ascending=True
        )
    z["preexhaust_rank"]=z[
        ["rank_ret20","rank_ma20_gap","rank_volr20"]
    ].mean(axis=1)
    return (
        z.sort_values(
            ["date","preexhaust_rank","tail_cdf","tail_p"],
            ascending=[True,True,False,False],
        )
        .groupby("date",as_index=False)
        .head(1)
        .reset_index(drop=True)
    )

def pstats(p):
    return {
        name:stats(p[(p.date>=a)&(p.date<=b)]["target5_no"])
        for name,(a,b) in PERIODS.items()
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tail-cache",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    q=pd.read_csv(a.tail_cache,parse_dates=["date","target_end_date"],dtype={"symbol":str})
    variants={}
    for name,gate in [("PREX3_ALL",False),("PREX3_MED5_NONPOS",True)]:
        picks=select(q,gate)
        periods=pstats(picks)
        pooled_2024=stats(picks[(picks.date>="2024-01-01")&(picks.date<="2024-12-31")].target5_no)
        pooled_2025=stats(picks[(picks.date>="2025-01-01")&(picks.date<="2025-12-31")].target5_no)
        variants[name]={
            "market_gate":"med_ret5 <= 0" if gate else None,
            "periods":periods,
            "pooled_2024":pooled_2024,
            "pooled_2025":pooled_2025,
        }
        picks.to_csv(out/f"v12_{name.lower()}_picks.csv",index=False)
    report={
        "status":"research_only_no_production_writes",
        "component":"V7 extreme Tail + within-day Pre-Exhaustion relative rank",
        "rank_features":["ret20","ma20_gap","volr20"],
        "rank_direction":"lower within-day percentile is preferred",
        "protocol":"2024 development; 2025 reporting/validation; 2026 unopened",
        "warning":"2025 has been inspected in prior research and is not a pristine holdout.",
        "variants":variants,
    }
    (out/"v12_preexhaust_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
