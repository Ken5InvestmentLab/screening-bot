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
   - **Active event experiment:** `TENTEI-4H-V20-SESSION-IMPULSE-CONTINUATION-20260914`, now formally owned by the :12 Canonical/Event worker. The earlier "parallel chat" ownership was retired because no dedicated automation or implementation existed.
   - V20 evaluator + contract tests are frozen; contract CI run `34769637874` passed.
   - V20 H1 cannot use the old 1,332-symbol raw panel: canonical prior-day H1 eligibility union is **1,810 symbols across 82 sessions**, sorted-list SHA `2437e240d549074594b8584a9e2403a153c20a377bcc9b842dc7f8b538d1516b`.
   - V20 dedicated H1 run `34774070956` completed with all four Yahoo fetch shards successful but fail-closed raw coverage verification failed before H1 evaluation. H1 outcomes remain unopened; do not interpret performance or open H2 until the frozen acceptance failure is diagnosed.
   - Must not duplicate Core breadth/stability or Consensus specialist work.

2. **Prospective shadow + data-integrity lane** — also branch `research/tvfree-canonical-batch02`.
   - Owns append-only prospective shadow evidence, freeze/integrity guards, daily-anchor reconstruction boundaries, and causal intraday-data quality.
   - V12 state-entry was rejected as Monster because +20% capture was far below the frozen Monster gate. Do not retune/relabel it to rescue the result.
   - Daily-only fallback is never the final 4H scoring representation.

3. **Core breadth/stability lane** — branch `research/tentei-cloud-mtf`.
   - Owns fixed reconstructed Core/SAFE stability, uncertainty, breadth diagnostics, and the separately preregistered failed-breakdown-reclaim Core family.
   - Canonical endpoint repair is **complete** on the exact unchanged fixed-Core candidate set: next official XTKS-session open -> fifth official XTKS-session close.
   - Canonical DEV at 0.5% cost: n=169, mean +0.712%, median +0.509%, win 55.62%, Top3-ex +0.393%.
   - Canonical 2025H2 at 0.5% cost: n=140, mean **-0.452%**, median **-0.745%**, win **41.43%**, Top1-ex **-0.700%**, Top3-ex **-0.874%**.
   - Even at 0% cost, 2025H2 median is -0.245%, win 45.71%, Top1-ex -0.200% and Top3-ex -0.374%. Therefore the weakness is not just the cost assumption.
   - Decision: **REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT_CANDIDATE** under the canonical endpoint. Do not use the stronger 2026 report-only block to rescue or retune it.
   - Already rejected pruning paths remain closed: broad-market hard gates, simple local single-feature hard gates, and positive peer-momentum hard gates.
   - `CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json` has now been evaluated correctly under the frozen canonical daily context and is **REJECTED at preconfirmation**. Corrected run `34768985489`: DEVELOPMENT mean -0.766%, median -0.832%, win 41.09%; INTERNAL_VALIDATION mean +0.331% but median -0.185%, win 48.13%. Both frozen blocks fail; locked 2025H2 remains unopened. Do not retune or reopen this family.
   - Core executable-entry audit `34774595196` is complete: DEV 169/169, 2025H2 140/140, 2026_YTD 116/118. The only unmatched rows are 4586 and 4709 for 2026-04-20 due to missing raw Yahoo 1H entry-bar/open data; this is report-only coverage diagnosis and does not change rejection decisions.

4. **Consensus specialist lane** — branch `research/consensus-atr-regime-gate`.
   - Owns fixed-min95 Consensus, frozen ATR OOD guard, realistic next-open execution, concentration/overlap diagnostics, V44 cooldown-with-replacement, and staged outcome-free V45 context audits.
   - Authoritative V44 run `34767664140` ended in `DATA_REPRO_FAILURE_DO_NOT_INTERPRET` because DEVELOPMENT baseline n=61 differed from expected 67. No V44 performance promotion evidence is valid from that run.
   - Historical universe limitation and split-adjusted absolute-price leakage are promotion blockers for legacy current-listed/run80 evidence.
   - V46 outcome-free PIT split eligibility audit run `34775030470` is accepted for the V47 data contract: 3700/3700 split coverage, no strategy returns/model scores opened, evidence artifact preserved.
   - Clean V47 materialization must be rebuilt from accepted PIT membership replay plus accepted V46 split evidence. Do not treat post-hoc deletion of current-selected rows as clean.
   - The historical prior-close <= JPY 1,000 rule is **not a global requirement**. V47 compares exactly **NOCAP** versus **CAP1000_PIT** under the same clean PIT model/data/target contract; do not grid-search additional price caps.
   - Performance is primary. Robustness/tail/concentration diagnostics remain mandatory, but causal rare monster winners are not an automatic rejection reason.
   - V47 outcomes must remain closed until PIT membership/daily/intraday/split coverage receipts pass. 2026 outcomes remain report/robustness-only.
   - V45 full-context ATR remains after V46/V47 and cannot rescue failed evidence through retuning.

## Cross-lane arbitration
- Core is the breadth/stability role; Monster/event-specific work is the right-tail role; Consensus is a specialist role conditional on diversification/generalization.
- Do not blend these lanes into one model merely because one period looks good.
- Final system selection must be based on comparable contracts and must explicitly allow NO TRADE when no lane passes its frozen validity/availability conditions.

## Supervisor correction rule
Before advancing any lane, read this file plus that lane's latest handoff/log. If the lane conflicts with this contract, fix the lane's log/spec first, record the correction, then continue. Do not silently keep an older premise.

## 2026-09-14 reconciliation
- Event V12/V17/V18/compression-breakout/canonical Monster-v2 are closed/rejected and may not be reopened by renaming or post-hoc retuning.
- Active Event experiment is V20 Session-Impulse; H1 is blocked on raw coverage acceptance, not performance.
- Core current fixed and Failed-Breakdown Reclaim are rejected; locked reclaim H2 remains unopened.
- Consensus V44 authoritative run is a data-reproduction failure and must not be interpreted for promotion. V46 is accepted outcome-free infrastructure evidence; V47 clean PIT rebuild is the active promotion path.
- Before final arbitration, re-fetch every active branch HEAD and require comparable endpoint/universe/cost/selection contracts.
