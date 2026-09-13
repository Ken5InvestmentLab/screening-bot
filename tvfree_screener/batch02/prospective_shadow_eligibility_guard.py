from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Mapping

ELIGIBLE_STATUS = "ELIGIBLE"


def evaluate_eligibility_rows(rows: Iterable[Mapping]) -> dict:
    rows_n = [dict(r) for r in rows]
    violations: list[dict] = []

    for index, row in enumerate(rows_n, start=1):
        status = str(row.get("eligibility_status", "")).strip()
        sufficient = row.get("data_sufficient")
        skip_reason = row.get("skip_reason")
        missing_fields = row.get("missing_fields")

        if status != ELIGIBLE_STATUS:
            violations.append({"row": index, "reason": "eligibility_status_not_eligible"})
            continue
        if sufficient is not True:
            violations.append({"row": index, "reason": "data_sufficient_not_true"})
            continue
        if skip_reason not in (None, ""):
            violations.append({"row": index, "reason": "skip_reason_present"})
            continue
        if missing_fields not in (None, "", [], ()):
            violations.append({"row": index, "reason": "missing_fields_present"})

    valid = bool(rows_n) and not violations
    return {
        "eligibility_valid": valid,
        "decision": "ALLOW_ELIGIBLE_SHADOW_ROWS" if valid else "BLOCK_INELIGIBLE_SHADOW_ROWS",
        "checked_rows": len(rows_n),
        "violation_count": len(violations),
        "violations": violations,
        "integrity": {
            "requires_explicit_eligibility_proof": True,
            "requires_data_sufficient_true": True,
            "forbids_skip_reason": True,
            "forbids_missing_fields": True,
            "batch_is_atomic": True,
            "opens_strategy_returns": False,
            "changes_model_or_thresholds": False,
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
    ap = argparse.ArgumentParser(description="Fail-closed eligibility/data-sufficiency guard for prospective-shadow rows")
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    result = evaluate_eligibility_rows(_load_rows(args.rows))
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    raise SystemExit(0 if result["eligibility_valid"] else 2)


if __name__ == "__main__":
    main()
