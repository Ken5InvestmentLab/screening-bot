# Causal 4H Monster V11 — weak reversal ignition event gate — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen hypothesis

Preregistered before V11 outcome evaluation in `CAUSAL_4H_MONSTER_V11_WEAK_REVERSAL_IGNITION_SPEC.json`.

Instead of ranking every eligible 4H bin, V11 first required a causal intraday event:
- market cohort breadth positive <= 50%;
- prior four 4H-bar mean log return <= 0;
- current 4H bar log return > 0;
- current range >= prior-four mean range;
- current same-bin raw volume >= the prior-20 same-bin median.

The gate is fully intraday-led and uses no current-day finalized daily OHLCV.

Feature-only population before outcome access:
- 13,873 events = 3.48% of the 2025 candidate population;
- 232 active dates;
- 1,210 symbols;
- AM 8,366 / PM 5,507.

The unchanged V10 21-feature q10/q50/q90 monthly causal model was then trained on event rows only, with V8 q90/q10 Pareto selection.

## H1 model-ranked results

March-June event evaluation rows: 4,734.

At 0.5% round-trip cost:
- Top1: n=124, mean -0.83%, >=+20% 7.26%, <=-10% 22.58%, Top1-excluded mean -1.71%. FAIL.
- Top2: mean -1.00%, >=+20% 5.24%. FAIL.
- Top3: mean -0.49%, >=+20% 5.11%. FAIL.
- Top5: mean -0.72%, >=+20% 3.78%. FAIL.

All frozen Monster policies fail. Per the preregistered rule, H2 remains unopened for V11.

## Gate-population diagnostic

To separate event-generation quality from ML ranking quality, the entire H1 event pool was compared with the entire otherwise-eligible H1 base population. This is a diagnostic of the already-frozen gate, not a threshold search.

At 0.5% cost:
- Base population (133,399 rows): mean about -0.01%, median -0.37%, win 46.12%, >=+20% 1.53%, <=-10% 5.09%.
- V11 event population (4,734 rows): mean **-1.06%**, median **-1.08%**, win **37.28%**, >=+20% **1.92%**, <=-10% **7.67%**.

The event gate provides only a small increase in +20% frequency while materially worsening mean, median, win rate and large-loss frequency.

## Decision

**REJECT V11 AT CANDIDATE-GENERATION LEVEL.**

The failure is not merely the q10/q50/q90 ranker. The frozen weak-reversal/ignition gate itself creates an inferior H1 population.

Do not tune its breadth, drift, range or volume thresholds against these outcomes.

The next direction should return to the sparse 4H mechanism family that motivated the existing production system: Bollinger/RSI/squeeze/persistence/reversal structure. Exact TradingView matching is not required for the new system, but the existing Pine mechanism may provide a better hypothesis class than generic all-bin ML ranking.

2026 outcomes opened: false.
Production modified: false.
