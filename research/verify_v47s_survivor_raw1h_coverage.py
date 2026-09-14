from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import verify_consensus_v47_raw1h_coverage as base


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily-candidates",required=True,type=Path)
    ap.add_argument("--daily-receipt",required=True,type=Path)
    ap.add_argument("--raw-dir",required=True,type=Path)
    ap.add_argument("--frozen-daily",required=True,type=Path)
    ap.add_argument("--output-dir",required=True,type=Path)
    a=ap.parse_args()

    src=json.loads(a.daily_receipt.read_text(encoding="utf-8"))
    if src.get("daily_coverage_pass"):
        raise RuntimeError("shadow verifier expects incomplete PIT daily source")
    if src.get("strategy_returns_opened") or src.get("model_scores_opened"):
        raise RuntimeError("source isolation contract violated")

    current=pd.read_csv(
        a.frozen_daily,usecols=["symbol"],dtype={"symbol":str}
    )["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip().unique()
    current=set(current)

    c=pd.read_csv(
        a.daily_candidates,dtype={"symbol":str,"date_s":str},low_memory=False
    )
    c["symbol"]=c["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
    if not set(c["symbol"].unique()).issubset(current):
        raise RuntimeError("shadow candidate file unexpectedly contains restored codes")

    available=base.load_available_pairs(a.raw_dir)
    results={}
    missing_files={}
    for name,col in [
        ("NOCAP","eligible_nocap_daily"),
        ("CAP1000_PIT","eligible_cap1000_daily"),
    ]:
        req=base.arm_required(c,col)
        st,missing=base.evaluate_arm(req,available,set())
        # Restored coverage is intentionally inapplicable in shadow mode.
        checks=dict(st["checks"])
        checks.pop("restored_pair_coverage_gte_99p0",None)
        accepted=bool(all(checks.values()))
        st["checks_shadow"]=checks
        st["accepted_shadow"]=accepted
        st["accepted"]=False
        st["promotion_grade"]=False
        results[name]=st
        missing_files[name]=missing

    accepted_shadow=all(x["accepted_shadow"] for x in results.values())
    out=a.output_dir
    out.mkdir(parents=True,exist_ok=True)
    missing_files["NOCAP"].to_csv(out/"v47s_missing_pairs_nocap.csv",index=False)
    missing_files["CAP1000_PIT"].to_csv(out/"v47s_missing_pairs_cap1000.csv",index=False)

    report={
        "scope":"V47S current-survivor raw1H coverage acceptance",
        "source_daily_run_is_known_incomplete":True,
        "shadow_accepted":accepted_shadow,
        "promotion_grade":False,
        "thresholds":{
            "pair_coverage_min":base.PAIR_MIN,
            "monthly_coverage_min":base.MONTH_MIN,
            "per_symbol_coverage_min_for_20plus_days":base.SYMBOL_MIN,
        },
        **results,
        "strategy_returns_opened":False,
        "model_scores_opened":False,
        "production_writes":False,
    }
    (out/"v47s_raw1h_coverage_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
