# Causal raw-intraday feature audit — 2026-09-13

Research-only. No strategy-return file was opened. This audit asks whether a TradingView-free intraday feature path can avoid same-day finalized daily anchors.

## Why this audit exists

The prior daily-anchor repair can make archived hourly aggregates resemble completed daily OHLCV, but same-day finalized H/L/C/volume cannot be used for an earlier pre-close 4H feature without leakage. We therefore tested only data-quality/feature-stability questions.

## 1. Can a causal prior-session scale factor repair today's raw 1h prices?

Complete seven-slot sample: 1,087 sessions.

| method | n | all OHLC <=1% | all OHLC <=2% |
|---|---:|---:|---:|
| raw hourly aggregate | 1,087 | 45.45% | 74.89% |
| previous complete session scale factor | 1,079 | 44.21% | 73.40% |
| trailing-5 prior scale median | 1,063 | 46.10% | 76.48% |

The trailing-5 method is only a very small data-quality improvement and previous-session scaling is worse than raw. Do not make causal price rescaling a required v1 step.

Scale-factor day-to-day stability itself is usually good (n=1,079; median absolute change 0.20%, p90 1.17%, p99 2.77%), but rare structural breaks remain and the causal rescale does not materially improve aggregate OHLC agreement.

**Decision:** prefer scale-invariant intraday features over trying to reconstruct absolute prices before the signal cutoff.

## 2. Can a causal prior-session volume factor repair today's raw hourly volume?

| method | n | median volume APE | within 5% | within 10% | p90 APE |
|---|---:|---:|---:|---:|---:|
| raw hourly sum | 1,087 | 37.72% | 5.98% | not frozen | not frozen |
| previous-session volume factor | 1,079 | 21.93% | 13.81% | 25.49% | 59.91% |
| trailing-5 prior factor median | 1,063 | 19.53% | 13.92% | 27.19% | 50.72% |

Prior-only calibration improves the aggregate error but remains far too noisy to treat as an exact absolute-volume repair. Volume-factor day-to-day change has median 22.24% and p90 60.35%.

**Decision:** do not trust an absolute pre-close volume rescale. Prefer source-internal relative volume features based only on prior completed comparable bins/sessions. Keep prior-day official daily volume as a separate causal liquidity filter.

## 3. Gate AM/PM bins independently instead of requiring a complete whole day

Raw observed symbol-sessions: 1,332.

Using clock bins consistent with the currently observed 09:00/13:00 legacy boundary:
- AM-like bin requires the observed 09,10,11,12 starts: 1,150 complete (86.34%)
- PM-like bin requires 13,14,15 starts: 1,155 complete (86.71%)
- both bins complete: 1,087 (81.61%)
- closing-snapshot rows observed: 8; they are not required as a normal volume bar.

Requiring all seven starts before using either bin unnecessarily discards 63 otherwise-complete AM bins and 68 otherwise-complete PM bins.

The 12:00 hourly interval crosses the lunch break in clock time. It may belong to a 09:00-13:00 clock bin, but this does **not** prove exact TradingView bar equivalence. The new system does not require exact legacy TradingView matching, so the bin must be named and audited as a TV-like/raw-source clock bin rather than asserted to be identical.

## 4. Stability of scale-invariant candidate features

On 1,051 sessions where the post-close repaired intraday shape remained valid, raw versus post-close-reconstructed features were compared for two bins (2,102 bin pairs). This is an internal stability test, not a truth test and not a performance test.

Overall:
- body_pct: Spearman 0.901; median absolute difference 0.347 percentage points
- range_pct: Spearman 0.984; median absolute difference 0.000 percentage points
- close_location: Spearman 0.826; median absolute difference 0.787 percentage points; p90 difference 29.73 percentage points
- within-day volume share: effectively invariant under the repair ladder, but a full-day share is not causal for the AM cutoff.

By bin:
- AM body_pct Spearman 0.902; range_pct 0.971; close_location 0.981
- PM body_pct Spearman 0.908; range_pct 0.991; close_location only 0.694

**Decision:** prioritize ratio/shape features whose interpretation survives scale problems:
- normalized range / ATR-like ratios
- body return / log return
- multi-bar returns
- RSI / stochastic / Bollinger-position style normalized price features
- realized volatility / compression ratios
- source-internal relative volume against prior comparable bins

Do not promote PM close-location as a trusted feature yet. Do not use same-day full-day volume share for an AM signal.

## 5. Architecture correction

The next 4H feature builder should have four independent layers:

1. **Universe/liquidity layer from prior completed daily data**
   - prior close / price cap
   - prior daily volume / liquidity
   - corporate-action or obvious-unit sanity where available

2. **Raw intraday clock-bin layer**
   - AM and PM completeness decided independently
   - no current-day finalized daily anchor before cutoff
   - raw source rows preserved

3. **Scale-invariant feature layer**
   - ratio/return/rank features first
   - absolute current-day intraday price and absolute rescaled volume are not required for v1 scoring

4. **Post-close reconstruction layer**
   - retained for audit/archival only
   - never silently substituted into an earlier feature cutoff

## Next
Implement a deterministic raw clock-bin builder and cutoff-aware feature extractor. Measure feature coverage and missingness before any new strategy-return evaluation.
