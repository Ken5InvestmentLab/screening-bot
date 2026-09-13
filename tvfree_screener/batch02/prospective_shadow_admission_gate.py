from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Mapping

from shadow_preflight import validate_shadow_export_rows
from prospective_shadow_postfreeze_guard import evaluate_postfreeze_rows
from prospective_shadow_eligibility_guard import evaluate_eligibility_rows


def evaluate_shadow_admission(manifest: Mapping, rows: Iterable[Mapping]) -> dict:
    rows = [dict(r) for r in rows]
    errors: list[str] = []

    try:
        preflight = validate_shadow_export_rows(rows)
    except Exception as exc:
        preflight = {"status": "FAIL", "error": str(exc)}
        errors.append(f"causal_preflight_failed:{exc}")

    try:
        postfreeze = evaluate_postfreeze_rows(manifest, rows)
        if not postfreeze.get("postfreeze_valid", False):
            errors.append("postfreeze_guard_failed")
    except Exception as exc:
        postfreeze = {"postfreeze_valid": False, "decision": "BLOCK_POSTFREEZE_SHADOW_ROWS", "error": str(exc)}
        errors.append(f"postfreeze_guard_error:{exc}")

    try:
        eligibility = evaluate_eligibility_rows(rows)
        if not eligibility.get("eligibility_valid", False):
            errors.append("eligibility_guard_failed")
    except Exception as exc:
        eligibility = {"eligibility_valid": False, "decision": "BLOCK_INELIGIBLE_SHADOW_ROWS", "error": str(exc)}
        errors.append(f"eligibility_guard_error:{exc}")

    admitted = not errors
    return {
        "admitted": admitted,
        "decision": "ADMIT_PROSPECTIVE_SHADOW_BATCH" if admitted else "BLOCK_PROSPECTIVE_SHADOW_BATCH",
        "checked_rows": len(rows),
        "causal_preflight": preflight,
        "postfreeze_guard": postfreeze,
        "eligibility_guard": eligibility,
        "errors": errors,
        "integrity": {
            "requires_causal_postfreeze_and_eligibility_checks": True,
            "requires_explicit_data_sufficiency_proof": True,
            "batch_is_atomic": True,
            "opens_strategy_returns": False,
            "uses_model_scores": False,
            "changes_model": False,
            "changes_thresholds": False,
            "production_modified": False,
        },
    }


def _load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        payload = payload["rows"]
    if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
        raise ValueError("rows must be a JSON array or JSONL of objects")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Unified causal + post-freeze + eligibility admission gate for prospective shadow rows")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    result = evaluate_shadow_admission(manifest, _load_rows(args.rows))
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    raise SystemExit(0 if result["admitted"] else 2)


if __name__ == "__main__":
    main()
