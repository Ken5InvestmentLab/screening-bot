#!/usr/bin/env python3
"""V18 Watch/Prime consensus lane (TEST ONLY).

Frozen definitions:
- Monster Watch = V16:
  V7 extreme Tail -> med_ret5 <= 0 -> lowest same-day volr20
- Monster Prime = exact same date+symbol selected independently by V14 and V16:
  V14 ranks same-day Tail candidates by low volr20 + low ret1,
  V16 ranks by low volr20 only.

No extra numeric threshold is introduced for Prime. Prime simply means two
independently derived pre-2025 rankings agree on the same candidate.

2023-2024 are historical reference; 2025/2026 are reporting only.
No production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

import v9_conditional_quality_research as v9
import v14_pre2025_stable_rank as v14
import v16_pre2025_volr20_rank as v16

OUT = Path("tvfree_screener/out")

def stats(s):
    return v16.stats(s)

def period_stats(df, periods):
    return {
        name: stats(df[(df.date >= a) & (df.date <= b)]["target5_no"])
        for name,(a,b) in periods.items()
    }

def consensus_prime(p14: pd.DataFrame, p16: pd.DataFrame) -> pd.DataFrame:
    if p14.empty or p16.empty:
        return p16.iloc[0:0].copy()
    keys = p14[["date","symbol"]].drop_duplicates()
    return (
        p16.merge(keys, on=["date","symbol"], how="inner")
        .sort_values("date")
        .reset_index(drop=True)
    )

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily",required=True)
    ap.add_argument("--tail-cache",required=True)
    a=ap.parse_args()

    raw=pd.read_csv(a.daily,parse_dates=["date"],dtype={"symbol":str})
    for c in ["open","high","low","close","volume"]:
        raw[c]=pd.to_numeric(raw[c],errors="coerce")
    raw=raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates=pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    hist=pd.read_csv(
        a.tail_cache,
        parse_dates=["date","target_end_date"],
        dtype={"symbol":str},
    )

    # Historical/reference selections from cached causal Tail candidates.
    ref=hist[(hist.date>="2023-01-01")&(hist.date<="2024-12-31")].copy()
    t25=hist[(hist.date>="2025-01-01")&(hist.date<="2025-12-31")].copy()

    watch_ref=v16.select(ref,trading_dates)
    prime_ref=consensus_prime(v14.select(ref,trading_dates),watch_ref)

    watch25=v16.select(t25,trading_dates)
    prime25=consensus_prime(v14.select(t25,trading_dates),watch25)

    q=v9.prepare(raw)
    t26=v9.generate_tail_pool(q,"2026-01-01","2026-08-31")
    watch26=v16.select(t26,trading_dates)
    prime26=consensus_prime(v14.select(t26,trading_dates),watch26)

    ref_periods={
        "2023H1":("2023-01-01","2023-06-30"),
        "2023H2":("2023-07-01","2023-12-31"),
        "2024H1":("2024-01-01","2024-06-30"),
        "2024H2":("2024-07-01","2024-12-31"),
    }
    p25={
        "2025H1":("2025-01-01","2025-06-30"),
        "2025H2":("2025-07-01","2025-12-31"),
    }
    p26={
        "2026H1":("2026-01-01","2026-06-30"),
        "2026_JulAug":("2026-07-01","2026-08-31"),
        "2026_MarAug":("2026-03-01","2026-08-31"),
    }

    report={
        "status":"research_only_no_production_writes",
        "component":"V18 consensus Watch/Prime",
        "definitions":{
            "Watch":"V16 = V7 Tail + med_ret5<=0 + lowest same-day volr20",
            "Prime":"V14 and V16 select the exact same date+symbol",
        },
        "prime_extra_numeric_threshold":None,
        "reference_2023_2024":{
            "Watch_periods":period_stats(watch_ref,ref_periods),
            "Watch_pooled":stats(watch_ref["target5_no"]),
            "Prime_periods":period_stats(prime_ref,ref_periods),
            "Prime_pooled":stats(prime_ref["target5_no"]),
        },
        "2025":{
            "Watch_periods":period_stats(watch25,p25),
            "Watch_pooled":stats(watch25["target5_no"]),
            "Prime_periods":period_stats(prime25,p25),
            "Prime_pooled":stats(prime25["target5_no"]),
        },
        "2026":{
            "Watch_periods":period_stats(watch26,p26),
            "Watch_JanAug":stats(watch26["target5_no"]),
            "Prime_periods":period_stats(prime26,p26),
            "Prime_JanAug":stats(prime26["target5_no"]),
        },
        "production_writes":False,
        "warning":"Prime is a consensus confidence tier, not a separately optimized return model.",
    }

    OUT.mkdir(parents=True,exist_ok=True)
    watch25.to_csv(OUT/"v18_watch_2025.csv",index=False)
    prime25.to_csv(OUT/"v18_prime_2025.csv",index=False)
    watch26.to_csv(OUT/"v18_watch_2026.csv",index=False)
    prime26.to_csv(OUT/"v18_prime_2026.csv",index=False)
    (OUT/"v18_consensus_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
