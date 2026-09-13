# Core stability disposition — 2026-09-14

Research-only. Production remains unchanged.

## Method correction
The first disposition draft incorrectly described run `34765954141` as using the canonical next-open -> fifth-session-close endpoint. It does not. `reconstruct_4h_from_1h.add_daily_context()` defines `ret5bd = target_close / candidate_session_close - 1`, so the stability/cost audit is a **signal-session-close -> fifth XTKS-session close** study.

This matters because the supervisor contract requires new comparable research to use:
- entry: next official XTKS session open;
- exit: fifth official XTKS session close after entry.

Therefore the prior `REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT` statement is withdrawn as a canonical-endpoint conclusion. The old audit remains valid descriptive evidence for the legacy signal-close endpoint only.

## Legacy-endpoint evidence retained
GitHub Actions run: `34765954141` (success).
Artifact: `tentei-cloud-core-stability`, id `10321056091`, SHA-256 `cc5d5071dfb7b6924d3d1ed46fe14a20be95d95ed476f61374706f677392fed9`.

Signal-close endpoint, zero cost:
- DEV 2024-11..2025-06: n=169, mean +1.3068%, median +1.2422%, win 58.58%, Top3-ex +0.9894%.
- 2025H2: n=140, mean +0.0808%, median -0.2389%, win 45.00%, Top3-ex -0.3498%.
- 2026YTD: n=118, mean +1.5555%; report-only.

Signal-close endpoint, assumed 0.5% round-trip cost:
- DEV: mean +0.8068%, median +0.7422%, win 55.62%, Top3-ex +0.4894%.
- 2025H2: mean -0.4192%, median -0.7389%, win 41.43%, Top3-ex -0.8498%.

These figures show the architecture is weak under the old endpoint, but they are not sufficient for the canonical replacement decision.

## Corrective decision
**CANONICAL_DISPOSITION_PENDING_NEXT_OPEN_REPLAY.**

Before rejecting or promoting the current fixed reconstructed Core, rerun the exact unchanged candidate set with the canonical endpoint. Do not change the candidate rule, thresholds, cooldown, periods, or costs while repairing the label definition.

Already rejected pruning paths remain closed:
- broad-market hard regime gates;
- simple local single-feature hard gates;
- positive peer-momentum hard gates.

2026 remains report-only and cannot rescue/tune the candidate.

## New-family preregistration status
`CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json` remains a valid outcome-unopened preregistration, but its execution is deferred until the canonical endpoint repair for the current fixed Core is complete. This avoids replacing an architecture on the basis of a mismatched endpoint.
