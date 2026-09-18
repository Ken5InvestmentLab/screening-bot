# V16 alternate-family historical complete receipt

ALT_HISTORICAL_COMPLETE=YES
CANDIDATE_ADMISSIBILITY=GO
SCOPE=REFERENCE_FAMILY_ONLY_NOT_PRIMARY
PERIOD=2022-2025
ENDPOINT=signal T -> next XTKS open -> fifth XTKS close
TRANSACTION_COST=0%
WIN_DEFINITION=gross_return > 0

## Frozen provenance
- candidate/source commit: `bcc2b9f1ce2a2b8ce6bc02e21be72c48899690d5`
- V16 selection blob: `13fd0e87e81034757ca6b6f0a0b57abecae35109`
- 2022 workflow run/artifact: `34605714116` / `10266990667`; artifact SHA256 `8254745a3508742de49339e6460a095a51c0a904442bb7f9cf3636da1aaa012e`; n=31; endpoint audit 31/31, missing=0.
- fixed daily corpus artifact: `10264205130`; SHA256 `095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`.
- causal Tail cache 2023-2025 artifact: `10264251140`; SHA256 `2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198`.
- 2023 canonical CSV SHA256: `1b304bb2a3c417967e0d94e263c8c4cc6acb5afb44fba43324928fb018810a1f`; n=70.
- 2024 canonical CSV SHA256: `ba5b8e9f68e1af309f9b8f16df6f94d85b037b071eb6366ec24af5b93405d674`; n=102. This serialization was regenerated from the frozen source/input chain; the same generator reproduced the already-pinned 2023 and 2025 CSV SHA256 byte-for-byte. It supersedes the earlier receipt-only 2024 byte digest `f19ce667...` while preserving the frozen candidate identity and 102-row result.
- 2025 canonical CSV SHA256: `d7dc0fa5716e9abdcb64b347bcd1762af16e13b7e889c4b6ae8355d6c1580169`; n=70.

## Historical metrics
All rates and returns are percentages. Top3-ex = mean gross return after removing the three largest gross-return rows. 100-share P/L = sum of `(exit_close-entry_open)*100`, no capital constraint/netting/fees.

| period | n | mean | median | win | +10 | +20 | -10 | -20 | max up | max down | Top3-ex | 100-share P/L |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022 | 31 | 1.2874 | -6.7340 | 35.4839 | 12.9032 | 12.9032 | 32.2581 | 9.6774 | 118.1303 | -35.1122 | -7.2694 | -49,611.11 JPY |
| 2023 | 70 | 0.1806 | -4.4401 | 41.4286 | 22.8571 | 15.7143 | 40.0000 | 21.4286 | 106.4039 | -41.0550 | -3.9135 | -9,286.67 JPY |
| 2024 | 102 | 2.9224 | -1.8250 | 46.0784 | 27.4510 | 18.6275 | 34.3137 | 13.7255 | 111.1111 | -52.3704 | 0.0430 | +32,340.00 JPY |
| 2025 | 70 | 1.3043 | -9.2491 | 34.2857 | 22.8571 | 14.2857 | 42.8571 | 17.1429 | 130.0000 | -46.4539 | -3.5407 | -60,865.00 JPY |
| 2022-2025 aggregate | 273 | 1.6188 | -5.4286 | 40.6593 | 23.4432 | 16.1172 | 37.7289 | 16.1172 | 130.0000 | -52.3704 | 0.3063 | -87,422.78 JPY |

## Reproduction check
The frozen V16 selector (`med_ret5<=0`; sort date/volr20 asc then tail_cdf/tail_p desc; same-day top4; one-XTKS-business-day same-symbol cooldown) was applied to the fixed causal Tail cache and fixed daily corpus. Re-running this chain produced 2023 n=70 SHA256 `1b304...10a1f` and 2025 n=70 SHA256 `d7dc...0169`, exactly matching their pinned canonical CSVs; 2024 produced n=102 with zero missing endpoints.

## Guards
- V16 backward is an alternate/reference exact family only; never merge its 2022 n=31 with primary 2022 volr20 n=23.
- No candidate selection was made from performance values.
- strict_3pt remains parked/reference-only.
- 2026 remains sealed and was not opened.
- No production/main/workflow/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes.
