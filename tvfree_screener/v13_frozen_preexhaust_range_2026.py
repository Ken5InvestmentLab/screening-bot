#!/usr/bin/env python3
"""V13 frozen Pre-Exhaustion+Range Tail lane, 2026 reporting only (TEST ONLY).

IMPORTANT:
- Logic was frozen before this runner opens 2026 outcomes.
- No 2026 threshold/model/feature selection.
- No production writes.

Frozen lane:
1. Generate causal V7 extreme Tail candidates (tail CDF >= 0.999).
2. Keep only days with cross-sectional median 5D return <= 0.
3. Within each day, prefer lower relative ranks of:
   ret20, ma20_gap, volr20, range_pct.
4. Tie-break by higher Tail CDF / Tail probability.
5. Apply one-business-day same-symbol cooldown.

Entry/evaluation: next-session open -> 5BD close.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

import v9_conditional_quality_research as v9

OUT = Path("tvfree_screener/out")
RANK_FEATURES = ["ret20","ma20_gap","volr20","range_pct"]

def stats(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    if x.empty:return {"n":0}
    y=x.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(x)),
        "mean":float(x.mean()),
        "median":float(x.median()),
        "win_rate":float((x>0).mean()),
        "hit10_rate":float((x>=.10).mean()),
        "hit20_rate":float((x>=.20).mean()),
        "hit50_rate":float((x>=.50).mean()),
        "hit100_rate":float((x>=1).mean()),
        "loss10_rate":float((x<=-.10).mean()),
        "loss20_rate":float((x<=-.20).mean()),
        "max":float(x.max()),
        "min":float(x.min()),
        "top1_removed_mean":float(y.iloc[1:].mean()) if len(y)>1 else None,
        "top3_removed_mean":float(y.iloc[3:].mean()) if len(y)>3 else None,
    }

def select(tail:pd.DataFrame,trading_dates:pd.Index)->pd.DataFrame:
    z=tail[tail["med_ret5"]<=0].copy()
    if z.empty:return z
    rank_cols=[]
    for c in RANK_FEATURES:
        rc=f"rank_{c}"
        z[rc]=z.groupby("date")[c].rank(
            pct=True,method="average",ascending=True
        )
        rank_cols.append(rc)
    z["preexhaust_range_rank"]=z[rank_cols].mean(axis=1)

    date_idx={pd.Timestamp(d):i for i,d in enumerate(trading_dates)}
    rows=[]; last_symbol=None; last_idx=None
    for date,day in z.groupby("date",sort=True):
        idx=date_idx.get(pd.Timestamp(date))
        if idx is None: continue
        day=day.sort_values(
            ["preexhaust_range_rank","tail_cdf","tail_p"],
            ascending=[True,False,False],
        )
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
            last_symbol=str(chosen["symbol"]); last_idx=idx
    return pd.DataFrame(rows).reset_index(drop=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",default=str(OUT/"tse_daily.csv"))
    args=ap.parse_args()

    raw=pd.read_csv(args.cache,parse_dates=["date"],dtype={"symbol":str})
    for c in ["open","high","low","close","volume"]:
        raw[c]=pd.to_numeric(raw[c],errors="coerce")
    raw=raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates=pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    q=v9.prepare(raw)
    tail=v9.generate_tail_pool(q,"2026-01-01","2026-08-31")
    picks=select(tail,trading_dates)

    jan_aug=picks[(picks.date>="2026-01-01")&(picks.date<="2026-08-31")].copy()
    mar_aug=picks[(picks.date>="2026-03-01")&(picks.date<="2026-08-31")].copy()

    monthly={
        str(m):stats(g["target5_no"])
        for m,g in jan_aug.groupby(jan_aug.date.dt.to_period("M"))
    }

    report={
        "status":"research_only_no_production_writes",
        "component":"V13 frozen V7 Tail + Pre-Exhaustion+Range rank",
        "frozen_before_2026":True,
        "tail_gate":v9.TAIL_GATE,
        "market_gate":"med_ret5 <= 0",
        "rank_features":RANK_FEATURES,
        "rank_direction":"lower within-day percentile preferred",
        "entry":"next_session_open_to_5BD_close",
        "tail_candidates_2026_jan_aug":int(len(tail)),
        "selected_2026_jan_aug":stats(jan_aug["target5_no"]),
        "selected_2026_mar_aug":stats(mar_aug["target5_no"]),
        "monthly_2026":monthly,
        "production_writes":False,
        "warning":"2026 is reporting-only; do not tune V13 from this result.",
    }

    OUT.mkdir(parents=True,exist_ok=True)
    jan_aug.to_csv(OUT/"v13_frozen_2026_picks.csv",index=False)
    (OUT/"v13_frozen_2026_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
