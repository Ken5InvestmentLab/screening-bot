from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_REQUESTED = 1910
MIN_OK = 1850
MIN_CANDIDATE_SYMBOLS = 1793
MIN_CANDIDATE_ROWS = 519163


def evaluate_acceptance(result: dict) -> dict:
    receipt = result.get("baseline_reproduction_receipt", {}) or {}
    fetch = result.get("hourly_fetch", {}) or {}

    checks = {
        "baseline_reproduction_passed": receipt.get("passed") is True,
        "requested_symbols_exact": int(fetch.get("requested_symbols", -1)) == EXPECTED_REQUESTED,
        "ok_symbols_min": int(fetch.get("ok_symbols", -1)) >= MIN_OK,
        "candidate_symbols_min": int(fetch.get("candidate_symbols", -1)) >= MIN_CANDIDATE_SYMBOLS,
        "candidate_rows_min": int(fetch.get("candidate_rows", -1)) >= MIN_CANDIDATE_ROWS,
        "nonchosen_validation_metrics_unopened": result.get("nonchosen_validation_metrics_opened") is False,
    }
    accepted = all(checks.values())
    return {
        "guard_id": "CONSENSUS-V44-RUN-ACCEPTANCE-GUARD-20260914-01",
        "authoritative_run_id": 34767664140,
        "accepted": bool(accepted),
        "decision": "ACCEPT_FOR_PERFORMANCE_INTERPRETATION" if accepted else "FETCH_OR_RECEIPT_DEGRADED_DO_NOT_INTERPRET",
        "checks": checks,
        "observed": {
            "requested_symbols": fetch.get("requested_symbols"),
            "ok_symbols": fetch.get("ok_symbols"),
            "candidate_symbols": fetch.get("candidate_symbols"),
            "candidate_rows": fetch.get("candidate_rows"),
            "baseline_reproduction_passed": receipt.get("passed"),
            "nonchosen_validation_metrics_opened": result.get("nonchosen_validation_metrics_opened"),
        },
        "performance_fields_inspected": False,
        "production_modified": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v44-json", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()

    result = json.loads(a.v44_json.read_text(encoding="utf-8"))
    receipt = evaluate_acceptance(result)

    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not receipt["accepted"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
