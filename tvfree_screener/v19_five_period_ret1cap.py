#!/usr/bin/env python3
"""V19 five-period-stable ret1-capped V7 Tail lane (TEST ONLY).

Selection uses only pre-2025 evidence:
- backward 2022H2,
- 2023H1,
- 2023H2,
- 2024H1,
- 2024H2.

Frozen rule:
- V7 extreme Tail candidates (cdf >= 0.999)
- market gate: med_ret5 <= 0
- among same-day Tail candidates choose the lowest volr20
- emit only if selected candidate ret1 <= +20%
- Tail score only as tie-break
- one-business-day same-symbol cooldown

The +20% ret1 cap is a simple overextension veto. It was chosen because, among
the predeclared simple post-selection vetoes, it kept all five pre-2025 periods
positive with the strongest minimum-period mean while reducing pooled loss10
versus ungated V16.

2025/2026 are reporting only. No production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import v9_conditional_quality_research as v9
import v16_pre2025_volr20_rank as v16

OUT = Path("tvfree_screener/out")

def select(tail: pd.DataFrame, trading_dates: pd.Index) -> pd.DataFrame:
    picks = v16.select(tail, trading_dates)
    if picks.empty:
        return picks
    return picks[picks["ret1"] <= 0.20].copy().reset_index(drop=True)

def pstats(p, periods):
    return {
        n: v16.stats(p[(p.date >= a) & (p.date <= b)]["target5_no"])
        for n,(a,b) in periods.items()
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--tail-cache", required=True)
    a = ap.parse_args()

    raw = pd.read_csv(a.cache, parse_dates=["date"], dtype={"symbol":str})
    for c in ["open","high","low","close","volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    hist = pd.read_csv(
        a.tail_cache,
        parse_dates=["date","target_end_date"],
        dtype={"symbol":str},
    )
    t25 = hist[(hist.date >= "2025-01-01") & (hist.date <= "2025-12-31")].copy()
    p25 = select(t25, trading_dates)

    q = v9.prepare(raw)
    t26 = v9.generate_tail_pool(q, "2026-01-01", "2026-08-31")
    p26 = select(t26, trading_dates)

    report = {
        "status":"research_only_no_production_writes",
        "component":"V19 five-period-stable ret1-capped V7 Tail lane",
        "selection_source":"2022H2 + 2023H1/H2 + 2024H1/H2 only",
        "market_gate":"med_ret5 <= 0",
        "rank_feature":"volr20 low",
        "post_selection_veto":"ret1 <= 0.20",
        "pre2025_reference":{
            "2022H2_mean":0.02551621052322065,
            "2023H1_mean":0.049939,
            "2023H2_mean":0.019562,
            "2024H1_mean":0.038334,
            "2024H2_mean":0.044047,
            "2022H2_2024_pooled_mean":0.036194,
            "2022H2_2024_pooled_loss10":0.311765,
            "2022H2_2024_pooled_hit20":0.170588,
        },
        "2025":pstats(p25,{
            "2025H1":("2025-01-01","2025-06-30"),
            "2025H2":("2025-07-01","2025-12-31"),
        }),
        "2025_pooled":v16.stats(p25["target5_no"]),
        "2026":pstats(p26,{
            "2026H1":("2026-01-01","2026-06-30"),
            "2026_JulAug":("2026-07-01","2026-08-31"),
            "2026_MarAug":("2026-03-01","2026-08-31"),
        }),
        "2026_JanAug":v16.stats(p26["target5_no"]),
        "2026_monthly":{
            str(m):v16.stats(g["target5_no"])
            for m,g in p26.groupby(p26.date.dt.to_period("M"))
        },
        "production_writes":False,
        "warning":"2025/2026 are reporting only; do not tune V19 from these results.",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    p25.to_csv(OUT/"v19_ret1cap_2025_picks.csv", index=False)
    p26.to_csv(OUT/"v19_ret1cap_2026_picks.csv", index=False)
    (OUT/"v19_ret1cap_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
