from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def clean(x: object) -> str:
    s=str(x).strip()
    return s[:-2] if s.endswith(".0") else s


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily-receipt",required=True,type=Path)
    ap.add_argument("--membership-events",required=True,type=Path)
    ap.add_argument("--frozen-daily",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--max-gap-days",type=int,default=10)
    a=ap.parse_args()

    receipt=json.loads(a.daily_receipt.read_text(encoding="utf-8"))
    missing=set(
        clean(x)
        for x in receipt.get("restored_daily_fetch",{}).get("missing_symbols",[])
    )

    e=pd.read_csv(a.membership_events,dtype={"code":str})
    e["code"]=e["code"].map(clean)
    e["event_date"]=pd.to_datetime(e["event_date"],errors="coerce").dt.normalize()
    e=e.dropna(subset=["event_date","code","event"])

    d=pd.read_csv(
        a.frozen_daily,
        usecols=["date","symbol"],
        dtype={"symbol":str},
        low_memory=False,
    )
    d["symbol"]=d["symbol"].map(clean)
    d["date"]=pd.to_datetime(d["date"],errors="coerce").dt.normalize()
    current=set(d["symbol"].unique())
    min_date=d.groupby("symbol")["date"].min()
    pre_counts={}

    listings=e[e["event"]=="listing"].copy()
    for r in listings.itertuples(index=False):
        code=str(r.code)
        if code not in current:
            continue
        pre=d[(d["symbol"]==code)&(d["date"]<r.event_date)]
        if len(pre):
            pre_counts[(code,pd.Timestamp(r.event_date))]={
                "prelisting_rows":int(len(pre)),
                "prelisting_min":str(pre["date"].min().date()),
                "prelisting_max":str(pre["date"].max().date()),
            }

    rows=[]
    for old in sorted(missing):
        dels=e[(e["code"]==old)&(e["event"]=="delisting")].sort_values("event_date")
        for dr in dels.itertuples(index=False):
            start=pd.Timestamp(dr.event_date)
            cand=listings[
                (listings["event_date"]>=start-pd.Timedelta(days=1))
                &(listings["event_date"]<=start+pd.Timedelta(days=a.max_gap_days))
            ]
            for lr in cand.itertuples(index=False):
                new=str(lr.code)
                key=(new,pd.Timestamp(lr.event_date))
                if key not in pre_counts:
                    continue
                meta=pre_counts[key]
                rows.append({
                    "predecessor_code":old,
                    "predecessor_delisting_date":str(start.date()),
                    "successor_candidate_code":new,
                    "successor_listing_date":str(pd.Timestamp(lr.event_date).date()),
                    "calendar_gap_days":int((pd.Timestamp(lr.event_date)-start).days),
                    **meta,
                    "status":"HEURISTIC_ONLY_REQUIRES_OFFICIAL_IDENTITY_VERIFICATION",
                })

    out=pd.DataFrame(rows)
    if len(out):
        out=out.sort_values([
            "predecessor_code","calendar_gap_days",
            "successor_listing_date","successor_candidate_code",
        ])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(a.output,index=False)

    summary={
        "scope":"outcome-free V47 missing restored-code alias shortlist",
        "missing_restored_symbols":len(missing),
        "candidate_rows":int(len(out)),
        "predecessors_with_candidate":int(out["predecessor_code"].nunique()) if len(out) else 0,
        "rule":"nearby listing event + successor current code has Yahoo frozen pre-listing history",
        "automatic_alias_acceptance":False,
        "strategy_returns_opened":False,
        "model_scores_opened":False,
        "production_writes":False,
    }
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
