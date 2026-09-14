from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable, Mapping

CHAIN_RECEIPT_TYPE = "PROSPECTIVE_SHADOW_RESOLUTION_CHAIN_LINK"


def _canonical_bytes(payload) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha_payload(payload) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _aware_timestamp(value: object) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    return dt


def _verify_resolution_receipt_self_hash(receipt: Mapping) -> str:
    body = dict(receipt)
    stated = str(body.pop("receipt_sha256", "")).strip()
    if not stated or stated != _sha_payload(body):
        raise ValueError("resolution receipt self-hash mismatch")
    return stated


def build_chain_link(*, resolution_receipt: Mapping, previous_link: Mapping | None = None) -> dict:
    resolution_sha = _verify_resolution_receipt_self_hash(resolution_receipt)
    created_at = str(resolution_receipt.get("created_at", "")).strip()
    current_ts = _aware_timestamp(created_at)
    experiment_id = str(resolution_receipt.get("experiment_id", "")).strip()
    model_freeze_id = str(resolution_receipt.get("model_freeze_id", "")).strip()
    resolved_output_sha = str(resolution_receipt.get("resolved_output_sha256", "")).strip()
    if not experiment_id or not model_freeze_id or not resolved_output_sha:
        raise ValueError("resolution receipt identity/output provenance required")

    core = {
        "receipt_type": CHAIN_RECEIPT_TYPE,
        "schema_version": 1,
        "created_at": created_at,
        "experiment_id": experiment_id,
        "model_freeze_id": model_freeze_id,
        "resolution_receipt_sha256": resolution_sha,
        "resolved_output_sha256": resolved_output_sha,
        "previous_chain_link_sha256": None,
        "previous_resolution_receipt_sha256": None,
        "previous_resolved_output_sha256": None,
        "production_authorized": False,
        "note": "Append-only cross-run chain for prospective-shadow resolution receipts; blocks replay and rollback.",
    }

    if previous_link is not None:
        previous = dict(previous_link)
        previous_stated = str(previous.pop("chain_link_sha256", "")).strip()
        if not previous_stated or previous_stated != _sha_payload(previous):
            raise ValueError("previous chain link self-hash mismatch")
        if previous_link.get("receipt_type") != CHAIN_RECEIPT_TYPE:
            raise ValueError("previous chain link type mismatch")
        if previous_link.get("experiment_id") != experiment_id or previous_link.get("model_freeze_id") != model_freeze_id:
            raise ValueError("cross-run identity changed")
        previous_ts = _aware_timestamp(previous_link.get("created_at"))
        if current_ts <= previous_ts:
            raise ValueError("resolution receipt created_at must strictly increase")
        if resolution_sha == previous_link.get("resolution_receipt_sha256"):
            raise ValueError("resolution receipt replay detected")
        if resolved_output_sha == previous_link.get("resolved_output_sha256"):
            raise ValueError("resolved output replay detected")
        core.update(
            {
                "previous_chain_link_sha256": str(previous_link.get("chain_link_sha256")),
                "previous_resolution_receipt_sha256": str(previous_link.get("resolution_receipt_sha256")),
                "previous_resolved_output_sha256": str(previous_link.get("resolved_output_sha256")),
            }
        )

    core["chain_link_sha256"] = _sha_payload(core)
    return core


def verify_chain(links: Iterable[Mapping]) -> dict:
    errors: list[str] = []
    seen_receipts: set[str] = set()
    seen_outputs: set[str] = set()
    previous: Mapping | None = None

    for index, raw in enumerate(links):
        link = dict(raw)
        body = dict(link)
        stated = str(body.pop("chain_link_sha256", "")).strip()
        if link.get("receipt_type") != CHAIN_RECEIPT_TYPE:
            errors.append(f"link_{index}:receipt_type_mismatch")
        if link.get("production_authorized") is not False:
            errors.append(f"link_{index}:production_authorized_must_be_false")
        if not stated or stated != _sha_payload(body):
            errors.append(f"link_{index}:chain_link_sha256_mismatch")

        try:
            current_ts = _aware_timestamp(link.get("created_at"))
        except Exception:
            current_ts = None
            errors.append(f"link_{index}:created_at_invalid")

        resolution_sha = str(link.get("resolution_receipt_sha256", "")).strip()
        output_sha = str(link.get("resolved_output_sha256", "")).strip()
        if not resolution_sha:
            errors.append(f"link_{index}:resolution_receipt_sha256_missing")
        if not output_sha:
            errors.append(f"link_{index}:resolved_output_sha256_missing")
        if resolution_sha in seen_receipts:
            errors.append(f"link_{index}:resolution_receipt_replay")
        if output_sha in seen_outputs:
            errors.append(f"link_{index}:resolved_output_rollback_or_replay")

        if previous is None:
            if any(link.get(field) not in (None, "") for field in (
                "previous_chain_link_sha256",
                "previous_resolution_receipt_sha256",
                "previous_resolved_output_sha256",
            )):
                errors.append(f"link_{index}:genesis_previous_reference_present")
        else:
            if link.get("experiment_id") != previous.get("experiment_id") or link.get("model_freeze_id") != previous.get("model_freeze_id"):
                errors.append(f"link_{index}:identity_changed")
            if link.get("previous_chain_link_sha256") != previous.get("chain_link_sha256"):
                errors.append(f"link_{index}:previous_chain_link_sha256_mismatch")
            if link.get("previous_resolution_receipt_sha256") != previous.get("resolution_receipt_sha256"):
                errors.append(f"link_{index}:previous_resolution_receipt_sha256_mismatch")
            if link.get("previous_resolved_output_sha256") != previous.get("resolved_output_sha256"):
                errors.append(f"link_{index}:previous_resolved_output_sha256_mismatch")
            try:
                previous_ts = _aware_timestamp(previous.get("created_at"))
                if current_ts is not None and current_ts <= previous_ts:
                    errors.append(f"link_{index}:created_at_not_strictly_increasing")
            except Exception:
                pass

        seen_receipts.add(resolution_sha)
        seen_outputs.add(output_sha)
        previous = link

    valid = not errors
    return {
        "valid": valid,
        "decision": "ALLOW_RESOLUTION_CHAIN_APPEND" if valid else "BLOCK_RESOLUTION_CHAIN_INVALID",
        "links": len(list(links)) if isinstance(links, list) else None,
        "errors": errors,
        "integrity": {
            "append_only": True,
            "receipt_replay_forbidden": True,
            "resolved_output_rollback_forbidden": True,
            "strict_time_order": True,
            "identity_pinned": True,
            "production_modified": False,
            "selects_on_performance": False,
        },
    }
