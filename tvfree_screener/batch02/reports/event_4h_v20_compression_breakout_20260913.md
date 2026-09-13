# EVENT 4H V20 — compression-breakout discovery — 2026-09-13

Research-only. No production writes. 2025 and 2026 outcomes remained closed for V20.

## Frozen mechanism

V20 was a genuinely distinct 4H event family, not a V12 reversal retune:
- prior four-bin compression: at least one prior bin with same-date/bin market-relative BB width rank <=30%;
- current close above the prior four-bin high;
- bullish current bar;
- close location >=75%;
- current same-date/bin range rank >=80%;
- current same-bin volume >= prior20 same-bin median;
- prior-day close <=1000 JPY and volume >=10000 shares;
- no ranking, five-XTKS-session same-symbol cooldown.

Discovery was restricted to 2024-10-01 through 2024-12-20, with exits matured by 2024-12-30. 2025 was only authorized if discovery passed.

## Discovery population

- raw signals before cooldown: **161**
- selected after cooldown: **148**
- symbols: **136**
- active dates: **43**
- 3.44 signals/active date

Density gate passed.

## 2024Q4 result at 0.5% cost

- mean **-1.017%**
- median **-1.670%**
- win **33.78%**
- >=+10% 4.73%
- >=+20% 2.03%
- >=+50% 0.68%
- <=-10% 3.38%
- Top1-excluded mean **-1.382%**
- Top3-excluded mean **-1.735%**
- positive-month fraction **0%**

Core gate: FAIL.
Monster gate: FAIL.

Even at zero assumed cost:
- mean **-0.517%**
- median **-1.170%**
- win 35.14%.

## Decision

**REJECT V20 IN DISCOVERY. DO NOT OPEN 2025.**

Do not retune the 30% compression, 80% range, 75% close-location, four-bin breakout or relative-volume thresholds on this result.

The next event-specific work should not continue inventing adjacent heuristic rules blindly. Revisit the previously documented Monster weak+early / volr20-low research structure and determine exactly what was robust, what was exposed, and what can still be reproduced under the current causal 4H contract.

2026 outcomes opened: false.
Production modified: false.
