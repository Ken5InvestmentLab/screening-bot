# Core + Cloud forensic research log — 2026-09-16 05:23 JST

Started from coordination state v101 and Core HEAD `bb7cc18df849cbe6095113af52c277905164b6fb`; that SHA was already processed, so this run only advanced new evidence.

Downloaded immutable JPX artifact `10411777912` and parsed the exact anchor workbook plus pinned listing/delisting/transfer HTML. Found that the prior 04:24 correction fixed mixed-date parsing for transfer rows but the listing/delisting forensic count still retained a period-required month parser. JPX writes May without a period. This omitted valid May delistings in 2025/2026.

Corrected exact-byte counts: through 2026-09-10, listing=134 and delisting=263, total=397. Reverse-replay window `(2024-09-17, 2026-08-31]`: listing=134, delisting=261, transfer=81, total=476. Starting from the frozen 3,707-code 2026-08-31 anchor, strict reverse transitions completed with zero quarantine and yielded 3,834 target members. Sorted `CODE,SEGMENT` membership SHA-256 is `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`.

No performance was opened. No costed calculation, reject-family retune, Cloud model-family guessing, main/production/workflow/Discord/Spreadsheet/TradingView/watchlist change occurred. Cloud Monster remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`.

Next P0: freeze a machine-readable PIT membership receipt and then move to independent exact-hour activity evidence; never manufacture expected hourly keys from membership alone.