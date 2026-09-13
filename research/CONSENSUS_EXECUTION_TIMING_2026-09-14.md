# Consensus execution-timing audit — 2026-09-14

Research-only. No production writes.

## Purpose

Test whether the strong 2025 uncapped Consensus result depends on entering exactly at the reconstructed signal-session close.

Inputs:
- V43 fixed-min95 selected artifact (2025)
- V42 fixed-min95 selected artifact (2026 robustness)
- preserved run-80 frozen daily OHLCV artifact
- frozen ATR OOD cap from the separate Consensus gate study: 2.8640659721

Daily price mapping was validated: recomputed signal-close -> D+5 close return matches stored `perf_5bd` to floating-point precision.

## Return definitions

For a signal on day D:
- original: signal-session close -> D+5 daily close
- next-open: D+1 daily open -> D+5 daily close
- next-close: D+1 daily close -> D+5 daily close

The next-open version is the primary realistic-delay check here.

## 2025 full-year min95

Original:
- n=112
- mean +6.35%
- median +4.67%
- win 65.18%
- +10% 36.61%
- <=-10% 11.61%
- Top3-ex mean +5.09%

Next-open:
- n=112
- mean **+5.87%**
- median +6.21%
- win 59.82%
- +10% 36.61%
- <=-10% 10.71%
- Top3-ex mean **+4.73%**

Next-close:
- mean +5.90%
- Top3-ex mean +4.83%

Interpretation: the 2025 signal survives a one-business-day execution delay.

## 2025 Jul-Dec forward-validation segment

Baseline original:
- n=37
- mean +6.28%
- Top3-ex mean +2.57%

Next-open:
- n=37
- mean **+6.02%**
- median +1.93%
- win 59.46%
- +10% 29.73%
- +20% 16.22%
- <=-10% 13.51%
- Top3-ex mean **+2.90%**

Frozen ATR-gated next-open:
- n=34
- mean **+6.33%**
- median +1.75%
- win 58.82%
- +10% 32.35%
- +20% 17.65%
- <=-10% 14.71%
- Top3-ex mean **+2.94%**

Thus the pre-2026 validation result does not disappear under next-open entry.

## Session split

2025 full-year:
- session 9: original +5.55% -> next-open +4.78%
- session 13: original +7.07% -> next-open +6.84%

2025 H2:
- session 9: original +3.51% -> next-open +3.24%
- session 13: original +9.20% -> next-open +8.95%

Both sessions remain positive, with the 13-session lane stronger.

## 2026 descriptive robustness

Original:
- n=69
- mean -7.05%

Next-open:
- n=69
- mean **-7.35%**
- median -8.13%
- win 14.49%
- <=-10% 33.33%
- Top3-ex mean -8.69%

Next-close:
- mean -5.41%

The failure remains severe after realistic delay. It is not an artifact of signal-close entry.

The frozen ATR OOD gate blocks all 69 min95 trades in this tested 2026 window, so execution timing does not weaken the gate conclusion.

## Decision

1. Keep fixed-min95 Consensus as a normal-volatility specialist candidate.
2. The 2025 result passes this first execution-delay sanity check.
3. Do not attempt to rescue 2026 with execution assumptions; the regime/model relationship is genuinely broken there.
4. Retain the frozen ATR OOD circuit breaker.
5. Before production promotion, still test transaction costs/slippage and prospective shadow timing using actual alert timestamps.
