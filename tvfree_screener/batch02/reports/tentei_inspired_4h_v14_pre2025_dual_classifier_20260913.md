# Tentei-inspired 4H V14 — pre-2025 event-specific dual classifier — H1 result — 2026-09-13

Research-only. No production writes. Historical 2026 strategy outcomes were not opened.

## Overlap / lane boundary

Before this evaluation, the parallel ChatGPT lane was checked. That lane had frozen `TENTEI-STATE-ENTRY-REPRESENTATION-20260913` from an outcome-free V12 structure audit and explicitly stated that it must not alter V14. This lane therefore continued V14 only and did not re-run or modify the state-entry experiment.

## Input integrity

The preserved canonical daily input was recovered from artifact `10264205130` / `tvfree-frozen-dataset-run80-preserved`.

- `tse_daily.csv` SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0` — exact expected match.
- raw hourly source: existing 8-shard artifact run `34592896202`.
- fast timestamp parser equivalence checks:
  - pre-2025 V12 candidates after prior-daily gates: **7,099 / 1,065 symbols**, exact registered receipt;
  - H1 V12 candidates after prior-daily gates: **8,245**, exact official V12 count.

A preregistration wording issue was found before V14 H1 metrics were opened: the registered `7,099` count is the V12 candidate pool before V14's 19-feature finiteness exclusion. The committed V14 evaluator excludes rows missing any model feature. After that fixed exclusion, the actual model-fit pool is **4,924 rows / 966 symbols**. This clarification is recorded in `TENTEI_V14_INPUT_RECEIPT_CORRECTION.json`; no threshold, feature, label, or model parameter was changed.

## Frozen model

- training labels: resolved V12 events with candidate date before 2025 and 5BD exit before 2025-01-01;
- 2025 labels are not used for fit;
- model 1: probability of gross 5BD >= +20%;
- model 2: probability of gross 5BD <= -10%;
- fixed HistGradientBoosting parameters from the preregistered V14 spec;
- selection: first same-date+bin Pareto front maximizing p(+20) and minimizing p(-10), then p(+20) descending;
- Top1/2/3/5 with five-XTKS-session same-symbol cooldown;
- primary assumed round-trip cost: 0.5%.

Training prevalence after the fixed feature-finiteness rule:
- +20%: **1.056%**
- <=-10%: **2.660%**

H1 feature-complete validation rows: **8,227**.

## H1 March-June result

| TopN | n | net mean | median | win | >=+20% | <=-10% | Top1-excluded mean | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 163 | **-0.689%** | -1.717% | 40.49% | 4.91% | 14.11% | -1.147% | FAIL |
| 2 | 322 | -0.372% | -1.384% | 39.75% | 3.42% | 9.63% | -0.602% | FAIL |
| 3 | 464 | -0.582% | -1.300% | 40.52% | 2.16% | 8.19% | -0.742% | FAIL |
| 5 | 653 | -0.481% | -0.500% | 43.49% | 1.68% | 7.20% | -0.594% | FAIL |

At zero cost, Top2 and Top5 means become only +0.128% and +0.019%; winner-excluded means remain negative. Thus the failure is not merely the 0.5% cost assumption.

## Decision

**REJECT V14 AFTER H1 / DO NOT OPEN V14 H2.**

The event-specific classifier trained only on pre-2025 V12 events does not concentrate the 2025 H1 right tail. All frozen TopN policies fail both mean robustness and the >=10% +20%-tail objective.

Do not tune tree depth, class weights, score combination, feature set, or thresholds against this H1 result.

A likely next research question is outcome-free: whether pre-2025 V12 model features shifted materially by H1 2025. That should be diagnosed before another supervised ranker is proposed.

2026 outcomes opened: **false**.
Production modified: **false**.
