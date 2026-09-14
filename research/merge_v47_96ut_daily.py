from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ANCHOR=pd.Timestamp("2026-09-11")
START=pd.Timestamp("2024-10-01")
END=pd.Timestamp("2026-01-15")


def clean(x: object) -> str:
    s=str(x).strip()
    return s[:-2] if s.endswith(".0") else s


def members_as_of(current:set[str],events:pd.DataFrame,as_of:pd.Timestamp)->set[str]:
    m=set(current)
    z=events[(events["event_date"]>as_of)&(events["event_date"]<=ANCHOR)]
    for r in z.sort_values(["event_date","code"],ascending=[False,True]).itertuples(index=False):
        c=clean(r.code)
        if r.event=="listing":
            m.discard(c)
        elif r.event=="delisting":
            m.add(c)
        else:
            raise RuntimeError(f"unknown event {r.event}")
    return m


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-dir",required=True,type=Path)
    ap.add_argument("--daily-receipt",required=True,type=Path)
    ap.add_argument("--membership-events",required=True,type=Path)
    ap.add_argument("--frozen-daily",required=True,type=Path)
    ap.add_argument("--output-dir",required=True,type=Path)
    a=ap.parse_args()

    receipt=json.loads(a.daily_receipt.read_text(encoding="utf-8"))
    expected=sorted(clean(x) for x in receipt["restored_daily_fetch"]["missing_symbols"])

    files=sorted(a.raw_dir.glob("**/v47_96ut_daily_shard_*.csv.gz"))
    if not files:
        raise RuntimeError("no 96ut shard csvs")
    parts=[]
    for p in files:
        d=pd.read_csv(p,dtype={"symbol":str},low_memory=False)
        if len(d):
            parts.append(d)
    merged=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    if merged.empty:
        raise RuntimeError("96ut merge empty")
    merged["symbol"]=merged["symbol"].map(clean)
    merged["date"]=pd.to_datetime(merged["date"],errors="coerce").dt.normalize()
    for c in ["open","high","low","close","volume"]:
        merged[c]=pd.to_numeric(merged[c],errors="coerce")
    merged=(merged.dropna(subset=["symbol","date","open","high","low","close","volume"])
            .drop_duplicates(["symbol","date"],keep="last")
            .sort_values(["symbol","date"]).reset_index(drop=True))

    got=set(merged["symbol"].unique())
    missing=sorted(set(expected)-got)
    extra=sorted(got-set(expected))

    ev=pd.read_csv(a.membership_events,dtype={"code":str})
    ev["code"]=ev["code"].map(clean)
    ev["event_date"]=pd.to_datetime(ev["event_date"],errors="coerce").dt.normalize()
    ev=ev.dropna(subset=["code","event_date","event"])

    fd=pd.read_csv(a.frozen_daily,usecols=["date","symbol"],dtype={"symbol":str},low_memory=False)
    fd["symbol"]=fd["symbol"].map(clean)
    fd["date"]=pd.to_datetime(fd["date"],errors="coerce").dt.normalize()
    current=set(fd["symbol"].dropna().unique())
    dates=sorted(d for d in fd["date"].dropna().unique() if START<=pd.Timestamp(d)<=END)

    required_by_symbol={s:[] for s in expected}
    for dt0 in dates:
        dt=pd.Timestamp(dt0)
        m=members_as_of(current,ev,dt)
        for s in set(expected)&m:
            required_by_symbol[s].append(dt)

    available_by_symbol={
        str(sym):set(pd.to_datetime(g["date"]).dt.normalize())
        for sym,g in merged.groupby("symbol",sort=False)
    }

    rows=[]
    for s in expected:
        req=set(required_by_symbol.get(s,[]))
        av=available_by_symbol.get(s,set())
        inter=req&av
        rows.append({
            "symbol":s,
            "required_member_dates":len(req),
            "available_dates_total":len(av),
            "available_required_dates":len(inter),
            "required_date_coverage":(len(inter)/len(req) if req else 1.0),
            "first_available":str(min(av).date()) if av else "",
            "last_available":str(max(av).date()) if av else "",
        })
    cov=pd.DataFrame(rows)

    out=a.output_dir
    out.mkdir(parents=True,exist_ok=True)
    merged.to_csv(out/"v47_restored_daily_96ut.csv.gz",index=False,compression="gzip")
    cov.to_csv(out/"v47_restored_daily_96ut_coverage_by_symbol.csv",index=False)

    report={
        "scope":"outcome-free 96ut restored/delisted daily merge + PIT coverage receipt",
        "expected_symbols":len(expected),
        "recovered_symbols":len(got & set(expected)),
        "missing_symbols":missing,
        "extra_symbols":extra,
        "rows":int(len(merged)),
        "symbol_coverage_fraction":float(len(got & set(expected))/len(expected)) if expected else 1.0,
        "median_required_date_coverage":float(cov["required_date_coverage"].median()) if len(cov) else 1.0,
        "min_required_date_coverage":float(cov["required_date_coverage"].min()) if len(cov) else 1.0,
        "symbols_below_90pct_required_date_coverage":cov.loc[cov["required_date_coverage"]<0.90,"symbol"].tolist(),
        "accepted_for_daily_rebuild":len(missing)==0,
        "source_basis":"96ut point-in-time nominal OHLCV",
        "strategy_returns_opened":False,
        "model_scores_opened":False,
        "production_writes":False,
    }
    (out/"v47_restored_daily_96ut_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
