#!/usr/bin/env python3
"""Classify Yahoo 1H fetch failures by their position relative to observed history.

Research-only data-quality audit.

For each target symbol:
- observed first/last timestamp from fetched CSVs
- failed chunk intervals from failure JSONs
- classify failures as before observed history, after observed history,
  overlapping observed history, or never-seen.

This does not assume the reason (IPO/delisting). It only describes topology.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd


def norm_symbol(x: object) -> str:
    return str(x or "").strip().replace(".T", "")


def parse_ts(x: object) -> pd.Timestamp:
    z = pd.to_datetime(x, errors="coerce", utc=True)
    if pd.isna(z):
        return pd.NaT
    return z


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--failure-glob", required=True)
    ap.add_argument("--csv-glob", required=True)
    ap.add_argument("--symbol-file", required=True)
    ap.add_argument("--outdir", required=True)
    a=ap.parse_args()

    out=Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    target=[
        norm_symbol(x)
        for x in Path(a.symbol_file).read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.startswith("#")
    ]

    obs_parts=[]
    for p in glob.glob(a.csv_glob, recursive=True):
        q=pd.read_csv(p, usecols=lambda c: c in {"symbol","timestamp","date"}, dtype={"symbol":"string"}, low_memory=False)
        if "symbol" not in q:
            continue
        q["symbol"]=q["symbol"].astype(str).map(norm_symbol)
        if "timestamp" in q:
            ts=pd.to_datetime(q["timestamp"], errors="coerce", utc=True)
        elif "date" in q:
            ts=pd.to_datetime(q["date"], errors="coerce", utc=True)
        else:
            continue
        z=pd.DataFrame({"symbol":q["symbol"],"ts":ts}).dropna(subset=["ts"])
        obs_parts.append(z)

    if obs_parts:
        obs=pd.concat(obs_parts, ignore_index=True)
        span=(obs.groupby("symbol")["ts"]
              .agg(first_observed="min", last_observed="max", observed_rows="size")
              .reset_index())
    else:
        span=pd.DataFrame(columns=["symbol","first_observed","last_observed","observed_rows"])

    failures=[]
    for p in glob.glob(a.failure_glob, recursive=True):
        data=json.loads(Path(p).read_text(encoding="utf-8"))
        for r in data:
            failures.append({
                "symbol":norm_symbol(r.get("symbol")),
                "fail_start":parse_ts(r.get("start")),
                "fail_end":parse_ts(r.get("end")),
                "error":str(r.get("error","")),
                "source_file":p,
            })
    f=pd.DataFrame(failures)
    if f.empty:
        f=pd.DataFrame(columns=["symbol","fail_start","fail_end","error","source_file"])

    x=pd.DataFrame({"symbol":sorted(set(target))}).merge(span,on="symbol",how="left")
    rows=[]
    detail=[]

    by_fail={s:g.copy() for s,g in f.groupby("symbol")} if not f.empty else {}
    for _,r in x.iterrows():
        s=r["symbol"]
        first=r["first_observed"]
        last=r["last_observed"]
        g=by_fail.get(s, pd.DataFrame(columns=f.columns))
        counts={"before":0,"after":0,"overlap":0,"unknown":0}

        for _,fr in g.iterrows():
            fs=fr["fail_start"]; fe=fr["fail_end"]
            cls="unknown"
            if pd.isna(first) or pd.isna(last):
                cls="never_seen"
            elif pd.isna(fs) or pd.isna(fe):
                cls="unknown"
            elif fe <= first:
                cls="before"
            elif fs >= last:
                cls="after"
            else:
                cls="overlap"

            if cls in counts:
                counts[cls]+=1
            detail.append({
                "symbol":s,
                "first_observed":first,
                "last_observed":last,
                "fail_start":fs,
                "fail_end":fe,
                "topology":cls,
                "error":fr.get("error",""),
            })

        if pd.isna(first):
            category="NEVER_SEEN"
        elif counts["overlap"]>0:
            category="INTERNAL_OR_EDGE_OVERLAP"
        elif counts["before"]>0 and counts["after"]>0:
            category="BEFORE_AND_AFTER_ONLY"
        elif counts["before"]>0:
            category="BEFORE_FIRST_ONLY"
        elif counts["after"]>0:
            category="AFTER_LAST_ONLY"
        elif len(g)>0:
            category="UNKNOWN_FAILURE_POSITION"
        else:
            category="NO_FAILURES"

        rows.append({
            "symbol":s,
            "first_observed":first,
            "last_observed":last,
            "observed_rows":0 if pd.isna(r["observed_rows"]) else int(r["observed_rows"]),
            "failed_chunks":int(len(g)),
            "before_failures":counts["before"],
            "after_failures":counts["after"],
            "overlap_failures":counts["overlap"],
            "unknown_failures":counts["unknown"],
            "category":category,
        })

    summary=pd.DataFrame(rows)
    summary.to_csv(out/"fetch_failure_topology_by_symbol.csv",index=False)
    pd.DataFrame(detail).to_csv(out/"fetch_failure_topology_detail.csv",index=False)

    cat=(summary.groupby("category").size().rename("symbols").reset_index().sort_values("symbols",ascending=False))
    cat.to_csv(out/"fetch_failure_topology_categories.csv",index=False)

    affected=summary[summary["failed_chunks"]>0].sort_values(
        ["category","failed_chunks","symbol"], ascending=[True,False,True]
    )
    affected.to_csv(out/"fetch_failure_topology_affected.csv",index=False)

    meta={
        "target_symbols":int(len(summary)),
        "symbols_with_failures":int((summary["failed_chunks"]>0).sum()),
        "never_seen":int((summary["category"]=="NEVER_SEEN").sum()),
        "symbols_with_internal_or_edge_overlap":int((summary["category"]=="INTERNAL_OR_EDGE_OVERLAP").sum()),
        "categories":cat.to_dict(orient="records"),
        "interpretation_guard":"topology only; IPO/delisting reason requires external/listing evidence",
    }
    (out/"fetch_failure_topology_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nAFFECTED")
    print(affected.to_string(index=False))


if __name__=="__main__":
    main()
