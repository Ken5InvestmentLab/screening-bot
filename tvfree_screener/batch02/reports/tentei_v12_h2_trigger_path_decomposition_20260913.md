# V12 H2 trigger-path decomposition — 2026-09-13

Research-only diagnostic. No production writes. 2026 outcomes remain closed.

## Purpose

After V19 showed that V12 ALL collapsed in 2025H2, and the outcome-free V17 audit showed a material trigger-composition shift, this diagnostic decomposed H2 using only the three trigger paths already frozen in V12:

- RSI_RECOVERY
- TREND_FLIP
- EMERGENCY_REVERSAL

No threshold, trigger definition, ranking, or cooldown was changed.

Each path uses the same prior-day gates and its own five-XTKS-session same-symbol cooldown, matching the V12 H1 path reporting contract.

## H2 results at 0.5% cost

### RSI_RECOVERY

- n = **4,776**
- mean **-0.484%**
- median **-0.500%**
- win **41.75%**
- >=+10% 3.66%
- >=+20% 1.05%
- <=-10% 3.54%
- Top1-excluded mean **-0.501%**
- Top3-excluded mean **-0.531%**
- positive-month fraction 16.7%
- Core gate: **FAIL**

At zero cost the mean is only +0.016%, win 46.98%, and Top3-excluded mean remains negative.

### TREND_FLIP

- n = **1,212**
- mean **-0.548%**
- median **-0.713%**
- win **39.60%**
- >=+20% 1.49%
- <=-10% 5.36%
- Top3-excluded mean **-0.930%**
- Core gate: **FAIL**

This path was already weak in H1 and remains weak.

### EMERGENCY_REVERSAL

- n = **2,475**
- mean **-1.249%**
- median **-1.197%**
- win **35.92%**
- >=+20% 0.93%
- <=-10% 4.97%
- Top1-excluded mean **-1.298%**
- Top3-excluded mean **-1.363%**
- positive-month fraction 16.7%
- Core gate: **FAIL**

Even at zero cost:
- mean **-0.749%**
- median **-0.697%**
- win 40.48%.

## Comparison with exposed H1 context

Previously observed H1:
- RSI_RECOVERY mean +1.90%, median +1.09%, win 59.17%.
- EMERGENCY_REVERSAL mean +2.13%, median +1.82%, win 62.06%.
- TREND_FLIP mean -0.44%, median -0.77%, win 40.80%.

Both previously strong paths collapse in H2.

## Frozen diagnostic decision

**WITHIN_PATH_DEGRADATION_SUPPORTED**

The H2 deterioration is not explained by trigger-mixture drift alone. The individual reversal mechanisms themselves lose their edge.

Therefore:
- do not rescue V12 by reweighting RSI vs Emergency;
- do not retune RSI/BB/ATR thresholds on exposed 2025 results;
- do not rename the same V12 reversal family and rerun it.

The event-specific lane should move to a genuinely different 4H mechanism family if research continues.

2026 outcomes opened: false.
Production modified: false.
