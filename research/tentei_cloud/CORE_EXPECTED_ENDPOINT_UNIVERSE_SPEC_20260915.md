# Core24 expected endpoint universe contract — 2026-09-15

## Status
FROZEN / OUTCOME-BLIND / PERFORMANCE UNOPENED.

This contract governs construction of the `expected` input consumed by `missing_inventory_runner.py` for the recovered extended Yahoo 1H bytes. It does not change production, model logic, candidate selection, or performance.

## Why this gate exists
The recovered observed raw1H bundle is byte-pinned (`de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`), but an observed-key complement is meaningful only if the expected keys are independently justified.

A naive Cartesian expansion of `historically listed symbol × XTKS session × required Yahoo hour` is **forbidden**. Official listing membership proves that a security was eligible to trade; it does not prove that an illiquid security had a trade in every one-hour interval. Treating legitimate no-trade intervals as provider/data failures would inflate the missing inventory and could introduce outcome-dependent repair choices later.

## Evidence layers
An expected 1H endpoint key may be admitted only when all four layers pass:

1. **Point-in-time security identity / membership**
   - source: official JPX current domestic-common snapshot plus official JPX new-listing/delisting archives, or an equivalently pinned official historical master;
   - listing date inclusive; delisting date exclusive unless a pinned source explicitly defines otherwise;
   - ambiguous market classification, same-day conflicting event, code reuse across issuer episodes, or unpinned source bytes => fail closed / quarantine;
   - do not infer listing/delisting boundaries from first/last Yahoo observation.

2. **XTKS session calendar**
   - Core-adopted receipt: `CORE_XTKS_CALENDAR_PIN_20260915.json`;
   - exact CSV SHA-256: `58e67bd20be08d04c143fa7e8f707bb3b82c21c2de2af9dfd7c2a05a406de71b`;
   - 1,220 sessions from 2022-01-04 through 2026-12-30;
   - source branch commits are pinned in the Core receipt; generator is `exchange_calendars 4.13.1` with `XTKS` sessions-in-range;
   - exact session date must exist in this pinned calendar;
   - weekends/holidays may not be inferred from observed Yahoo rows.

3. **Raw-hour semantic contract**
   - AM required hours: 09,10,11,12 JST;
   - PM before 2024-11-05: 13,14 JST;
   - PM on/after 2024-11-05: 13,14,15 JST;
   - this follows the already-audited Yahoo/XTKS clock-bin rule; a pre-extension 15:00 flat close snapshot is not a required trading interval;
   - timestamp normalization must be deterministic and timezone-aware.

4. **Independent activity evidence**
   - each exact `(symbol, session_date, hour)` asserted as expected must have evidence independent of the Yahoo 1H file being audited that the interval should contain a bar/trade;
   - acceptable examples: pinned trade/tick/shorter-interval source, or another independently acquired formally accepted intraday source whose semantics establish interval activity;
   - JPX membership alone is not sufficient;
   - daily OHLCV, Google Finance snapshots, and absence/presence in the audited Yahoo 1H file are not sufficient to assert exact hourly activity;
   - no interpolation, forward/back fill, or daily-to-intraday synthesis.

## Required expected CSV
Columns are exactly:
- `symbol`
- `timestamp`
- `timeframe` = `1h`
- `decision_ts`
- `membership_source_sha256`
- `calendar_sha256`
- `activity_source`
- `activity_raw_sha256`

Every key must be unique. `timestamp <= decision_ts` is mandatory. Inputs and output are byte-hashed. Duplicate/conflicting identity or activity evidence fails closed.

## Inventory seal
Once the exact expected CSV is generated and SHA-pinned, run `missing_inventory_runner.py` once against the pinned observed bytes. Do not alter eligibility/activity evidence after viewing the resulting gaps. Any corrected input requires a new versioned contract + explicit reason, never silent replacement.

## Current evidence disposition
- exact observed Yahoo raw1H: PASS / pinned;
- official JPX point-in-time reconstruction code exists elsewhere in research and is outcome-blind in design, but its actual source receipts still must be frozen for Core before adoption;
- XTKS calendar: **PASS / Core-pinned** via `CORE_XTKS_CALENDAR_PIN_20260915.json`;
- exact interval-level independent activity evidence for the full recovered period has **not yet been pinned**;
- therefore formal missing inventory remains CLOSED. This is a provenance blocker, not a performance result.

## Cost / outcome guard
No strategy outcomes are read by this contract. No backtest is run. When performance later reopens after the data gate, all newly computed statistics use transaction cost 0% and win = gross return > 0; 2026 remains report-only.
