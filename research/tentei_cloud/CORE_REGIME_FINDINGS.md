# Reconstructed Core regime findings — 2026-09-14 JST

Research-only. Production, Discord, Spreadsheet, current Stable/Sniper/Mega, V12 state-entry work, and the separate V14 lane were not modified.

## Scope

This is a separate Core lane. It evaluates the already-fixed 天底極致 Cloud SAFE/Core rule on the common reconstructed 4H/session baseline made from genuine Yahoo 1H data.

Fixed Core definition:
- previous daily close <= 1,000 JPY
- previous daily volume >= 10,000
- candidate session volume >= 5,000
- RSI(12) < 45
- previous three completed reconstructed session closes descending
- current close > Bollinger(20) midline
- ATR(14) / close < 5%
- 5-business-day same-symbol cooldown

The 4H/session split is the existing fixed 13:00 reconstruction. This is **not** claimed to be exact reproduction of the historical/original 4H candidate set.

Market context uses the previous trading day only. Fixed gates were tested without fitting thresholds to outcomes.

## Reproducibility

Final reporting run:
- trigger commit: `9916b58a96db91d431edb5d906dc69abca8be8ae`
- workflow run: `34764868293`
- artifact: `10319769611`
- artifact ZIP SHA-256: `002e3da9d23a305a1a1c9d1564c584be0d83574d4a4bd61bb6fa7a6bec243a1b`
- script: `research/tentei_cloud/audit_core_regime.py`
- production writes: none

## Fixed Core baseline

### 2026 Jan-Aug

The ungated fixed Core produced:

- n = **118**
- mean = **+1.56%**
- median = **+0.48%**
- win rate = **53.39%**
- >= +10% = **8.47%**
- >= +20% = **1.69%**
- <= -10% = **1.69%**
- max = **+35.02%**
- top-1-winner-removed mean = **+1.27%**
- top-3-winner-removed mean = **+0.92%**
- top-5-winner-removed mean = **+0.66%**

This is materially less tail-dependent than the Monster families and supports keeping Core as the steadier lane.

2026 subperiod baseline means:
- Jan-Feb: n21, about **0.00%**
- Mar-Apr: n38, **+1.79%**
- May-Jun: n38, **+2.39%**
- Jul-Aug: n21, **+1.18%**

Only Jan-Feb was flat; the other three blocks were positive.

### Broader 2025H2-Aug2026 block

- n = 258
- mean = +0.76%
- <= -10% = 1.94%
- top-3-removed mean = +0.40%
- top-5-removed mean = +0.27%

2025H2 itself was near flat (+0.08%), so the stronger 2026 result should not be generalized backward without qualification.

## Market-regime gate comparison on 2026 Jan-Aug

| gate | n | mean | median | win | >=10% | <=-10% | top-3 removed |
|---|---:|---:|---:|---:|---:|---:|---:|
| ALL | 118 | **+1.56%** | +0.48% | 53.4% | 8.47% | 1.69% | **+0.92%** |
| NOT_RISK_OFF | 89 | +1.17% | +0.73% | 53.9% | 6.74% | 2.25% | +0.57% |
| R5_POS | 61 | +0.80% | +0.15% | 50.8% | 8.20% | 3.28% | +0.09% |
| B5_50 | 73 | +0.73% | +0.15% | 50.7% | 5.48% | 1.37% | +0.13% |
| R20_POS | 41 | +1.11% | +0.99% | 56.1% | 7.32% | 0.00% | +0.23% |
| R5_AND_RISING | 59 | +0.82% | +0.15% | 50.8% | 8.47% | 3.39% | +0.08% |

Every tested regime restriction lowered the 2026 mean versus the ungated Core.

`R20_POS` removed all <=-10% observations in this 2026 block, but it kept only 41/118 candidates, lowered mean to +1.11%, was negative in the DEV block (-1.00%), and had no candidates at all in 2026 May-Jun. It is therefore not a viable global Core gate.

`NOT_RISK_OFF` also failed the intended purpose: mean fell from +1.56% to +1.17%, the <=-10% rate increased from 1.69% to 2.25%, and robust top-winner-removed means weakened.

## Decision

**Keep the fixed Core rule ungated by broad market regime.**

Do not add any of the tested market-regime gates to Core. The current evidence says broad market state is more useful as metadata/context than as a hard ON/OFF switch.

Architectural implication:
- **Core:** retain as the lower-downside, higher-frequency lane; no global market gate.
- **Monster Watch/Prime:** keep separate; the learned-rank regime-veto audit also failed to justify a stable hard gate.
- **Market regime:** record it for forward analysis, but do not make it a shared system-level blocker.

The next Core research should focus on improving candidate quality **inside the Core setup itself** (or on genuinely forward evidence), not on increasingly elaborate broad-market filters against already-inspected periods.
