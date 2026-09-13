from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping


def _parse_aware_iso(value: object, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return dt


def evaluate_postfreeze_rows(manifest: Mapping, rows: Iterable[Mapping]) -> dict:
    frozen_at = _parse_aware_iso(manifest.get("frozen_at"), "frozen_at")
    experiment_id = str(manifest.get("experiment_id", "")).strip()
    model_freeze_id = str(manifest.get("model_freeze_id", "")).strip()
    if not experiment_id or not model_freeze_id:
        raise ValueError("manifest experiment_id/model_freeze_id required")

    violations: list[dict] = []
    checked = 0
    for index, row in enumerate(rows, start=1):
        checked += 1
        row_exp = str(row.get("experiment_id", experiment_id)).strip()
        row_freeze = str(row.get("model_freeze_id", model_freeze_id)).strip()
        if row_exp != experiment_id:
            violations.append({"row": index, "reason": "experiment_id_mismatch"})
            continue
        if row_freeze != model_freeze_id:
            violations.append({"row": index, "reason": "model_freeze_id_mismatch"})
            continue
        try:
            cutoff = _parse_aware_iso(row.get("feature_cutoff"), "feature_cutoff")
        except ValueError as exc:
            violations.append({"row": index, "reason": str(exc)})
            continue
        if cutoff <= frozen_at:
            violations.append({
                "row": index,
                "reason": "feature_cutoff_not_strictly_after_freeze",
                "feature_cutoff": cutoff.isoformat(),
                "frozen_at": frozen_at.isoformat(),
            })

    ok = checked > 0 and not violations
    return {
        "postfreeze_valid": ok,
        "decision": "ALLOW_POSTFREEZE_SHADOW_ROWS" if ok else "BLOCK_POSTFREEZE_SHADOW_ROWS",
        "checked_rows": checked,
        "violation_count": len(violations),
        "violations": violations,
        "integrity": {
            "strict_relation": "feature_cutoff > frozen_at",
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
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError("each JSONL row must be an object")
                rows.append(item)
        return rows
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        payload = payload["rows"]
    if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
        raise ValueError("rows file must contain a JSON array of objects or JSONL objects")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Reject prospective-shadow candidates whose decision cutoff is not strictly post-freeze")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    result = evaluate_postfreeze_rows(manifest, _load_rows(args.rows))
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    raise SystemExit(0 if result["postfreeze_valid"] else 2)


if __name__ == "__main__":
    main()
