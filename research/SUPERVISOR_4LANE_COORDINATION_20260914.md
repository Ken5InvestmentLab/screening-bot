# Supervisor 4-lane coordination — 2026-09-14

This file is the cross-lane coordination contract for the four parallel ChatGPT research lanes. It is research-only. Production main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater remain untouched.

## Global rules
- Goal: a TradingView-free JPX individual-stock system that can compete with the current benchmark on forward 5BD performance and robustness, while preserving right-tail capture.
- Stable★6 / Sniper / Mega are benchmark/context only, never components that the replacement depends on.
- Final scoring logic must be 4H/intraday-led. Daily data may be used for completed-day context, canonical 5BD labels, repair/reconciliation, or explicit fallback; do not fabricate AM/PM or 4H bars from one daily row.
- Canonical evaluation endpoint for new comparable research: enter at the next official XTKS session open and exit at the fifth official XTKS session close. Keep any legacy signal-close metrics clearly separate.
- 2026 outcomes are report/robustness evidence only. Do not choose thresholds, models, gates, cooldowns, or candidate families from 2026 returns.
- Do not compare headline means across different populations/endpoints as if they were the same experiment. Always state universe, period, entry/exit, cooldown, costs, and selection policy.
- Preserve all preregistration/freeze artifacts. A rejected family may not be resurrected by renaming and retuning it on already-opened outcomes.

## The four active lanes
1. **Event-specific V12/V17/V18 lane** — branch `research/tvfree-canonical-batch02`.
   - Owns V12 event generation, V17 cross-sectional representation, V18 quantile evaluation.
   - V17 classifier H1 is rejected; do not tune it on opened H1.
   - V18 is a new frozen target-family experiment. Open H2 only if a frozen H1 policy passes its preregistered gate.
   - Must not duplicate Core breadth pruning or Consensus V44.

2. **Prospective shadow + data-integrity lane** — also branch `research/tvfree-canonical-batch02`.
   - Owns append-only prospective shadow evidence, freeze/integrity guards, daily-anchor reconstruction boundaries, and causal intraday-data quality.
   - V12 state-entry was rejected as Monster because +20% capture was far below the frozen Monster gate. Do not retune/relabel it to rescue the result.
   - Daily-only fallback is never the final 4H scoring representation.

3. **Core breadth/stability lane** — branch `research/tentei-cloud-mtf`.
   - Owns fixed reconstructed Core/SAFE stability, uncertainty and breadth diagnostics.
   - Broad-market hard gates, simple local single-feature hard gates, and positive peer-momentum hard gates are already rejected. Do not keep threshold-searching those opened results.
   - Latest fixed-Core stability audit (run 34765762025) is a corrective finding: DEV n=169 mean +1.31%; 2025H2 n=140 mean +0.08%, median -0.24%, win 45.0%, Top3-ex mean -0.35%; 2026YTD n=118 mean +1.56% is report-only. Therefore the current fixed Core is **not a passed replacement candidate**. Do not use the stronger 2026 block to promote it.
   - Next work must either (a) document uncertainty/rejection cleanly or (b) preregister a genuinely new low-DOF Core hypothesis before opening its outcomes.

4. **Consensus specialist lane** — branch `research/consensus-atr-regime-gate`.
   - Owns fixed-min95 Consensus, frozen ATR OOD guard, realistic next-open execution, concentration/episode diagnostics and V44 cooldown-with-replacement.
   - Frozen ATR q90 is a model-version OOD guard, not an adaptive rolling timing rule. Do not tune the cap from 2026.
   - Current headline is heavily concentrated in repeated same-symbol episodes; episode-first mean is near flat. V44 is decisive.
   - If V44 preserves edge with replacements, Consensus remains a candidate specialist. If V44 collapses, demote it to continuation/re-entry/pyramiding research, not a Stable★6 replacement.

## Cross-lane arbitration
- Core is the breadth/stability role; Monster/event-specific work is the right-tail role; Consensus is a specialist role conditional on diversification/generalization.
- Do not blend these lanes into one model merely because one period looks good.
- Final system selection must be based on comparable contracts and must explicitly allow NO TRADE when no lane passes its frozen validity/availability conditions.

## Supervisor correction rule
Before advancing any lane, read this file plus that lane's latest handoff/log. If the lane conflicts with this contract, fix the lane's log/spec first, record the correction, then continue. Do not silently keep an older premise.
