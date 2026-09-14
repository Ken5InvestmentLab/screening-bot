# Parallel Condition Exploration — Wave 1 Readiness Audit

Date: 2026-09-15 JST
Branch: `research/parallel-condition-exploration`
Status: READINESS AUDIT COMPLETE / PERFORMANCE UNOPENED

## Guardrails
This lane is isolated from Weak+Early Phase-2. It does not alter DUAL_TOP1, G3, any opened Weak+Early evidence, production/main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or watchlist-updater.

All later performance work must use transaction cost 0%, win = gross return > 0, canonical endpoint next XTKS open -> fifth XTKS close. 2026 is report/robustness-only. Opened 2022 Weak+Early outcomes are not discovery/tuning input.

## Source/provenance inventory
Repository evidence confirms a preserved frozen research dataset artifact containing `tse_daily.csv` is part of the causal research lineage (`tvfree-preserve-dataset.yml`). The preservation workflow hashes and line-counts the CSV before re-upload. This audit does not assume unverified columns beyond the daily OHLCV lineage already used by the frozen research generator; before performance, the execution worker must materialize the exact preserved source/schema receipt and fail closed if any required field is absent.

## Family readiness

| Family | Readiness | Causal/provenance assessment | Disposition |
|---|---|---|---|
| A Compression -> expansion | **DERIVABLE-CAUSALLY** | Uses only trailing daily OHLC plus signal-session OHLC known before next-session entry. No future pivot required. | **SELECT Wave 1** |
| B Relative strength / reversal | **DERIVABLE-CAUSALLY** | Uses candidate trailing returns and same-date cross-sectional market median from the preserved daily universe; all data precedes next-session entry. | **SELECT Wave 1** |
| C Gap / overnight | **TIMING-AMBIGUOUS** | A next-session opening gap is only known at/after the canonical entry print. Using it to decide a trade executed at that same open risks look-ahead/execution leakage unless a later executable price arm is separately preregistered. | **DEFER** |
| D Liquidity / turnover shock | **DERIVABLE-BUT-REDUNDANCY-RISK** | Daily volume supports causal acceleration measures, but the lane must prove semantic separation from already-opened `volr20 LOW`; otherwise this becomes a disguised retune. | **DEFER Wave 1** |
| E Distance to prior structure | **DERIVABLE-CAUSALLY** | Uses only trailing highs/lows/range boundaries strictly before the signal/entry; no centered/look-ahead pivot. | **SELECT Wave 1** |

## Selection rationale
Wave 1 is limited to **A / B / E** because they can be constructed from causal daily price history without changing the canonical endpoint and without depending on the entry-session open itself. C is deferred on execution-timing grounds. D is deferred until a separate semantic/provenance test shows it is not merely a re-expression of `volr20 LOW`.

Selection was made before opening any Wave-1 performance and therefore is not outcome-driven.

## Required fail-closed checks before backtest
1. Bind the run to an immutable preserved-source receipt: artifact/run identifier, CSV SHA-256, schema/column list, row count, min/max date.
2. Verify each feature uses data timestamped no later than the signal session close; entry remains next XTKS open.
3. Verify trailing windows exclude all future rows and use symbol/date sorted unique rows.
4. Verify market-relative statistics use only symbols available in the same causal daily universe/date.
5. If exact XTKS session mapping or required endpoint rows are missing/duplicated, fail closed; no observed-row shifting.
6. Do not use 2022 Weak+Early fresh outcomes or 2026 outcomes for threshold selection.

## Advancement
Readiness classification and Wave-1 family selection are complete. Performance remains unopened. Next step is to freeze the exact experiment manifest for A/B/E and then execute one cost-0 batch without threshold retuning.

Current decision: **NO-GO / Wave-1 preregistration advancing**.
