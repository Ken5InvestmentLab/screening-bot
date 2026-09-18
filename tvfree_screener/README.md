# TradingView-free screener (TEST ONLY)

This directory is an isolated test implementation for replacing the TradingView watchlist-alert dependency.

## Goal

- Target all TSE domestic common stocks (exclude ETF/ETN/REIT/preferred etc. from the JPX universe file).
- Use daily OHLCV from Yahoo Finance.
- Generate candidates without TradingView, Pine Script, or 天底極致 signals.
- Rank candidates using two supervised probabilities:
  - probability of +5% or better after 5 trading days
  - probability of -10% or worse after 5 trading days
- Current prototype score: `score = p_big5 - 6 * p_loss10`.
- Keep production Discord, Spreadsheet, Stable/Sniper/Mega, workflows, and main branch untouched until explicit Go approval.

## Prototype result from the existing teacher OHLCV snapshot

The source snapshot was aggregated from 4-hour bars into daily bars only to test the idea. It is not the final production data source.

For May-August 2026, rolling monthly training with XGBoost and one top-ranked candidate per day produced:

- 82 candidates
- 5BD close-to-close mean: +2.25%
- median: +1.86%
- win rate: 61.0%
- -10% or worse: 0.0%
- realistic next-open to 5BD-close mean: +1.94%

Current Stable★6 over the same May-August window:

- 41 confirmed candidates
- mean: +1.12%
- median: -0.40%
- win rate: 48.8%
- -10% or worse: 12.2%

These numbers are exploratory and not sufficient for production adoption. The next stage is a longer independent daily-data walk-forward test over the full TSE universe.

## Guardrails

1. No writes to production Sheets or Discord.
2. No change to existing TradingView workflows.
3. No merge to `main` without explicit user approval.
4. Training rows must have their full 5BD outcome known before the prediction month starts (purged walk-forward).
5. Report both signal-close and next-session-open entry performance.
