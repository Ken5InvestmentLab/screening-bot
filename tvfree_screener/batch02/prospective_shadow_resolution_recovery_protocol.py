from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from tvfree_screener.batch02.prospective_shadow_resolution_recovery import (
    classify_resolution_recovery_state,
)

RECOVERY_RECORD_TYPE = "PROSPECTIVE_SHADOW_RESOLUTION_RECOVERY_RECORD"


def _canonical_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha_payload(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def build_recovery_record(
    chain: Sequence[Mapping[str, object]],
    current_resolved_sha256: str,
    *,
    chain_valid: bool,
) -> dict:
    """Build outcome-blind append-only evidence for resolver startup recovery state.

    The record never repairs, truncates, deletes, or rewrites immutable chain history.
    A sidecar-ahead interruption is classified as recoverable evidence only; callers
    must still explicitly decide whether to complete or abort the interrupted write.
    """
    state = classify_resolution_recovery_state(
        chain,
        current_resolved_sha256,
        chain_valid=chain_valid,
    )
    core = {
        "record_type": RECOVERY_RECORD_TYPE,
        "schema_version": 1,
        "state": state.state,
        "current_resolved_sha256": state.current_resolved_sha256,
        "tail_resolved_sha256": state.tail_resolved_sha256,
        "prior_resolved_sha256": state.prior_resolved_sha256,
        "recovery_allowed": state.recovery_allowed,
        "reason": state.reason,
        "strategy_outcomes_opened": False,
        "gross_returns_computed": False,
        "production_authorized": False,
        "immutable_chain_rewritten": False,
    }
    core["record_sha256"] = _sha_payload(core)
    return core


def write_immutable_recovery_record(path: Path, record: Mapping[str, object]) -> None:
    """Create recovery evidence once; exact replay is idempotent, conflict fails closed."""
    payload = _canonical_bytes(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return
        raise FileExistsError(f"conflicting recovery record already exists: {path}")
    with path.open("xb") as f:
        f.write(payload)
