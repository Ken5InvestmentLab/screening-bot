from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
PLACEHOLDER_MARKERS = ("REPLACE_WITH_", "YYYY-MM-DD", "IMMUTABLE_FREEZE_ID")
REQUIRED_FIELDS = ("experiment_id", "model_freeze_id", "frozen_at", "model_spec_sha256")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_freeze_manifest(data: dict, *, expected_model_spec_sha256: str | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        errors.append(f"missing required fields: {missing}")

    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")
            continue
        if any(marker in value for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{field} still contains template placeholder text")

    experiment_id = str(data.get("experiment_id", "")).strip()
    model_freeze_id = str(data.get("model_freeze_id", "")).strip()
    if experiment_id and model_freeze_id and experiment_id == model_freeze_id:
        errors.append("model_freeze_id must be distinct from experiment_id")

    model_spec_sha256 = str(data.get("model_spec_sha256", "")).strip()
    if model_spec_sha256 and not HEX64_RE.fullmatch(model_spec_sha256):
        errors.append("model_spec_sha256 must be exactly 64 hexadecimal characters")

    if expected_model_spec_sha256:
        if not HEX64_RE.fullmatch(expected_model_spec_sha256):
            errors.append("expected_model_spec_sha256 must be exactly 64 hexadecimal characters")
        elif model_spec_sha256.lower() != expected_model_spec_sha256.lower():
            errors.append("model_spec_sha256 does not match expected model spec SHA")

    frozen_at = str(data.get("frozen_at", "")).strip()
    if frozen_at:
        try:
            parsed = datetime.fromisoformat(frozen_at)
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                errors.append("frozen_at must include an explicit timezone offset")
        except ValueError:
            errors.append("frozen_at must be valid ISO-8601 datetime text")

    known = set(REQUIRED_FIELDS) | {"notes"}
    unknown = sorted(set(data) - known)
    if unknown:
        warnings.append(f"unknown fields preserved: {unknown}")

    ready = not errors
    return {
        "ready_for_shadow_ingest": ready,
        "decision": "READY_FOR_SHADOW_INGEST" if ready else "BLOCK_SHADOW_INGEST",
        "errors": errors,
        "warnings": warnings,
        "identity": {
            "experiment_id": experiment_id or None,
            "model_freeze_id": model_freeze_id or None,
            "frozen_at": frozen_at or None,
            "model_spec_sha256": model_spec_sha256 or None,
        },
        "integrity": {
            "uses_strategy_returns": False,
            "uses_model_scores": False,
            "changes_model_or_thresholds": False,
            "promotion_authorized": False,
        },
    }


def validate_freeze_manifest_file(path: Path, *, expected_model_spec_sha256: str | None = None) -> dict:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    result = validate_freeze_manifest(data, expected_model_spec_sha256=expected_model_spec_sha256)
    result["freeze_manifest_sha256"] = sha256_bytes(raw)
    result["freeze_manifest_path"] = str(path)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Outcome-free validator for a prospective shadow freeze manifest")
    ap.add_argument("--freeze-manifest", type=Path, required=True)
    ap.add_argument("--expected-model-spec-sha256")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    result = validate_freeze_manifest_file(
        args.freeze_manifest,
        expected_model_spec_sha256=args.expected_model_spec_sha256,
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")
    if not result["ready_for_shadow_ingest"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
