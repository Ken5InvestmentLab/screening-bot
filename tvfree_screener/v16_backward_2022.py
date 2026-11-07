#!/usr/bin/env python3
"""V16 backward holdout report on 2022 data (TEST ONLY).

The V16 selection rule is unchanged:
- V7 extreme Tail candidates
- market gate med_ret5 <= 0
- same-day candidate with the lowest volr20
- Tail score only as tie-break
- one-business-day same-symbol cooldown

This runner does not modify the rule. It only reports the months in 2022 where
the causal V7 monthly Tail model has enough prior data to emit candidates.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import v9_conditional_quality_research as v9
import v16_pre2025_volr20_rank as v16

OUT = Path("tvfree_screener/out")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    a = ap.parse_args()

    raw = pd.read_csv(a.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open","high","low","close","volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)

    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()
    q = v9.prepare(raw)
    tail = v9.generate_tail_pool(q, "2022-01-01", "2022-12-31")
    picks = v16.select(tail, trading_dates)

    monthly = {
        str(m): v16.stats(g["target5_no"])
        for m,g in picks.groupby(picks.date.dt.to_period("M"))
    }
    h1 = picks[(picks.date >= "2022-01-01") & (picks.date <= "2022-06-30")]
    h2 = picks[(picks.date >= "2022-07-01") & (picks.date <= "2022-12-31")]

    report = {
        "status":"research_only_no_production_writes",
        "component":"V16 backward 2022 reporting",
        "rule_changed":False,
        "rule":{
            "tail_gate":0.999,
            "market_gate":"med_ret5 <= 0",
            "rank_feature":"volr20 low",
        },
        "tail_candidates_2022":int(len(tail)),
        "first_tail_date":str(tail.date.min().date()) if len(tail) else None,
        "selected_2022":v16.stats(picks["target5_no"]),
        "selected_2022H1":v16.stats(h1["target5_no"]),
        "selected_2022H2":v16.stats(h2["target5_no"]),
        "monthly_2022":monthly,
        "production_writes":False,
        "warning":"Backward holdout only; V16 was designed later using 2023-2024.",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    picks.to_csv(OUT/"v16_backward_2022_picks.csv", index=False)
    (OUT/"v16_backward_2022_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
