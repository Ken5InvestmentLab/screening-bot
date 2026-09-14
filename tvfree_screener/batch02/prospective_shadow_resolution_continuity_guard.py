from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Mapping

ALLOWED_STATUSES = {"PENDING_5BD", "UNRESOLVED_ENDPOINT", "RESOLVED"}
CANDIDATE_FIELDS = (
    "key",
    "experiment_id",
    "model_freeze_id",
    "symbol",
    "signal_date",
    "bin_name",
    "feature_cutoff",
    "source_tag",
    "score",
    "rank",
    "payload_sha256",
)
RESOLUTION_FIELDS = ("entry_date", "exit_date", "entry_open", "exit_close", "ret5bd_gross")
ALLOWED_TRANSITIONS = {
    "PENDING_5BD": {"PENDING_5BD", "UNRESOLVED_ENDPOINT", "RESOLVED"},
    "UNRESOLVED_ENDPOINT": {"UNRESOLVED_ENDPOINT", "RESOLVED"},
    "RESOLVED": {"RESOLVED"},
}


def _canonical_key(row: Mapping) -> str:
    fields = ("experiment_id", "model_freeze_id", "symbol", "signal_date", "bin_name")
    values = [str(row.get(field, "")).strip() for field in fields]
    if any(not value for value in values):
        raise ValueError("candidate identity fields are required")
    return "|".join(values)


def _row_key(row: Mapping) -> str:
    expected = _canonical_key(row)
    actual = str(row.get("key", "")).strip()
    if not actual:
        raise ValueError("key is required")
    if actual != expected:
        raise ValueError(f"key does not match candidate identity: expected={expected} actual={actual}")
    return actual


def _same_value(left, right) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return left == right


def _validate_row(row: Mapping, *, row_number: int, label: str) -> list[str]:
    errors: list[str] = []
    try:
        _row_key(row)
    except ValueError as exc:
        errors.append(f"{label}_row_{row_number}:{exc}")
        return errors

    status = str(row.get("status", "")).strip()
    if status not in ALLOWED_STATUSES:
        errors.append(f"{label}_row_{row_number}:unsupported_status:{status}")
        return errors

    if status == "PENDING_5BD":
        leaked = [field for field in RESOLUTION_FIELDS if row.get(field) not in (None, "")]
        if leaked:
            errors.append(f"{label}_row_{row_number}:pending_contains_resolution_fields:{','.join(leaked)}")
        return errors

    if not str(row.get("entry_date", "")).strip() or not str(row.get("exit_date", "")).strip():
        errors.append(f"{label}_row_{row_number}:endpoint_dates_required")

    if status == "UNRESOLVED_ENDPOINT":
        leaked = [field for field in ("entry_open", "exit_close", "ret5bd_gross") if row.get(field) not in (None, "")]
        if leaked:
            errors.append(f"{label}_row_{row_number}:unresolved_contains_resolved_fields:{','.join(leaked)}")
        return errors

    try:
        entry_open = float(row["entry_open"])
        exit_close = float(row["exit_close"])
        ret = float(row["ret5bd_gross"])
    except (KeyError, TypeError, ValueError):
        errors.append(f"{label}_row_{row_number}:resolved_numeric_fields_invalid")
        return errors

    if not math.isfinite(entry_open) or not math.isfinite(exit_close) or entry_open <= 0 or exit_close <= 0:
        errors.append(f"{label}_row_{row_number}:resolved_prices_must_be_finite_positive")
        return errors
    expected = exit_close / entry_open - 1.0
    if not math.isfinite(ret) or abs(ret - expected) > 1e-12:
        errors.append(f"{label}_row_{row_number}:ret5bd_gross_inconsistent")
    return errors


def _index_rows(rows: list[dict], label: str) -> tuple[list[str], dict[str, dict], list[str]]:
    keys: list[str] = []
    by_key: dict[str, dict] = {}
    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        errors.extend(_validate_row(row, row_number=i, label=label))
        try:
            key = _row_key(row)
        except ValueError:
            continue
        if key in by_key:
            errors.append(f"{label}_row_{i}:duplicate_key:{key}")
            continue
        keys.append(key)
        by_key[key] = row
    return keys, by_key, errors


def compare_resolution_snapshots(
    previous_rows: Iterable[Mapping],
    current_rows: Iterable[Mapping],
) -> dict:
    previous = [dict(row) for row in previous_rows]
    current = [dict(row) for row in current_rows]
    prev_keys, prev_by_key, errors = _index_rows(previous, "previous")
    curr_keys, curr_by_key, curr_errors = _index_rows(current, "current")
    errors.extend(curr_errors)

    if len(curr_keys) < len(prev_keys):
        errors.append("candidate_rows_removed")
    elif curr_keys[: len(prev_keys)] != prev_keys:
        errors.append("candidate_order_or_prefix_changed")

    for key in prev_keys:
        old = prev_by_key[key]
        new = curr_by_key.get(key)
        if new is None:
            errors.append(f"candidate_missing:{key}")
            continue

        for field in CANDIDATE_FIELDS:
            if not _same_value(old.get(field), new.get(field)):
                errors.append(f"candidate_field_changed:{key}:{field}")

        old_status = str(old.get("status", ""))
        new_status = str(new.get("status", ""))
        if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
            errors.append(f"invalid_status_transition:{key}:{old_status}->{new_status}")
            continue

        if old_status in {"UNRESOLVED_ENDPOINT", "RESOLVED"}:
            for field in ("entry_date", "exit_date"):
                if old.get(field) != new.get(field):
                    errors.append(f"endpoint_date_changed:{key}:{field}")

        if old_status == "RESOLVED":
            for field in RESOLUTION_FIELDS:
                if not _same_value(old.get(field), new.get(field)):
                    errors.append(f"resolved_field_changed:{key}:{field}")

    valid = not errors
    return {
        "resolution_continuity_valid": valid,
        "decision": "ALLOW_RESOLUTION_SNAPSHOT_UPDATE" if valid else "BLOCK_RESOLUTION_SNAPSHOT_UPDATE",
        "previous_rows": len(previous),
        "current_rows": len(current),
        "new_rows": max(0, len(current) - len(previous)),
        "previous_resolved": sum(1 for row in previous if row.get("status") == "RESOLVED"),
        "current_resolved": sum(1 for row in current if row.get("status") == "RESOLVED"),
        "errors": errors,
        "integrity": {
            "resolved_rows_are_immutable": True,
            "resolved_to_unresolved_regression_forbidden": True,
            "unresolved_endpoint_dates_are_pinned": True,
            "candidate_prefix_must_be_preserved": True,
            "new_appended_candidates_allowed": True,
            "compares_returns_only_for_immutability": True,
            "selects_on_performance": False,
            "changes_model_or_thresholds": False,
            "production_modified": False,
        },
    }


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("each JSONL row must be an object")
            rows.append(item)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Fail-closed continuity guard for prospective-shadow 5BD resolution snapshots")
    ap.add_argument("--previous", type=Path, required=True)
    ap.add_argument("--current", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    result = compare_resolution_snapshots(_load_jsonl(args.previous), _load_jsonl(args.current))
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    raise SystemExit(0 if result["resolution_continuity_valid"] else 2)


if __name__ == "__main__":
    main()
