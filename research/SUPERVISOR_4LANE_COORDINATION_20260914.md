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
   - V20 H1 cannot use the old 1,332-symbol raw panel: canonical prior-day H1 eligibility union is **1,810 symbols across 82 sessions**, sorted-list SHA `2437e240d549074594b8584a9e2403a153c20a377bcc9b842dc7f8b538d1516b`. Dedicated fail-closed H1 raw workflow is staged.
   - Do not duplicate V20 in another chat/worker. Do not start its dedicated Yahoo fetch until active V44 Yahoo-heavy runs stop.
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

4. **Consensus specialist lane** — branch `research/consensus-atr-regime-gate`.
   - Owns fixed-min95 Consensus, frozen ATR OOD guard, realistic next-open execution, concentration/overlap diagnostics, V44 cooldown-with-replacement, and staged outcome-free V45 context audits.
   - Current +7.72% headline is materially inflated by repeated same-symbol selections, but the earlier chained "episode-first near flat" diagnostic was too strict for a true 5BD holding policy.
   - Correct one-position-per-symbol five-session cooldown with re-entry gives 2025 n=52 mean +3.05%, Top3-ex +1.21%; 2025H2 n=22 mean +3.58%, Top3-ex -0.81%. Corrected V44 replacement remains decisive for diversification/generalization.
   - The first V44 run that opened all H2 cooldown metrics is invalid/superseded. Only authoritative hardened run `34767664140` may support V44 conclusions once completed and receipt-checked. Runs `34765427789` and `34766353425` are invalid/superseded for final conclusions.
   - Intraday naming correction: integer session `9` / `13` denotes reconstructed Yahoo raw clock bins, **not** an alert known exactly at 09:00 / 13:00 JST. Shared Batch02 causal raw-bin semantics control production claims.
   - Historical universe limitation: V43/V44 use the **2026-09-11 current-listed domestic common-stock universe** backfilled historically. This is reproducible but not point-in-time survivorship-neutral. A surviving Consensus model still needs promotion-grade point-in-time JPX universe validation.
   - Training-target mismatch: current Consensus heads were trained on **signal-bin-close -> D+5 close**, while canonical comparison is **next-XTKS-open -> D+5 close**. On the 2025 five-session no-replacement sample, mean falls from +4.13% to +3.05% and 13.46% of rows change sign.
   - V44 remains interpretable because its policies use one fixed model/ranking and one canonical evaluation endpoint. **Do not change the training target mid-V44.**
   - If V44 survives, any production candidate requires a separately versioned canonical-target retrain with architecture/hyperparameters initially frozen, plus canonical raw-bin materialization and point-in-time universe validation. These dependencies cannot be used to rescue a failed V44.
   - V45 is outcome-free context auditing only and must not rescue V44 through ATR retuning.
   - Authoritative V44 performance must not be interpreted immediately on completion. First run `.github/workflows/no-tv-consensus-v44-acceptance.yml` and require `accepted=true` for baseline reproduction, live-fetch coverage and locked-validation invariants. Strict5 post-run is allowed only after that acceptance receipt passes.
   - If corrected V44 collapses, demote Consensus to continuation/re-entry/pyramiding research rather than a Stable★6 replacement.

## Cross-lane arbitration
- Core is the breadth/stability role; Monster/event-specific work is the right-tail role; Consensus is a specialist role conditional on diversification/generalization.
- Do not blend these lanes into one model merely because one period looks good.
- Final system selection must be based on comparable contracts and must explicitly allow NO TRADE when no lane passes its frozen validity/availability conditions.

## Supervisor correction rule
Before advancing any lane, read this file plus that lane's latest handoff/log. If the lane conflicts with this contract, fix the lane's log/spec first, record the correction, then continue. Do not silently keep an older premise.


## 2026-09-14 supervisor reconciliation addendum
- This coordination file supersedes older per-lane wording where it conflicts with newer branch-local corrective findings.
- Core canonical endpoint repair is complete; the current fixed reconstructed Core is **rejected as a replacement candidate** after 2025H2 fails robustness under next-open -> fifth-close. The separate failed-breakdown-reclaim family remains outcome-unopened.
- Consensus raw-bin labels are semantic reconstruction labels, not exact alert-clock promises.
- Event-specific V12/V17/V18/compression-breakout and canonical Monster-v2 closed decisions must not be reopened by renaming or post-hoc threshold changes.
- Immediately before any prospective-shadow authorization or cross-lane comparison, re-fetch all source-branch HEADs; stale readiness snapshots are blocking, not advisory.

- Consensus promotion dependency clarified: surviving V44 evidence is necessary but not sufficient; canonical-target training, canonical raw-bin semantics, and point-in-time universe membership remain mandatory before a production claim.

- Consensus authoritative V44 live-fetch acceptance guard: before reading performance from run `34767664140`, verify `research/CONSENSUS_V44_RUN_ACCEPTANCE_GUARD_20260914.json`. Required receipts: baseline reproduction pass; requested_symbols=1910; ok_symbols>=1850; candidate_symbols>=1793; candidate_rows>=519163. Any failure => mark fetch-degraded and rerun the exact frozen evaluator later; do not interpret outcomes.

- **Point-in-time split eligibility blocker:** run80 daily OHLC was downloaded with yfinance/Yahoo on 2026-09-11. Yahoo OHLC is split-adjusted historically, so applying historical absolute-price gates such as prior close <= JPY 1,000 directly to the frozen present-basis OHLC can use future corporate-action information. This can create adjusted-only false positives after later forward splits and adjusted-only false negatives around later reverse splits. Until the outcome-free V46 audit reconstructs point-in-time nominal prior-close eligibility, no lane may claim promotion-grade evidence from a run80 backtest whose candidate universe depends on an absolute historical price threshold. Relative-return/shape diagnostics remain usable if their own contract is otherwise valid.
- V46 is owned by the Consensus/data-integrity interface and must remain outcome-free. It may quantify universe changes and corporate-action factors but must not use strategy returns to choose a correction. If material, the corrected PIT eligibility contract must be propagated to any affected lane before final cross-lane arbitration.
