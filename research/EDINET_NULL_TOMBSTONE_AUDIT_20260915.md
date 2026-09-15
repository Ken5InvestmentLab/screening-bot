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

The second failure is not a normal filing row. It has:

- `docTypeCode = null`
- `submitDateTime = "2023-01-10 15:30"` (timestamp retained)
- `withdrawalStatus = "1"`
- `parentDocID = "S100PV94"`
- `disclosureStatus = "0"`
- `xbrlFlag/pdfFlag/attachDocFlag/englishDocFlag/csvFlag/legalStatus = "0"`
- filing identity fields such as edinetCode/secCode/filerName/formCode are null

This means the first repair was too narrow because it required `submitDateTime=null`.

## Outcome-blind 2023 shape scan

Across the frozen 2023 metadata artifact, rows with `docTypeCode=null` or `submitDateTime=null` are distributed as:

- 32,852 rows: docType null, submitDateTime null, withdrawalStatus 0, disclosureStatus 0, all content/legal flags 0
- 52 rows: docType null, submitDateTime null, withdrawalStatus 2, disclosureStatus 0, all content/legal flags 0
- 31 rows: docType null, submitDateTime present, withdrawalStatus 1, disclosureStatus 0, all content/legal flags 0

Total: **32,935 inert document-list rows** in the inspected 2023 artifact.

No strategy returns, labels, or performance outcomes were opened for this audit.

## Narrow repair

The skip predicate is widened only to rows where:

1. `docTypeCode is null`
2. `disclosureStatus == "0"`
3. every content/legal flag is `"0"`

`submitDateTime` may be null or retained. All other malformed rows remain fail-closed.

Implementation commit: `819d63bbad4c995d8f6345280ce67df0e455effb`

Exact regression fixture commit: `90265c5ecc0b2e3d96d1c85f39eb665e9d4535fc`

OSS validation test run `34936903249`: **PASS**.

Full 2023-2025 metadata freeze retry `34936903153` is running. Do not loosen the predicate further without inspecting and freezing any new exact failing raw shape first.


## Repeated docID observation audit

The next full-freeze failure was not a network/API failure. Run `34936903153` acquired all three year artifacts successfully, then failed on repeated `doc_id` values.

Outcome-blind scan of the exact 2023-2025 artifacts found:

- normalized non-inert rows: **216,094**
- repeated doc IDs: **1,017**
- repeated observation rows: **2,056**
- every repeated doc ID keeps the **same submitDateTime**
- doc IDs touching preregistered doc types 120/130: **7**
- all 7 eligible repeated doc IDs are **120 -> 120** with identical submitDateTime
- no 120/130 repeated doc ID changes eligible status
- 56 repeated doc IDs change docType across observations, but none touch 120/130

Representative rows show EDINET emitting the same document again when `opeDateTime` / `docInfoEditStatus` changes. The frozen sample selector already sorts and deduplicates by `doc_id` after restricting to doc types 120/130.

### Narrow duplicate policy

The snapshot therefore no longer rejects all repeated doc IDs. It retains the repeated observations and records a receipt, while failing closed if either:

1. a repeated doc ID has conflicting `submitDateTime`, or
2. a repeated doc ID touches preregistered type 120/130 and its doc type is not identical across all observations.

This preserves the real EDINET document-list history while preventing any ambiguity that could alter the preregistered sample.

Implementation commit: `e05a17714e3d7e809d27a1eeb5abbfe1c44b9fe6`

Regression-test commit: `43fcdaa2dde2fb22be257828d930a1d0bdfba94b`

Triggered validation runs:

- OSS validation: `34940882491`
- full EDINET metadata freeze: `34940882530`

No returns, strategy labels, or performance outcomes were opened.
