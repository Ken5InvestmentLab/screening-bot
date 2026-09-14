from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def clean(x: object)->str:
    s=str(x).strip()
    return s[:-2] if s.endswith(".0") else s


def summarize(c: pd.DataFrame, arm_col: str, current: set[str]) -> dict:
    z=c[c[arm_col].astype(bool)].copy()
    if z.empty:
        return {"rows":0}
    z["is_restored"]=~z["symbol"].isin(current)
    z["half"]=z["date_s"].apply(
        lambda x: "H1" if str(x) <= "2025-06-30" else "H2"
    )
    by_day=z.groupby("date_s").agg(
        total=("symbol","size"),
        restored=("is_restored","sum"),
    )
    by_day["share"]=by_day["restored"]/by_day["total"]
    out={
        "rows":int(len(z)),
        "symbols":int(z["symbol"].nunique()),
        "restored_rows":int(z["is_restored"].sum()),
        "restored_row_share":float(z["is_restored"].mean()),
        "restored_symbols":int(z.loc[z["is_restored"],"symbol"].nunique()),
        "median_daily_restored_share":float(by_day["share"].median()),
        "p95_daily_restored_share":float(by_day["share"].quantile(.95)),
        "max_daily_restored_share":float(by_day["share"].max()),
        "halves":{},
    }
    for half,g in z.groupby("half"):
        out["halves"][half]={
            "rows":int(len(g)),
            "restored_rows":int(g["is_restored"].sum()),
            "restored_row_share":float(g["is_restored"].mean()),
            "restored_symbols":int(g.loc[g["is_restored"],"symbol"].nunique()),
        }
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily-candidates",required=True,type=Path)
    ap.add_argument("--frozen-daily",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()

    c=pd.read_csv(a.daily_candidates,dtype={"symbol":str,"date_s":str},low_memory=False)
    c["symbol"]=c["symbol"].map(clean)
    d=pd.read_csv(a.frozen_daily,usecols=["symbol"],dtype={"symbol":str})
    current=set(d["symbol"].map(clean).unique())

    report={
        "scope":"outcome-free V47 intraday survivorship omission audit",
        "NOCAP":summarize(c,"eligible_nocap_daily",current),
        "CAP1000_PIT":summarize(c,"eligible_cap1000_daily",current),
        "strategy_returns_opened":False,
        "model_scores_opened":False,
        "interpretation":"Restored-row share is the exact daily-eligibility mass that a current-survivor-only raw1H backtest would omit before session-volume/technical/model filters.",
        "production_writes":False,
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
