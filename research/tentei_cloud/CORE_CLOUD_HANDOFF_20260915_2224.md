# Core + Cloud handoff — 2026-09-15 22:24 JST

## Core24
Start SHA `80bcd6c14cd3dcc7254f934af195eaf9d7e6d084` was already processed in coordination STATE v92; not duplicated.

P0 advanced from generic "find anchor universe" to an executable official-JPX route. The provenance capture now includes `https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html`, the official page publishing the previous-month-end List of TSE-listed Issues workbook. Commit `8c11ebfe1dc6122668acade4eea6480980f68af6` triggered run `34974570085`.

Next owner action:
1. collect run `34974570085` and artifact;
2. verify `listed_issues_page` HTTP 200 / bytes / SHA;
3. parse only the pinned HTML bytes to discover the official workbook href;
4. add byte-preserving workbook capture and pin workbook SHA/effective month-end;
5. reverse-replay frozen 375-event ledger to `2024-09-17` under `CORE_JPX_PIT_ANCHOR_SPEC_20260915.md`;
6. quarantine conflicts and freeze PIT membership receipt;
7. only after PIT PASS proceed to independent exact-hour activity evidence.

Do not substitute current JPxData CSV, Yahoo observation windows, search snippets, or a surrogate universe for the pinned official workbook. Do not open performance yet.

## Cloud Monster
Remain CLOSED / `HISTORICAL_EXACT_REPRO_UNAVAILABLE`. No new identity-critical evidence this run; do not restart family guessing.

## Guardrails
No production changes. No reject-family retune. No new costed calculations. New performance, when eventually opened, is cost 0% only and win = gross return > 0. 2026 remains report-only.
