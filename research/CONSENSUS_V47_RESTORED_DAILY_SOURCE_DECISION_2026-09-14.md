# V47 restored/delisted daily source decision — 2026-09-14

Outcome-free data-integrity note. Strategy returns/model scores remain unopened.

## Yahoo global chart result

Authoritative V47D v6 run 34788533946:
- expected restored/delisted PIT symbols: 251
- Yahoo direct fetch usable symbols: **0 / 251**
- every request failed as HTTP 429 in that run
- daily_coverage_pass: false

To distinguish rate-limit from actual delisted-symbol removal, a separate five-symbol query2+crumb probe was run:
- run 34798785536
- symbols: 1439, 5595, 7205, 8515, 8940
- crumb endpoint: HTTP 200
- chart endpoint: **HTTP 404 for all 5**
- Yahoo message: `No data found, symbol may be delisted`

Conclusion: old-code Yahoo history is genuinely unavailable for at least the probe set; changing query1/query2/crumb alone does not solve restored-history coverage.

## 96ut daily fallback probe

Run 34798904873 tested the same type of delisted codes via 96ut yearly history pages.

All five probe symbols returned daily OHLCV:
- 1439: 2024 241 rows; 2025 23 rows through 2025-02-10
- 5595: 2024 245 rows; 2025 219 rows through 2025-11-26
- 7205: 2024 245 rows; 2025 243 rows through 2025-12-30
- 8515: 2024 245 rows; 2025 243 rows through 2025-12-30
- 8940: 2024 245 rows; 2025 219 rows through 2025-11-26

Independent spot-check on 3350 confirms 96ut presents point-in-time nominal pre-split prices/volumes rather than Yahoo's present-basis split-normalized history.

## Full restore

Full 251-symbol restore run: **34798987098**
- 10 deterministic shards
- max-parallel=2
- years 2024, 2025, 2026
- one request per code/year with 1 second pacing
- outcome-free only

Early receipts:
- shard 0: 26/26 symbols recovered
- shard 1: 25/25
- shard 2: 25/25
- shard 3: 25/25
- first 101/101 recovered, missing 0

## Intraday consequence

96ut is a daily fallback, not a recovered historical 1H source.

Therefore:
- full-PIT promotion-grade path still requires historical 1H coverage under the frozen raw1H acceptance contract;
- if delisted 1H remains structurally unavailable, use the preregistered `V47S_SURVIVOR_SHADOW` fallback only for non-promotion research;
- do not lower full-PIT coverage thresholds or impute 1H from daily bars.

Production modified: false.
