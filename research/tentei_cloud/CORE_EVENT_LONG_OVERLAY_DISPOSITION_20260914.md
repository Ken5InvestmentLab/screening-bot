# Core disposition — canonical event long-overlay audit — 2026-09-14

## Scope
Research-only disposition of workflow run `34788539483` / artifact `tentei-cloud-event-long-overlay`.

This audit is **not** a new canonical 5BD Core mechanism. It consumes the canonical event detection source and overlays the previously tested long-horizon daily Deep/Wick conditions, so it overlaps the Canonical/Event lane and the separate 40BD role diagnostic. It must not enter the canonical Core candidate ranking.

## Artifact findings
Coverage receipt:
- 2025H1: event_rows=0, daily_context_matched=0, executable40=0.
- 2025H2: event_rows=0, daily_context_matched=0, executable40=0.
- 2026_MATURED: event_rows=46, daily_context_matched=41, mature40=37, executable40=35.

The artifact rows show the preserved 2025 canonical event detections with blank `date`, so they cannot be joined to daily context or evaluated under this consumer integration. This is a source-key limitation, not evidence that the 2025 event policy had zero signals.

2026 matured report-only metrics:
- EVENT_ONLY: n=35, mean -15.529%, median -27.241%, win 22.86%, >=30% 14.29%, >=50% 8.57%, <=-20% 57.14%, max +107.35%, min -77.39%, Top1-ex -19.14%, Top3-ex -25.04%, Top5-ex -29.42%.
- EVENT_PLUS_DEEP: n=1, return +72.922%.
- EVENT_PLUS_WICK: n=0.
- EVENT_PLUS_ANY_LONG_OVERLAY: n=1, return +72.922%.

The single Deep overlap is not selection evidence: it is n=1 and belongs to the already-viewed 2026 report-only period. It may not justify a gate, score, threshold, or combined model.

## Decision
`DIAGNOSTIC_ONLY_NOT_CORE_EVIDENCE`

- Do not promote, reject, or retune canonical 5BD Core from this audit.
- Do not use the n=1 2026 Deep overlap to design an Event/Core blend.
- Do not repair/reconstruct the 2025 canonical event source from this Core lane; Canonical/Event owns event reconstruction and V20.
- Keep current fixed Core and Failed-Breakdown Reclaim REJECTED; locked reclaim H2 remains unopened.
- The newly identified PIT daily-volume leakage blocker also means historical research using an absolute prior-day volume gate is provisional until PIT daily-volume semantics are corrected. Do not use return outcomes to tune around it.
- Until a genuinely different low-DOF canonical 5BD Core mechanism is preregistered before outcome access, Core remains on cross-lane integrity/reproducibility/endpoint audit duty.

Production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater remain untouched.
