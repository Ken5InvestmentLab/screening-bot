# Walk-forward regime-veto findings — 2026-09-14 JST

Research-only. Production, Discord, Spreadsheet, Stable/Sniper/Mega, V12 state-entry work, and the separate V14 lane were not modified.

## Scope

This audit deliberately stayed outside the parallel V12/V14 work. It used the already-fixed reconstructed 4H walk-forward ensemble from `research/tentei-cloud-mtf` and changed neither its feature set, model parameters, target, seeds, Watch quantile, nor Prime quantile.

Only **previous-trading-day** broad-market context was attached. Missing regime context was fail-open.

Fixed vetoes:
- `VETO_RISK_OFF_MOMENTUM`: exclude when prior-day cross-sectional median 5D return <= 0 **and** 20D breadth is not rising versus five sessions earlier.
- `VETO_WEAK_NARROW_FALLING`: the above plus breadth20 < 50%.
- `VETO_BREADTH_BREAKDOWN`: breadth20 < 50% and breadth20 is not rising.

No veto threshold was fit to candidate outcomes. The 2025H2/2026 blocks were already inspected in prior research, so this is retrospective causal evidence, not pristine OOS validation.

## Reproducibility

- Trigger commit: `35a72aa5a38983ce87c2744a149273e1efd958fb`
- Workflow run: `34764604761`
- Artifact: `10319184830`
- Artifact ZIP SHA-256: `38375ca380fd602d9bc0b80db9378e4daebd0e1036e7bacc731d2b0b264bd40d`
- Script: `research/tentei_cloud/audit_walkforward_regime_veto.py`
- Candidate context complete for all selected Watch/Prime rows.

## Aggregate result

### Watch

| policy | n | mean | median | win | >=10% | >=20% | <=-10% | top-3 removed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NONE | 70 | +0.44% | 0.00% | 44.3% | 10.0% | 4.29% | 4.29% | -0.85% |
| risk-off momentum veto | 45 | +0.51% | 0.00% | 44.4% | 13.3% | 4.44% | 4.44% | -0.95% |
| weak+narrow+falling veto | 57 | +0.27% | 0.00% | 43.9% | 10.5% | 3.51% | 3.51% | -0.88% |
| breadth-breakdown veto | 57 | +0.27% | 0.00% | 43.9% | 10.5% | 3.51% | 3.51% | -0.88% |

The broad risk-off veto removes 25/70 Watch picks but improves mean by only **+0.07 percentage points** and makes top-3-removed mean slightly worse. The other two vetoes reduce aggregate mean. None qualifies as a Watch improvement.

### Prime

| policy | n | mean | median | win | >=10% | >=20% | <=-10% | top-3 removed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NONE | 20 | +1.59% | -0.34% | 40.0% | 15.0% | 10.0% | 0.0% | -1.77% |
| risk-off momentum veto | 15 | +2.53% | 0.00% | 40.0% | 20.0% | 13.3% | 0.0% | -1.99% |
| weak+narrow+falling veto | 19 | +1.88% | 0.00% | 42.1% | 15.8% | 10.5% | 0.0% | -1.63% |
| breadth-breakdown veto | 19 | +1.88% | 0.00% | 42.1% | 15.8% | 10.5% | 0.0% | -1.63% |

The risk-off momentum veto raises Prime mean by **+0.94 percentage points**, but the sample drops from 20 to 15 and robustness is not established.

## Temporal stability

The risk-off momentum veto is not directionally stable:

- 2025H2 Watch: +4.62% -> +2.56% (**worse**)
- 2026 Jan-Feb Watch: -1.64% -> -2.18% (**worse**)
- 2026 Mar-Apr Watch: -2.40% -> +0.17% (**better**)
- 2026 May-Jun Watch: +1.60% -> -0.18% (**worse**)
- 2026 Jul-Aug Watch: +0.31% -> +1.13% (**better**)

Prime also remains unstable:
- 2025H2: +6.76% -> +7.96%
- Jan-Feb: -1.85% -> -1.55%
- Mar-Apr: -1.53% -> -0.34%
- May-Jun: +27.01% -> unchanged
- Jul-Aug: -2.67% -> **-4.15%**

The full candidate-pool regime audit independently showed the same non-stationarity: the `RISK_OFF_ONLY` bucket was poor in Jan-Apr and Jul-Aug, but **strong in May-Jun**. Therefore the regime state should not be assumed to have a fixed sign for Monster-like setups.

## Decision

**Do not add a blanket market-regime veto to Watch or Prime.**

- Watch: reject all three vetoes.
- Prime: `VETO_RISK_OFF_MOMENTUM` is the only version worth retaining as a **forward-observation hypothesis**, not as a promoted rule.
- Do not tune thresholds or add combinations against these already-opened outcomes.
- Prefer logging/annotating the regime state on future selections so genuinely new forward data can decide whether a Prime-only veto is useful.

The primary Monster lesson is that regime interaction is conditional/non-stationary. A hard global risk-on filter would suppress profitable contrarian periods and is not justified by this evidence.
