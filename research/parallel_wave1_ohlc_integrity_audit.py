#!/usr/bin/env python3
"""Outcome-blind integrity audit for the frozen Parallel Wave-1 daily source.

This script never computes forward returns or strategy performance. It records
only source/schema/invariant facts needed to resolve step8 fail-closed behavior.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

DAILY_SHA256 = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
DAILY_HEADER = ["date", "open", "high", "low", "close", "volume", "symbol"]

def sha256_file(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024), b""): h.update(c)
    return h.hexdigest()

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--daily",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    if sha256_file(a.daily) != DAILY_SHA256: raise SystemExit("FAIL_CLOSED: frozen daily SHA-256 mismatch")
    z=pd.read_csv(a.daily,dtype={"date":"string","symbol":"string"},low_memory=False)
    if list(z.columns) != DAILY_HEADER or len(z) != 4_061_361: raise SystemExit("FAIL_CLOSED: source schema/row count mismatch")
    for c in ["open","high","low","close","volume"]: z[c]=pd.to_numeric(z[c],errors="coerce")
    high_bad=z["high"] < z[["open","low","close"]].max(axis=1)
    low_bad=z["low"] > z[["open","high","close"]].min(axis=1)
    bad=z.loc[high_bad|low_bad,["date","symbol","open","high","low","close","volume"]].copy()
    by_date=bad.groupby("date",sort=True).size()
    receipt={
      "contract_version":1,"status":"OUTCOME_BLIND_OHLC_INTEGRITY_FINDING","performance_opened":False,"return_computed":False,
      "source_sha256":DAILY_SHA256,"source_rows":int(len(z)),
      "high_order_violation_rows":int(high_bad.sum()),"low_order_violation_rows":int(low_bad.sum()),"union_violation_rows":int((high_bad|low_bad).sum()),
      "affected_dates":int(bad["date"].nunique()),"affected_symbols":int(bad["symbol"].nunique()),
      "violations_by_date":{str(k):int(v) for k,v in by_date.items()},
      "finding":"Frozen source contains impossible OHLC ordering. Do not silently repair/drop rows and do not open performance. Establish source-grounded disposition first.",
      "next_boundary":"classify source-generation cause and preregister fail-closed disposition before causal ledger rerun"
    }
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2,sort_keys=True))
    if len(bad): raise SystemExit("FAIL_CLOSED: OHLC integrity violations recorded; disposition required")
if __name__=="__main__": main()
