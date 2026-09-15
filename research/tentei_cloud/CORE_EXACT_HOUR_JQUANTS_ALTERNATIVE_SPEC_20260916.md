# Core exact-hour activity alternative-source spec — 2026-09-16 08:24 JST

## Finding
JPX/JPXI announced on 2026-01-19 that **J-Quants API now provides equity minute-bar and tick data** as an add-on for Light Plan or higher. JPX describes the data as equity tick-by-tick and minute-bar data, delivered daily (not real time). The add-on fee announced by JPXI is JPY 5,500/month including tax, in addition to an eligible base plan.

Official references:
- https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260119.html
- https://www.jpx.co.jp/english/markets/other-data-services/j-quants-api/

## Contract assessment
This is a materially cheaper candidate than FLEX Historical for the frozen independent exact-hour witness contract. Tick data is semantically sufficient if it exposes actual cash-equity executions with issue code and timestamps. Minute bars are also potentially sufficient for **activity presence** if their rows are emitted only when actual trades occurred; that emission/zero-volume behavior must be verified from official API specification or pinned raw evidence before adoption.

## Critical unresolved point
The currently inspected public JPX pages do not establish the historical lookback available for the tick/minute add-on far enough to cover the Core research window beginning 2024-09-17. Therefore J-Quants is classified:

`LOWER_COST_OFFICIAL_CANDIDATE_HISTORY_COVERAGE_UNVERIFIED`

It must not yet generate formal expected keys.

## Acceptance path
1. Obtain/pin official J-Quants tick/minute API specification showing endpoint fields, timestamp semantics, trade/activity semantics, and historical availability window.
2. If coverage includes the required 2024-09-17 onward period, acquire a small raw sample first and freeze byte/response SHA, request parameters, API version, and acquisition timestamp.
3. Verify symbol mapping, JST/session mapping, and whether absent/zero-volume minute rows distinguish no-trade from missing data.
4. Prefer tick executions when available; deduplicate actual executions to `(symbol, session_date, raw_hour)`.
5. Only after source completeness is established, bind activity-key SHA to the frozen PIT membership/calendar receipts and open the one-shot missing inventory runner.

## Guardrails
FLEX Historical remains an accepted semantic source, but expensive access is no longer the only official path under investigation. Yahoo raw1H self-witness, membership×calendar×hour, synthesized intraday rows, performance opening, rejected-family retune, and production/main changes remain forbidden. Cloud Monster remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`.
