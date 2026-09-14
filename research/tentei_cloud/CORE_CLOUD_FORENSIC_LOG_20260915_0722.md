# Core + Cloud forensic log — 2026-09-15 07:22 JST

## Start-of-run dedupe / guardrail check
- `research/automation-coordination` STATE v63 and README read first.
- `research/tentei-cloud-mtf` starting HEAD was `8bcde5f474fb6f11b5979a876f342de6c87b567b`.
- STATE had both `last_seen_sha` and `last_processed_sha` equal to that HEAD, so that SHA was not reprocessed.
- Latest Supervisor coordination, RESEARCH_DASHBOARD, Core handoff `CORE_CLOUD_HANDOFF_20260915_0626.md`, recent Actions and artifacts were checked.
- current fixed Core / Failed-Breakdown Reclaim / Prior-Close Reclaim / Precision 3-family and other rejected families remain closed; no retune/rescue.
- production/main, production workflows/integrations, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater were not changed.
- Cloud exact remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; old `n=63 / +9.86%` remains historical evidence only.

## Evidence located
Outcome-blind infrastructure already exists on the coordination research branch:
- official-JPX point-in-time universe reconstruction (`tvfree_screener/point_in_time_universe.py`), including fail-closed handling of ambiguous market rows/same-day collisions and explicit code-reuse quarantine;
- frozen XTKS calendar manifest using `exchange_calendars 4.13.2`, 2022-01-04..2026-12-30, 1,220 sessions, CSV SHA-256 `74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68`;
- audited raw-hour semantics: AM 09/10/11/12 JST; PM 13/14 before 2024-11-05 and 13/14/15 from 2024-11-05 onward.

These are useful provenance components, but they are not by themselves sufficient to assert every exact expected 1H endpoint.

## Material forensic finding
A historically listed security on an XTKS session is only *eligible* to trade. It is not evidence that an illiquid security necessarily traded during every one-hour interval. Therefore a Cartesian expansion of `PIT member × XTKS session × required hour` would falsely label legitimate no-trade intervals as provider/data gaps.

That would contaminate the missing inventory before any fallback source is consulted. It is also inconsistent with the existing handoff rule that forbids naive full Cartesian expansion.

Formal expected keys therefore require an independent interval-level activity witness for each exact `(symbol, session_date, hour)`. The audited Yahoo 1H file cannot supply that witness because using the audited source to define its own expected rows is circular. Daily OHLCV and Google Finance snapshots also cannot establish exact hourly activity, and daily-to-intraday synthesis remains forbidden.

## Frozen action this run
Created `CORE_EXPECTED_ENDPOINT_UNIVERSE_SPEC_20260915.md` to freeze a four-layer evidence contract:
1. official point-in-time JPX identity/membership;
2. pinned XTKS session calendar;
3. frozen raw-hour semantics;
4. independent exact-hour activity evidence.

The expected CSV additionally binds membership, calendar, and activity source SHA-256 receipts. Missing-inventory execution remains sealed until this evidence passes. Once pinned, the inventory may be opened exactly once; later changes require a versioned correction with reason rather than silent replacement.

## Performance / cost state
- No strategy outcomes were opened.
- No backtest, portability statistic, or forensic performance comparison was computed.
- No 0.5%/1% transaction-cost calculation was run.
- Future newly computed performance remains cost 0% only; win = gross return > 0; 2026 remains report-only.

## Exact continuation
1. Pin the exact official-JPX source receipts needed by the PIT reconstruction into the Core evidence chain.
2. Pin the exact adopted XTKS CSV + manifest bytes on Core.
3. Locate and pin an independent intraday activity source capable of proving exact hourly activity for the recovered period, or formally record that such a source is unavailable.
4. Only if (3) succeeds, generate and SHA-pin the expected endpoint CSV and run `missing_inventory_runner.py` once against the already-pinned observed bundle.
5. Acquire fallback rows only for those declared missing pairs; record accepted/rejected/conflicted and coverage delta.
6. Keep performance closed until the data-provenance gate passes.

If independent activity evidence cannot be obtained, do not manufacture a formal missing inventory. Session/symbol coverage diagnostics may still be reported separately as diagnostics, but they are not a substitute for an activity-backed endpoint universe.
