# Prospective shadow evidence-chain audit verification — 2026-09-14

## Scope

Research-only prospective-shadow infrastructure. No model logic, selection thresholds, production workflows, Discord, Sheets, Stable/Sniper/Mega, or 2026 historical strategy tuning was modified.

## Added

- `prospective_shadow_evidence_chain_audit.py`
- `test_prospective_shadow_evidence_chain_audit.py`

The audit composes the already-separated shadow safeguards into one read-only evidence-chain check. It verifies:

1. freeze identity exists and manifest/spec hashes are valid SHA-256 values;
2. freeze continuity says `CONTINUE_SAME_FREEZE`;
3. append-only integrity is still valid;
4. the performance report is explicitly `PROSPECTIVE_SHADOW_ONLY`;
5. report-time selection/threshold tuning remains disabled;
6. the report contains exactly one `experiment_id|model_freeze_id` partition matching the manifest;
7. maturity and performance-report row/resolved counts agree;
8. resolved counts are sane;
9. when `--require-mature` is used, evidence maturity must have passed.

The audit never uses return magnitudes to decide whether the evidence chain is valid and never authorizes promotion.

## Initial verification

Local equivalent unit execution: **8/8 PASS**.

Covered failures:
- immature evidence when maturity is required;
- freeze partition mismatch;
- maturity/report count mismatch;
- freeze-continuity failure;
- append-only failure;
- report tuning flag enabled;
- malformed model-spec SHA;
- valid pre-maturity evidence chain when maturity is not required.

## Contract reconciliation — 2026-09-14

A follow-up wiring audit found a real producer/consumer schema mismatch: `prospective_shadow_append_guard.py` emits `append_only_valid` plus decision `APPEND_ONLY_OK`, while the evidence-chain audit was reading a synthetic `ok` flag. The unit fixture had reproduced the synthetic field instead of consuming the real append-guard output, so a valid real guard result would have been stopped incorrectly.

Fixed:
- evidence-chain audit now requires the real fields `append_only_valid is true` and `decision == APPEND_ONLY_OK`;
- the CLI now exits non-zero when the composed evidence chain is invalid, so it can act as a blocking preflight rather than a report-only warning;
- tests now create append-guard input through `compare_append_only_snapshots()` itself;
- a legacy `{\"ok\": true}` mock is explicitly rejected;
- a mismatched append decision is explicitly rejected.

Direct contract replay passed the valid real-output path and blocked historical truncation, legacy synthetic `ok`, and decision mismatch. No model outcomes or return magnitudes were used.

## Concurrency / lane isolation

The parallel Event experiment remains separately owned. This Shadow/Data step did not edit or evaluate active Event logic or outcomes.

## Operational meaning

A future frozen candidate can now be reviewed through a provenance gate that consumes the actual append-guard contract. If identity, continuity, append-only history, partitioning, counts, or the append decision disagree, the decision is `STOP_EVIDENCE_REVIEW` and the CLI returns failure rather than silently continuing.

Production modified: **false**.
