# Broad causal intraday v1 audit — 2026-09-13

Research-only. Production is unchanged.

## Scope

An existing, already-created GitHub Actions raw Yahoo 1h dataset was recovered from run `34592896202` (`Tentei Cloud 1H Research Fetch`), rather than issuing any new market-data request.

- source branch/head: `research/tentei-cloud-mtf` / `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`
- artifacts: 8 shards, `tentei-cloud-1h-shard-0` through `-7`
- target comparison universe file: `research/tentei_cloud/symbols_4h_universe.txt` (1,332 symbols)
- raw rows recovered: **4,019,524**
- usable symbols: **1,315 / 1,332 = 98.72%**
- raw date range: **2024-09-17 through 2026-09-10**
- failure records: 272 across 61 symbols (HTTP 400: 153; HTTP 404: 119)
- invalid OHLCV rows in the recovered raw files: **0**
- duplicate symbol/date/hour groups: **0**
- broad raw manifest SHA-256: `4d64471b7099b9e57485c8efd41d0dbbc6dca014e6e634b85bca56f04a502cda`

This universe is a historical 1,332-symbol **4H comparison set**, not proven to be the full TSE listing. It is suitable for broader retrospective feature/data-quality work but must not be described as historical all-TSE coverage.

## Exchange-close correction found during the audit

The TSE cash-session close changed from 15:00 to 15:30 effective 2024-11-05. The old generic PM clock-bin rule had required 13:00, 14:00, and 15:00 hourly starts for all dates.

The recovered raw source shows that this is incorrect before the close extension:

### 15:00-start rows before 2024-11-05
- rows: 40,038
- zero volume: 97.36%
- flat OHLC: 96.00%
- zero-volume + flat OHLC: **93.43%**
- nonzero-volume + nonflat: only 0.08%

### 15:00-start rows on/after 2024-11-05
- rows: 504,919
- zero volume: 1.12%
- flat OHLC: 15.43%
- zero-volume + flat OHLC: 0.47%
- nonzero-volume + nonflat: **83.92%**

This is data-structure evidence, not a strategy-return decision.

The research clock-bin implementation is therefore corrected to:
- AM: 09/10/11/12 starts for all dates
- PM before 2024-11-05: 13/14 starts, 15:00 close snapshot not required as a trading interval
- PM on/after 2024-11-05: 13/14/15 starts
- rolling same-bin baselines separate `PM_PRE_20241105` and `PM_POST_20241105`
- AM remains `AM_STABLE`
- pre-extension PM cutoff: 15:00 JST
- post-extension PM cutoff: conservatively 16:00 JST until provider publication latency is independently verified

This corrects a methodological bug in the earlier Codex-era session reconstruction.

## Broad v1 feature coverage after the correction

Across **618,775 normal raw symbol-days**:

- attempted AM/PM bins: **1,237,550**
- complete raw clock bins: **1,017,531** (82.22% of attempts)
- AM complete bins: 513,238
- PM complete bins: 504,293
- PM pre-extension complete: 35,000
- PM post-extension complete: 469,293

Frozen v1 candidate features remain unchanged:

1. `bar_log_return`
2. `range_pct`
3. `upper_wick_pct`
4. `lower_wick_pct`
5. `prev4_log_return_mean`
6. `prev4_range_mean`
7. `log_range_vs_prior20`

Rows with all seven available:
- **941,118 / 1,017,531 = 92.49%** of complete bins
- **76.05%** of all attempted bins

The feature list was frozen before this broad audit and was not changed in response to strategy outcomes.

### Coverage by year

| Year | complete bins | v1-complete | v1 completeness |
|---|---:|---:|---:|
| 2024 | 143,803 | 72,011 | 50.08% |
| 2025 | 514,098 | 510,213 | **99.24%** |
| 2026 | 359,630 | 358,894 | **99.80%** |

The weaker 2024 percentage is expected from the initial 20-same-bin warmup plus the PM close-regime reset at 2024-11-05.

## Broad feature distributions

| Feature | n | p01 | median | p99 |
|---|---:|---:|---:|---:|
| bar_log_return | 1,017,531 | -0.05311 | ~0 | +0.05203 |
| range_pct | 1,017,531 | 0.00194 | 0.01432 | 0.12088 |
| upper_wick_pct | 1,017,531 | — | — | 0.05000 |
| lower_wick_pct | 1,017,531 | — | — | 0.03571 |
| prev4_log_return_mean | 1,012,271 | -0.02669 | ~0 | +0.02518 |
| prev4_range_mean | 1,012,271 | 0.00361 | 0.01603 | 0.09959 |
| log_range_vs_prior20 | 941,118 | 0.21439 | 0.69129 | 1.90483 |

Observed extremes:
- `range_pct > 30%`: 586 bins
- `abs(bar_log_return) > log(1.2)`: 712 bins

These are not automatically clipped. The project explicitly wants to retain the possibility of genuine explosive winners; magnitude alone is insufficient evidence that a row is bad.

## Historical-universe limitation

The source state calls `symbols_4h_universe.txt` a “1,332-symbol same-universe comparison set.” The commit that introduced the list does not preserve a reproducible derivation recipe. Therefore:

- do not call it full-TSE history;
- use it as a broad production-like historical comparison population;
- the final live system must still support the full eligible TSE individual-stock universe dynamically.

## Outcome-exposure integrity note

While tracing how the historical 1,332-symbol universe had been created, the old `research/tentei_cloud/RESEARCH_STATE.md` was opened. That document contains previously exposed 2026 strategy summaries.

This is recorded as **source-discovery contamination**.

Important safeguards:
- the v1 seven-feature list had already been frozen before that file was opened;
- the broad raw audit itself did not join outcome columns;
- the exposed 2026 summaries must not be used to select features, thresholds, models, cooldowns, or correction rules;
- 2026 remains report-only for the new frozen experiment.

## Decision

**DATA-QUALITY PASS FOR THE FROZEN V1 FEATURE ARCHITECTURE.**

The broad raw source is large enough to move from data-quality work into a preregistered retrospective scoring experiment. It does not by itself prove strategy performance, all-TSE historical coverage, or exact TradingView bar equivalence.

Next: freeze the canonical feature-to-label experiment and its Core/Monster heads before opening the corresponding outcomes.
