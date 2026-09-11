#!/usr/bin/env python3
"""V19 Consensus Monster Ignition (research only).

Base: V18 Consensus Monster.
Additional pre-2025-derived ignition gate:
    volr5 >= 1.4034296170763991

Threshold source:
- median volr5 among 2023 V18 consensus signals.
Development/validation before opening later years:
- 2023 mean about +8.50%
- 2024H1 about +7.12%
- 2024H2 about +4.12%

Interpretation:
- V16 already prefers low 20-day volume ratio (not long-term exhausted).
- V19 additionally requires short-term 5-day volume expansion (fresh ignition).

No production writes. 2025/2026 are reporting only.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import v9_conditional_quality_research as v9
import v18_consensus_monster as v18

OUT=Path("tvfree_screener/out")
VOLR5_MIN=1.4034296170763991

def filter_ignition(p):
    if p.empty:return p.copy()
    return p[p["volr5"]>=VOLR5_MIN].copy().reset_index(drop=True)

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
    hist_parts=[]
    for yr in [2023,2024,2025]:
        t=hist[(hist.date>=f"{yr}-01-01")&(hist.date<=f"{yr}-12-31")].copy()
        base=v18.consensus(v18.select_v16(t,trading_dates),v18.select_v17(t,trading_dates))
        z=filter_ignition(base)
        if not z.empty:
            z["ignition_year"]=yr
            hist_parts.append(z)
    hist_ign=pd.concat(hist_parts,ignore_index=True) if hist_parts else pd.DataFrame()

    q=v9.prepare(raw)
    t26=v9.generate_tail_pool(q,"2026-01-01","2026-08-31")
    c26=v18.consensus(v18.select_v16(t26,trading_dates),v18.select_v17(t26,trading_dates))
    z26=filter_ignition(c26)

    report={
        "status":"research_only_no_production_writes",
        "component":"V19 Consensus Monster Ignition",
        "base":"V18 exact V16+V17 consensus",
        "ignition_gate":{
            "feature":"volr5",
            "minimum":VOLR5_MIN,
            "source":"2023 V18 consensus median",
        },
        "pre2025_reference":{
            "2023_mean":0.085001,
            "2024H1_mean":0.07117127462816117,
            "2024H2_mean":0.041178542862332315,
            "2024_pooled_mean":0.05717466647077436,
        },
        "historical":v18.period_stats(hist_ign,{
            "2023H1":("2023-01-01","2023-06-30"),
            "2023H2":("2023-07-01","2023-12-31"),
            "2024H1":("2024-01-01","2024-06-30"),
            "2024H2":("2024-07-01","2024-12-31"),
            "2025H1":("2025-01-01","2025-06-30"),
            "2025H2":("2025-07-01","2025-12-31"),
        }),
        "2025_pooled":v18.stats(
            hist_ign[(hist_ign.date>="2025-01-01")&(hist_ign.date<="2025-12-31")]["target5_no"]
        ) if not hist_ign.empty else {"n":0},
        "2026":v18.period_stats(z26,{
            "2026H1":("2026-01-01","2026-06-30"),
            "2026_MarAug":("2026-03-01","2026-08-31"),
            "2026_JulAug":("2026-07-01","2026-08-31"),
        }),
        "2026_JanAug":v18.stats(z26["target5_no"]),
        "2026_monthly":{str(m):v18.stats(g["target5_no"]) for m,g in z26.groupby(z26.date.dt.to_period("M"))},
        "production_writes":False,
        "warning":"2025/2026 are reporting only; do not tune V19 from these outcomes.",
    }

    OUT.mkdir(parents=True,exist_ok=True)
    hist_ign.to_csv(OUT/"v19_ignition_2023_2025.csv",index=False)
    z26.to_csv(OUT/"v19_ignition_2026.csv",index=False)
    (OUT/"v19_ignition_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
