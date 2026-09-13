# Consensus V44 handoff / lane ownership

Updated: 2026-09-14 JST

## Active experiment
- Experiment: CONSENSUS-V44-TOPK-COOLDOWN-REPLACEMENT-20260914
- Branch: research/consensus-atr-regime-gate
- Authoritative hardened GitHub Actions run: 34767664140
- Superseded locked-validation run: 34766353425 (does not include later baseline/dependency/SHA hardening; do not use conclusions)
- Invalid/superseded run: 34765427789 (opened all H2 cooldown metrics before the preregistered development choice; do not use results)
- Workflow: No-TV Consensus V44 TopK Cooldown
- Trigger commit: fe24a4b2b350a94a20d0c90c04d36ef975e62870
- Current state when recorded: authoritative hardened run in_progress
- Production writes: false

## This lane owns
- fixed-min95 independent Consensus;
- frozen ATR OOD circuit breaker;
- next-open execution audit;
- symbol/concentration/overlap audit;
- Top-K cooldown-with-replacement test.

## Other lanes must not duplicate
Do not independently rerun or retune:
- Consensus ATR q90 gate;
- rolling ATR variants;
- fixed-cap sensitivity;
- same-symbol overlap/cooldown diagnostics;
- V44 3/5-day Top-K replacement experiment.

## This lane does NOT own
- V15/V16 Tentei-inspired representation drift work;
- Core local-quality / failed-breakdown architecture;
- Monster weak+early/body/volume rank work;
- prospective-shadow / batch02 contracts;
- 1H fetch-coverage audit.

## Current conclusions before V44 result
1. Online rolling ATR q90 is rejected; high-volatility observations normalize the failed regime and reopen bad trades.
2. ATR q90 around 2.864 is frozen as an OOD model-version guard, not an adaptive timing rule.
3. 2025 min95 survives next-business-day-open execution delay.
4. Current Top-1 headline is strongly concentrated in repeated same-symbol signals.
5. IMPORTANT CORRECTION: the prior chained "43 episodes / episode-first +0.23%" diagnostic is too strict for a true 5BD holding policy and must not be used as the capital interpretation.
6. Correct one-position-per-symbol 5-session cooldown with re-entry after exit gives 2025 n=52 mean +3.05%, Top3-ex +1.21%; 2025H2 n=22 mean +3.58%, Top3-ex -0.81%.
7. Therefore overlap materially inflates the +7.72% headline, but the edge does not collapse all the way to zero before replacement.
8. Same-day 09/13 duplication is not the main issue; multi-day repeat selection is.
9. Preserved Stable★6 benchmark is far less symbol-concentrated (55 trades / 54 symbols).
10. V44 is the decisive test of whether alternate ranked names can preserve more of the edge under one-position-per-symbol style constraints.


## V44 integrity correction
The first V44 evaluator computed H2 metrics for cooldown 0/3/5 before applying the preregistered development chooser. It did not use those H2 metrics to choose a cooldown, but merely opening/reporting them violated the locked-validation intent.

Correction:
- run 34765427789 is invalidated for research conclusions;
- evaluator commit 9ac2c78e79e2f535f3fbed04703c3188b7b0640b computes DEV metrics for 0/3/5 only;
- DEV chooses at most one of cooldown 3/5 using the frozen preregistration;
- only baseline and that one chosen cooldown may report H2 replacement outcomes;
- losing cooldown H2 metrics are not emitted;
- H2 Top-K candidate export is outcome-blind;
- corrected pre-hardening run 34766353425 is superseded for final conclusions by authoritative hardened run 34767664140;
- **only run 34767664140 may support the final V44 conclusion** once completed and receipt-checked.


## V45 staged next action — not triggered while V44 is fetching Yahoo 1H
A non-overlapping outcome-free follow-up is now preregistered and implemented:
- spec: research/consensus_v45_full_context_atr_preregister.json
- evaluator: research/no_tv_v45_full_context_atr.py
- workflow: .github/workflows/no-tv-consensus-v45.yml
- status: NOT TRIGGERED

Purpose:
- current 2.8640659721 ATR cap came from min95-selected contexts only;
- V45 recomputes Jan-Jun 2025 ATR distribution from every distinct eligible date/session, one context = one vote;
- evaluator reads no strategy-return outcome and opens neither 2025H2 nor 2026 outcomes;
- V45 cannot promote/reject Consensus and cannot silently replace the current cap.

Execution ordering:
- do not run V45 concurrently with V44 because both reconstruct Yahoo 1H across roughly 1,900 symbols and concurrent fetching could create avoidable coverage/rate-limit drift;
- once valid V44 is complete and receipt-checked, trigger V45 if the Consensus lane still has research value;
- if V44 fails, V45 may still run as a diagnostic, but its result must not be used to rescue V44 via ATR retuning.


## Cross-lane intraday semantics correction
The canonical Batch02 data-integrity lane already established that Yahoo 1h timestamps are interval-start and that the 12:00-start row crosses the TSE lunch boundary. It intentionally treats 09/10/11/12 as a raw-source first clock bin rather than an exact exchange morning bar.

Therefore, in V43/V44:
- integer `session=9` means the first reconstructed Yahoo raw clock bin, **not an alert known at 09:00 JST**;
- integer `session=13` means the second raw clock bin, not necessarily an alert known exactly at 13:00 JST;
- old `synthetic_sessions()` is research reconstruction, not production-final exact TradingView/4H semantics.

The current as-of builder is still causal with respect to finalized daily OHLC: it uses only completed prior days plus current raw sessions up to the candidate index. With canonical entry at next XTKS session open, this naming correction does not invalidate V44 return timing, but it blocks any direct production claim until a surviving Consensus model is migrated/retrained on the shared canonical raw-bin materializer.

Detail: `research/CONSENSUS_INTRADAY_SEMANTICS_ALIGNMENT_2026-09-14.md`.


## Universe provenance correction
The preserved run80 daily cache is reproducible but not point-in-time survivorship-neutral:
- source run 34545440155 fetched the **2026-09-11 run-date JPX current-listed domestic common-stock universe** (3,700 symbols);
- historical Yahoo data from 2022 onward was then fetched only for those run-date symbols;
- source manifest itself warns that listings/delistings can change historical backtest membership.

Therefore V43/V44 2025 results can omit stocks that traded in 2025 but were delisted before the 2026-09-11 universe snapshot. V44 remains an internally fair comparison because all cooldown policies use the same frozen universe, but it is not yet a survivorship-free all-TSE historical proof.

Do not attempt outcome-aware manual repair. If Consensus survives V44, promotion-grade validation requires the shared data-integrity lane to provide frozen point-in-time JPX membership. Detail: `research/CONSENSUS_UNIVERSE_PROVENANCE_2026-09-14.md`.


## Training-target alignment dependency
Current Consensus heads are trained on signal-bin-close -> D+5 return, while canonical comparison uses next-XTKS-open -> D+5.

On the correct 5-session no-replacement 2025 sample:
- signal-close mean +4.13%;
- next-open mean +3.05%;
- about 1.08 percentage points are lost between endpoints;
- 13.46% of rows change return sign.

The ranking relationship remains present, so V44's fixed-ranker comparison is still interpretable. Do not change its target mid-run.

If Consensus survives V44, a future separately-versioned experiment should retrain the unchanged architecture on the canonical next-open target before any production claim. Do not use this redesign to rescue a failed V44. Detail: `research/CONSENSUS_TARGET_ALIGNMENT_AUDIT_2026-09-14.md`.


## V44 hardening v3
Run 34766353425 was started before the later reproducibility hardening landed, so it is also superseded for conclusions.

Only run **34767664140** is authoritative. Its trigger commit includes:
- locked H2 validation behavior;
- V43 DEV baseline reproduction guard;
- pinned V43 dependency versions;
- checkout by `github.sha`;
- evidence hashing;
- workflow concurrency for later runs.

Required DEV reproduction receipt:
- cooldown0 n = 67
- mean_pct = 8.424148981560009
- max_symbol_share = 0.44776119402985076

If any receipt item fails, V44 must fail closed before any H2 conclusion is accepted.

An outcome-free exact-tie prevalence audit has also been preregistered. It does not alter the running V44 policy.


## V44 workflow reproducibility hardening
After the corrected evaluator was already running, the workflow was hardened:
- checkout is pinned to the triggering commit SHA instead of a moving branch ref;
- package versions are pinned;
- concurrency uses one branch-specific V44 group with cancel-in-progress for future hardened launches;
- evidence files receive SHA-256 receipts before upload;
- artifact retention is 90 days.

Because run `34767664140` is the first run launched from the hardened workflow, it supersedes the older corrected-but-pre-hardening run `34766353425` for final research conclusions.

At the time of this handoff update, GitHub still displayed the older runs as in-progress. Their eventual output must be ignored even if they finish successfully.


## Frozen H2 pass/fail gate (added before authoritative replacement outcome access)
Source: `research/consensus_v44_h2_validation_gate_addendum.json`.

The single DEV-chosen cooldown passes H2 only if **all** are true:
- n >= 20;
- mean > 0;
- mean >= 80% of cooldown0 H2 baseline mean;
- median >= 0;
- Top3-excluded mean > 0;
- max-symbol share <= 75% of cooldown0 H2 baseline share.

If any condition fails, do not retune on H2. Demote current Consensus from Stable★6 replacement candidate to continuation/re-entry/pyramiding specialist research.


## Authoritative V44 live-fetch acceptance guard

Because invalid/superseded V44 runs were still concurrently fetching Yahoo 1H when authoritative run `34767664140` started, the outcome is not accepted solely because the workflow completes.

Frozen pre-outcome guard:
- `research/CONSENSUS_V44_RUN_ACCEPTANCE_GUARD_20260914.json`
- guard commit: `10d2e193979fc5418364f0af5fb243752c4a8587`

Reference receipt from preserved V43 artifact `10274083399`:
- requested symbols: 1,910
- ok symbols: 1,850
- errors: HTTPError 59 / too_few_sessions 1
- candidate rows: 519,163
- candidate symbols: 1,793

Before interpreting V44 outcomes, the authoritative artifact must satisfy all of:
1. baseline reproduction receipt passed;
2. requested symbols == 1,910;
3. ok symbols >= 1,850;
4. candidate symbols >= 1,793;
5. candidate rows >= 519,163.

If any receipt check fails, mark the run **fetch-degraded** and do not interpret its performance. Rerun the exact frozen evaluator only after the superseded Yahoo-heavy runs are no longer active. No model, ATR, cooldown, Top-K, or validation rule may change.


## Strict 5BD no-overlap interpretation
Source: `research/consensus_v44_strict_5bd_addendum.json`.

A 3-session cooldown may reduce concentration but can reselect a symbol before a D+1-open -> D+5-close position has exited. Therefore:
- cooldown3 is descriptive partial-diversification / re-entry evidence only;
- only cooldown5 can qualify the current Consensus family under a strict one-position-per-symbol 5BD interpretation.

Strict cooldown5 DEV eligibility reuses the original frozen gates:
- mean >= 80% of cooldown0 DEV baseline;
- max-symbol share <= 75% of cooldown0 DEV baseline.

If cooldown5 fails DEV eligibility, do not open its H2 outcome. If it passes, evaluate exactly cooldown5 on the validation-blind pool using the already frozen H2 gate, even if the original 3/5 chooser prefers cooldown3.


## Strict5 contract verification
- workflow: Consensus V44 Strict Contract Tests
- run: 34768248451
- conclusion: SUCCESS
- tested:
  - exact 5-trading-day re-entry boundary;
  - DEV 80% mean-retention boundary;
  - DEV 25% max-symbol-share reduction boundary;
  - H2 all-conditions-required gate;
  - exact cons_min tie prevalence logic.

Failure interpretation is also frozen in `CONSENSUS_V44_FAILURE_DISPOSITION_2026-09-14.md`:
- baseline/data receipt failure = DATA_REPRO_FAILURE, not strategy evidence;
- only after baseline reproduction can return-policy failures be called STRATEGY_FAIL.


## V45 contract verification
- workflow: Consensus V44 Strict Contract Tests (extended to V45 helpers)
- successful run: **34768430860**
- conclusion: SUCCESS
- prior failed helper-test runs: 34768326827 (missing lightweight dependency due eager import), 34768383325 (helper refactor recursion); both were test-infrastructure failures and were fixed before any V45 full-data run.
- verified:
  - one distinct date/session context = one vote;
  - internally inconsistent market context fails closed;
  - ATR q90 is unweighted by candidate count;
  - requested-universe drift fails;
  - <95% V43 candidate-symbol coverage fails.

V45 full Yahoo/data audit remains untriggered until authoritative V44 finishes so it does not add concurrent historical Yahoo load.
