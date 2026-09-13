# Consensus V44 handoff / lane ownership

Updated: 2026-09-14 JST

## Active experiment
- Experiment: CONSENSUS-V44-TOPK-COOLDOWN-REPLACEMENT-20260914
- Branch: research/consensus-atr-regime-gate
- Valid GitHub Actions run: 34766353425
- Invalid/superseded run: 34765427789 (opened all H2 cooldown metrics before the preregistered development choice; do not use results)
- Workflow: No-TV Consensus V44 TopK Cooldown
- Trigger commit: d11e69056e0c5e34c48d0253e629655eaf45d5a7
- Current state when recorded: corrected locked-validation run in_progress
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
- corrected run 34766353425 is the only valid V44 run.


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
