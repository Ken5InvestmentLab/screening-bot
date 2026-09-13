# Long-horizon role coverage finding — 2026-09-14 JST

Research-only. No production or selection logic changed.

## Question

Can the currently fixed Cloud lanes (Core and the short-horizon learned Monster Watch/Prime) also replace the current Mega40 40-business-day modes?

## Reproducibility

- trigger commit: `925bd7e4023f0bb71960e8a23e4d12df19305d94`
- workflow run: `34788118628`
- artifact: `10327581179`
- artifact ZIP SHA-256: `c3d4a82ace64eaeef13a8c0f5b225361e049162f3999332c42fca5e5c1552998`

Selection was unchanged. Only 40BD outcome labels were added.

## Current Mega40 benchmarks

Saved current reports:
- Mega40 Deep: n26, mean **+17.6%**, win 53.8%, +30% hit 19.2%.
- Mega40 Wick: n8, mean **+10.6%**, win 62.5%, +50% hit 25.0%.

These are product benchmarks, not clean prospective validation.

## Fixed Cloud lanes at 40BD

### Core — 2026 matured

- n103
- mean **+2.88%**
- median +0.67%
- win 52.4%
- >= +30% **8.74%**
- >= +50% 2.91%
- <= -20% 5.83%
- top-3-removed mean +1.16%
- top-5-removed mean +0.25%

Core does not approach current Mega40 headline behavior.

The 2025H2 Core 40BD mean (+3.72%) was itself tail-dependent: one +438% outcome; top-3 removal turned the mean slightly negative.

### Existing short-horizon Monster — 2026 matured

Monster Watch:
- n42
- mean **-5.29%**
- median -6.67%
- win 28.6%
- >=+30% 7.14%
- <=-20% 16.67%

Monster Prime:
- n11
- mean **-0.40%**
- median -5.56%
- win 27.3%
- >=+30% 9.09%

The short-horizon learned Monster clearly does not double as a reliable 40BD recovery lane.

## Decision

**The current Core / Monster architecture does not cover the Mega40 product role.**

A dedicated long-horizon TV-free research lane is required if the replacement system is intended to cover the user's full requirement set, not only Stable/Sniper/Mega5-like short horizons.

Do not:
- relabel Core as Mega40;
- reuse short-horizon Monster Prime as a 40BD confidence tier;
- claim the replacement is feature-complete while long-horizon coverage is absent.

## Next experiment ownership

This branch takes ownership of the non-overlapping long-horizon lane.

Initial baseline:
- reconstruct the semantic current Mega40 Deep and Wick conditions from daily OHLCV;
- apply them directly to the TV-free TSE universe rather than requiring a TradingView BOTTOM teacher event;
- use fixed standard formulas and no 2026 threshold sweep;
- compare current-like <=1000 JPY universe with a no-price-cap variant because the user explicitly allows removing the 1000 JPY constraint when performance supports it.

This is a new architecture lane, not a modification of Core or the parallel V20 Monster work.
