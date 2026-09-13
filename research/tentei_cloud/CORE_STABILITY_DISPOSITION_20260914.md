# Core stability disposition — 2026-09-14

Research-only. Production remains unchanged.

## Scope
This closes the current fixed reconstructed Core/SAFE architecture as a replacement candidate. It does not reject the need for a Core lane; it rejects this specific fixed rule and the already-tested pruning approaches.

Canonical comparison contract for this disposition:
- branch: `research/tentei-cloud-mtf`
- source: extended Yahoo 1H panel reconstructed into the fixed 13:00 split Core representation
- universe: production-like prior daily close <= 1,000 JPY, prior daily volume >= 10,000 shares, candidate session volume >= 5,000 shares
- repeated symbols: 5 official XTKS-session cooldown
- endpoint: next official XTKS session open -> fifth official XTKS session close
- 2026: report-only; never used for selection/tuning

## Latest stability audit
GitHub Actions run: `34765954141` (success).
Artifact: `tentei-cloud-core-stability`, id `10321056091`, SHA-256 `cc5d5071dfb7b6924d3d1ed46fe14a20be95d95ed476f61374706f677392fed9`.

Zero-cost baseline:
- DEV 2024-11..2025-06: n=169, mean +1.3068%, median +1.2422%, win 58.58%, Top3-ex +0.9894%.
- 2025H2: n=140, mean +0.0808%, median -0.2389%, win 45.00%, Top3-ex -0.3498%.
- 2026YTD: n=118, mean +1.5555%; this is descriptive/report-only and cannot rescue the architecture.

Assumed 0.5% round-trip cost:
- DEV: mean +0.8068%, median +0.7422%, win 55.62%, Top3-ex +0.4894%; weekly-block bootstrap P(mean>0)=0.6656 and 95% mean CI [-2.09%, +2.68%].
- 2025H2: mean **-0.4192%**, median **-0.7389%**, win **41.43%**, Top3-ex **-0.8498%**; P(mean>0)=0.1902 and 95% mean CI [-1.25%, +0.53%].
- 2026YTD: mean +1.0555%, but report-only.

Assumed 1.0% round-trip cost:
- DEV: mean +0.3068%, Top3-ex -0.0106%.
- 2025H2: mean **-0.9192%**, median -1.2389%, win 35.0%, Top3-ex -1.3498%, P(mean>0)=0.0294.

Temporal robustness is also inadequate before costs: only 2/6 months in 2025H2 have positive mean; leave-one-month-out means range roughly -0.33% to +0.33%. The strong 2026 descriptive block is explicitly excluded from promotion logic.

## Decision
**REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT.**

Reasons:
1. 2025H2 central tendency is essentially flat before costs and negative after plausible costs.
2. Median and win rate are below zero/50% in 2025H2 even before costs.
3. Top3-ex mean is negative in 2025H2, so the result is not a robust broad Core edge.
4. Weekly-block uncertainty comfortably includes zero.
5. 2026 is stronger but is already exposed report-only evidence and cannot be used to rescue or retune the architecture.

Already closed pruning paths remain closed:
- broad-market hard regime gates;
- simple local single-feature hard gates;
- positive peer-momentum hard gates.

Do not threshold-tune the fixed Core on these opened outcomes. Do not rename the same architecture and retry it.

## Next Core research
A genuinely different low-DOF mechanism is preregistered separately as `CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json` before opening any outcomes. It is an event-family replacement, not a filter layered onto the rejected fixed Core.
