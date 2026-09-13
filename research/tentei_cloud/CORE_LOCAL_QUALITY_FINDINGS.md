# Core local-quality audit — 2026-09-14 JST

Research-only. Production, Discord, Spreadsheet, current Stable/Sniper/Mega, the separate V12/V15 event-representation lane, and the separate gap-up Core experiment were not modified.

## Scope

This audit tested only five candidate-local signal-time features inside the already-fixed reconstructed Core:

- RSI(12)
- BB reclaim width: close / BB20 mid - 1
- ATR(14) / close
- reconstructed-session volume / previous daily volume
- close / EMA75 - 1

No broad-market features, gap-up features, V12/V15 event-representation features, or feature combinations were used.

Protocol:
- DEV = 2024-11-01..2025-06-30.
- DEV_A = 2024-11-01..2025-02-28.
- DEV_B = 2025-03-01..2025-06-30.
- Each feature got exactly one outcome-independent threshold: pooled DEV median.
- LOW and HIGH sides were compared.
- A side could freeze only if, in BOTH DEV halves, it had n>=15, higher mean, no-worse median, and no-worse <=-10% rate than the opposite side.
- At most one feature could freeze; no combinations or secondary threshold sweeps.

## Reproducibility

- trigger commit: `e19a8ee27976444f520f1fbfff083ebc37e9675f`
- workflow run: `34765124157`
- artifact: `10320890234`
- artifact ZIP SHA-256: `1c576a3c7cec5c53e3f87f755a3edc41dc54b07385e732eb8a4a28532ff13ef1`
- script: `research/tentei_cloud/audit_core_local_quality.py`

## Result

**No feature/side qualified. No rule was frozen.**

Notable diagnostics:

- RSI: lower RSI was better in DEV_A but materially worse in DEV_B. Direction reversed.
- BB reclaim: smaller reclaim was better in DEV_A but larger reclaim was better in DEV_B. Direction reversed.
- EMA75 gap: closer-to-EMA75 was better in DEV_A but worse in DEV_B. Direction reversed.
- ATR high side had higher mean and median in both DEV halves, but <=-10% rate was worse in both:
  - DEV_A mean +0.44% vs -0.16%, but loss10 5.56% vs 2.04%.
  - DEV_B mean +2.84% vs +0.92%, but loss10 3.03% vs 2.78%.
  This violates Core's lower-downside objective.
- Higher session/previous-day volume ratio had higher mean in both DEV halves:
  - DEV_A +0.60% vs -0.54%.
  - DEV_B +2.43% vs +1.88%.
  But median/downside conditions were not consistently better across both halves, so it also failed the preregistered gate.

## Decision

**Do not add a hard candidate-local quality filter to Core from these five features.**

Combined with the previous regime audit, two common simplification paths are now rejected:
1. broad-market hard gating;
2. simple single-feature local hard gating.

The fixed reconstructed Core itself remains useful as the steadier lane; the evidence currently favors preserving its breadth rather than pruning it with simple thresholds.

Any later soft-ranking experiment using ATR or session-volume ratio must be explicitly registered as a new hypothesis and must not retroactively call this audit a pass.
