# Parallel Condition Exploration — Wave 1

Date: 2026-09-14 JST
Branch: research/parallel-condition-exploration
Status: INITIALIZED / RESEARCH-ONLY

## Contract
This lane is isolated from Weak+Early Phase-2. It may not alter or rescue any opened Weak+Early family. It must not touch production/main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or watchlist-updater.

All new performance work uses transaction cost 0%, win = gross return > 0, canonical endpoint next XTKS open -> fifth XTKS close. 2026 is report/robustness-only. Opened 2022 Weak+Early outcomes are not tuning input for this lane.

## Wave-1 families
A. compression-to-expansion
B. relative-strength / relative-reversal versus causal broad-market context
C. gap / overnight structure
D. liquidity / turnover shock structure distinct from plain volr20 LOW
E. distance-to-causal prior structure (prior swing/range boundary; no look-ahead pivots)

## Archetypes
- Stable-replacement path: target win >=55%, positive median, sufficient n, durable Top3-ex.
- Monster path: target mean/right-tail capture; lower win may be acceptable only if Top3-ex remains strong and tail concentration is reported.

## Sparse search rule
No dense threshold grids and no feature-weight optimization. Wave 1 may select at most three low-leakage families after a data/provenance readiness audit. Exact experiment thresholds/states must be written to a frozen manifest before opening performance.

## Advancement screen
Research-advancement only, not production GO:
- Stable path: win >=55%, mean >=+4%, median >0, Top3-ex >=+3%, sufficient n.
- Monster path: mean >=+6%, Top3-ex >=+4%, sufficient n; win/median/tail concentration must be explicitly reported.

## Immediate next stage
1. inventory repository/artifacts for causal inputs needed by A-E;
2. classify READY / DERIVABLE-CAUSALLY / MISSING;
3. choose <=3 families by provenance/leakage quality, not outcome;
4. freeze the Wave-1 experiment manifest;
5. only then run cost0 performance.

Current decision: NO-GO / exploration initialization.
