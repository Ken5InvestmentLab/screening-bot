# Core24 JPX PIT anchor parser contract — 2026-09-15 23:24 JST

Research-only. No production changes. No performance opened.

## Immutable source
- Artifact: `10398473275` from Actions run `34974864648` (SUCCESS)
- Workbook: `listed_issues_workbook.xlsx`
- bytes: `227579`
- SHA-256: `4d10497c2aa03bcca0b92f0673d3ab19ecc6aca6a9c9a70a3e19cd490f1d8754`
- JPX source URL: `https://www.jpx.co.jp/english/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_e.xlsx`
- `jyoujyou(updated)_e.xlsx` remains excluded correction evidence and MUST NOT be substituted.

## Workbook verification
Immutable artifact was opened directly. Workbook has one sheet, `Sheet1`, 4,442 rows including header, 10 columns.

Exact header row:
`Effective Date | Local Code | Name (English) | Section/Products | 33 Sector(Code) | 33 Sector(name) | 17 Sector(Code) | 17 Sector(name) | Size Code (New Index Series) | Size (New Index Series)`

Every inspected data row carries Effective Date `20260831`; parser MUST require a single effective date over all non-empty rows and fail closed otherwise. Anchor effective month-end is therefore `2026-08-31`.

## Frozen eligibility contract
Target universe is TSE domestic individual equities only. Anchor rows are eligible iff `Section/Products` is exactly one of:
- `Prime Market (Domestic)`
- `Standard Market(Domestic)`
- `Growth Market(Domestic)`

Current anchor counts under this exact filter: Prime 1,556; Standard 1,555; Growth 596; total 3,707.

Explicitly excluded: ETFs/ETNs, PRO Market, REIT/Venture/Country/Infrastructure funds, all Foreign market rows, Equity Contribution Securities, and any unknown/new section label. Unknown labels quarantine/fail closed; do not infer eligibility from code/name.

## Identity normalization
- `Local Code` is canonicalized as trimmed uppercase string, preserving alphanumeric codes (e.g. `130A`). Numeric spreadsheet cells are rendered without decimal suffix.
- Identity key is `(local_code)` for membership replay; name is audit metadata only.
- Duplicate eligible anchor code with conflicting identity/section is quarantine and blocks PASS.

## Replay boundary
Start from eligible membership at close/effective snapshot `2026-08-31`. Reverse-replay the already-frozen 375 JPX listing/delisting events to target `2024-09-17` without retuning or surrogate sources. Events later than the target are reversed in descending effective-date order. A forward listing is undone by removal; a forward delisting is undone by restoration only when its event market segment is Prime/Standard/Growth domestic-equity eligible. Conflicts or impossible transitions quarantine and block PIT PASS.

No Cartesian `membership × XTKS × hour` expected-key generation is permitted from membership alone. Independent exact-hour activity evidence remains a separate prerequisite after PIT membership receipt.
