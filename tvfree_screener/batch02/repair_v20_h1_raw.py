#!/usr/bin/env python3
"""Outcome-blind repair for frozen V20 H1 Yahoo 1H raw coverage.

Only missing canonical-active symbol/date pairs are queried. Verified predecessor
query identities are kept separate from the frozen output identity. Strategy
returns are never read here.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd

from fetch_v20_h1_1h import request_json, extract_rows
from verify_v20_h1_raw_coverage import (
    RAW_START,
    RAW_END,
    expected_active_pairs_from_daily,
    normalize_symbols,
)

RAW_COLUMNS=["timestamp","symbol","open","high","low","close","volume"]


def load_raw(pattern: str) -> pd.DataFrame:
    frames=[]
    for fp in sorted(glob.glob(pattern)):
        d=pd.read_csv(fp)
        if len(d):
            frames.append(d[RAW_COLUMNS].copy())
    if not frames:
        return pd.DataFrame(columns=RAW_COLUMNS)
    x=pd.concat(frames,ignore_index=True)
    x["symbol"]=(x["symbol"].astype(str)
                 .str.replace(r"\.0$","",regex=True)
                 .str.strip().str.upper())
    x["timestamp"]=x["timestamp"].astype(str)
    x["date"]=x["timestamp"].str[:10]
    x=x[x["date"].between(RAW_START,RAW_END)].copy()
    x=x.drop_duplicates(["symbol","timestamp"],keep="first")
    return x


def load_map(path: Path) -> dict[str,str]:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status")!="FROZEN_OUTCOME_BLIND":
        raise RuntimeError("identity map is not frozen outcome-blind")
    out={}
    for m in payload.get("mappings",[]):
        sym=str(m["output_symbol"]).upper()
        qry=str(m["query_symbol_for_h1_2025"]).upper()
        out[sym]=qry
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",required=True,type=Path)
    ap.add_argument("--daily",required=True,type=Path)
    ap.add_argument("--raw-glob",required=True)
    ap.add_argument("--identity-map",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--audit",required=True,type=Path)
    ap.add_argument("--failures",required=True,type=Path)
    a=ap.parse_args()

    expected=normalize_symbols(a.symbols.read_text(encoding="utf-8").splitlines())
    expected_pairs=expected_active_pairs_from_daily(a.daily,expected)
    raw=load_raw(a.raw_glob)
    observed_pairs=set(zip(raw["symbol"].astype(str),raw["date"].astype(str)))
    missing=sorted(expected_pairs-observed_pairs)
    identity=load_map(a.identity_map)

    rows_by_key={}
    for r in raw[RAW_COLUMNS].itertuples(index=False,name=None):
        rows_by_key[(str(r[1]),str(r[0]))]=r

    audit=[]; failures=[]
    for n,(out_sym,date_s) in enumerate(missing,1):
        query_sym=identity.get(out_sym,out_sym)
        day=pd.Timestamp(date_s).date()
        status="missing_after_query"
        count=0
        err=None
        try:
            fetched=extract_rows(query_sym,request_json(query_sym,day,day),day,day)
            for row in fetched:
                # Preserve prices/volumes/timestamps from the raw source, but
                # normalize identity back to the exact frozen V20 output symbol.
                repaired=(row[0],out_sym,row[2],row[3],row[4],row[5],row[6])
                rows_by_key[(out_sym,row[0])]=repaired
                count+=1
            status="repaired" if count else "missing_after_query"
        except Exception as e:
            err=str(e)
            failures.append({
                "output_symbol":out_sym,
                "query_symbol":query_sym,
                "date":date_s,
                "error":err,
            })
        audit.append({
            "output_symbol":out_sym,
            "query_symbol":query_sym,
            "date":date_s,
            "status":status,
            "rows_added":count,
            "error":err,
        })
        if n%25==0 or n==len(missing):
            print(f"repair {n}/{len(missing)} added={sum(x['rows_added'] for x in audit)} failures={len(failures)}",flush=True)

    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("w",encoding="utf-8",newline="") as f:
        pd.DataFrame(
            [rows_by_key[k] for k in sorted(rows_by_key,key=lambda z:(z[0],z[1]))],
            columns=RAW_COLUMNS,
        ).to_csv(f,index=False)
    a.audit.write_text(json.dumps({
        "contract":"V20_H1_RAW_REPAIR_PREREG_20260914",
        "strategy_outcomes_read":False,
        "missing_pairs_before":len(missing),
        "verified_identity_mappings":identity,
        "rows_added":sum(x["rows_added"] for x in audit),
        "pairs_repaired":sum(1 for x in audit if x["status"]=="repaired"),
        "pairs_unrepaired":sum(1 for x in audit if x["status"]!="repaired"),
        "queries":audit,
    },ensure_ascii=False,indent=2),encoding="utf-8")
    a.failures.write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":
    main()
