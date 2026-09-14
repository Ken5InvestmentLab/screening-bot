from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Mapping

RECEIPT_TYPE = "PROSPECTIVE_SHADOW_RESOLUTION_RECEIPT"
SUCCESS_DECISION = "VERIFIED_RESOLUTION_WRITE_COMPLETE"


def _canonical_bytes(payload) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha_payload(payload) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_aware_iso(value: object) -> None:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")


def _verify_completeness_receipt_reference(resolve_result: Mapping) -> tuple[str, Path]:
    stated_sha = str(resolve_result.get("endpoint_completeness_receipt_sha256", "")).strip()
    path_text = str(resolve_result.get("endpoint_completeness_receipt_path", "")).strip()
    if not stated_sha or not path_text:
        raise ValueError("resolution receipt requires endpoint completeness receipt provenance")
    path = Path(path_text)
    if not path.exists():
        raise ValueError("endpoint completeness receipt path does not exist")
    payload = json.loads(path.read_text(encoding="utf-8"))
    embedded_sha = str(payload.get("receipt_sha256", "")).strip()
    body = dict(payload)
    body.pop("receipt_sha256", None)
    if embedded_sha != stated_sha or embedded_sha != _sha_payload(body):
        raise ValueError("endpoint completeness receipt self-hash mismatch")
    return stated_sha, path


def build_resolution_receipt(
    *,
    freeze_manifest: Mapping,
    freeze_manifest_path: Path,
    shadow_path: Path,
    daily_path: Path,
    daily_manifest_path: Path,
    sessions_csv_path: Path,
    sessions_manifest_path: Path,
    resolved_path: Path,
    resolve_result: Mapping,
    created_at: str,
) -> dict:
    if resolve_result.get("resolved_written") is not True or resolve_result.get("decision") != SUCCESS_DECISION:
        raise ValueError("resolution receipt requires a successful verified resolution write")
    _parse_aware_iso(created_at)

    experiment_id = str(freeze_manifest.get("experiment_id", "")).strip()
    model_freeze_id = str(freeze_manifest.get("model_freeze_id", "")).strip()
    if not experiment_id or not model_freeze_id:
        raise ValueError("freeze manifest identity required")

    resolved_sha = _sha_file(resolved_path)
    if resolve_result.get("output_sha256_after") != resolved_sha:
        raise ValueError("resolve_result output SHA does not match resolved file")

    provenance_enforced = bool(
        isinstance(resolve_result.get("integrity"), Mapping)
        and resolve_result["integrity"].get("provenance_chain_enforced") is True
    )

    core = {
        "receipt_type": RECEIPT_TYPE,
        "schema_version": 2 if provenance_enforced else 1,
        "created_at": str(created_at),
        "experiment_id": experiment_id,
        "model_freeze_id": model_freeze_id,
        "freeze_manifest_sha256": _sha_file(freeze_manifest_path),
        "shadow_input_sha256": _sha_file(shadow_path),
        "daily_input_sha256": _sha_file(daily_path),
        "daily_manifest_sha256": _sha_file(daily_manifest_path),
        "session_calendar_csv_sha256": _sha_file(sessions_csv_path),
        "session_calendar_manifest_sha256": _sha_file(sessions_manifest_path),
        "resolved_output_sha256": resolved_sha,
        "resolve_result_sha256": _sha_payload(dict(resolve_result)),
        "production_authorized": False,
        "note": "Pins the exact input/output bundle for one prospective-shadow 5BD resolution event.",
    }

    if provenance_enforced:
        completeness_receipt_sha, _ = _verify_completeness_receipt_reference(resolve_result)
        expected_upstream = {
            "daily_endpoint_manifest_sha256": _sha_file(daily_manifest_path),
            "pinned_xtks_calendar_sha256": _sha_file(sessions_csv_path),
            "frozen_selection_ledger_sha256": _sha_file(shadow_path),
        }
        for field, expected in expected_upstream.items():
            if resolve_result.get(field) != expected:
                raise ValueError(f"resolve_result {field} does not match verified artifact")
        core.update(
            {
                "frozen_selection_ledger_sha256": _sha_file(shadow_path),
                "daily_endpoint_manifest_sha256": _sha_file(daily_manifest_path),
                "pinned_xtks_calendar_sha256": _sha_file(sessions_csv_path),
                "endpoint_completeness_receipt_sha256": completeness_receipt_sha,
                "note": "Pins the full verified input/output and completeness-provenance chain for one prospective-shadow 5BD resolution event.",
            }
        )

    core["receipt_sha256"] = _sha_payload(core)
    return core


def verify_resolution_receipt(
    receipt: Mapping,
    *,
    freeze_manifest: Mapping,
    freeze_manifest_path: Path,
    shadow_path: Path,
    daily_path: Path,
    daily_manifest_path: Path,
    sessions_csv_path: Path,
    sessions_manifest_path: Path,
    resolved_path: Path,
    resolve_result: Mapping,
) -> dict:
    errors: list[str] = []

    if receipt.get("receipt_type") != RECEIPT_TYPE:
        errors.append("receipt_type_mismatch")
    if receipt.get("production_authorized") is not False:
        errors.append("production_authorized_must_be_false")
    if receipt.get("experiment_id") != str(freeze_manifest.get("experiment_id", "")).strip():
        errors.append("experiment_id_mismatch")
    if receipt.get("model_freeze_id") != str(freeze_manifest.get("model_freeze_id", "")).strip():
        errors.append("model_freeze_id_mismatch")

    expected_hashes = {
        "freeze_manifest_sha256": _sha_file(freeze_manifest_path),
        "shadow_input_sha256": _sha_file(shadow_path),
        "daily_input_sha256": _sha_file(daily_path),
        "daily_manifest_sha256": _sha_file(daily_manifest_path),
        "session_calendar_csv_sha256": _sha_file(sessions_csv_path),
        "session_calendar_manifest_sha256": _sha_file(sessions_manifest_path),
        "resolved_output_sha256": _sha_file(resolved_path),
        "resolve_result_sha256": _sha_payload(dict(resolve_result)),
    }

    provenance_enforced = int(receipt.get("schema_version", 1)) >= 2
    if provenance_enforced:
        try:
            completeness_receipt_sha, _ = _verify_completeness_receipt_reference(resolve_result)
        except Exception:
            completeness_receipt_sha = ""
            errors.append("endpoint_completeness_receipt_invalid")
        expected_hashes.update(
            {
                "frozen_selection_ledger_sha256": _sha_file(shadow_path),
                "daily_endpoint_manifest_sha256": _sha_file(daily_manifest_path),
                "pinned_xtks_calendar_sha256": _sha_file(sessions_csv_path),
                "endpoint_completeness_receipt_sha256": completeness_receipt_sha,
            }
        )

    for field, expected in expected_hashes.items():
        if receipt.get(field) != expected:
            errors.append(f"{field}_mismatch")

    try:
        _parse_aware_iso(receipt.get("created_at"))
    except Exception:
        errors.append("created_at_invalid")

    body = dict(receipt)
    stated = body.pop("receipt_sha256", None)
    if stated != _sha_payload(body):
        errors.append("receipt_sha256_mismatch")

    valid = not errors
    return {
        "valid": valid,
        "decision": "RESOLUTION_RECEIPT_VERIFIED" if valid else "BLOCK_RESOLUTION_RECEIPT_INVALID",
        "errors": errors,
        "integrity": {
            "pins_freeze_manifest": True,
            "pins_shadow_input": True,
            "pins_daily_input_and_manifest": True,
            "pins_session_calendar_and_manifest": True,
            "pins_completeness_receipt": provenance_enforced,
            "pins_resolved_output": True,
            "pins_resolve_result": True,
            "authorizes_production": False,
        },
    }


def write_immutable_receipt(path: Path, receipt: Mapping) -> None:
    if path.exists():
        raise FileExistsError(f"resolution receipt already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(dict(receipt)))


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify an immutable prospective-shadow resolution receipt")
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--freeze-manifest", type=Path, required=True)
    ap.add_argument("--shadow", type=Path, required=True)
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--daily-manifest", type=Path, required=True)
    ap.add_argument("--sessions-csv", type=Path, required=True)
    ap.add_argument("--sessions-manifest", type=Path, required=True)
    ap.add_argument("--resolved", type=Path, required=True)
    ap.add_argument("--resolve-result", type=Path, required=True)
    args = ap.parse_args()

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    freeze = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    result = json.loads(args.resolve_result.read_text(encoding="utf-8"))
    out = verify_resolution_receipt(
        receipt,
        freeze_manifest=freeze,
        freeze_manifest_path=args.freeze_manifest,
        shadow_path=args.shadow,
        daily_path=args.daily,
        daily_manifest_path=args.daily_manifest,
        sessions_csv_path=args.sessions_csv,
        sessions_manifest_path=args.sessions_manifest,
        resolved_path=args.resolved,
        resolve_result=result,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if out["valid"] else 2)


if __name__ == "__main__":
    main()
