# Shadow resolution crash-consistency audit — 2026-09-16

Research-only Canonical/Event + Shadow/Data integrity work. No performance/H1/H2/2026 outcome opened.

## Finding
Current prewrite enforcement correctly makes the immutable resolution receipt and chain link durable before `staged.replace(output_path)`. This closes the earlier failure mode where resolved history could change without durable provenance.

However, that ordering creates a distinct crash-consistency window:

1. prospective receipt is written;
2. prospective chain link is appended;
3. process/filesystem failure occurs before `staged.replace(output_path)` completes.

On the next invocation, the existing chain tail names the staged/new resolved-output SHA while the still-current resolved file retains the prior SHA. Startup therefore fails closed at the chain-head/current-output equality check. This is safe against silent mutation, but it can strand the resolver in a durable sidecar-ahead state requiring explicit recovery.

## Classification
`OUTCOME_BLIND_INTEGRITY_GAP_FAIL_CLOSED_RECOVERY_REQUIRED`

This is not performance evidence and does not alter strategy logic, thresholds, TopN, ranker, cooldown, endpoint, or frozen families.

## Required next safe work unit
Add a research-only crash-consistency protocol and regression coverage before claiming the write boundary fully transaction-safe. Acceptable designs must preserve fail-closed semantics and must not silently delete or rewrite immutable receipts/chain history. A recovery record should distinguish at least:

- committed: chain tail SHA == current resolved SHA;
- sidecar-ahead/interrupted: chain tail SHA != current resolved SHA and prior link SHA == current resolved SHA;
- invalid/tampered: neither current nor prior committed state can be proven.

For interrupted state, recovery must be explicit and provenance-preserving (for example, append-only abort/recovery metadata or a two-phase pending/commit record), never threshold/data relaxation or synthetic reconstruction.

## Evidence inspected before this audit
- Canonical HEAD before work: `90f56dcd426e8d1a85cfd8f38eee5a8afda9d471`.
- Coordination STATE had the same SHA as both `last_seen_sha` and `last_processed_sha`; therefore no prior HEAD was reprocessed.
- Latest relevant Actions were green: `34943281926`, `34943400594`, `34943418395`.
- Existing write-boundary guard status: `RESOLUTION_CHAIN_ENFORCED_AT_PREWRITE_BOUNDARY_CI_GREEN`.

## Guardrails
production/main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater unchanged. 2026 remains report/robustness-only. All future performance, if any, remains cost 0% with win = gross return > 0.
