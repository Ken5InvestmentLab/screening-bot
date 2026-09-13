# Tentei-inspired V12 ALL as Core — H2 retrospective check

Research-only. This hypothesis was frozen after H1 had already been exposed, so the H2 readout is retrospective refutation evidence only. It does not modify the V12 generator, V13, V14, Monster models, or production.

## Frozen interpretation

Use the unchanged V12 ALL candidate generator, unchanged prior-completed-daily price/volume gates, unchanged five-XTKS-session same-symbol cooldown, and the common next-session-open to fifth-session-close endpoint. No trigger-path selection or tail model is used.

Frozen Core gate: resolved n >= 50; 0.5%-cost mean > 0; median >= 0; win rate > 50%; Top3-winner-excluded mean > 0; <=-10% rate <= 20%. H2 must pass every gate. A pass could only keep the hypothesis alive for prospective shadow evidence; it could not promote retrospectively.

## H2 result — 2025-07-01 through 2025-12-31

- raw V12 ALL signal rows before prior-day gates: **15,604**
- after prior-day close/volume gates: **12,438**
- after five-session same-symbol cooldown: **6,205**
- endpoint resolved: **6,205 / 6,205**

At assumed 0.5% round-trip cost:

- mean: **-0.5023%**
- median: **-0.5000%**
- win rate: **41.05%**
- +10% rate: **3.63%**
- +20% rate: **1.03%**
- +50% rate: **0.258%**
- <= -10% rate: **3.63%**
- <= -20% rate: **0.55%**
- best-one-excluded mean: **-0.5455%**
- best-three-excluded mean: **-0.5736%**

Cost sensitivity does not rescue the interpretation: at 0% assumed cost the mean is approximately **-0.0023%**, median **0%**, win **46.25%**, and Top3-excluded mean remains negative. At 1% cost mean is **-1.0023%**.

## Decision

**REJECT_V12_AS_CORE_RETROSPECTIVE**.

The unchanged V12 ALL population does not generalize from its positive H1 central tendency into H2. It fails mean, median, win-rate, and Top3-exclusion Core gates. Do not tune V12 thresholds, trigger paths, cooldown, daily gates, or Core criteria against H2.

2026 strategy outcomes opened by this lane: **false**. Production modified: **false**.

Frozen spec: `tvfree_screener/batch02/TENTEI_V12_CORE_RETROSPECTIVE_SPEC.json`.
