# Core stability disposition — 2026-09-14

Research-only. Production remains unchanged.

## Endpoint correction history

The first stability/cost audit used a legacy **signal-session close -> fifth XTKS-session close** target. That evidence remains descriptive only and is not the canonical replacement endpoint.

A dedicated repair run then relabeled the **exact unchanged fixed-Core candidate set** with:
- entry: next observed official XTKS session open;
- exit: signal date + 5 official XTKS sessions close;
- no candidate-rule, threshold, cooldown, or cost change;
- 2026 kept report-only.

Canonical repair run: `34766143681` — success.
Artifact: `tentei-cloud-core-canonical-endpoint`, id `10320537228`, SHA-256 `ad66fd569f7d7423b5649ba314eb5dee4d752027ea76d44b85581148f06c7d8f`.

## Canonical next-open evidence

### DEV — 2024-11 through 2025-06

At 0.5% assumed round-trip cost:
- n = **169**
- mean **+0.712%**
- median **+0.509%**
- win **55.62%**
- +10% **7.10%**
- +20% **0.59%**
- <=-10% **3.55%**
- Top1-excluded mean **+0.587%**
- Top3-excluded mean **+0.393%**
- Top5-excluded mean **+0.211%**

The fixed architecture is positive in DEV under the canonical endpoint.

### 2025H2

At the same 0.5% cost:
- n = **140**
- mean **-0.452%**
- median **-0.745%**
- win **41.43%**
- +10% **1.43%**
- +20% **0.71%**
- <=-10% **2.14%**
- Top1-excluded mean **-0.700%**
- Top3-excluded mean **-0.874%**
- Top5-excluded mean **-1.006%**

This is a clear out-of-development deterioration.

At **0% cost**, H2 still does not show a robust Core profile:
- mean **+0.048%**
- median **-0.245%**
- win **45.71%**
- Top1-excluded mean **-0.200%**
- Top3-excluded mean **-0.374%**
- Top5-excluded mean **-0.506%**

Therefore the weakness is not explained by the 0.5% cost assumption alone.

### 2026YTD — report only

The canonical replay reports 116 resolved of 120 selected:
- 0.5% cost mean **+1.432%**
- median **+0.098%**
- win **50.86%**

This block is **report-only** and cannot rescue or tune the candidate.

## Canonical disposition

**REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT_CANDIDATE.**

Reason:
- canonical DEV is positive;
- canonical 2025H2 is negative on mean, median and winner-excluded robustness at the primary 0.5% cost;
- even zero-cost H2 has negative median, sub-50% win rate and negative winner-excluded means;
- 2026 is not allowed to overturn the H2 failure.

This decision rejects the **current fixed reconstructed Core architecture as a replacement candidate**. It does not authorize threshold tuning on the opened blocks.

Already rejected pruning paths remain closed:
- broad-market hard regime gates;
- simple local single-feature hard gates;
- positive peer-momentum hard gates.

## New-family status

`CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json` remains an outcome-unopened, genuinely new low-DOF Core hypothesis.

Now that the canonical endpoint repair is complete, that family may proceed only under its already-frozen contract. It must not inherit or retune the rejected fixed-Core thresholds from opened outcomes.

Production remains unchanged.
