# Core endpoint reproducibility audit — 2026-09-14 22:47 JST

## Scope

Research-only forensic/reproducibility audit. No rejected Core family is reopened or retuned. No performance outcome is recomputed. No production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater change.

Cloud Monster historical exact replay remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no new contemporaneous identity-critical evidence was found, so model-family guessing and portability replay remain prohibited.

## Frozen evaluation contract

- Any future new calculation in this lane: transaction cost **0% only**.
- Win definition: gross return > 0.
- Canonical endpoint: next XTKS trading-session open -> fifth XTKS trading-session close, with the entry session counted as holding session 1.
- 2026 outcome: report-only, never selection/tuning input.
- Required statistics when a valid new evaluation exists: period n, mean 5BD, median, win, +10/+20/+50, -10/-20, Top1/Top3 removed, month/week dependence.

## Outcome-blind reproducibility findings

Current `research/tentei_cloud/audit_core_canonical_endpoint.py` is cost0-only and emits the required gross summary/dependence fields, but it derives the trading-date sequence from dates *observed in the downloaded raw panel* and labels entry/exit using that sequence.

This creates two reproducibility/provenance risks before any new performance result can be treated as canonical:

1. **Observed-date calendar risk.** A market-wide missing date in the source panel can silently compress the calendar and move the nominal `next open` / `fifth close` dates. Canonical evaluation must be bound to a pinned XTKS calendar, not inferred solely from data presence.
2. **Endpoint-row completeness risk.** Daily open/close are reconstructed from the first/last available raw intraday rows. A partial symbol/session can therefore supply an apparent entry open or exit close even when the true required endpoint row is missing. Canonical evaluation must fail closed unless the required entry/exit session rows satisfy an explicit completeness contract.

These are audit findings, not evidence that any historical metric is wrong. No strategy outcome was opened to discover them.

## Next safe action

Before any Core endpoint rerun, freeze a data-only endpoint provenance contract that:

- pins the XTKS calendar/version/hash used for signal->entry->exit mapping;
- defines the required intraday row(s) for the official entry open and exit close;
- records source run/artifact SHA or immutable receipt;
- counts missing/non-finite endpoint rows and fails closed rather than shifting to another observed date/row;
- leaves candidate selection, thresholds, cooldown and rejected-family decisions untouched.

Only after that contract is implemented and tested may an already-frozen candidate set be re-labeled cost0 for reproducibility comparison. This is not permission to reopen or promote rejected Core families.
