# Core / Monster complementarity findings — 2026-09-14 JST

Research-only architecture audit. No Core or Monster rule, production workflow, Discord, Spreadsheet, or parallel V20 temporal-coverage work was modified.

## Question

Are fixed Core and fixed walk-forward Monster Watch/Prime actually complementary, or are they mostly different names for the same candidates?

Definitions:
- Core = fixed reconstructed SAFE/Core rule.
- Monster Watch/Prime = fixed expanding walk-forward 4H ensemble, Watch q65 / Prime q90.
- exact overlap = same symbol + date + reconstructed session.
- same-day overlap = same symbol + date, ignoring session.

No allocation, weighting, or threshold was optimized.

## Reproducibility

- trigger commit: `ad6b3da3176c00210094dd6e17989d813781e208`
- workflow run: `34770490191`
- artifact: `10321568115`
- artifact ZIP SHA-256: `7c1712d8ff6a099277990c93ba4b240432c0538cda025e5a367a95f924e8c2ed`
- script: `research/tentei_cloud/audit_core_monster_complementarity.py`

## Overlap result

Across every fixed walk-forward test block:

- 2025H2
- 2026 Jan-Feb
- 2026 Mar-Apr
- 2026 May-Jun
- 2026 Jul-Aug

the result was:

- **Core ∩ Watch exact overlap = 0**
- **Core ∩ Prime exact overlap = 0**
- **Core ∩ Watch same-symbol same-date overlap = 0**
- **Core ∩ Prime same-symbol same-date overlap = 0**

This is stronger than merely “low correlation”: the fixed reconstructed lanes selected completely disjoint symbol-date candidates over the audited folds.

## Timing complementarity

The two lanes also tend not to activate on the same days.

Core vs Watch daily signal-count correlations:
- 2025H2: -0.02
- 2026 Jan-Feb: -0.55
- 2026 Mar-Apr: -0.38
- 2026 May-Jun: -0.05
- 2026 Jul-Aug: -0.61

Common active days were sparse:
- 2025H2: 7 days
- Jan-Feb: 2
- Mar-Apr: 2
- May-Jun: 5
- Jul-Aug: 4

Where enough common active days existed to estimate daily return correlation, it was near zero or negative:
- 2025H2 Core vs Watch: -0.01
- May-Jun: +0.09
- Jul-Aug: -0.75

Small common-day counts mean these correlations are descriptive only, but the activation pattern clearly differs.

## Performance consequence

Distinct does **not** mean both lanes should be blindly merged.

Core 2026 Jan-Aug:
- n118
- mean +1.56%
- comparatively low downside and strong 2026 stability evidence.

Fixed Monster Watch across 2026 folds:
- n57
- weighted mean about **-0.51%**

Fixed Monster Prime across 2026 folds:
- n15
- weighted mean about **-0.14%**

Monster is highly period/tail dependent:
- 2025H2 Watch mean +4.62%
- May-Jun 2026 Prime contained one +27.0% winner
- but Jan-Feb, Mar-Apr, and Jul-Aug Monster tiers were weak or negative.

Descriptive exact-deduplicated unions illustrate the risk:
- Jan-Feb and Mar-Apr: adding Monster worsened Core.
- May-Jun: Prime improved the union because of the +27% tail event.
- Jul-Aug: adding Monster again worsened Core.

Therefore a single blended “Core + Monster” score would hide two genuinely different behaviors and can dilute the steadier lane during weak Monster regimes.

## Decision

**Keep Core and Monster as separate named lanes. Do not merge them into one score or one undifferentiated signal class.**

Supported architecture:
- **Core:** steadier, broader, lower-downside lane.
- **Monster:** separate positive-skew / rare-tail lane that still needs stronger forward stability evidence.
- Same symbol/date duplicate-suppression is currently unnecessary because audited overlap was zero, but retaining a defensive dedup guard in eventual production is still sensible.
- User-facing notifications should preserve the lane identity rather than present Core and Monster as equivalent confidence levels.

The complementarity hypothesis passes; the “blind union improves performance” hypothesis does not.
