#!/usr/bin/env python3
"""Research-only deterministic reconstruction of the 2022 primary weak+early Tail gate.

Contract source: research/WEAK_EARLY_PHASE2_2022_FRESH_VALIDATION_20260914.md
at commit d9792122a541847c3e4ed82604bffa220dab4a33.

This entrypoint deliberately stops at the frozen gated candidate ledger. It does
not calculate performance summaries and does not implement/modify production.
It never reads 2026 rows: input is clipped before feature construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tvfree_screener"))
import v9_conditional_quality_research as v9  # noqa: E402

TAIL_START = "2022-06-01"
TAIL_END = "2022-12-31"
TAIL_GATE = 0.999
MED_RET5_MAX = 0.0
RET10_MAX = 0.5735294117647058
# January 2023 is retained only so late-December signal rows can obtain the
# already-fixed next-open -> fifth-session-close target during prepare().
RAW_CUTOFF = "2023-01-31"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out-dir", default="research/out/2022_primary_reconstruction")
    args = ap.parse_args()

    cache = Path(args.cache)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(cache, parse_dates=["date"], dtype={"symbol": str})
    raw = raw[raw["date"] <= RAW_CUTOFF].copy()
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "open", "high", "low", "close", "volume"])
    raw = raw.sort_values(["symbol", "date"]).reset_index(drop=True)

    q = v9.prepare(raw)
    tail = v9.generate_tail_pool(q, TAIL_START, TAIL_END)
    # v9.score_tail_month already applies tail_cdf >= 0.999; assert the frozen contract.
    if tail.empty or not (tail["tail_cdf"] >= TAIL_GATE).all():
        raise RuntimeError("Tail reconstruction violated frozen tail gate")

    gated = tail[(tail["med_ret5"] <= MED_RET5_MAX) & (tail["ret10"] <= RET10_MAX)].copy()
    tail = tail.sort_values(["date", "symbol"]).reset_index(drop=True)
    gated = gated.sort_values(["date", "symbol"]).reset_index(drop=True)

    tail_path = out / "primary_2022_extreme_tail_candidates.csv"
    gate_path = out / "primary_2022_weak_early_gated_rows.csv"
    tail.to_csv(tail_path, index=False)
    gated.to_csv(gate_path, index=False)

    receipt = {
        "status": "research_only",
        "authoritative_commit": "d9792122a541847c3e4ed82604bffa220dab4a33",
        "source_cache": str(cache),
        "source_cache_sha256": sha256(cache),
        "raw_cutoff": RAW_CUTOFF,
        "tail_period": [TAIL_START, TAIL_END],
        "tail_gate": TAIL_GATE,
        "weak_early_gate": {"med_ret5_lte": MED_RET5_MAX, "ret10_lte": RET10_MAX},
        "tail_rows": int(len(tail)),
        "gated_rows": int(len(gated)),
        "gated_signal_dates": int(gated["date"].nunique()),
        "tail_artifact": str(tail_path),
        "tail_sha256": sha256(tail_path),
        "gated_artifact": str(gate_path),
        "gated_sha256": sha256(gate_path),
        "historical_target": {"tail_rows": 89, "gated_rows": 29, "gated_signal_dates": 23},
        "historical_identity": bool(len(tail) == 89 and len(gated) == 29 and gated["date"].nunique() == 23),
        "performance_metrics_computed": False,
        "production_writes": False,
    }
    rp = out / "reconstruction_receipt.json"
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
