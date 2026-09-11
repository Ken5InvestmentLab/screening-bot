#!/usr/bin/env python3
"""Audit fetch failure JSONs from sharded Yahoo 1H research artifacts."""
from __future__ import annotations
import argparse, glob, json
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd

def normalize_error(s: str) -> str:
    s = str(s or "")
    if "HTTP " in s:
        p = s.find("HTTP ")
        return s[p:p+8].strip()
    if "Timeout" in s or "timed out" in s:
        return "timeout"
    if "No data" in s:
        return "no_data"
    return s[:160]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--failure-glob", required=True)
    ap.add_argument("--csv-glob", required=True)
    ap.add_argument("--symbol-file", required=True)
    ap.add_argument("--outdir", required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    failures=[]
    for p in glob.glob(a.failure_glob, recursive=True):
        try:
            data=json.loads(Path(p).read_text(encoding="utf-8"))
            for x in data:
                y=dict(x); y["source_file"]=p; failures.append(y)
        except Exception as e:
            failures.append({"symbol":"","start":"","end":"","error":f"failure_json_parse:{e}","source_file":p})
    fdf=pd.DataFrame(failures)
    if fdf.empty:
        fdf=pd.DataFrame(columns=["symbol","start","end","error","source_file"])
    fdf["error_group"]=fdf["error"].map(normalize_error)
    fdf.to_csv(out/"fetch_failures_all.csv", index=False)

    err=(fdf.groupby("error_group",dropna=False).size().rename("count").reset_index().sort_values("count",ascending=False))
    err.to_csv(out/"fetch_failure_error_groups.csv",index=False)

    target=[x.strip().replace(".T","") for x in Path(a.symbol_file).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    seen=set()
    rows=0
    for p in glob.glob(a.csv_glob, recursive=True):
        q=pd.read_csv(p,usecols=["symbol"],dtype={"symbol":"string"},low_memory=False)
        rows += len(q)
        seen.update(q["symbol"].astype(str).str.replace(".T","",regex=False).dropna().unique().tolist())
    target_set=set(target)
    missing=sorted(target_set-seen)
    extra=sorted(seen-target_set)

    sym_fail=(fdf.groupby("symbol").size().rename("failed_chunks").reset_index().sort_values("failed_chunks",ascending=False)) if not fdf.empty else pd.DataFrame(columns=["symbol","failed_chunks"])
    sym_fail.to_csv(out/"fetch_failures_by_symbol.csv",index=False)
    (out/"fetch_missing_symbols.txt").write_text("\n".join(missing),encoding="utf-8")

    meta={
        "target_symbols":len(target_set),
        "seen_symbols":len(seen & target_set),
        "missing_symbols":len(missing),
        "extra_symbols":len(extra),
        "csv_rows":int(rows),
        "failed_chunks":int(len(fdf)),
        "unique_symbols_with_failures":int(fdf["symbol"].nunique()) if len(fdf) else 0,
        "error_groups":err.to_dict(orient="records"),
    }
    (out/"fetch_audit.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
