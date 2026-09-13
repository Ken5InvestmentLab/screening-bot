# Tentei-inspired V12 state-entry H1 evaluation — 2026-09-13

Research-only retrospective evaluation of the separately frozen `TENTEI-STATE-ENTRY-REPRESENTATION-20260913` hypothesis. This does not rewrite V12/V13/V14 and does not use 2026 strategy outcomes.

## Reproduction correction before result acceptance

The first local reconstruction produced 6,521 H1 state-entry rows, nine more than the frozen structural reference. That run was not accepted. The discrepancy was traced to warm-up scope: the outcome-free structure audit retained raw rows from **2024-12-01**, while the first reconstruction had included earlier September-November 2024 observations. Because Wilder-style RSI/ATR state is recursive, the earlier start can change later indicator state.

The evaluator was corrected to the frozen warm-up start `2024-12-01`. The H1 structural state-entry count then reproduced exactly at **6,512**, matching the preregistered reference. No threshold or event rule was changed.

## Frozen H1 result

Sequence: V12 causal state -> first-transition/state-entry filter -> prior completed daily close <= 1,000 JPY and volume >= 10,000 shares -> five-XTKS-session same-symbol cooldown -> common next-session-open to fifth-session-close endpoint.

- H1 structural state-entry rows before daily gate: **6,512**
- After prior-day price/volume gate: **5,330**
- After five-session cooldown: **3,445**
- Endpoint resolved: **3,445 / 3,445**

At assumed 0.5% round-trip cost:

- mean: **+1.4647%**
- median: **+0.6385%**
- win rate: **55.27%**
- +10% rate: **9.06%**
- +20% rate: **2.03%**
- +50% rate: **0.087%**
- <= -10% rate: **4.41%**
- <= -20% rate: **0.58%**
- best-one-excluded mean: **+1.3354%**
- best-three-excluded mean: **+1.2987%**

Cost sensitivity: mean **+1.9647%** at 0% cost and **+0.9647%** at 1% cost.

## Decision

`REJECT_AS_MONSTER / DO_NOT_OPEN_H2_FOR_THIS_HYPOTHESIS`.

The hypothesis has strong central tendency and low downside in H1, but it fails the frozen Monster right-tail gate decisively: +20% rate is **2.03%**, versus the required **>=10%**. This is not a near miss and does not justify opening H2 to search for rescue evidence.

Do not tune state-entry definition, trigger paths, cooldown, thresholds, daily gates, or cost assumptions from this H1 result. H2 for this state-entry hypothesis remains unopened. 2026 strategy outcomes remain unopened. Production remains unchanged.

Reproducible runner: `tvfree_screener/batch02/eval_tentei_state_entry_h1.py`.
