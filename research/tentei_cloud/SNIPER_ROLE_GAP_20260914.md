# Sniper short-horizon role gap — 2026-09-14 JST

Research-only architecture audit. No signal logic, thresholds, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, or V20 logic was modified.

## Product role being tested

Current Sniper is not primarily a Monster/tail mode. Its distinguishing role is:
- short 5BD horizon;
- comparatively high positive-return hit rate;
- moderate average return rather than dependence on a few huge winners.

Two preserved current-system snapshots are consistent with that role:

### Saved scoring-report snapshot — 2026-09-11
- confirmed n = 40
- mean = **+2.4%**
- win rate = **65.8%**
- official target = positive 5BD return

### current_logic_sniper.json snapshot — updated 2026-08-16
- n = 32
- decisive n = 30
- mean = **+3.1%**
- decisive win rate = **66.7%**

The exact n differs because the snapshots were generated at different dates/policies, but both describe the same product shape: roughly two-thirds positive outcomes.

## Does current Cloud Core fill this role?

Canonical-endpoint Core audit run `34766143681`:

2026 report-only:
- resolved n = 116
- mean = **+1.93%**
- median = +0.60%
- win rate = **53.45%**
- <= -10% = 1.72%
- top-5-winner-removed mean = +1.08%

Core is materially safer in large-loss frequency and has a robust-floor character, but its hit rate is about **12-13 percentage points below Sniper**.

Therefore Core should not be relabeled or marketed as the Sniper replacement merely because both use a 5BD horizon.

## Does current learned Monster fill this role?

Fixed expanding walk-forward Monster tiers are worse fits.

2026 folds combined:
- Watch: n57, approximately **40.4%** winners
- Prime: n15, approximately **26.7%** winners

They are intentionally tail-seeking and period-dependent. Their 2025H2 win rates were much higher, but that did not persist through 2026.

Monster is therefore the opposite of the Sniper product role.

## Architecture conclusion

**The current Cloud architecture has an uncovered short-horizon precision role.**

Current role map:
- Core = broad steady / low-downside 5BD floor;
- Monster Watch / Prime = rare positive-skew / tail lane, still awaiting forward qualification;
- Mega40-equivalent long-horizon lane = separately identified as missing;
- **Sniper-equivalent high-hit-rate 5BD lane = also missing.**

This does not mean the old Sniper formula must be cloned.

It means the replacement system still lacks a lane whose forward-qualified behavior is approximately:
- positive-return hit rate materially above Core;
- moderate positive mean;
- not dependent on extreme winners;
- canonical next-XTKS-open -> D+5-close evaluation;
- sufficiently broad n to matter operationally.

## What NOT to do

Do not:
- force Core thresholds to chase a 65% historical win rate;
- rename Monster as Sniper;
- select a high-win subset from already-opened 2025/2026 Core outcomes and call it validated;
- copy the legacy Sniper conditions merely to preserve the name.

Those would either damage Core's role separation or introduce direct overfit.

## Next research contract for this role

A future short-horizon precision hypothesis should be a **separate low-DOF lane** and must be preregistered before opening its selection outcomes.

Minimum design requirements:
- canonical next-XTKS-open -> fifth-XTKS-close target;
- PIT-valid universe / raw1H volume semantics;
- 2025H1 discovery only;
- 2025H2 locked validation;
- 2026 report-only;
- objective is not maximum mean alone;
- primary role metrics must include win rate, median, <=-10%, top-winner-removed mean, and sample size.

The eventual product name does not need to be decided yet. The important finding is that the **role itself is not currently covered**.
