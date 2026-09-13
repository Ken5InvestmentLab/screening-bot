# Tentei-inspired 4H V12 — state-reversal candidate generator — 2026-09-13

Research-only. No production writes. Historical 2026 strategy outcomes were not opened.

## Frozen design

Preregistered in `TENTEI_INSPIRED_4H_V12_STATE_REVERSAL_SPEC.json` before outcome access.

V12 is explicitly **not** an exact TradingView/Tentei reproduction. It uses only confirmed legacy structure:
- BB20 / 2 sigma;
- RSI12 with OS=35;
- 5-bar setup memory;
- 2.5 ATR emergency reversal concept;
- stateful trigger-path design.

Three frozen trigger paths were evaluated:
1. RSI recovery: RSI12 crosses above 35 after a prior-5 oversold/lower-band setup.
2. Trend flip: BB20 slope turns positive while RSI12 crosses above 50.
3. Emergency reversal: close exceeds prior-5 low + 2.5 ATR, also requiring the same prior setup.

Raw 1h bars were aggregated into the existing AM/PM causal clock bins. No daily row was synthesized into intraday bars.

## Candidate population

- 2025 after prior-day price/volume gates: **23,959 signals**
- H1 raw signal rows before cooldown: **8,245**
- All endpoint rows were resolved.

## H1 March-June at 0.5% cost

### ALL
- n=3,583 after 5-session cooldown
- mean **+1.43%**
- median **+0.58%**
- win rate **55.04%**
- >=+20% **1.98%**
- <=-10% **4.30%**
- Top1-removed mean **+1.31%**
- Monster gate: FAIL (right-tail frequency)

### RSI_RECOVERY
- n=2,662
- mean **+1.90%**
- median **+1.09%**
- win rate **59.17%**
- >=+20% **2.14%**
- <=-10% **4.28%**
- Top1-removed mean **+1.74%**
- Monster gate: FAIL (right-tail frequency)

### TREND_FLIP
- n=674
- mean **-0.44%**
- median **-0.77%**
- win rate **40.80%**
- >=+20% **2.23%**
- <=-10% **6.08%**
- Top1-removed mean **-0.55%**
- Monster gate: FAIL

### EMERGENCY_REVERSAL
- n=1,874
- mean **+2.13%**
- median **+1.82%**
- win rate **62.06%**
- >=+20% **1.71%**
- <=-10% **3.09%**
- Top1-removed mean **+2.09%**
- Monster gate: FAIL (right-tail frequency only)

## Decision

**V12 does not pass the frozen Monster gate. H2 remains unopened for V12.**

However, unlike V11, V12 creates a clearly positive and robust H1 candidate population. RSI recovery and emergency reversal are especially strong on central tendency, but those path-level results are now exposed and must not be used to claim validation.

The next frozen experiment therefore does **not** choose one trigger path post hoc. V13 keeps the entire V12 ALL signal population unchanged and tests whether the already-existing causal V6 quantile predictions can rank the V12 events for tail capture.

2026 outcomes opened: false.
Production modified: false.
