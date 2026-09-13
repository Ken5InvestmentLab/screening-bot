# Consensus V44 handoff / lane ownership

Updated: 2026-09-14 JST

## Active experiment
- Experiment: CONSENSUS-V44-TOPK-COOLDOWN-REPLACEMENT-20260914
- Branch: research/consensus-atr-regime-gate
- GitHub Actions run: 34765427789
- Workflow: No-TV Consensus V44 TopK Cooldown
- Trigger commit: c6e2ff2c70b0e659dfb8f2c1a1af204bb37c091c
- Current state when recorded: in_progress
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
