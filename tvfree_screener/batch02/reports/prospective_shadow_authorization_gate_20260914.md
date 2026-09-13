# Prospective shadow authorization gate verification — 2026-09-14

## Scope
Research-only final authorization gate immediately before prospective-shadow evidence collection. This does not promote any model, does not open strategy returns, and does not modify production.

## Motivation
The supervisor reconciliation now explicitly requires all source-branch HEADs to be re-fetched immediately before any prospective-shadow authorization or cross-lane comparison. A stale readiness snapshot is blocking, not advisory. The prior staleness and ancestry guards are therefore composed into one final authorization boundary.

## Required source branches
- `research/tvfree-canonical-batch02`
- `research/tentei-cloud-mtf`
- `research/consensus-atr-regime-gate`

Each source must satisfy:
- readiness OK
- staleness OK
- ancestry OK
- current HEAD exactly equals the HEAD observed by the authorization payload

Global requirements:
- current supervisor-contract SHA256 exactly equals the expected pinned SHA256
- all source HEADs were re-fetched immediately before authorization
- production isolation confirmed
- historical 2026 tuning forbidden

## Decision
Only if every requirement passes:
`AUTHORIZE_PROSPECTIVE_SHADOW_START`

Otherwise:
`BLOCK_PROSPECTIVE_SHADOW_START`

## Verification
Focused local logic tests: **8/8 PASS**.

Covered cases:
1. all requirements pass -> authorize
2. one stale source lane -> block
3. source HEAD changed despite other flags -> block
4. supervisor contract SHA mismatch -> block
5. immediate HEAD re-fetch not confirmed -> block
6. production isolation not confirmed -> block
7. required source branch missing -> block
8. gate never uses returns, ranks candidates, or modifies production

## Current branch observations before implementation
- event/shadow branch: `6ecb94f1532f0f6b7493f864112c0c806b1639bc`
- Core branch: `6dd089b04db901579fcd0f90ecb8a657ff486acb`
- Consensus branch: `4fe2d76359234863c0c72bc728497b8ba3c4287d`

All three had just synchronized the supervisor contract with Consensus dependencies. These observations are descriptive only and are not themselves a future authorization; a real authorization must re-fetch heads again at that exact decision boundary.

## Integrity
- strategy returns used: false
- candidate ranking performed: false
- model/threshold/cooldown/eligibility changed: false
- production modified: false
- 2026 outcomes opened for tuning: false
