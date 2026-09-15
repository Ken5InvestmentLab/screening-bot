from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ResolutionRecoveryState:
    state: str
    current_resolved_sha256: str
    tail_resolved_sha256: str | None
    prior_resolved_sha256: str | None
    recovery_allowed: bool
    reason: str


def classify_resolution_recovery_state(
    chain: Sequence[Mapping[str, object]],
    current_resolved_sha256: str,
    *,
    chain_valid: bool,
) -> ResolutionRecoveryState:
    """Classify crash-consistency state without mutating immutable provenance.

    This helper is deliberately outcome-blind.  It only compares already-recorded
    resolution-chain hashes with the SHA of the currently durable resolved file.
    It never rewrites, truncates, or deletes chain history.
    """
    current = str(current_resolved_sha256).lower()
    if not chain_valid:
        return ResolutionRecoveryState(
            "invalid_tampered", current, None, None, False,
            "resolution chain failed cryptographic/structural verification",
        )
    if not chain:
        return ResolutionRecoveryState(
            "uninitialized", current, None, None, False,
            "no immutable resolution-chain history exists",
        )

    tail = str(chain[-1].get("resolved_output_sha256") or "").lower() or None
    prior = None
    if len(chain) >= 2:
        prior = str(chain[-2].get("resolved_output_sha256") or "").lower() or None

    if tail == current:
        return ResolutionRecoveryState(
            "committed", current, tail, prior, False,
            "chain tail matches currently durable resolved output",
        )
    if prior == current and tail is not None:
        return ResolutionRecoveryState(
            "sidecar_ahead_interrupted", current, tail, prior, True,
            "verified chain advanced one link while resolved output remained at prior committed SHA",
        )
    return ResolutionRecoveryState(
        "invalid_tampered", current, tail, prior, False,
        "current resolved SHA matches neither verified tail nor immediately prior committed SHA",
    )
