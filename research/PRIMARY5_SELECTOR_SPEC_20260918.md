# PRIMARY5_SELECTOR_SPEC_20260918

Status: RESEARCH ONLY / PARTIAL EXACT PIN. 2026 SEALED. No production writes. No use of old 2022 29-row/23-date membership or performance.

Authoritative context: STATE v133 and `DETERMINISTIC_2022_FALLBACK_MANIFEST_20260918.md`. Eligible pool for every selector is the same signal-date pool after V9 raw Tail (`tail_cdf >= 0.999`) and frozen weak+early gate (`med_ret5 <= 0 AND ret10 <= 0.5735294117647058`). Candidate identity is `signal_date + symbol + candidate_name`.

Feature source is validation commit `d9792122a541847c3e4ed82604bffa220dab4a33`, path `tvfree_screener/run.py`; V7/V9 source blobs are respectively `f7f49ab2e09496494adfb365c94e969973c4070c` and `45a1272fe49c526bbf69956419e34e96d696f7d6`. Input is artifact `10264205130`, `tse_daily.csv`, content SHA256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`.

## User-facing display names — PINNED

The research/internal selector identities remain unchanged for reproducibility. User-facing labels are pinned as follows:

| User-facing name | Internal selector identity |
|---|---|
| **Shadow** | `mean-rank(volr20, body_pct)` |
| **Dive** | `body_pct LOW` |
| **Silence** | `volr20 LOW` |
| **Fusion** | `DUAL_TOP1_AGREEMENT` |
| **Balance** | `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF` |

These are display aliases only. Do not alter selector expressions, ranking, tie-breaks, candidate identity fields, or historical hashes solely to apply these names.

## Shared deterministic ordering
All ranks are cross-sectional within one `signal_date`, ascending for LOW. To make exact reconstruction independent of input row order, equal metric values are resolved by lexical ascending `symbol`. This is a deterministic identity tie-break only; it is not selected from returns or the old 2022 summary. Missing required selector values fail closed for that candidate/date.

## C1 — body_pct LOW — PINNED
Required columns: `date/signal_date`, `symbol`, `open`, `high`, `low`, `close`, `body_pct` plus upstream gate identity fields.
Feature expression from `run.py`: `rng=(high-low)` with zero range -> NaN; `body_pct=(close-open)/rng`.
Selector: for each signal date, order `(body_pct ASC, symbol ASC)` and select exactly row 1.
Ranking: ordinal position in that deterministic ordering; no percentile threshold and no return field.
Output candidate name: `body_pct LOW`.

## C2 — volr20 LOW — PINNED
Required columns: `date/signal_date`, `symbol`, `volume`, `volr20` plus upstream gate identity fields.
Feature expression from `run.py`: per symbol, `va20 = rolling(volume,20,min_periods=20).mean()`; `volr20=volume/va20`, zero denominator -> NaN.
Selector: for each signal date, order `(volr20 ASC, symbol ASC)` and select exactly row 1.
Ranking: ordinal position in that deterministic ordering.
Output candidate name: `volr20 LOW`.

## C3 — mean-rank(volr20, body_pct) — PINNED
Required columns: all C1+C2 selector columns.
Within each signal date compute deterministic ordinal ranks `r_body` from `(body_pct ASC,symbol ASC)` and `r_vol` from `(volr20 ASC,symbol ASC)`. Define `mean_rank=(r_body+r_vol)/2`. Select one row ordered `(mean_rank ASC, r_body ASC, r_vol ASC, symbol ASC)`.
Output candidate name: `mean-rank(volr20, body_pct)`.

## C4 — DUAL_TOP1_AGREEMENT — PINNED
Required columns: C1+C2.
Compute C1 top-1 and C2 top-1 independently under the exact ordering above. Emit a row iff both top-1 symbols are identical; otherwise emit no C4 row for that signal date. No fallback to second place.
Output candidate name: `DUAL_TOP1_AGREEMENT`.

## C5 — DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF — FAIL-CLOSED PENDING G3 VALUE SEMANTICS
C5 first requires C4 identity. The current authoritative manifest names the frozen gate `G3 NO_ACUTE_SELLOFF` but deliberately requires its threshold semantics to come from a pinned existing-value receipt/code. The latest STATE/Dashboard and admissible manifest do not contain that expression/threshold/source SHA. Therefore this spec does NOT invent one. C5 remains PENDING until that exact G3 source is supplied/pinned; :48 may generate C1-C4 now and must not approximate C5.

## Implementation handoff
`:48` can implement C1-C4 directly against the deterministic weak+early ledger produced by entrypoint commit `42e5cd8fd7e9e34e90ddae790b1d4cbd3ede1887`. Preserve `signal_date,symbol,candidate_name,body_pct,volr20` and upstream model/gate identity columns in emitted ledgers. Do not inspect endpoint returns while selecting. C5 is fail-closed, not a reason to block C1-C4 TRADE_ROWS.
