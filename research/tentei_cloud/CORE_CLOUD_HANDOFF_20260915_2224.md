# Core + Cloud handoff — 2026-09-15 22:24 JST

## Core24
Start SHA `80bcd6c14cd3dcc7254f934af195eaf9d7e6d084` was already processed in coordination STATE v92; not duplicated.

P0 advanced from generic "find anchor universe" to an executable official-JPX route. Run `34974570085` SUCCESS pinned the official `List of TSE-listed Issues` publication page: 30,060 bytes, SHA-256 `19dd761cdf1ef75ce02e84a398c97dc2be4ee44021824756b6450a906cfe9389`, artifact `10399005661`, digest `sha256:900252325c56d7d7a966dfba7b789217ca32973e7c1a947972733efd21cf39fa`.

Important forensic correction: the pinned page exposes TWO Excel hrefs. The first selector version chose `jyoujyou(updated)_e.xlsx`; artifact inspection proved this is the historical April-2022 correction workbook (337 rows, `Effective Date` 20220428), not the current universe. It is therefore explicitly rejected as an anchor and must not enter PIT membership.

The actual current listed-issues workbook href in the same pinned page is `/english/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_e.xlsx`. Commit `bf1de1d2875463fc43b284664499011d36293c4a` fixes discovery to require exactly one `/data_e.xlsx` and records the correction workbook only as excluded evidence. Actions run `34974864648` is capturing the corrected workbook.

Next owner action:
1. collect run `34974864648` and artifact;
2. verify `data_e.xlsx` HTTP 200 / bytes / SHA and inspect workbook header/effective month-end;
3. freeze anchor-universe parser/eligibility contract before performance;
4. reverse-replay frozen 375-event ledger to `2024-09-17` under `CORE_JPX_PIT_ANCHOR_SPEC_20260915.md`;
5. quarantine conflicts and freeze PIT membership receipt;
6. only after PIT PASS proceed to independent exact-hour activity evidence.

Do not use the rejected correction workbook, JPxData surrogate, Yahoo observation windows, search snippets, or a guessed universe. Do not open performance yet.

## Cloud Monster
Remain CLOSED / `HISTORICAL_EXACT_REPRO_UNAVAILABLE`. No new identity-critical evidence this run; do not restart family guessing.

## Guardrails
No production changes. No reject-family retune. No new costed calculations. New performance, when eventually opened, is cost 0% only and win = gross return > 0. 2026 remains report-only.
