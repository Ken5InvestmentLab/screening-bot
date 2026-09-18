#!/usr/bin/env python3
"""Research-only deterministic 2022 fallback entrypoint.

Contract source: DETERMINISTIC_2022_FALLBACK_MANIFEST_20260918.md.
This script intentionally emits only raw Tail + frozen weak/early ledgers. It does
not calculate returns, inspect 2026, or infer unresolved primary candidate gates.
Run against code checked out at validation commit d9792122a541847c3e4ed82604bffa220dab4a33.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TVFREE = ROOT / "tvfree_screener"
sys.path.insert(0, str(TVFREE))
import v9_conditional_quality_research as v9  # noqa: E402

EXPECTED_CORPUS_SHA256 = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
START = "2022-06-01"
END = "2022-12-31"
WEAK_EARLY_RET10_MAX = 0.5735294117647058


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="tvfree_screener/out/tse_daily.csv")
    ap.add_argument("--out", default="research/out/2022_fallback")
    args = ap.parse_args()

    cache = Path(args.cache)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    corpus_sha = sha256(cache)
    if corpus_sha != EXPECTED_CORPUS_SHA256:
        raise SystemExit(f"corpus SHA mismatch: {corpus_sha}")

    raw = pd.read_csv(cache)
    q = v9.prepare(raw)
    tail = v9.generate_tail_pool(q, START, END).copy()
    gated = tail[(tail["med_ret5"] <= 0) & (tail["ret10"] <= WEAK_EARLY_RET10_MAX)].copy()

    # Historical 89/29/23 values are diagnostics only. Never tune to them.
    diagnostics = {
        "raw_tail_rows": int(len(tail)),
        "gated_rows": int(len(gated)),
        "gated_signal_dates": int(pd.to_datetime(gated["date"]).nunique()) if not gated.empty else 0,
        "old_summary_reference_only": {"raw_tail_rows": 89, "gated_rows": 29, "gated_signal_dates": 23},
        "old_summary_exactly_reproduced": bool(len(tail) == 89 and len(gated) == 29 and (pd.to_datetime(gated["date"]).nunique() if not gated.empty else 0) == 23),
    }

    raw_path = out / "tail_raw_2022.csv"
    gated_path = out / "weak_early_gated_2022.csv"
    tail.to_csv(raw_path, index=False)
    gated.to_csv(gated_path, index=False)

    receipt = {
        "status": "DETERMINISTIC_2022_FALLBACK_BASE_LEDGERS_EMITTED",
        "validation_commit": "d9792122a541847c3e4ed82604bffa220dab4a33",
        "v9_blob_sha": "45a1272fe49c526bbf69956419e34e96d696f7d6",
        "v7_blob_sha": "f7f49ab2e09496494adfb365c94e969973c4070c",
        "input": {"path": str(cache), "sha256": corpus_sha},
        "period": [START, END],
        "gate": "med_ret5 <= 0 AND ret10 <= 0.5735294117647058",
        "outputs": {
            str(raw_path): sha256(raw_path),
            str(gated_path): sha256(gated_path),
        },
        "diagnostics": diagnostics,
        "candidate_rows": "NOT_EMITTED_HERE; primary selectors require separately pinned exact candidate/G3 semantics",
        "forbidden": ["retune_to_29_23", "2026", "production_write", "return_recompute"],
    }
    receipt_path = out / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
