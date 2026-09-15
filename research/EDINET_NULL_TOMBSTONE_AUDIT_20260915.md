# EDINET document-list inert-row audit — 2026-09-15

Research-only, outcome-blind data-integrity note.

## Source receipt

- Workflow run: `34922234308`
- Artifact: `edinet-metadata-2023`
- Artifact ID: `10378661856`
- Artifact digest reported by GitHub Actions: `sha256:ed838ba08104d6e1c379db0c45673ffd31359068c1c082cb9f1e68806993d496`
- Raw daily file inspected: `2023-01-10.json`
- Raw daily SHA-256: `a2dd6ebd77d4aa5819e267eec072575e050d2d6c60eea7dfc5bdd8873668039c`
- Failing row: result index 292 / seqNumber 293 / docID `S100PXGH`

## Exact second null shape

The second failure is not a normal filing row. It has `docTypeCode = null`, retained submitDateTime, disclosureStatus 0, and all content/legal flags 0. Across the frozen 2023 metadata artifact there are **32,935 inert document-list rows**. No strategy returns, labels, or performance outcomes were opened.

## Narrow repair

Skip only rows where docTypeCode is null, disclosureStatus is 0, and every content/legal flag is 0. All other malformed rows remain fail-closed. Implementation `819d63bbad4c995d8f6345280ce67df0e455effb`; fixture `90265c5ecc0b2e3d96d1c85f39eb665e9d4535fc`; OSS validation `34936903249` PASS.

## Repeated docID observation audit

Run `34936903153` acquired all three year artifacts successfully, then failed on repeated doc_id values. Outcome-blind scan found **216,094 normalized non-inert rows**, **1,017 repeated doc IDs**, **2,056 repeated observations**. Only 7 repeated doc IDs touch preregistered types 120/130; all 7 are 120 -> 120. 56 type-changing repeats do not touch 120/130. Implementation `e05a17714e3d7e809d27a1eeb5abbfe1c44b9fe6`; tests `43fcdaa2dde2fb22be257828d930a1d0bdfba94b`.

## Timezone-rendering false conflict

Fresh full-freeze run `34940882530` acquired all 2023/2024/2025 artifacts and reached the snapshot stage, then failed on docID `S1006Y3L` because the duplicate guard compared rendered timezone strings. The same historical local timestamp was rendered once as `+09:00` and once as `+09:18`, creating a formatting-level conflict rather than evidence of a different filing instant.

The guard is now narrower and more semantically correct: duplicate submitDateTime equality is checked by converting the already-parsed timestamps to normalized UTC instants (`pd.to_datetime(..., utc=True)`) and comparing those instants. The original Asia/Tokyo representation remains in emitted rows/receipt material; eligible 120/130 doc-type conflict remains fail-closed. No outcome data were opened and no selection/performance threshold changed.

Implementation commit: `77116de3e4d5ea19540d06eb9983f1d5b879ab0e`.

The commit triggers fresh OSS validation and EDINET full-freeze workflows. Next action is terminal inspection; if PASS, freeze metadata/sample receipts and proceed to selected ZIP byte SHA -> same-ZIP parser cross-check. If FAIL, inspect the exact next invariant before changing policy.
