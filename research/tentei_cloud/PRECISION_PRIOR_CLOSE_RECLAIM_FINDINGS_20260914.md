# Precision prior-close reclaim — preconfirmation findings — 2026-09-14 JST

Research-only. This experiment was preregistered before its outcomes were opened.

Experiment:
`PRECISION-PRIOR-CLOSE-RECLAIM-20260914-01`

Frozen mechanism:
- previous completed daily candle bearish;
- candidate session opens below previous daily close;
- candidate session reclaims previous daily close;
- candidate session closes bullish;
- no free numeric thresholds;
- canonical next-XTKS-date open -> signal-date+5 XTKS-date close;
- primary round-trip cost stress = 0.5%.

## Reproducibility

- preregistration commit: `6344001654fa8c3afe1d436a05e23d57efaa70bd`
- workflow run: `34799151144`
- artifact: `10330224447`
- artifact ZIP SHA-256: `dd9ae8489924f274e9dc081d9a8e425f57742dfb1f3c8d3e6c1fa93036530b0f`

2025H2 locked confirmation was NOT opened.
2026 outcomes were NOT opened.

## DEVELOPMENT — 2024-11-01..2025-03-31

Resolved n = 3,809.

Gross:
- mean -0.06%
- median -0.21%
- win 46.0%
- <= -10% 3.73%

Primary 0.5% cost:
- mean **-0.56%**
- median **-0.71%**
- win **41.3%**
- top-3-removed mean **-0.63%**

Frozen gate failures:
- net mean >0: FAIL
- net median >0: FAIL
- net win >=60%: FAIL
- net top3-removed mean >0: FAIL

## INTERNAL VALIDATION — 2025-04-01..2025-06-30

Resolved n = 2,318.

Gross:
- mean +0.85%
- median +0.50%
- win 53.7%
- <= -10% 3.75%

Primary 0.5% cost:
- mean **+0.35%**
- median approximately **0.00% but slightly negative**
- win **49.96%**
- top-3-removed mean +0.23%

Frozen gate failures:
- net median >0: FAIL
- net win >=60%: FAIL

## Decision

**REJECT PRIOR_CLOSE_RECLAIM as the Sniper-like precision lane.**

Reasons:
- the development block is negative even before the 0.5% stress is fully considered;
- validation improves, but not remotely to the required high-hit-rate role;
- the desired Sniper role is about precision, and ~50% net win cannot satisfy that role.

Do not:
- add RSI/ATR/volume thresholds to rescue it;
- restrict to AM/PM after seeing these outcomes;
- open 2025H2;
- open 2026;
- reuse these outcomes as clean validation for a modified version.

The family is closed.
