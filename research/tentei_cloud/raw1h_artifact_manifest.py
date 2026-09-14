#!/usr/bin/env python3
"""Outcome-blind manifest builder for a downloaded 8-shard raw 1H fetch.

This binds the exact bytes used as Core24 observed input before any gap/fallback
or performance work. It never calculates returns.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

REQUIRED_COLS=("symbol","timestamp","open","high","low","close","volume")

def sha256_file(p: Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def build_manifest(root: Path)->dict:
    entries=[]
    missing=[]
    for i in range(8):
        matches=sorted(root.glob(f"**/ohlcv_1h_shard_{i}.csv"))
        if len(matches)!=1:
            missing.append({"shard":i,"matches":[str(x) for x in matches]})
            continue
        p=matches[0]
        df=pd.read_csv(p)
        absent=[c for c in REQUIRED_COLS if c not in df.columns]
        if absent: raise ValueError(f"shard {i} missing columns: {absent}")
        entries.append({
            "shard":i,"path":str(p),"size_bytes":p.stat().st_size,"sha256":sha256_file(p),
            "rows":int(len(df)),"symbols":int(df["symbol"].astype(str).nunique()),
            "min_timestamp":None if df.empty else str(df["timestamp"].min()),
            "max_timestamp":None if df.empty else str(df["timestamp"].max()),
        })
    if missing: raise RuntimeError(json.dumps({"status":"FAIL_CLOSED_SHARD_SET","detail":missing},ensure_ascii=False))
    bundle_material="\n".join(f"{e['shard']}:{e['sha256']}:{e['size_bytes']}:{e['rows']}" for e in entries).encode()
    return {
        "status":"PASS","scope":"OUTCOME_BLIND_RAW1H_ARTIFACT_PIN","shard_count":8,
        "total_rows":sum(e["rows"] for e in entries),"entries":entries,
        "bundle_sha256":hashlib.sha256(bundle_material).hexdigest(),
        "outcome_informed":False,"performance_opened":False,"production_writes":False,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    m=build_manifest(Path(a.root)); Path(a.out).write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(m,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
