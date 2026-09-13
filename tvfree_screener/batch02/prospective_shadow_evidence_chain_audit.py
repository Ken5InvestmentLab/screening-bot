from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Mapping

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def audit_evidence_chain(
    manifest: Mapping,
    continuity: Mapping,
    append_guard: Mapping,
    maturity: Mapping,
    report: Mapping,
    *,
    require_mature: bool = False,
) -> dict:
    experiment_id = manifest.get("experiment_id")
    freeze_id = manifest.get("model_freeze_id")
    manifest_sha = manifest.get("freeze_manifest_sha256")
    model_spec_sha = manifest.get("model_spec_sha256")

    overall = report.get("overall") if isinstance(report.get("overall"), Mapping) else {}
    mat_counts = maturity.get("counts") if isinstance(maturity.get("counts"), Mapping) else {}

    report_rows = int(overall.get("rows", 0) or 0)
    report_resolved = int(overall.get("resolved", 0) or 0)
    maturity_rows = int(mat_counts.get("total_rows", 0) or 0)
    maturity_resolved = int(mat_counts.get("resolved_rows", 0) or 0)

    by_freeze = report.get("by_model_freeze")
    expected_key = f"{experiment_id}|{freeze_id}"
    report_freeze_partition_ok = (
        isinstance(by_freeze, Mapping)
        and set(by_freeze.keys()) == {expected_key}
    )

    append_only_valid = append_guard.get("append_only_valid") is True
    append_decision_valid = append_guard.get("decision") == "APPEND_ONLY_OK"

    checks = {
        "manifest_identity_present": bool(experiment_id) and bool(freeze_id),
        "manifest_hashes_valid": _is_sha256(manifest_sha) and _is_sha256(model_spec_sha),
        "continuity_same_freeze": continuity.get("decision") == "CONTINUE_SAME_FREEZE",
        "append_only_integrity": append_only_valid and append_decision_valid,
        "report_scope_prospective_only": report.get("scope") == "PROSPECTIVE_SHADOW_ONLY",
        "report_tuning_disabled": report.get("selection_or_threshold_tuning_allowed") is False,
        "report_single_freeze_partition": report_freeze_partition_ok,
        "count_consistency": report_rows == maturity_rows and report_resolved == maturity_resolved,
        "count_sanity": 0 <= report_resolved <= report_rows,
        "maturity_policy_respected": (not require_mature) or maturity.get("mature") is True,
    }
    ok = all(checks.values())
    return {
        "ok": ok,
        "decision": "EVIDENCE_CHAIN_OK" if ok else "STOP_EVIDENCE_REVIEW",
        "experiment_id": experiment_id,
        "model_freeze_id": freeze_id,
        "checks": checks,
        "counts": {
            "report_rows": report_rows,
            "report_resolved": report_resolved,
            "maturity_rows": maturity_rows,
            "maturity_resolved": maturity_resolved,
        },
        "integrity": {
            "uses_return_values_for_gate": False,
            "changes_model_or_thresholds": False,
            "promotion_authorized": False,
            "note": "This audit checks evidence provenance/identity/count continuity only; it never promotes a model.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only prospective shadow evidence-chain audit")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--continuity", type=Path, required=True)
    ap.add_argument("--append-guard", type=Path, required=True)
    ap.add_argument("--maturity", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--require-mature", action="store_true")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    result = audit_evidence_chain(
        _load_json(args.manifest),
        _load_json(args.continuity),
        _load_json(args.append_guard),
        _load_json(args.maturity),
        _load_json(args.report),
        require_mature=args.require_mature,
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
