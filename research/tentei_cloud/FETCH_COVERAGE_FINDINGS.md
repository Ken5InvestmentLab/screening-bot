# Yahoo 1H historical coverage findings — 2026-09-14 JST

Research-only data-quality audit. No model, production workflow, Discord, Spreadsheet, V12/V15 event representation, or legacy-4H repair logic was modified.

## Source / reproducibility

Extended Yahoo 1H research pull:
- target symbols: 1,332
- seen symbols: 1,315
- raw rows: 4,019,524
- failed chunks: 272 across 61 symbols
- HTTP 400: 153
- HTTP 404: 119

Coverage topology audit:
- trigger commit: `5940e8ce59c7ed1784a99e5f46b467d0d192e9af`
- workflow run: `34765338387`
- artifact: `10320545595`
- artifact ZIP SHA-256: `022a8632015e467f859ce615ab826c6695355410b578f96889e9d9e396d56b05`
- scripts:
  - `audit_fetch_failures.py`
  - `audit_fetch_failure_topology.py`

## Failure topology

Across the 1,332-symbol target set:
- **1,271 symbols:** no failed chunks
- **44 symbols:** failures only BEFORE the first observed Yahoo 1H bar
- **17 symbols:** never observed at all
- **0 symbols:** failure interval overlapping the observed history
- **0 symbols:** after-last-only failures

This is important: **where Yahoo returned history, the chunked pull has no detected internal holes.**

## The 17 never-seen symbols

All 17 are 2026 delistings in the JPX delisted-stock list:

| code | company | delisting date |
|---|---|---|
| 1726 | BR Holdings | 2026-06-01 |
| 2196 | ESCRIT | 2026-03-30 |
| 2686 | G-FOOT | 2026-06-23 |
| 3541 | Nousouken / Agricultural General Research Institute | 2026-04-27 |
| 3681 | V-cube | 2026-07-01 |
| 3924 | Land Computer | 2026-03-30 |
| 3961 | Silver Egg Technology | 2026-03-23 |
| 5856 | LIEH | 2026-06-26 |
| 6173 | Aqualine | 2026-06-01 |
| 6210 | TOYO INNOVEX | 2026-03-30 |
| 6293 | Nissei Plastic Industrial | 2026-03-30 |
| 7205 | Hino Motors | 2026-03-30 |
| 7455 | PARIS MIKI Holdings | 2026-03-30 |
| 7922 | Sanko Sangyo | 2026-06-25 |
| 8289 | Olympic Group | 2026-06-29 |
| 8515 | AIFUL | 2026-03-30 |
| 9067 | Maruun | 2026-06-04 |

JPX source: https://www.jpx.co.jp/listing/stocks/delisted/

Therefore these are not random current-symbol fetch misses. Yahoo currently does not provide the requested historical 1H windows for these delisted tickers.

## The 44 before-first-only symbols

The 44 split into two qualitatively different groups.

### 39 genuine recent-listing windows

- 38 alphanumeric new-listing codes (323A, 330A, ... 604A) have failures only before their first observed/listed history.
- 8729 Sony Financial Group is observed from 2025-09-29, which is its actual TSE listing date.

These pre-first failures are structurally expected and should not be treated as internal data loss.

### 5 legacy numeric codes with Yahoo history truncation around delisting

| code | observed Yahoo 1H span in this pull | listing status evidence |
|---|---|---|
| 2162 | 2026-07-17 .. 2026-08-27 | delisted 2026-08-28 |
| 3271 | 2026-07-17 .. 2026-07-27 | delisted 2026-07-28 |
| 5103 | 2026-07-17 .. 2026-08-24 | delisted 2026-08-25 |
| 6096 | 2026-07-17 .. 2026-07-28 | delisted 2026-07-29 |
| 7851 | 2026-07-17 .. 2026-09-10 | JPX delisting scheduled 2026-10-01 |

JPX source: https://www.jpx.co.jp/listing/stocks/delisted/

These are long-standing numeric codes, not new-listing codes. Their earlier requested Yahoo 1H chunks failed while a short terminal window remained available. This is consistent with **provider-side historical truncation associated with delisting / delisting status**, not with the normal new-listing pattern.

## Research consequence

The broad Yahoo 1H comparison set is internally contiguous for symbols it can observe, but it is **not point-in-time complete**.

At minimum:
- 17 / 1,332 = **1.28%** of target symbols are fully absent because the tickers subsequently delisted.
- Adding the 5 legacy numeric partial-history symbols gives 22 / 1,332 = **1.65%** of the target universe with materially compromised historical intraday coverage tied to delisting status.

This creates survivorship-related selection risk because delisting/distressed names are not random members of the universe and could disproportionately affect downside or Monster-tail research.

Do not describe the Yahoo 1H historical dataset as full-universe or survivorship-free.

## Decision / ownership boundary

- Keep the current Yahoo dataset for controlled Core/Monster comparisons, with the limitation explicitly attached.
- Do not silently delete the 17 or 5 affected symbols from historical-universe claims.
- Do not fabricate intraday bars from daily OHLCV.
- Historical recovery of these delisted symbols should use an independently validated real intraday/legacy source if available.
- The parallel V12/V15 data-quality lane already owns legacy-4H / causal intraday reconstruction and source-reconciliation work. This branch will **not duplicate that repair work**.

The useful result from this lane is the precise failure classification: no detected internal holes, but a delisting-linked survivorship hole affecting 22 target symbols.
