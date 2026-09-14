# Core + Cloud handoff — 2026-09-14 19:24 JST

## Start-state audit
- `research/automation-coordination` STATE had `research/tentei-cloud-mtf` last_seen/last_processed at `0886fd65f9413dc2591a47475364e736516dbf93`, matching the actual Core/Cloud HEAD at run start; no previously processed SHA was reprocessed.
- Existing rejected families remain closed: current fixed Core, Failed-Breakdown Reclaim, Prior-Close Reclaim, Precision 3-family, and prior simple-gate families. No retune/relabel was run.
- Cloud remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no new contemporaneous original model/script/manifest evidence appeared, so no model-family guessing and no portability replay were performed.

## New reproducibility finding
Cross-lane endpoint/cost-contract audit found a stale research script contract in `research/tentei_cloud/audit_core_canonical_endpoint.py`:
- it still enumerated `COSTS = [0.0, 0.005, 0.01]`, so a future trigger would have recomputed 0.5% and 1% costed metrics contrary to the current lane rule;
- it did not emit `+50%` and `-20%` rates required by the current evaluation contract;
- it did not emit month/week dependence tables.

This was a reproducibility-contract defect, not new strategy evidence.

## Repair
Commit `f1a1bd23d7e7286b9390d84ffaf18069043c53e8` hardens the canonical endpoint audit so that any future new computation:
- uses transaction cost **0% only**;
- defines win as gross return > 0;
- emits +10/+20/+50 and -10/-20 rates plus Top1/Top3 removed means;
- writes monthly and ISO-week dependence tables;
- keeps 2026 report-only;
- does not change candidate selection or thresholds.

No workflow trigger file was touched, so this repair did not launch a new backtest and generated no new ranking/GO-NO-GO evidence.

## Cloud forensic
Historical Cloud Monster headline remains legacy evidence only: n=63 / 5BD mean +9.86% / median +3.33% / win 57.1%. Exact 575 Watch pool and identity-critical model/features/transforms/calibration/training manifest remain unavailable. Exact replay stays closed unless genuinely new original evidence appears.

## Production safety
No changes were made to main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or updater.

## Next action
Continue cross-lane reproducibility auditing for stale cost/endpoint contracts. Do not run rejected Core families merely to regenerate metrics. Cloud exact replay remains closed absent new original identity evidence.
