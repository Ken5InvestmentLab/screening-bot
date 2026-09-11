#!/usr/bin/env python3
"""V20 Consensus Monster Early (research only).

Base: V18 Consensus Monster.
Pre-2025-derived maturity gate:
    ret10 <= 0.5735294117647058

Threshold source: 2023 V18 consensus median ret10.
2024 validation:
- H1 mean ~+10.81%
- H2 mean ~+3.48%
- pooled ~+7.15%

Interpretation: keep consensus Monster candidates that have not already run too
far over the prior 10 sessions.

2025/2026 reporting only. No production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import v9_conditional_quality_research as v9
import v18_consensus_monster as v18

OUT=Path("tvfree_screener/out")
RET10_MAX=0.5735294117647058

def filt(p):
    if p.empty:return p.copy()
    return p[p["ret10"]<=RET10_MAX].copy().reset_index(drop=True)

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
    parts=[]
    for yr in [2023,2024,2025]:
        t=hist[(hist.date>=f"{yr}-01-01")&(hist.date<=f"{yr}-12-31")].copy()
        base=v18.consensus(v18.select_v16(t,trading_dates),v18.select_v17(t,trading_dates))
        z=filt(base)
        if not z.empty:
            z["early_year"]=yr
            parts.append(z)
    hist_z=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()

    q=v9.prepare(raw)
    t26=v9.generate_tail_pool(q,"2026-01-01","2026-08-31")
    c26=v18.consensus(v18.select_v16(t26,trading_dates),v18.select_v17(t26,trading_dates))
    z26=filt(c26)

    report={
        "status":"research_only_no_production_writes",
        "component":"V20 Consensus Monster Early",
        "base":"V18 exact V16+V17 consensus",
        "maturity_gate":{
            "feature":"ret10",
            "maximum":RET10_MAX,
            "source":"2023 V18 consensus median",
        },
        "pre2025_reference":{
            "2023_mean":0.080347,
            "2024H1_mean":0.10809275575924432,
            "2024H2_mean":0.03484865925792852,
            "2024_pooled_mean":0.07147070750858642,
        },
        "historical":v18.period_stats(hist_z,{
            "2023H1":("2023-01-01","2023-06-30"),
            "2023H2":("2023-07-01","2023-12-31"),
            "2024H1":("2024-01-01","2024-06-30"),
            "2024H2":("2024-07-01","2024-12-31"),
            "2025H1":("2025-01-01","2025-06-30"),
            "2025H2":("2025-07-01","2025-12-31"),
        }),
        "2025_pooled":v18.stats(
            hist_z[(hist_z.date>="2025-01-01")&(hist_z.date<="2025-12-31")]["target5_no"]
        ) if not hist_z.empty else {"n":0},
        "2026":v18.period_stats(z26,{
            "2026H1":("2026-01-01","2026-06-30"),
            "2026_MarAug":("2026-03-01","2026-08-31"),
            "2026_JulAug":("2026-07-01","2026-08-31"),
        }),
        "2026_JanAug":v18.stats(z26["target5_no"]),
        "2026_monthly":{str(m):v18.stats(g["target5_no"]) for m,g in z26.groupby(z26.date.dt.to_period("M"))},
        "production_writes":False,
        "warning":"2025/2026 are reporting only; do not tune V20 from these outcomes.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    hist_z.to_csv(OUT/"v20_early_2023_2025.csv",index=False)
    z26.to_csv(OUT/"v20_early_2026.csv",index=False)
    (OUT/"v20_early_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
