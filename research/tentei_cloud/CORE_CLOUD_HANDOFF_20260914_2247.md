# Core + Cloud handoff — 2026-09-14 22:47 JST

## Start-state check

- Start HEAD: `30ddf9120188fd62cc5d29d2ab235df58b4e94e0`.
- Coordination STATE had the same Core `last_seen_sha` and `last_processed_sha`; no unprocessed Core SHA was duplicated.
- Latest Core action remains `34799307163` (`Precision Discovery Batch`) SUCCESS; it is legacy rejected-family evidence and was not rerun.
- Rejected Core families remain closed: fixed Core, Failed-Breakdown Reclaim, Prior-Close Reclaim, Precision 3-family.

## Cloud forensic

No genuinely new contemporaneous evidence surfaced. Historical `n=63 / mean +9.86%` remains legacy evidence only. Exact replay remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing and no portability replay.

## Work completed this pass

Added `CORE_ENDPOINT_REPRO_AUDIT_20260914_2247.md`. Outcome-blind inspection of the existing canonical endpoint evaluator identified two provenance requirements that must be frozen before any new canonical relabeling is considered reproducible:

1. signal->entry->exit dates must use a pinned XTKS calendar rather than only dates observed in the raw panel;
2. entry-open / exit-close must fail closed on incomplete endpoint rows rather than accept the first/last available row from a partial session.

No performance was recomputed. Cost policy remains 0% only; 2026 remains report-only. Candidate ranking and GO/NO-GO are unchanged.

## Next action

Freeze and implement a data-only endpoint provenance receipt/calendar completeness contract, with tests, without touching candidate logic or reopening rejected families. If new contemporaneous Cloud identity evidence appears, forensic exact replay may resume; otherwise Cloud remains closed.
