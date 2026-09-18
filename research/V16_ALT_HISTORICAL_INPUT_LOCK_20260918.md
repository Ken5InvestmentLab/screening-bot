# V16 alternate-family historical input lock — 2026-09-18

CANDIDATE_ADMISSIBILITY=GO
SCOPE=REFERENCE_FAMILY_ONLY_NOT_PRIMARY
NEXT_TARGET=2023_CANONICAL_ROWS

## Candidate identity
Frozen at source commit `bcc2b9f1ce2a2b8ce6bc02e21be72c48899690d5`.
Selection implementation: `tvfree_screener/v16_pre2025_volr20_rank.py`, blob `13fd0e87e81034757ca6b6f0a0b57abecae35109`.
2022 runner: `tvfree_screener/v16_backward_2022.py`, blob `159994c571403f7c349dded7a3851a5d9338a479`.
Rule: V7 extreme Tail (cdf>=0.999), med_ret5<=0, same-day volr20 ascending, tail_cdf/tail_p descending tie-break, one-business-day same-symbol cooldown.

## Canonical endpoint contract
signal T -> next XTKS open -> fifth XTKS close; cost=0%; win iff gross return > 0.
2022 anchor remains workflow run `34605714116`, artifact `10266990667`, digest `sha256:8254745a3508742de49339e6460a095a51c0a904442bb7f9cf3636da1aaa012e`, n=31, Supervisor endpoint audit 31/31, missing=0. It is not primary 2022 volr20 n=23.

## Locked cross-year inputs
Daily corpus: run `34599959356`, artifact `10264205130` (`tvfree-frozen-dataset-run80-preserved`), digest `sha256:095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`, source head `d03cdff1f27628f44f78d3787b0cc55bfa4bd271`.
Causal Tail cache 2023-2025: run `34600083474`, artifact `10264251140` (`tvfree-v7-causal-tail-cache-2023-2025`), digest `sha256:2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198`, source head `ef8754d835ccb39faf783092f969417a3ea74ce9`.

## Frozen generation command shape
For each year Y in 2023, 2024, 2025: load the locked daily corpus and locked causal Tail cache; filter Tail rows to `Y-01-01..Y-12-31`; construct trading_dates from the daily corpus; call the frozen V16 `select(tail_year, trading_dates)`; normalize endpoints from the daily corpus under the canonical endpoint contract; emit year-specific canonical rows plus SHA256 receipt. No rule tuning or candidate-name search.

TRADE_ROWS_2023=PENDING_GENERATION
TRADE_ROWS_2024=PENDING_GENERATION
TRADE_ROWS_2025=PENDING_GENERATION

## Guards
No 2026. strict_3pt remains REFERENCE_ONLY/PARKED absent a new explicit artifact. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist-builder/updater changes.