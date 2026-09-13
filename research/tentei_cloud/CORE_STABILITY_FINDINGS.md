# Fixed reconstructed Core stability audit — 2026-09-14 JST

Research-only. No rule selection, threshold tuning, production write, V12/V15 event-representation change, or Monster logic change occurred.

## Purpose

After rejecting three simple Core pruning paths (broad-market gates, single local-feature gates, positive peer-momentum gates), this audit asks a different question:

**How stable is the fixed reconstructed Core itself?**

No new feature or condition is tested.

Uncertainty method:
- 5,000 bootstrap repetitions;
- sample whole ISO-week clusters with replacement;
- fixed seed `20260914`;
- this preserves same-week cross-sectional clustering better than row-wise resampling.

## Reproducibility

- trigger commit: `89194f5c914db2c6d6a3cbcf8bc5fafa664edc7b`
- workflow run: `34765762025`
- artifact: `10320111880`
- artifact ZIP SHA-256: `64751dd2a282619be0cebccefe0af2e0b24e1f5fc674b9d3b5a97e392ba66f47`
- script: `research/tentei_cloud/audit_core_stability.py`

## 2026 Jan-Aug — strongest stability block

Fixed Core baseline:
- n = **118**
- mean = **+1.56%**
- median = **+0.48%**
- win rate = **53.39%**
- >= +10% = **8.47%**
- >= +20% = **1.69%**
- <= -10% = **1.69%**
- top-1 winner removed mean = **+1.27%**
- top-3 removed mean = **+0.92%**
- top-5 removed mean = **+0.66%**

Monthly:
- Jan +3.71%
- Feb -1.49%
- Mar +3.35%
- Apr +0.78%
- May +0.59%
- Jun +2.95%
- Jul +0.68%
- Aug +1.43%

So **7 of 8 months were positive**. February was the only negative month.

### Leave-one-month-out

Removing any single 2026 month leaves the aggregate mean positive:

- minimum leave-one-month-out mean: **+1.10%**
- maximum: **+2.00%**
- all 8 leave-one-month-out means: positive

This is strong evidence that the +1.56% mean is not produced by one isolated calendar month.

### Week-cluster bootstrap

5,000 week-cluster bootstrap repetitions:
- probability bootstrapped mean > 0: **99.18%**
- 95% bootstrap interval for mean: **+0.29% to +2.88%**

This interval remains above zero despite resampling entire weeks.

## Historical contrast

### DEV — 2024-11 through 2025-06

- n169
- mean +1.31%
- 5/8 positive months
- bootstrap P(mean>0) 77.18%
- 95% mean interval **-1.65% to +3.16%**
- leave-one-month-out fails robustness because removing April 2025 changes aggregate mean to -0.44%

DEV therefore contains useful Core behavior but is materially dependent on April 2025.

### 2025H2

- n140
- mean +0.08%
- only 2/6 positive months
- bootstrap P(mean>0) 57.12%
- 95% mean interval **-0.76% to +1.03%**
- leave-one-month-out mean ranges -0.33% to +0.33%

This block is effectively flat and does not establish a stable edge.

## Decision

The fixed reconstructed Core has a **credible stable positive 2026 block**, but should not be described as universally stable across all historical regimes.

What is supported:
- 2026 Jan-Aug performance is not driven by one winner or one month.
- top-winner removal remains positive.
- week-cluster bootstrap mean interval stays above zero.
- the large-loss rate is low relative to Monster research.

What is not supported:
- a claim that the same Core edge was stable in 2025H2.
- using 2026 strength to retroactively tune 2025 filters.

Architecture implication:
- keep Core broad and fixed;
- treat it as the current steadier lane, especially based on 2026 evidence;
- do not force another pruning rule merely to improve historical averages;
- preserve Monster as a separate positive-skew lane rather than asking Core to produce Monster-like returns.

The next useful Core work should focus on execution/cost sensitivity and genuinely forward monitoring, not additional outcome-driven filtering of the already-opened history.
