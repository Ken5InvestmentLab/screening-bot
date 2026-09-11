#!/usr/bin/env python3
"""Compare a current reproducibility manifest with frozen run #80 (TEST ONLY).

The guard distinguishes source/universe drift from unexplained model-output
change. It only demands exact frozen V3 output hashes when the historical input
contract itself is byte-for-byte comparable.

No production writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_BASELINE = Path("tvfree_screener/fixed_baseline_run80.json")
DEFAULT_MANIFEST = Path("tvfree_screener/out/reproducibility_manifest.json")
DEFAULT_REPORT = Path("tvfree_screener/out/fixed_baseline_guard_report.json")

FROZEN_OUTPUTS = [
    "v3_short_reconstruction_core.csv",
    "v3_short_reconstruction_defensive.csv",
    "v3_swing_v2_s_picks.csv",
]


def evaluate(baseline: dict, current: dict) -> dict:
    bh = baseline["hashes"]

    universe_now = (current.get("universe") or {}).get("sha256")
    cache = current.get("cache") or {}
    coverage_now = cache.get("historical_date_symbol_sha256")
    ohlcv_now = cache.get("historical_ohlcv_sha256")

    source_checks = {
        "universe": {
            "baseline": bh["universe_sha256"],
            "current": universe_now,
            "match": universe_now == bh["universe_sha256"],
        },
        "historical_date_symbol": {
            "baseline": bh["historical_date_symbol_sha256"],
            "current": coverage_now,
            "match": coverage_now == bh["historical_date_symbol_sha256"],
        },
        "historical_ohlcv": {
            "baseline": bh["historical_ohlcv_sha256"],
            "current": ohlcv_now,
            "match": ohlcv_now == bh["historical_ohlcv_sha256"],
        },
    }
    comparable = all(x["match"] for x in source_checks.values())

    output_checks = {}
    for name in FROZEN_OUTPUTS:
        current_hash = ((current.get("outputs") or {}).get(name) or {}).get("historical_sha256")
        expected = bh[name]
        output_checks[name] = {
            "baseline": expected,
            "current": current_hash,
            "match": current_hash == expected,
        }

    outputs_match = all(x["match"] for x in output_checks.values())
    if comparable and outputs_match:
        status = "exact_baseline_reproduced"
    elif comparable and not outputs_match:
        status = "ERROR_model_output_changed_with_identical_inputs"
    else:
        status = "source_or_universe_drift_not_exactly_comparable"

    return {
        "status": status,
        "exact_input_comparable": comparable,
        "frozen_v3_outputs_match": outputs_match,
        "source_checks": source_checks,
        "output_checks": output_checks,
        "policy": (
            "Identical frozen inputs require identical frozen V3 outputs. "
            "When source/universe hashes drift, do not attribute output drift to model code "
            "until the source difference is investigated."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--out", default=str(DEFAULT_REPORT))
    args = ap.parse_args()

    with open(args.baseline, "r", encoding="utf-8") as fh:
        baseline = json.load(fh)
    with open(args.manifest, "r", encoding="utf-8") as fh:
        current = json.load(fh)

    report = evaluate(baseline, current)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["status"] == "ERROR_model_output_changed_with_identical_inputs":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
