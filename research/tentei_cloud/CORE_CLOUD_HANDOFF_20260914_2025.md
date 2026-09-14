# Core + Cloud handoff — 2026-09-14 20:25 JST

## Start-state audit
- `research/automation-coordination` STATE had `research/tentei-cloud-mtf` last_seen/last_processed at `291cbdd41f98d24da29a5b2f0195893c5b8ae884`, matching the actual Core/Cloud HEAD at run start. No already-processed Core SHA was reprocessed.
- Latest Core/Cloud Actions remained historical only; no new Action was associated with the start HEAD. The most recent listed Core workflow remained Precision Discovery Batch run `34799307163` (SUCCESS).
- Existing rejected families remain closed: current fixed Core, Failed-Breakdown Reclaim, Prior-Close Reclaim, Precision 3-family, and previously rejected simple-gate families. No strategy retune/relabel/replay was run.
- Old Cloud Monster remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`. Historical `n=63 / 5BD mean +9.86%` remains legacy evidence only; no new original identity-critical model/script/manifest evidence appeared, so no model-family guessing or portability replay was performed.

## New reproducibility-contract finding
The stale-contract audit found two additional research documents that still contradicted the current user-mandated cost policy:

1. `CORE_FORWARD_EVALUATION_CONTRACT_20260914.md`
   - still required newly computed 0.5% round-trip cost stress metrics;
   - early/main gates still depended on 0.5%-cost net performance.

2. `FINAL_REPLACEMENT_COMPARISON_PROTOCOL_20260914.md`
   - still required newly computed 0.5% stress comparisons and Precision costed metrics.

These were contract/documentation defects, not new strategy evidence.

## Repair
- Commit `c13231739c3fd28a2b52f1d274f21eff45b1a296` hardens the Core forward evaluation contract to **transaction cost 0% only**, `win = gross return > 0`, preserves legacy costed evidence only as historical context, and adds the required +50% / -20% / monthly / ISO-week reporting surface.
- Commit `7e1ce41468c89df0c1cd1a43653ab0aefa48c876` aligns the final replacement comparison protocol to the same cost0-only rule and removes new nonzero-cost requirements from comparison/ranking logic.
- No candidate thresholds, score logic, cooldown, entry/exit rule, or selection policy were changed.
- No backtest/workflow was triggered, so there is no new performance result and no ranking / GO-NO-GO change.

## Cloud forensic
- Status stays `HISTORICAL_EXACT_REPRO_UNAVAILABLE`.
- Historical headline stays separated from any modern reproduction: `n=63 / 5BD mean +9.86%` is not a newly reproduced result.
- Exact 575 Watch pool plus identity-critical original model/features/transforms/calibration/training manifest remain unavailable.
- Do not resume surrogate/model-family guessing absent genuinely new contemporaneous original evidence.

## Production safety
No changes were made to main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or updater.

## Next action
Continue outcome-blind reproducibility auditing for stale cost/endpoint assumptions in remaining Core/Cloud research contracts/scripts. Do not rerun rejected families merely to regenerate metrics. Keep Cloud exact replay closed unless genuinely new original evidence appears.
