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
1. **Event-specific / Monster lane** — branch `research/tvfree-canonical-batch02`.
   - Owns causal 4H event-family research, V17 stable cross-sectional representation, and Monster/event-specific reconciliation.
   - V12 reversal family is **closed** after 2025H2 within-path degradation: RSI Recovery and Emergency Reversal themselves lost edge. Do not rescue it by threshold tuning, trigger reweighting, or renaming.
   - V17 dual-classifier and V18 quantile ranking are rejected on opened H1 and must not be retuned there.
   - Distinct compression-breakout V20 was rejected in 2024Q4 discovery; 2025 remains unopened for that family.
   - Canonical Monster v2 `ALL_WEAK_EARLY` exact replay is also rejected as a passed policy: 2025 locked replay mean +2.19% and +20% 12.96%, but frozen 0.5%-cost Top1-winner-excluded mean was -0.21%.
   - **Active parallel event experiment:** `TENTEI-4H-V20-SESSION-IMPULSE-CONTINUATION-20260914`. Other chats must not duplicate or pre-empt that experiment while it remains active.
   - Must not duplicate Core breadth/stability or Consensus specialist work.

2. **Prospective shadow + data-integrity lane** — also branch `research/tvfree-canonical-batch02`.
   - Owns append-only prospective shadow evidence, freeze/integrity guards, daily-anchor reconstruction boundaries, and causal intraday-data quality.
   - V12 state-entry was rejected as Monster because +20% capture was far below the frozen Monster gate. Do not retune/relabel it to rescue the result.
   - Daily-only fallback is never the final 4H scoring representation.

3. **Core breadth/stability lane** — branch `research/tentei-cloud-mtf`.
   - Owns fixed reconstructed Core/SAFE stability, uncertainty, breadth diagnostics, and the separately preregistered failed-breakdown-reclaim Core family.
   - IMPORTANT ENDPOINT CORRECTION: the earlier fixed-Core stability run used **signal-session close -> fifth XTKS-session close**, not the canonical next-open endpoint. Therefore its prior rejection is **not** a canonical replacement decision.
   - Canonical disposition is currently **PENDING_NEXT_OPEN_REPLAY**. The exact unchanged fixed-Core candidate set must be relabeled with next official XTKS-session open -> fifth official XTKS-session close before promotion/rejection.
   - Legacy signal-close evidence remains descriptive only: DEV n=169 mean +1.31%; 2025H2 n=140 mean +0.08%, median -0.24%, win 45.0%, Top3-ex -0.35%; 2026YTD +1.56% is report-only.
   - Already rejected pruning paths remain closed: broad-market hard gates, simple local single-feature hard gates, and positive peer-momentum hard gates.
   - `CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json` remains outcome-unopened, but execution is deferred until the canonical endpoint repair for current fixed Core completes.
   - Do not use 2026 to rescue, tune, or promote Core.

4. **Consensus specialist lane** — branch `research/consensus-atr-regime-gate`.
   - Owns fixed-min95 Consensus, frozen ATR OOD guard, realistic next-open execution, concentration/overlap diagnostics, V44 cooldown-with-replacement, and staged outcome-free V45 full-context ATR audit.
   - Current +7.72% headline is materially inflated by repeated same-symbol selections, but the earlier chained "episode-first near flat" diagnostic was too strict for a true 5BD holding policy.
   - Correct one-position-per-symbol five-session cooldown with re-entry gives 2025 n=52 mean +3.05%, Top3-ex +1.21%; 2025H2 n=22 mean +3.58%, Top3-ex -0.81%. V44 replacement remains decisive for diversification/generalization.
   - The first V44 run that opened all H2 cooldown metrics is invalid/superseded. Only the corrected locked-validation V44 run may support conclusions.
   - Intraday naming correction: integer session `9` / `13` denotes reconstructed Yahoo raw clock bins, **not** an alert known exactly at 09:00 / 13:00 JST. Shared Batch02 causal raw-bin semantics control production claims.
   - Even if V44 survives, direct production migration is blocked until the surviving model is migrated/retrained on the canonical raw-bin materializer and timing contract.
   - V45 is outcome-free context auditing only and must not rescue a failed V44 by ATR retuning.
   - If corrected V44 collapses, demote Consensus to continuation/re-entry/pyramiding research rather than a Stable★6 replacement.

## Cross-lane arbitration
- Core is the breadth/stability role; Monster/event-specific work is the right-tail role; Consensus is a specialist role conditional on diversification/generalization.
- Do not blend these lanes into one model merely because one period looks good.
- Final system selection must be based on comparable contracts and must explicitly allow NO TRADE when no lane passes its frozen validity/availability conditions.

## Supervisor correction rule
Before advancing any lane, read this file plus that lane's latest handoff/log. If the lane conflicts with this contract, fix the lane's log/spec first, record the correction, then continue. Do not silently keep an older premise.


## 2026-09-14 supervisor reconciliation addendum
- This coordination file supersedes older per-lane wording where it conflicts with newer branch-local corrective findings.
- Core canonical status is **PENDING_NEXT_OPEN_REPLAY**, not rejected, until the endpoint-repair run completes.
- Consensus raw-bin labels are semantic reconstruction labels, not exact alert-clock promises.
- Event-specific V12/V17/V18/compression-breakout and canonical Monster-v2 closed decisions must not be reopened by renaming or post-hoc threshold changes.
- Immediately before any prospective-shadow authorization or cross-lane comparison, re-fetch all source-branch HEADs; stale readiness snapshots are blocking, not advisory.


## Consensus cross-lane promotion dependencies — 2026-09-14 update
Two data-contract limitations are now explicit and must be checked before any final integration claim:

1. **Raw-bin timing semantics**
   - Consensus V43/V44 integer `session=9` / `session=13` come from the older `synthetic_sessions()` reconstruction.
   - Batch02 data-integrity already established that Yahoo timestamps are interval-start and the 12:00-start row crosses the lunch boundary.
   - Therefore these labels are raw clock bins, not exact 09:00 / 13:00 executable alerts and not exact TradingView 4H bars.
   - Canonical next-open evaluation remains temporally valid, but production promotion requires migration/retraining on the shared causal raw-bin materializer if Consensus survives.

2. **Historical universe provenance**
   - run80 was built from the 2026-09-11 current-listed JPX domestic common-stock snapshot (3,700 symbols), then historical Yahoo data was fetched for those symbols.
   - It is reproducible but not a point-in-time survivorship-neutral 2025 universe.
   - V44 remains an internally fair policy comparison; it is not sufficient evidence for a survivorship-free all-TSE claim.
   - Final promotion requires outcome-independent point-in-time listing membership from the shared data-integrity path.

Do not make the Consensus lane independently duplicate the Batch02 raw-clock or point-in-time-universe work. Treat them as integration dependencies.
