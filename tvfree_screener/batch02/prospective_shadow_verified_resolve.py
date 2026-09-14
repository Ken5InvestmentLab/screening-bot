from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Mapping, Sequence

from prospective_shadow import resolve_shadow_file
from prospective_shadow_endpoint_completeness_guard import audit_endpoint_completeness
from prospective_shadow_resolution_continuity_guard import compare_resolution_snapshots

COMPLETENESS_RECEIPT_TYPE = "PROSPECTIVE_SHADOW_ENDPOINT_COMPLETENESS_RECEIPT"


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(payload) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha_payload(payload) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("each resolved JSONL row must be an object")
            rows.append(item)
    return rows


def build_endpoint_completeness_receipt(
    *,
    input_path: Path,
    daily_rows: Sequence[Mapping],
    sessions: Sequence[str],
    completeness: Mapping,
) -> dict:
    """Build an outcome-blind receipt for the exact pre-write completeness decision."""
    core = {
        "receipt_type": COMPLETENESS_RECEIPT_TYPE,
        "schema_version": 1,
        "decision": str(completeness.get("decision", "")),
        "endpoint_completeness_valid": completeness.get("endpoint_completeness_valid") is True,
        "shadow_input_sha256": _sha256(input_path),
        "daily_rows_sha256": _sha_payload(list(daily_rows)),
        "session_calendar_sha256": _sha_payload(list(sessions)),
        "completeness_result_sha256": _sha_payload(dict(completeness)),
        "mature_candidate_count": int(completeness.get("mature_candidate_count", 0)),
        "pending_candidate_count": int(completeness.get("pending_candidate_count", 0)),
        "required_endpoint_pair_count": int(completeness.get("required_endpoint_pair_count", 0)),
        "missing_required_endpoint_pair_count": int(completeness.get("missing_required_endpoint_pair_count", 0)),
        "invalid_required_endpoint_price_count": int(completeness.get("invalid_required_endpoint_price_count", 0)),
        "missing_required_endpoint_symbol_count": int(completeness.get("missing_required_endpoint_symbol_count", 0)),
        "endpoint_contract": "CANONICAL_NEXT_XTKS_OPEN_TO_FIFTH_XTKS_CLOSE",
        "strategy_outcomes_opened": False,
        "gross_returns_computed": False,
        "production_authorized": False,
    }
    core["receipt_sha256"] = _sha_payload(core)
    return core


def write_immutable_endpoint_completeness_receipt(path: Path, receipt: Mapping) -> None:
    """Create once. Exact replay is idempotent; conflicting overwrite is forbidden."""
    payload = _canonical_bytes(dict(receipt))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return
        raise FileExistsError(f"conflicting endpoint completeness receipt already exists: {path}")
    with path.open("xb") as f:
        f.write(payload)


def verified_resolve_shadow_file(
    input_path: Path,
    output_path: Path,
    daily_rows: Iterable[Mapping],
    sessions: Sequence[str],
    *,
    completeness_receipt_path: Path | None = None,
) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    before_sha = _sha256(output_path)

    materialized_daily_rows = [dict(row) for row in daily_rows]
    session_list = [str(value) for value in sessions]
    shadow_rows = _load_jsonl(input_path)
    daily_by_key: dict[tuple[str, str], Mapping] = {}
    duplicate_daily_keys: list[str] = []
    for row in materialized_daily_rows:
        symbol = str(row.get("symbol", "")).strip().replace(".0", "").upper()
        date = str(row.get("date", ""))[:10]
        key = (symbol, date)
        if key in daily_by_key:
            duplicate_daily_keys.append(f"{symbol}|{date}")
        daily_by_key[key] = row

    completeness = audit_endpoint_completeness(shadow_rows, daily_by_key, session_list)
    if duplicate_daily_keys:
        completeness = dict(completeness)
        errors = list(completeness.get("errors", []))
        errors.append(f"daily_duplicate_symbol_date:{len(set(duplicate_daily_keys))}")
        completeness["errors"] = errors
        completeness["endpoint_completeness_valid"] = False
        completeness["decision"] = "BLOCK_SHADOW_ENDPOINT_RESOLUTION"
        completeness["duplicate_daily_symbol_dates"] = sorted(set(duplicate_daily_keys))

    completeness_receipt = build_endpoint_completeness_receipt(
        input_path=input_path,
        daily_rows=materialized_daily_rows,
        sessions=session_list,
        completeness=completeness,
    )
    if completeness_receipt_path is None:
        receipt_dir = output_path.parent / ".prospective_shadow_receipts"
        completeness_receipt_path = receipt_dir / (
            f"{output_path.name}.endpoint-completeness."
            f"{completeness_receipt['receipt_sha256']}.json"
        )
    write_immutable_endpoint_completeness_receipt(completeness_receipt_path, completeness_receipt)

    if not completeness.get("endpoint_completeness_valid", False):
        return {
            "resolved_written": False,
            "decision": "BLOCK_ENDPOINT_COMPLETENESS_FAILURE",
            "endpoint_completeness": completeness,
            "endpoint_completeness_receipt_sha256": completeness_receipt["receipt_sha256"],
            "endpoint_completeness_receipt_path": str(completeness_receipt_path),
            "output_sha256_before": before_sha,
            "output_sha256_after": _sha256(output_path),
            "integrity": {
                "endpoint_completeness_checked_before_resolution": True,
                "completeness_receipt_emitted_before_resolved_write": True,
                "completeness_receipts_append_only": True,
                "resolved_history_preserved_on_failure": True,
                "strategy_outcomes_opened_by_completeness_gate": False,
                "production_modified": False,
            },
        }

    with TemporaryDirectory(dir=output_path.parent) as tmp:
        staged = Path(tmp) / "resolved.jsonl"
        resolution = resolve_shadow_file(input_path, staged, materialized_daily_rows, session_list)
        previous_rows = _load_jsonl(output_path)
        current_rows = _load_jsonl(staged)
        continuity = compare_resolution_snapshots(previous_rows, current_rows)

        if not continuity.get("resolution_continuity_valid", False):
            return {
                "resolved_written": False,
                "decision": "BLOCK_RESOLUTION_CONTINUITY_FAILURE",
                "resolution": resolution,
                "continuity": continuity,
                "endpoint_completeness": completeness,
                "endpoint_completeness_receipt_sha256": completeness_receipt["receipt_sha256"],
                "endpoint_completeness_receipt_path": str(completeness_receipt_path),
                "output_sha256_before": before_sha,
                "output_sha256_after": _sha256(output_path),
                "integrity": {
                    "staged_before_replace": True,
                    "endpoint_completeness_checked_before_resolution": True,
                    "completeness_receipt_emitted_before_resolved_write": True,
                    "completeness_receipts_append_only": True,
                    "resolved_history_preserved_on_failure": True,
                    "production_modified": False,
                },
            }

        staged.replace(output_path)

    after_sha = _sha256(output_path)
    return {
        "resolved_written": True,
        "decision": "VERIFIED_RESOLUTION_WRITE_COMPLETE",
        "resolution": resolution,
        "continuity": continuity,
        "endpoint_completeness": completeness,
        "endpoint_completeness_receipt_sha256": completeness_receipt["receipt_sha256"],
        "endpoint_completeness_receipt_path": str(completeness_receipt_path),
        "output_sha256_before": before_sha,
        "output_sha256_after": after_sha,
        "integrity": {
            "staged_before_replace": True,
            "endpoint_completeness_checked_before_resolution": True,
            "completeness_receipt_emitted_before_resolved_write": True,
            "completeness_receipts_append_only": True,
            "continuity_required_before_replace": True,
            "resolved_rows_immutable_after_first_resolution": True,
            "production_modified": False,
        },
    }
