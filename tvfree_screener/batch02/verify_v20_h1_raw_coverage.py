from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

EXPECTED_COUNT=1810
EXPECTED_SHA="2437e240d549074594b8584a9e2403a153c20a377bcc9b842dc7f8b538d1516b"
EXPECTED_DAILY_SHA="6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
RAW_START="2025-01-06"
RAW_END="2025-06-30"


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def normalize_symbols(lines):
    return sorted({x.strip().upper() for x in lines if x.strip() and not x.startswith("#")})


def list_sha(symbols):
    return hashlib.sha256(("\n".join(symbols)+"\n").encode("utf-8")).hexdigest()


def expected_active_pairs_from_daily(daily_path: Path, expected_symbols: list[str]) -> set[tuple[str,str]]:
    actual=sha256_file(daily_path)
    if actual!=EXPECTED_DAILY_SHA:
        raise RuntimeError(f"daily SHA mismatch {actual}")
    wanted=set(expected_symbols)
    pairs:set[tuple[str,str]]=set()
    for c in pd.read_csv(
        daily_path,
        usecols=["date","symbol","close","volume"],
        dtype={"date":"string","symbol":"string"},
        chunksize=400000,
        low_memory=False,
    ):
        c["date"]=c["date"].astype(str).str[:10]
        c["symbol"]=c["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip().str.upper()
        c["close"]=pd.to_numeric(c["close"],errors="coerce")
        c["volume"]=pd.to_numeric(c["volume"],errors="coerce")
        q=c[
            c["symbol"].isin(wanted)
            & c["date"].between(RAW_START,RAW_END)
            & np.isfinite(c["close"])
            & (c["close"]>0)
            & np.isfinite(c["volume"])
            & (c["volume"]>0)
        ]
        pairs.update(zip(q["symbol"].astype(str),q["date"].astype(str)))
    return pairs


def evaluate_temporal_presence(
    expected_active_pairs:set[tuple[str,str]],
    observed_pairs:set[tuple[str,str]],
) -> dict:
    missing=sorted(expected_active_pairs-observed_pairs)
    observed_expected=expected_active_pairs & observed_pairs
    return {
        "expected_active_symbol_dates":len(expected_active_pairs),
        "observed_expected_symbol_dates":len(observed_expected),
        "missing_active_symbol_date_count":len(missing),
        "missing_active_symbol_dates_sample":[
            {"symbol":s,"date":d} for s,d in missing[:100]
        ],
        "all_expected_active_symbol_dates_present":len(missing)==0,
    }


def evaluate_coverage(
    expected_symbols,
    observed_symbols,
    failures,
    temporal:dict|None=None,
    duplicate_symbol_timestamps:int=0,
    raw_dates:set[str]|None=None,
):
    exp=set(expected_symbols); obs=set(observed_symbols)
    missing=sorted(exp-obs); extra=sorted(obs-exp)
    temporal_ok=True if temporal is None else bool(temporal["all_expected_active_symbol_dates_present"])
    dates_ok=True
    if raw_dates is not None:
        dates_ok=all(RAW_START<=d<=RAW_END for d in raw_dates)
    checks={
        "expected_count_exact":len(exp)==EXPECTED_COUNT,
        "expected_sha_exact":list_sha(sorted(exp))==EXPECTED_SHA,
        "no_missing_symbols":len(missing)==0,
        "no_extra_symbols":len(extra)==0,
        "zero_fetch_failures":len(failures)==0,
        "all_expected_active_symbol_dates_present":temporal_ok,
        "zero_duplicate_symbol_timestamps":int(duplicate_symbol_timestamps)==0,
        "raw_dates_inside_frozen_window":dates_ok,
    }
    out={
        "accepted":all(checks.values()),
        "checks":checks,
        "expected_symbols":len(exp),
        "observed_symbols":len(obs),
        "missing_symbols":missing,
        "extra_symbols":extra,
        "fetch_failure_count":len(failures),
        "duplicate_symbol_timestamp_count":int(duplicate_symbol_timestamps),
        "strategy_outcomes_read":False,
    }
    if temporal is not None:
        out["temporal_presence"]=temporal
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",required=True,type=Path)
    ap.add_argument("--daily",required=True,type=Path)
    ap.add_argument("--raw-glob",required=True)
    ap.add_argument("--failures-glob",required=True)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()

    expected=normalize_symbols(a.symbols.read_text(encoding="utf-8").splitlines())
    expected_pairs=expected_active_pairs_from_daily(a.daily,expected)

    observed=set(); observed_pairs:set[tuple[str,str]]=set()
    seen_keys:set[tuple[str,str]]=set(); duplicates=0
    raw_dates:set[str]=set()
    rows=0; ts_min=None; ts_max=None
    for fp in sorted(glob.glob(a.raw_glob)):
        d=pd.read_csv(fp,dtype={"symbol":"string","timestamp":"string"},usecols=["timestamp","symbol"])
        d["symbol"]=d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip().str.upper()
        d["date"]=d["timestamp"].astype(str).str[:10]
        observed.update(d["symbol"].dropna())
        observed_pairs.update(zip(d["symbol"].astype(str),d["date"].astype(str)))
        raw_dates.update(d["date"].dropna().astype(str))
        for sym,ts in zip(d["symbol"].astype(str),d["timestamp"].astype(str)):
            key=(sym,ts)
            if key in seen_keys:
                duplicates+=1
            else:
                seen_keys.add(key)
        rows+=len(d)
        if len(d):
            mn=str(d["timestamp"].min()); mx=str(d["timestamp"].max())
            ts_min=mn if ts_min is None or mn<ts_min else ts_min
            ts_max=mx if ts_max is None or mx>ts_max else ts_max

    failures=[]
    for fp in sorted(glob.glob(a.failures_glob)):
        failures.extend(json.loads(Path(fp).read_text(encoding="utf-8")))

    temporal=evaluate_temporal_presence(expected_pairs,observed_pairs)
    out=evaluate_coverage(
        expected,
        observed,
        failures,
        temporal=temporal,
        duplicate_symbol_timestamps=duplicates,
        raw_dates=raw_dates,
    )
    out.update({
        "receipt_id":"V20-H1-RAW-COVERAGE-20260914-V2",
        "raw_rows":rows,
        "timestamp_min":ts_min,
        "timestamp_max":ts_max,
        "canonical_daily_sha256":EXPECTED_DAILY_SHA,
        "temporal_presence_definition":(
            "For every frozen-universe symbol/date from 2025-01-06..2025-06-30 "
            "where canonical daily has finite positive close and volume>0, "
            "the fetched raw 1H source must contain at least one row for that symbol/date."
        ),
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
