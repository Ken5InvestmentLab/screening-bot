# Supervisor OHLCV Supplement Acceptance Boundary — 2026-09-15 02:02 JST

Status: **PREREGISTERED / DATA-PLANE ONLY / PERFORMANCE UNOPENED**

This note governs the OHLCV supplementation work currently being explored in the Core lane. It is research-only and does not authorize changes to production/main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or updater.

## Purpose

Allow missing OHLCV to be supplemented without silently converting transport/data gaps into strategy evidence or introducing time leakage.

## Frozen acceptance requirements

A supplemented row may enter any formal research dataset only when all of the following are recorded and verified:

1. Exact symbol, session/date, timeframe, and required OHLCV fields.
2. Source vendor/provider identity and acquisition method.
3. Acquisition timestamp and the latest market timestamp represented by the row.
4. Original-observed vs supplemented provenance flag; supplemented rows must never be indistinguishable from native rows.
5. Exact raw payload/file SHA-256 or equivalent immutable byte receipt when a raw file/payload is retained.
6. No future information relative to the research decision timestamp. A row acquired later may repair historical coverage only if it represents the same already-completed market interval and the provider exposes that historical interval directly; it may not use later bars to synthesize the missing bar.
7. OHLC consistency: finite positive prices, high >= max(open, close, low), low <= min(open, close, high), volume finite and nonnegative when volume is required.
8. Calendar/session consistency against the pinned XTKS calendar and the frozen canonical endpoint mapping.
9. Duplicate conflict handling is fail-closed: if native and supplement sources disagree materially, preserve both receipts and exclude the conflicted pair from formal acceptance until resolved; do not average/interpolate.
10. No interpolation, forward-fill/back-fill of OHLC, synthetic intraday reconstruction from daily bars, or outcome-informed source selection.

## Source hierarchy

No vendor priority is promoted here without a reproducibility receipt. A proposed fallback chain may be implemented by Core24, but each source must pass the same provenance and temporal-causality checks above. Source choice must be determined before strategy outcomes are opened, not selected per-symbol according to resulting performance.

## Interaction with V47 / Weak+Early / Parallel Wave-1

- V47 systemic Yahoo HTTP429 remains a transport blocker, not negative strategy evidence.
- Existing frozen raw-acceptance thresholds are unchanged. Supplemented rows do not relax pair coverage/monthly/symbol acceptance thresholds.
- Weak+Early DUAL/G3, G3 -1% threshold, and closed Round2 remain unchanged.
- Parallel Wave-1 A1/B1/E1 remains performance-unopened; supplement work cannot be used to retune its thresholds.
- All new performance comparisons remain transaction cost 0%, win = gross return > 0; 2026 outcomes remain report/robustness-only.

## Required Core24 handoff before Supervisor adoption

The Core24 lane should hand off:

- exact missing pair inventory before supplementation;
- source hierarchy/config used;
- per-pair provenance table;
- accepted/rejected/conflicted counts by source and month;
- immutable receipt/hashes for source payloads or files;
- deterministic verifier output proving the acceptance contract above;
- resulting coverage delta before any strategy-performance recomputation.

Only after this data-plane receipt passes may a frozen strategy evaluator consume the supplemented dataset. Coverage improvement is not itself GO evidence.

Current decision: **NO-GO / SUPPLEMENTATION METHOD MAY PROCEED UNDER THIS FAIL-CLOSED CONTRACT**.
