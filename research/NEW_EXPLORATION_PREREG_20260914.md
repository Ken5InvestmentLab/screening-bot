# Parallel New-Condition Exploration — Preregistered Plan

Date: 2026-09-14 JST
Status: PREREGISTERED / RESEARCH-ONLY

## Purpose
Run a new exploration lane in parallel with the frozen Weak+Early Phase-2 program. This lane must not modify or rescue any opened Weak+Early family and must not touch production/main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or watchlist-updater.

## Separation from Weak+Early Phase-2
- Weak+Early Phase-2 remains frozen and continues root-cause / population-scarcity audit.
- No new condition discovered here may be retrofitted into the opened Weak+Early Phase-2 evidence set.
- 2022 fresh outcomes already opened in Weak+Early are NOT discovery/tuning input for this lane.
- 2026 outcomes are report/robustness-only.
- All performance comparisons use transaction cost 0%; win = gross return > 0.
- Canonical endpoint: next XTKS open -> fifth XTKS close.

## Research objective
Search for qualitatively different signal families, not micro-retunes of body_pct / volr20 / mean-rank / DUAL / G3.

Two explicit target archetypes are allowed:
1. Stable-replacement archetype: priority on win >=55%, positive median, Top3-ex durability, sufficient n.
2. Monster archetype: priority on mean / right-tail capture; lower win rate may be acceptable if Top3-ex remains strong and tail dependence is explicitly reported.

## First-wave preregistered families
Only these families are allowed in Wave 1. Thresholds are coarse and sparse; no dense continuous grid search.

A. Compression-to-expansion
- Market/candidate volatility compression followed by causal expansion evidence available before entry.
- Features may include ATR/range compression percentile, prior multi-day realized-vol compression, and current-session causal expansion.

B. Relative-strength / relative-reversal structure
- Candidate move relative to broad market/sector proxy using only information available before entry.
- Purpose: distinguish idiosyncratic early reversal from market-wide drift.

C. Gap / overnight structure
- Prior-close to next-session-open gap context and recent gap history, with no future-bar leakage.
- Test only a small number of directional states (e.g. adverse/neutral/favorable), not a fine threshold sweep.

D. Liquidity / turnover shock structure
- Causal turnover/volume acceleration and abnormal participation, normalized to trailing history.
- Must not duplicate plain volr20 LOW ranking; intended as a different temporal structure rather than another static rank weight.

E. Distance-to-structure
- Distance to causal prior swing high/low, recent range boundary, or trailing breakout/reversal reference.
- No look-ahead pivots.

## Discovery / validation boundary
- Use only a preregistered discovery segment that does not include already-opened 2022 fresh validation as tuning input.
- Preserve at least one untouched holdout or walk-forward block for confirmation before any promotion claim.
- 2026 remains report-only.
- Any family selected after viewing a holdout must be considered opened and cannot be retuned against that holdout.

## Wave-1 acceptance screen
A candidate family may advance only if, at cost 0%:
- sufficient sample size for interpretation;
- stable-replacement path: win >=55%, mean >=+4%, positive median, Top3-ex >=+3%; OR
- monster path: mean >=+6%, Top3-ex >=+4%, with explicit reporting of win/median and tail concentration;
- no single tiny-period artifact dominates the conclusion;
- no post-hoc threshold rescue after opened results.

These are research advancement screens, not production GO criteria.

## Prohibited Wave-1 behavior
- No candidate-level weight optimization across dozens of features.
- No dense threshold grid search.
- No tuning on 2022 fresh outcomes.
- No use of 2026 for selection.
- No changing canonical endpoint, cost contract, or win definition.
- No modification of Weak+Early frozen thresholds or G3 -1% threshold.

## First execution stage
Before any backtest:
1. identify existing causal raw/features already present in repository/artifacts for A-E;
2. classify each as READY / DERIVABLE-CAUSALLY / MISSING;
3. select at most 3 families with the lowest leakage/provenance risk for Wave-1;
4. write a frozen experiment manifest before opening performance.

GO/NO-GO at this stage: NO-GO / exploration initialization only.
