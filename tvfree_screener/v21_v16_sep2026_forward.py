#!/usr/bin/env python3
"""V21 frozen V16 September 2026 forward-style report (TEST ONLY).

V16 rule is unchanged:
- V7 extreme Tail
- med_ret5 <= 0
- choose lowest volr20 among same-day Tail candidates
- Tail score tie-break
- one-business-day same-symbol cooldown

Runs on September 2026 data available in the frozen dataset. Only picks whose
5BD target has matured by the dataset end are included in performance metrics.
No tuning and no production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

import v9_conditional_quality_research as v9
import v16_pre2025_volr20_rank as v16

OUT=Path("tvfree_screener/out")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",required=True)
    a=ap.parse_args()

    raw=pd.read_csv(a.cache,parse_dates=["date"],dtype={"symbol":str})
    for c in ["open","high","low","close","volume"]:
        raw[c]=pd.to_numeric(raw[c],errors="coerce")
    raw=raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)

    trading_dates=pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()
    q=v9.prepare(raw)
    tail=v9.generate_tail_pool(q,"2026-09-01","2026-09-11")
    picks=v16.select(tail,trading_dates)

    matured=picks[picks["target5_no"].notna()].copy()
    immature=picks[picks["target5_no"].isna()].copy()

    report={
        "status":"research_only_no_production_writes",
        "component":"V21 frozen V16 September 2026 forward-style report",
        "rule_changed":False,
        "rule":{
            "tail_gate":0.999,
            "market_gate":"med_ret5 <= 0",
            "rank_feature":"volr20 low",
        },
        "dataset_end":str(raw.date.max().date()),
        "tail_candidates_sep":int(len(tail)),
        "selected_sep":int(len(picks)),
        "matured_selected":int(len(matured)),
        "immature_selected":int(len(immature)),
        "matured_stats":v16.stats(matured["target5_no"]),
        "matured_dates":[str(x.date()) for x in matured["date"].tolist()],
        "immature_dates":[str(x.date()) for x in immature["date"].tolist()],
        "production_writes":False,
        "warning":"Forward-style reporting only; do not tune V16 from this tiny September sample.",
    }

    OUT.mkdir(parents=True,exist_ok=True)
    picks.to_csv(OUT/"v21_v16_sep2026_picks.csv",index=False)
    (OUT/"v21_v16_sep2026_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
