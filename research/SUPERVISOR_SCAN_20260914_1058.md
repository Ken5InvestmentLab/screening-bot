# Supervisor cross-lane scan — 2026-09-14 10:58 JST

Research-only. Production/main and all production integrations remain untouched.

## Branch reconciliation

- `research/tvfree-canonical-batch02` actual HEAD: `c5ea4d3fe0d12fbb9effc341a24a406dad4285d8` (previous processed `83a64ff84531665e04e3ff5110ce731a53e17a18`). Ten commits were new to coordination state. They are Shadow/Data integrity work only: continuity-safe resolve CLI/write boundary plus a pinned XTKS session-calendar guard. No V20 H1/H2 outcome was opened. Dedicated XTKS calendar CI run `34795620704` is SUCCESS. V20 raw acceptance remains blocked at 1806/1810 symbols and 734 canonical-active symbol/date gaps; performance stays unopened.
- `research/tentei-cloud-mtf` actual HEAD remains `2429a6f9dcd9cd1f73b501efe510bb29fc0cc33f`; no new Core delta. Current fixed Core and Failed-Breakdown Reclaim remain REJECT; locked H2 unopened.
- `research/consensus-atr-regime-gate` actual HEAD: `a137ef8b1e48968997f8d2f32a719d308aaa533f` (previous processed `92218001d86890e99e6108ec729dc6cb5acc2443`). Eight new commits added an outcome-blind Yahoo canary and exact-251 rate-safe direct retry workflow/spec/handoff.

## Consensus V47 exact-251 retry result

Authoritative retry workflow `34796618901` completed SUCCESS. Artifact `consensus-v47-restored-daily-direct-retry-34796618901` was inspected before any strategy outcomes.

Receipt:
- requested symbols: 251
- provider controls: 7203 returned HTTP 200 at both start and end, 420 daily rows each
- direct usable historical codes: 2 (`3079`, `5660`)
- terminal HTTP historical codes: 249
- unresolved/retryable/provider-failure symbols: 0
- strategy outcomes read: false
- model scores read: false

Interpretation: the earlier all-429 result was provider throttling, but under normal provider conditions 249/251 codes are genuinely terminal on the direct current-code Yahoo path. Those 249 may now advance only to the preregistered official JPX/company identity-continuity verification path. Automatic alias heuristics/provider substitution remain forbidden. Daily V47 acceptance is still not passed, so raw1H/features/NOCAP/CAP1000_PIT performance remain closed.

## Cross-lane decision

Final GO/NO-GO is not ready. Current blockers:
1. V20 raw acceptance still fails (734 active symbol/date gaps; H1/H2 unopened).
2. V47 daily PIT coverage still fails until the 249 terminal codes are resolved through official identity continuity and the two direct-usable recoveries are incorporated into a new accepted materialization receipt.
3. No passing canonical 5BD Core replacement exists.

No lane is allowed to use 2026 for tuning or to alter the canonical next-XTKS-open -> fifth-XTKS-close endpoint.
