from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def validate_continuity(
    baseline: dict,
    current: dict,
    current_manifest_sha256: str,
    current_model_spec_sha256: str,
) -> dict:
    required = [
        "experiment_id",
        "model_freeze_id",
        "freeze_manifest_sha256",
        "model_spec_sha256",
    ]
    missing = [k for k in required if not baseline.get(k)]
    if missing:
        raise ValueError(f"baseline missing fields: {missing}")

    checks = {
        "experiment_id_unchanged": current.get("experiment_id") == baseline["experiment_id"],
        "model_freeze_id_unchanged": current.get("model_freeze_id") == baseline["model_freeze_id"],
        "freeze_manifest_sha256_unchanged": current_manifest_sha256.lower() == str(baseline["freeze_manifest_sha256"]).lower(),
        "model_spec_sha256_unchanged": current_model_spec_sha256.lower() == str(baseline["model_spec_sha256"]).lower(),
        "manifest_declared_model_spec_sha256_unchanged": str(current.get("model_spec_sha256", "")).lower() == str(baseline["model_spec_sha256"]).lower(),
    }
    intact = all(checks.values())
    return {
        "continuity_intact": intact,
        "decision": "CONTINUE_PROSPECTIVE_SHADOW" if intact else "STOP_AND_ROTATE_FREEZE_ID",
        "checks": checks,
        "baseline_identity": {
            "experiment_id": baseline["experiment_id"],
            "model_freeze_id": baseline["model_freeze_id"],
            "freeze_manifest_sha256": baseline["freeze_manifest_sha256"],
            "model_spec_sha256": baseline["model_spec_sha256"],
        },
        "current_identity": {
            "experiment_id": current.get("experiment_id"),
            "model_freeze_id": current.get("model_freeze_id"),
            "freeze_manifest_sha256": current_manifest_sha256,
            "model_spec_sha256": current_model_spec_sha256,
            "manifest_declared_model_spec_sha256": current.get("model_spec_sha256"),
        },
        "integrity": {
            "model_changes_authorized": False,
            "threshold_changes_authorized": False,
            "feature_changes_authorized": False,
            "ranking_changes_authorized": False,
            "cooldown_changes_authorized": False,
            "eligibility_changes_authorized": False,
            "note": "Any failed continuity check requires a new model_freeze_id and a new prospective evidence stream; historical shadow rows must not be relabeled under the changed freeze.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify prospective shadow freeze continuity")
    ap.add_argument("--baseline-receipt", type=Path, required=True)
    ap.add_argument("--freeze-manifest", type=Path, required=True)
    ap.add_argument("--model-spec", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    baseline = json.loads(args.baseline_receipt.read_text(encoding="utf-8"))
    current = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    result = validate_continuity(
        baseline,
        current,
        sha256_file(args.freeze_manifest),
        sha256_file(args.model_spec),
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")
    if not result["continuity_intact"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
