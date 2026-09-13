from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

import pandas as pd

EXPECTED_COUNT=1810
EXPECTED_SHA="2437e240d549074594b8584a9e2403a153c20a377bcc9b842dc7f8b538d1516b"


def normalize_symbols(lines):
    return sorted({x.strip().upper() for x in lines if x.strip() and not x.startswith("#")})


def list_sha(symbols):
    return hashlib.sha256(("\n".join(symbols)+"\n").encode("utf-8")).hexdigest()


def evaluate_coverage(expected_symbols, observed_symbols, failures):
    exp=set(expected_symbols); obs=set(observed_symbols)
    missing=sorted(exp-obs); extra=sorted(obs-exp)
    checks={
        "expected_count_exact":len(exp)==EXPECTED_COUNT,
        "expected_sha_exact":list_sha(sorted(exp))==EXPECTED_SHA,
        "no_missing_symbols":len(missing)==0,
        "no_extra_symbols":len(extra)==0,
        "zero_fetch_failures":len(failures)==0,
    }
    return {
        "accepted":all(checks.values()),
        "checks":checks,
        "expected_symbols":len(exp),
        "observed_symbols":len(obs),
        "missing_symbols":missing,
        "extra_symbols":extra,
        "fetch_failure_count":len(failures),
        "strategy_outcomes_read":False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",required=True,type=Path)
    ap.add_argument("--raw-glob",required=True)
    ap.add_argument("--failures-glob",required=True)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()

    expected=normalize_symbols(a.symbols.read_text(encoding="utf-8").splitlines())
    observed=set(); rows=0; ts_min=None; ts_max=None
    for fp in sorted(glob.glob(a.raw_glob)):
        d=pd.read_csv(fp,dtype={"symbol":"string","timestamp":"string"},usecols=["timestamp","symbol"])
        d["symbol"]=d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip().str.upper()
        observed.update(d["symbol"].dropna())
        rows+=len(d)
        if len(d):
            mn=str(d["timestamp"].min()); mx=str(d["timestamp"].max())
            ts_min=mn if ts_min is None or mn<ts_min else ts_min
            ts_max=mx if ts_max is None or mx>ts_max else ts_max

    failures=[]
    for fp in sorted(glob.glob(a.failures_glob)):
        failures.extend(json.loads(Path(fp).read_text(encoding="utf-8")))

    out=evaluate_coverage(expected,observed,failures)
    out.update({
        "receipt_id":"V20-H1-RAW-COVERAGE-20260914",
        "raw_rows":rows,
        "timestamp_min":ts_min,
        "timestamp_max":ts_max,
        "raw_query_mode":"explicit period1/period2 Yahoo 1h with div,splits events",
        "split_adjustment_note":"V20 signal features are within-bar scale invariant; absolute prior-day eligibility and endpoint labels come from frozen canonical daily.",
        "production_modified":False,
    })
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))
    if not out["accepted"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
