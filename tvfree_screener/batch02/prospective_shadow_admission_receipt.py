from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping


RECEIPT_TYPE = "PROSPECTIVE_SHADOW_ADMISSION_RECEIPT"
ADMIT_DECISION = "ADMIT_PROSPECTIVE_SHADOW_BATCH"


def _canonical_bytes(payload) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(payload) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _normalize_rows(rows: Iterable[Mapping]) -> list[dict]:
    return [dict(r) for r in rows]


def build_admission_receipt(
    manifest: Mapping,
    rows: Iterable[Mapping],
    admission_result: Mapping,
    created_at: str,
) -> dict:
    rows_n = _normalize_rows(rows)
    decision = str(admission_result.get("decision", ""))
    if decision != ADMIT_DECISION or admission_result.get("admitted") is not True:
        raise ValueError("receipt can only be created for an admitted batch")
    if not rows_n:
        raise ValueError("rows must be nonempty")
    if not str(created_at).strip():
        raise ValueError("created_at is required")

    core = {
        "receipt_type": RECEIPT_TYPE,
        "created_at": str(created_at),
        "decision": decision,
        "manifest_sha256": _sha(dict(manifest)),
        "candidate_rows_sha256": _sha(rows_n),
        "admission_result_sha256": _sha(dict(admission_result)),
        "row_count": len(rows_n),
        "experiment_id": str(manifest.get("experiment_id", "")),
        "model_freeze_id": str(manifest.get("model_freeze_id", "")),
        "append_authorized": True,
        "production_authorized": False,
        "note": "Pins the exact admitted shadow batch before append. It does not authorize production use.",
    }
    if not core["experiment_id"] or not core["model_freeze_id"]:
        raise ValueError("manifest experiment_id/model_freeze_id required")
    core["receipt_sha256"] = _sha(core)
    return core


def verify_admission_receipt(
    receipt: Mapping,
    manifest: Mapping,
    rows: Iterable[Mapping],
    admission_result: Mapping,
) -> dict:
    rows_n = _normalize_rows(rows)
    errors: list[str] = []

    if receipt.get("receipt_type") != RECEIPT_TYPE:
        errors.append("receipt_type_mismatch")
    if receipt.get("decision") != ADMIT_DECISION:
        errors.append("receipt_decision_not_admit")
    if admission_result.get("decision") != ADMIT_DECISION or admission_result.get("admitted") is not True:
        errors.append("admission_result_not_admitted")
    if receipt.get("append_authorized") is not True:
        errors.append("append_authorized_must_be_true")
    if receipt.get("production_authorized") is not False:
        errors.append("production_authorized_must_be_false")
    if receipt.get("row_count") != len(rows_n):
        errors.append("row_count_mismatch")
    if receipt.get("experiment_id") != str(manifest.get("experiment_id", "")):
        errors.append("experiment_id_mismatch")
    if receipt.get("model_freeze_id") != str(manifest.get("model_freeze_id", "")):
        errors.append("model_freeze_id_mismatch")
    if receipt.get("manifest_sha256") != _sha(dict(manifest)):
        errors.append("manifest_sha256_mismatch")
    if receipt.get("candidate_rows_sha256") != _sha(rows_n):
        errors.append("candidate_rows_sha256_mismatch")
    if receipt.get("admission_result_sha256") != _sha(dict(admission_result)):
        errors.append("admission_result_sha256_mismatch")

    body = dict(receipt)
    stated = body.pop("receipt_sha256", None)
    if stated != _sha(body):
        errors.append("receipt_sha256_mismatch")

    valid = not errors
    return {
        "valid": valid,
        "decision": "ADMISSION_RECEIPT_VERIFIED" if valid else "BLOCK_APPEND_RECEIPT_INVALID",
        "errors": errors,
        "row_count": len(rows_n),
        "integrity": {
            "pins_manifest": True,
            "pins_candidate_batch": True,
            "pins_admission_result": True,
            "authorizes_production": False,
        },
    }


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    payload = _load_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        payload = payload["rows"]
    if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
        raise ValueError("rows must be a JSON array or JSONL of objects")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Create/verify exact prospective-shadow admission receipts")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--manifest", type=Path, required=True)
    c.add_argument("--rows", type=Path, required=True)
    c.add_argument("--admission", type=Path, required=True)
    c.add_argument("--created-at", required=True)
    c.add_argument("--output", type=Path, required=True)

    v = sub.add_parser("verify")
    v.add_argument("--receipt", type=Path, required=True)
    v.add_argument("--manifest", type=Path, required=True)
    v.add_argument("--rows", type=Path, required=True)
    v.add_argument("--admission", type=Path, required=True)

    args = ap.parse_args()
    manifest = _load_json(args.manifest)
    rows = _load_rows(args.rows)
    admission = _load_json(args.admission)

    if args.cmd == "create":
        receipt = build_admission_receipt(manifest, rows, admission, args.created_at)
        raw = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print(raw, end="")
    else:
        receipt = _load_json(args.receipt)
        result = verify_admission_receipt(receipt, manifest, rows, admission)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0 if result["valid"] else 2)


if __name__ == "__main__":
    main()
