# Prospective shadow verified resolution boundary — 2026-09-14

Research-only Shadow/Data integrity work. No strategy outcomes were used for model/threshold/candidate selection and no production path was modified.

## Problem closed

The append side was already fail-closed, but `resolve_shadow_file()` rewrites the separate resolved JSONL. Without an explicit continuity boundary, a later daily-data/session-calendar change could silently mutate an already recorded 5BD endpoint.

## Implemented contract

- `prospective_shadow_resolution_continuity_guard.py`
  - candidate identity/order must preserve the prior prefix;
  - new candidates may append only after that prefix;
  - `PENDING_5BD -> UNRESOLVED_ENDPOINT/RESOLVED` is allowed;
  - `UNRESOLVED_ENDPOINT -> RESOLVED` is allowed only with unchanged entry/exit dates;
  - `RESOLVED -> PENDING/UNRESOLVED` is forbidden;
  - once resolved, entry date, exit date, entry open, exit close, and `ret5bd_gross` are immutable;
  - return consistency is mechanically checked as `exit_close / entry_open - 1`;
  - no performance-based selection is performed.
- `prospective_shadow_verified_resolve.py`
  - writes the newly calculated resolution snapshot to a temporary file first;
  - compares it with the existing snapshot;
  - replaces the existing resolved JSONL only after continuity passes;
  - on failure, the existing resolved file is left byte-for-byte unchanged.
- `prospective_shadow_cli.py resolve`
  - now uses the verified resolver instead of the direct overwrite path;
  - exits nonzero when continuity fails.

## Commits

- `ba3a7020cfedbf7c24091dbf854ac6d29e1616f4` — resolution continuity guard.
- `82ec671aa3b782c1a78385a696308f96cc70fb27` — continuity contract tests.
- `8ed3b5ebb4df3afb442485cfdd3297756e1d388a` — verified staged resolution writer.
- `7fa8007061af76b8476caabd32a0f6a6f60a8acb` — verified writer tests.
- `73ae086000545cac20c5f27a5fc56595aaa0019b` — CLI resolve routed through verified writer.
- `d89b33c964a0603b5e390ac38bcf7f3ddbc0a93d` — CLI rewrite-blocking regression test.
- `51e53f274995e578ae95d68130fd8346e353aaa0` — CI extended through guard + writer + CLI.
- `4748c7596aa3205abbf705296790ddb798ccba5a` — CI package-path fix.

## Verification

Expanded GitHub Actions run `34795406123` initially failed because the workflow executed from `tvfree_screener/batch02` without the repository root on `PYTHONPATH`; the guard/writer tests themselves passed before the package import error.

After fixing the workflow environment, run `34795438012` completed **SUCCESS**:

- 20 tests run;
- 20 passed;
- resolved endpoint mutation is blocked;
- the prior resolved file is preserved on failure;
- pending/unresolved rows may advance causally to resolved;
- candidate removal/reordering is blocked;
- CLI-level resolve cannot bypass the continuity guard.

## Lane isolation

This work does not alter V20 Event logic, Core logic, Consensus V47 logic, model scores, thresholds, candidate selection, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production/main.

V20 strategy outcomes remain closed while its raw-data acceptance/repair lane is handled by the dedicated Canonical/Event worker.
