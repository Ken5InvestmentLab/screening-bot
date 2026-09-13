from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prospective_shadow import resolve_shadow_file
from prospective_shadow_admission_gate import evaluate_shadow_admission
from prospective_shadow_admission_receipt import build_admission_receipt
from prospective_shadow_append_guard import compare_append_only_snapshots
from prospective_shadow_verified_append import verified_append


def _candidate_rows() -> list[dict]:
    common = {
        "experiment_id": "SYNTHETIC-SHADOW-E2E",
        "model_freeze_id": "SYNTHETIC-FREEZE-001",
        "source_tag": "RAW_CAUSAL_INTRADAY",
        "eligibility_status": "ELIGIBLE",
        "data_sufficient": True,
        "skip_reason": None,
        "missing_fields": [],
    }
    return [
        {
            **common,
            "symbol": "1111.T",
            "signal_date": "2026-09-15",
            "bin_name": "AM_09_13",
            "feature_cutoff": "2026-09-15T13:00:00+09:00",
            "rank": 1,
        },
        {
            **common,
            "symbol": "2222.T",
            "signal_date": "2026-09-16",
            "bin_name": "PM_13_CLOSE",
            "feature_cutoff": "2026-09-16T15:30:00+09:00",
            "rank": 2,
        },
    ]


def run_synthetic_shadow_e2e() -> dict:
    manifest = {
        "experiment_id": "SYNTHETIC-SHADOW-E2E",
        "model_freeze_id": "SYNTHETIC-FREEZE-001",
        "frozen_at": "2026-09-14T00:00:00+09:00",
        "model_spec_sha256": "a" * 64,
    }
    rows = _candidate_rows()

    admission = evaluate_shadow_admission(manifest, rows)
    if not admission.get("admitted"):
        return {
            "decision": "BLOCK_SYNTHETIC_E2E",
            "stage": "admission",
            "admission": admission,
        }

    receipt = build_admission_receipt(
        manifest,
        rows,
        admission,
        "2026-09-16T15:31:00+09:00",
    )

    sessions = [
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
        "2026-09-21",
        "2026-09-22",
        "2026-09-23",
        "2026-09-24",
    ]
    daily_rows = [
        {"symbol": "1111.T", "date": "2026-09-16", "open": 100.0, "close": 101.0},
        {"symbol": "1111.T", "date": "2026-09-22", "open": 110.0, "close": 120.0},
        {"symbol": "2222.T", "date": "2026-09-17", "open": 200.0, "close": 201.0},
    ]

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        shadow_path = root / "shadow.jsonl"
        resolved_path = root / "resolved.jsonl"

        old_lines: list[str] = []
        append_result = verified_append(shadow_path, manifest, rows, admission, receipt)
        if not append_result.get("appended"):
            return {
                "decision": "BLOCK_SYNTHETIC_E2E",
                "stage": "verified_append",
                "admission": admission,
                "append": append_result,
            }

        new_lines = shadow_path.read_text(encoding="utf-8").splitlines()
        append_guard = compare_append_only_snapshots(old_lines, new_lines)
        if not append_guard.get("append_only_valid"):
            return {
                "decision": "BLOCK_SYNTHETIC_E2E",
                "stage": "append_guard",
                "append": append_result,
                "append_guard": append_guard,
            }

        duplicate_result = verified_append(shadow_path, manifest, rows, admission, receipt)
        duplicate_lines = shadow_path.read_text(encoding="utf-8").splitlines()
        duplicate_guard = compare_append_only_snapshots(new_lines, duplicate_lines)
        if not duplicate_guard.get("append_only_valid"):
            return {
                "decision": "BLOCK_SYNTHETIC_E2E",
                "stage": "duplicate_append_guard",
                "duplicate_append": duplicate_result,
                "duplicate_guard": duplicate_guard,
            }

        resolution = resolve_shadow_file(shadow_path, resolved_path, daily_rows, sessions)
        resolved_rows = [json.loads(line) for line in resolved_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    statuses = [row.get("status") for row in resolved_rows]
    resolved = [row for row in resolved_rows if row.get("status") == "RESOLVED"]
    unresolved = [row for row in resolved_rows if row.get("status") == "UNRESOLVED_ENDPOINT"]

    checks = {
        "admission_pass": admission.get("admitted") is True,
        "eligibility_pass": admission.get("eligibility_guard", {}).get("eligibility_valid") is True,
        "verified_append_pass": append_result.get("appended") is True,
        "two_candidates_appended": append_result.get("append_result", {}).get("added") == 2,
        "duplicate_reappend_is_idempotent": duplicate_result.get("append_result", {}).get("added") == 0 and duplicate_result.get("append_result", {}).get("skipped_duplicate") == 2,
        "append_only_history_preserved": append_guard.get("append_only_valid") is True and duplicate_guard.get("append_only_valid") is True,
        "one_row_resolved": len(resolved) == 1,
        "one_row_left_unresolved_without_imputation": len(unresolved) == 1,
        "canonical_endpoint_dates": bool(resolved) and resolved[0].get("entry_date") == "2026-09-16" and resolved[0].get("exit_date") == "2026-09-22",
        "resolution_statuses_expected": statuses == ["RESOLVED", "UNRESOLVED_ENDPOINT"],
    }
    ok = all(checks.values())
    return {
        "decision": "SYNTHETIC_E2E_PASS" if ok else "SYNTHETIC_E2E_FAIL",
        "checks": checks,
        "admission": admission,
        "receipt": receipt,
        "append": append_result,
        "duplicate_append": duplicate_result,
        "append_guard": append_guard,
        "duplicate_guard": duplicate_guard,
        "resolution": resolution,
        "resolved_statuses": statuses,
        "integrity": {
            "synthetic_data_only": True,
            "explicit_eligibility_required": True,
            "receipt_required_before_append": True,
            "live_admission_replayed_before_append": True,
            "opens_real_strategy_returns": False,
            "uses_2026_historical_outcomes_for_tuning": False,
            "changes_model": False,
            "changes_thresholds": False,
            "production_modified": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_synthetic_shadow_e2e(), ensure_ascii=False, indent=2, sort_keys=True))
