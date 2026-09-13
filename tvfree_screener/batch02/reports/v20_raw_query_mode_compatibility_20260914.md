# V20 raw Yahoo query-mode compatibility — 2026-09-14

Research-only input-semantics audit. No strategy outcome was opened and no V20 threshold was changed.

## Cross-lane evidence

The Consensus lane compared two Yahoo 1H query modes fetched on the same calendar day:
- V43: `range=730d&interval=1h`
- Core archive / V20-style source: explicit `period1/period2&interval=1h&events=div,splits`

On 89 overlapping selected symbol/session observations:
- session volume matched **89/89 exactly**;
- session return differed by at most about **7.21e-8**;
- session range/open differed by at most about **5.90e-8**;
- session body/open differed by at most about **7.21e-8**;
- session close-location differed by at most about **1.04e-6**.

Absolute OHLC scales sometimes differed by later stock-split factors (2x/3x/5x/10x), so the explicit-period source is not a drop-in replacement for models using absolute `log_price`.

## V20 relevance

V20 Session-Impulse does **not** use absolute intraday price level.

Its frozen intraday inputs are:
- session return = close/open - 1;
- close location within the same completed session bar;
- range/close;
- trailing quantiles/medians of those scale-invariant quantities;
- session volume divided by trailing median session volume.

The cross-lane audit also found session volume exact on all 89 overlaps.

Absolute-price uses in V20 are isolated to the frozen canonical daily source:
- prior completed daily close <=1000 JPY gate;
- prior completed daily volume >=10000 shares gate;
- canonical next-open -> fifth-close evaluation endpoint.

Therefore the known Yahoo query-mode split-adjustment difference does not invalidate the frozen V20 feature representation.

## Boundary

This compatibility conclusion does **not** authorize future V20 revisions that add:
- absolute intraday price level;
- cross-bar absolute price differences;
- unversioned split-adjusted price features.

Any such feature would require an explicit corporate-action adjustment contract first.

The dedicated H1 fetch must still pass the independent exact-symbol + temporal-presence raw coverage guard before any H1 outcome is opened.

2026 outcomes opened: false.
Production modified: false.
