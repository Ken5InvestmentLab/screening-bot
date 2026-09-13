# Prospective shadow snapshot staleness guard — 2026-09-14

## Scope
Research-only supervisor/data-integrity infrastructure. No strategy returns opened, no model/threshold/ranking/cooldown/eligibility changes, no production writes.

## Motivation
Readiness snapshots can become stale immediately when parallel research branches advance. A previously READY candidate must not remain authorized from an old snapshot after its source branch HEAD changes.

Observed during this work:
- `research/tvfree-canonical-batch02` HEAD: `4799a535a258d62e14e05d76080d5a4683e2a1ef`
- `research/tentei-cloud-mtf` HEAD: `d20f0b27c0d6b89ed234c579bf2811c98b1a7381`
- `research/consensus-atr-regime-gate` HEAD advanced to `e92178959167a54a546f537bfa15a2abcf8b5e21` with a reproducible Consensus uncertainty audit.

## Added
- `prospective_shadow_snapshot_staleness.py`
- `test_prospective_shadow_snapshot_staleness.py`

The guard compares each candidate snapshot's `observed_head` with the current branch HEAD. Any mismatch or unavailable current HEAD marks the candidate snapshot stale and blocks prospective-shadow start from that snapshot, even if it had previously been READY.

## Local functional verification
6/6 PASS:
1. unchanged HEAD keeps a READY snapshot eligible;
2. advanced HEAD makes it stale and blocks start;
3. unavailable current HEAD is stale;
4. not-ready stays blocked even when fresh;
5. mixed candidates report correct fresh/stale counts;
6. no return/performance fields are required or opened.

## Decision
`SNAPSHOT_STALENESS_GUARD_READY`

Operational rule: re-fetch branch HEADs immediately before any shadow-start authorization. If a source branch changed, regenerate readiness from the new exact HEAD; never carry forward the prior authorization.
