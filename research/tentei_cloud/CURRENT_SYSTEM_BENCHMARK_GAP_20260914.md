# Current-system benchmark gap — 2026-09-14 JST

Research-only benchmark audit. No production or signal logic was modified.

## Frozen current benchmark snapshot

Source: saved scoring reports generated **2026-09-11 14:14:31 JST**.

| mode | official horizon / target | confirmed n | mean | win | target hit |
|---|---|---:|---:|---:|---:|
| Stable ★6 | 5BD / +10% | 56 | **+6.1%** | 55.4% | 10 / 56 |
| Sniper | 5BD / positive return | 40 | +2.4% | **65.8%** | 27 / 40 |
| Mega5 | 5BD / +20% | 10 | **+14.5%** | 50.0% | 4 / 10 |
| Mega40 Deep | 40BD / +30% | 26 | **+17.6%** | 53.8% | 5 / 26 |
| Mega40 Wick | 40BD / +50% | 8 | **+10.6%** | 62.5% | 2 / 8 |

Do not collapse these modes into one average. Their horizons and product roles differ.

## Stable ★6 versus fixed Core on the Stable confirmed window

Stable report confirmed-date window parsed from the saved report:
- **2026-03-05 through 2026-09-03**
- all 56 confirmed rows parsed successfully.

### Current Stable ★6

- n56
- mean **+6.06%**
- median +1.20%
- win 55.36%
- >= +10% **17.86%**
- >= +20% **14.29%**
- <= -10% **12.50%**
- max +90.20%
- min -22.90%
- top-1 removed mean **+4.53%**
- top-3 removed mean **+1.70%**
- top-5 removed mean **-0.31%**

### Fixed Cloud Core — first executable next-1H-open entry

Same signal-date window:
- n88
- mean **+1.68%**
- median +0.37%
- win 51.14%
- >= +10% 7.95%
- >= +20% 2.27%
- <= -10% **1.14%**
- max +35.02%
- min -11.70%
- top-1 removed mean **+1.30%**
- top-3 removed mean **+0.86%**
- top-5 removed mean **+0.55%**

## Interpretation

Core is not a Stable★6 replacement by headline mean.

The gap is large:
- Stable +6.06%
- Core +1.68%

But their return shapes are very different:
- Stable has far more +20% tails: 14.29% vs Core 2.27%.
- Stable also has far more <=-10% losses: 12.50% vs Core 1.14%.
- removing Stable's top five winners pushes its mean slightly negative.
- Core remains positive after removing its top five winners.

Therefore the current-system architecture target is clearer:

**Core should provide the robust floor; Monster must supply the positive-skew tail that creates Stable-like headline performance.**

Do not try to force Core itself to +6% by historical pruning. That would conflict with its demonstrated lower-downside / lower-tail role.

## Arithmetic Monster requirement

This is a planning calculation, not a validated union backtest.

Holding the common-window Core result fixed at:
- 88 Core signals
- +1.6795% mean

To make a simple no-overlap Core+Monster signal union reach the Stable headline mean of +6.0607%, Monster would need approximately:

| added Monster signals | required Monster mean |
|---:|---:|
| 5 | +83.2% |
| 10 | +44.6% |
| 15 | +31.8% |
| 20 | +25.3% |
| 30 | +18.9% |
| 40 | +15.7% |
| 43 | **+15.0%** |
| 50 | +13.8% |

This demonstrates why Monster must be both selective and genuinely tail-seeking.

## Connection to existing descriptive Monster evidence

The previously recorded **weak-market + early-maturity Cloud Monster** descriptive subset had:
- n43
- mean **+14.56%**
- median +5.86%
- >=20% 39.5%
- top-3-removed mean +8.81%

Pure arithmetic using 88 Core signals at +1.6795% plus 43 hypothetical non-overlapping Monster signals at +14.56% gives a combined signal mean of roughly **+5.91%**, very close to Stable's +6.06%.

However:
- the Monster number is retrospective/descriptive;
- its exact date window / executable entry convention is not identical to this benchmark calculation;
- zero overlap has not been proven for that specific weak+early Monster subset;
- therefore **+5.91% is not a validated system backtest**.

It is only evidence that the two-lane architecture has the right order of magnitude.

## Research priority consequence

Core optimization is no longer the highest-value path.

The bottleneck is now clearly Monster:
1. keep Core fixed and forward-monitor it;
2. let the parallel V20 / Consensus Monster lane prove a genuinely prospective tail edge;
3. once a forward-qualified Monster implementation exists, run a common-window / common-entry / deduplicated Core+Monster benchmark against Stable ★6;
4. require not only Stable-like mean/tail capture, but also monitor whether the replacement retains Core's much lower large-loss rate.

The desired replacement is not a clone of Stable's return distribution. It should aim for **Stable-like upside with better robustness if possible**.
