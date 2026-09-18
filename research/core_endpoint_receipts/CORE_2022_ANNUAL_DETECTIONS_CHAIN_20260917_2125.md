# Core P0 receipt — 2022 annual detections endpoint chain

Date: 2026-09-17 JST
Scope: research-only; no production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes.

## Source chain fixed

Freeze ref: `4b37f18d`

- `tvfree_screener/batch02/reports/annual_candidate_pool_2022_2026.csv`
  - 2022 rows are present.
  - family: `monster_weak_early_v20_lag1`
  - includes signal date, symbol, volr20/tail fields, cooldown status and year.
- `tvfree_screener/batch02/reports/annual_candidate_detections_2022_2026.csv`
  - 2022 DETECTED rows are present.
  - contains `signal_date`, `symbol`, `entry_date`, `exit_date`, `entry_price`, `exit_price`, `label_status`, `entry_fill_quality`, `label_definition`.
  - label definition is `v1_next_xtks_open_to_fifth_close_with_ohlcv_actionability_guards`.
  - observed 2022 rows are `label_status=RESOLVED` and carry concrete entry/exit prices.
  - however `entry_fill_quality=open_price_proxy_execution_unverified`; therefore this receipt does NOT promote those prices to verified canonical `entry_open`/`exit_close` and does NOT assert `true_missing=0`.

## P0 classification

This advances the 2022 raw artifact/receipt chain: the preserved annual detections file is a concrete historical rows source with canonical endpoint dates/prices and an explicit quality caveat. Under fail-closed policy, endpoint OHLC verification remains `UNKNOWN` until `entry_price` and `exit_price` are mechanically matched against the fixed daily corpus O/C for the same symbol/date.

No 2023-25 primary-five re-audit was performed. No 2026 data/outcome was opened. No all-market 797-invalid-row recheck was performed.

## Next mechanical step

Filter 2022 DETECTED rows, map `entry_price -> required entry_date Open` and `exit_price -> required exit_date Close`, then join to the fixed daily corpus. Emit per-row `symbol/date/field` for absent or mismatching endpoints, separating normal no-data / true missing / unknown. Only after exact selector identity is established should these rows be attributed to a Phase-2 comparison candidate such as volr20 LOW.