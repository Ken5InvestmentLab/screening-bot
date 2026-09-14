# OSS/Validation handoff — 2026-09-14 13:53 JST

Branch: `research/oss-validation-tooling`  
Scope: research-only. Production/main and all production integrations remain untouched.

## Current frozen contracts

- `research/OPTUNA_DISCOVERY_CONTRACT_20260914.json`: Optuna is discovery-only, 2022-07-01..2023-12-31 selection period, later periods excluded from selection, one optimized parameter (`LogisticRegression C`), all trial Sharpes retained for PSR/DSR sensitivity.
- `research/EDINET_OSS_CROSSCHECK_CONTRACT_20260914.json`: same-ZIP custom-vs-edinet-tools parser audit, parser disagreement fail-closed for research admission, issued-share semantic priority fixed before outcome inspection.

## EDINET real-sample boundary

Commit `8d4188e6e67a56a837bba4903dbdc1911ccda332` preregistered the real historical sample before opening any real parser comparison:

- 2023-01-01 through 2025-12-31;
- document types 120 and 130;
- calendar-quarter x doc-type strata;
- first two unique doc IDs by submit datetime ascending then doc ID ascending;
- metadata only may select rows;
- full-period metadata coverage is required;
- selected filings are not replaced because a parser fails or disagrees;
- selected doc IDs and source ZIP hashes are frozen before mismatch review;
- strategy returns, ranks, labels, model scores, accounting values and 2026 market outcomes are forbidden sample-selection inputs.

The preregistration CI run `34807402370` completed **SUCCESS**.

## Metadata selector implementation

A deterministic selector now exists in `tvfree_screener/edinet_oss_sample_selector.py`:

- commit `6b46dda3980aec746022cc6f2b16405b1332304d` adds the selector and a receipt with input/sample hashes;
- commit `2d0e5177ffbd481bf655a1fc9d9f8e5d80f901b0` adds deterministic-order, incomplete-coverage, and required-metadata fail-closed tests;
- commit `a642bee0da15391dfa448c351ca923fc5715fc62` wires selector/tests into isolated OSS CI.

CI run `34807566909` is currently in progress. No real EDINET parser comparison has been opened yet.

## Next safe action

1. Collect `34807566909`; fix only selector/infrastructure defects if it fails.
2. Locate or materialize an EDINET document-metadata source that demonstrably covers the full frozen 2023-2025 interval.
3. Run the selector once, freeze the selected doc IDs plus metadata-input/sample hashes.
4. Fetch/materialize the exact selected XBRL-to-CSV ZIP bytes without replacement around parser failures.
5. Freeze each ZIP hash, then run the custom and edinet-tools parsers against identical bytes.
6. Treat all mismatches/one-sided missing values as audit findings; never choose a parser based on strategy outcome.

Optuna/purgedcv work remains available for the next genuinely new family, but no rejected or outcome-opened family is being reopened here.
