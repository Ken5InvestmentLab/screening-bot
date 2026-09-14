#!/usr/bin/env python3
"""Outcome-free lineage audit for reconstructed Core PIT absolute gates.

This audit does not calculate returns and does not change candidate logic.

It verifies that the reconstructed Core implementation derives:
- previous daily close from explicit-period raw Yahoo 1H bars (last close);
- previous daily volume from the same raw Yahoo 1H bars (summed volume);
- session volume from raw Yahoo 1H bars.

Why this matters:
Shared V47 data-integrity receipts established that frozen Yahoo DAILY data has
future-split-adjusted volume and split-normalized absolute price, while the Core
explicit-period RAW 1H archive has different semantics:
- raw 1H volume is already on point-in-time share-count scale;
- explicit-period raw 1H prices preserve the historical nominal scale on audited
  split-affected rows relative to the range-query/frozen-daily basis.

Therefore this Core path must not be "corrected" by applying the DAILY split
factor transform to its raw-1H-derived absolute gates.

This script freezes only implementation lineage. It does NOT promote Core.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path

import pandas as pd

import reconstruct_4h_from_1h as recon


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-file",default="research/tentei_cloud/reconstruct_4h_from_1h.py")
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    source_path=Path(a.source_file)
    source=source_path.read_text(encoding="utf-8")
    add_daily_src=inspect.getsource(recon.add_daily_context)
    aggregate_src=inspect.getsource(recon.aggregate)

    checks={
        "daily_context_groups_raw_symbol_date":
            '.groupby(["symbol","date"],as_index=False)' in add_daily_src.replace(" ", ""),
        "daily_close_is_last_raw_close":
            'daily_close=("close","last")' in add_daily_src.replace(" ", ""),
        "daily_volume_is_sum_raw_volume":
            'daily_volume=("volume","sum")' in add_daily_src.replace(" ", ""),
        "prev_daily_close_is_shifted_raw_daily_close":
            'prev_daily_close' in add_daily_src and 'shift(1)' in add_daily_src,
        "prev_daily_volume_is_shifted_raw_daily_volume":
            'prev_daily_volume' in add_daily_src and 'shift(1)' in add_daily_src,
        "session_volume_is_sum_raw_volume":
            'volume=("volume","sum")' in aggregate_src.replace(" ", ""),
        "no_split_factor_transform_in_reconstruction":
            all(term not in source.lower() for term in [
                "future_split_factor",
                "cumulative_future_split",
                "split_ratio",
                "stock splits",
            ]),
    }

    # Synthetic lineage receipt: prove add_daily_context uses input rows directly,
    # with no hidden daily-provider path.
    raw=pd.DataFrame([
        {"symbol":"9999","date":"2025-03-31","timestamp":pd.Timestamp("2025-03-31 09:00",tz="Asia/Tokyo"),"open":900.0,"high":910.0,"low":895.0,"close":905.0,"volume":4000},
        {"symbol":"9999","date":"2025-03-31","timestamp":pd.Timestamp("2025-03-31 13:00",tz="Asia/Tokyo"),"open":905.0,"high":920.0,"low":900.0,"close":915.0,"volume":7000},
        {"symbol":"9999","date":"2025-04-01","timestamp":pd.Timestamp("2025-04-01 09:00",tz="Asia/Tokyo"),"open":92.0,"high":94.0,"low":91.0,"close":93.0,"volume":8000},
        {"symbol":"9999","date":"2025-04-01","timestamp":pd.Timestamp("2025-04-01 13:00",tz="Asia/Tokyo"),"open":93.0,"high":95.0,"low":92.0,"close":94.0,"volume":9000},
    ])
    sessions=pd.DataFrame([
        {"symbol":"9999","date":"2025-03-31","session":"AM","close":905.0},
        {"symbol":"9999","date":"2025-03-31","session":"PM","close":915.0},
        {"symbol":"9999","date":"2025-04-01","session":"AM","close":93.0},
        {"symbol":"9999","date":"2025-04-01","session":"PM","close":94.0},
    ])
    enriched,dates=recon.add_daily_context(sessions,raw)
    apr1=enriched[enriched["date"]=="2025-04-01"].iloc[0]
    synthetic={
        "expected_prev_close":915.0,
        "actual_prev_close":float(apr1["prev_daily_close"]),
        "expected_prev_volume":11000.0,
        "actual_prev_volume":float(apr1["prev_daily_volume"]),
    }
    synthetic["pass"]=(
        synthetic["actual_prev_close"]==synthetic["expected_prev_close"]
        and synthetic["actual_prev_volume"]==synthetic["expected_prev_volume"]
    )

    if not all(checks.values()) or not synthetic["pass"]:
        raise RuntimeError(json.dumps({"checks":checks,"synthetic":synthetic},ensure_ascii=False))

    receipt={
        "status":"PASS",
        "scope":"OUTCOME_FREE_CORE_RAW1H_PIT_LINEAGE",
        "source_file":str(source_path),
        "source_sha256":sha256_file(source_path),
        "checks":checks,
        "synthetic_lineage_check":synthetic,
        "frozen_semantics":{
            "prev_daily_close":"last close from explicit-period raw 1H rows on prior date",
            "prev_daily_volume":"sum of explicit-period raw 1H volume on prior date",
            "session_volume":"sum of explicit-period raw 1H volume in reconstructed session",
            "daily_provider_used_for_absolute_gates":False,
            "apply_daily_split_volume_transform_to_raw1h":False,
        },
        "external_contract_dependencies":[
            "CONSENSUS_RAW1H_SPLIT_ADJUSTMENT_AUDIT_2026-09-14.md",
            "CONSENSUS_V47_SPLIT_VOLUME_AUDIT_2026-09-14.md",
            "CONSENSUS_V47_RAW1H_VOLUME_CONTRACT_CORRECTION_20260914.md",
        ],
        "promotion_effect":"NONE; current fixed Core replacement rejection remains unchanged",
        "production_writes":False,
    }
    (out/"core_raw1h_pit_lineage_receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
