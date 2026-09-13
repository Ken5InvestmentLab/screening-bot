# Canonical next-open benchmark context — 2026-09-14

Research-only. No production writes. This is **context**, not a direct winner/loser comparison, because the periods and regimes differ.

## Why this audit

New TV-free research now uses the canonical endpoint:
- signal on D;
- enter at next official XTKS session open (D+1 open);
- exit at D+5 official daily close.

The preserved Stable★6 teacher stores legacy signal-time performance, so its headline cannot be compared directly with new next-open results without remapping the entry.

## Preserved Stable★6 teacher

Source:
- preserved Stable★6 teacher from run 34608845800;
- 55 confirmed Stable★6 rows;
- period 2026-03-05 through 2026-08-31;
- 54 unique symbols.

Legacy stored signal-time 5BD:
- n=55
- mean +6.59%
- median +1.50%
- win 56.36%
- >=10% 18.18%
- >=20% 14.55%
- <=-10% 10.91%
- <=-20% 1.82%
- Top3-ex mean +2.18%

Remapped canonical next-open -> D+5 close:
- n=55
- mean **+2.64%**
- median **-0.28%**
- win 45.45%
- >=10% 12.73%
- >=20% 10.91%
- <=-10% 14.55%
- <=-20% 3.64%
- Top3-ex mean **-0.55%**

Approximate fixed round-trip friction sensitivity:
- 0.5% total cost: mean about +2.14%, median about -0.78%, Top3-ex about -1.05%.
- 1.0% total cost: mean about +1.64%, median about -1.28%, Top3-ex about -1.55%.

Important: this does **not** mean legacy Stable★6 is weak. Its actual user workflow may allow same-session entry near the alert, while the new research contract intentionally uses a stricter next-open entry for reproducibility/actionability.

## Consensus normal-volatility specialist context

Fixed-min95 + frozen ATR OOD gate, realistic next-open endpoint.

Raw 2025 gated signals:
- n=101
- mean +7.72%
- Top3-ex +6.52%

Correct one-position-per-symbol 5-session cooldown, **no replacement**:
- n=52
- mean **+3.05%**
- median +0.29%
- win 50.00%
- >=10% 19.23%
- >=20% 9.62%
- <=-10% 9.62%
- Top3-ex **+1.21%**

2025 Jul-Dec:
- n=22
- mean **+3.58%**
- median +0.29%
- win 50.00%
- Top3-ex **-0.81%**

Approximate fixed 0.5% total cost:
- full 2025 no-replacement cooldown mean about +2.55%, Top3-ex about +0.71%.
- 2025H2 mean about +3.08%, Top3-ex about -1.31%.

## Interpretation

Do not compare +3.05% Consensus against +2.64% Stable and declare a winner.

Reasons:
1. Stable sample is Mar-Aug 2026; Consensus sample is 2025.
2. 2026 is a high-volatility/OOD period in which frozen Consensus correctly emits no min95 trades.
3. Stable alerts came from the legacy intraday workflow and may be actionable before the next-day-open benchmark.
4. Both samples are small enough that Top3 sensitivity matters.

What this audit does establish:
- a diversified Consensus result in the +3% range would still be economically relevant under the strict canonical endpoint;
- V44 does **not** need to preserve the inflated raw +7.72% headline to be useful;
- robust metrics (Top3-ex, median, symbol concentration, period stability) matter more than simply maximizing mean;
- the final replacement system needs another validated lane for the high-ATR/OOD regime where Consensus is off.
