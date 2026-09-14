# OSS/Validation handoff — 2026-09-14 14:55 JST

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

The preregistration CI run `34807402370` completed **SUCCESS**. The deterministic selector CI run `34807566909` also completed **SUCCESS**.

## Metadata selector + snapshot audit layer

The deterministic selector in `tvfree_screener/edinet_oss_sample_selector.py` remains the only component allowed to choose the real filing sample.

This run added a provenance layer before that selector:

- `561fddb1c0ae33b7128fe2f9886f652982c0e305` adds `tvfree_screener/edinet_metadata_snapshot.py`;
- `bb6b424906c6ef5bf3384ae9f2fc851925906ad7` adds fail-closed tests for missing calendar days, non-200 metadata status, malformed required fields, duplicate doc IDs, deterministic timezone normalization, and outcome-blind manifest flags;
- `1de1597af88be852fb264a30cbf6cc60f0b5042f` wires the snapshot tests into isolated OSS CI.

The snapshot layer deliberately performs **no network acquisition**. It consumes exact raw daily EDINET JSON responses named `YYYY-MM-DD.json`, requires every calendar day in the frozen interval, hashes every raw response, builds a deterministic daily hash chain, normalizes only `docID` / `docTypeCode` / `submitDateTime` plus source date, and emits a manifest with `strategy_outcomes_opened=false` and `parser_outputs_used_for_selection=false`.

This keeps credential/retry concerns outside the audit boundary and prevents a partially downloaded 2023-2025 metadata set from being mislabeled as complete. No real parser comparison or strategy outcome has been opened.

CI run `34811269556` for the new snapshot layer is currently **in progress**. If it fails, only infrastructure/contract defects may be repaired; no sample or parser rule may be changed in response to accounting/strategy outcomes.

## Cross-lane follow-up

Consensus branch SHA `9bbdef6fead6d1494b0b10030b466a2bdb0a22a8` was reviewed as the only new unprocessed active-lane SHA at the start of this pass. It contains research-only V47 raw1H/rate-limit follow-up. V47 raw1H run `34810592135` remains queued/in progress, so there is no completed artifact to collect yet. No duplicate Consensus data acquisition was launched from the OSS lane.

## Next safe action

1. Collect isolated OSS CI run `34811269556`; repair only snapshot/infrastructure defects if needed.
2. Materialize exact raw EDINET document-list JSON for every calendar day from 2023-01-01 through 2025-12-31 using an acquisition step separate from the audit parser.
3. Run `edinet_metadata_snapshot.py` to freeze per-day SHA256 values, aggregate hash-chain receipt, and normalized metadata CSV.
4. Feed that frozen normalized metadata CSV to `edinet_oss_sample_selector.py` exactly once and freeze selected doc IDs plus input/sample hashes.
5. Fetch/materialize the exact selected XBRL-to-CSV ZIP bytes without replacement around parser failures; freeze each ZIP SHA256 before opening parser comparison.
6. Run custom and `edinet-tools` parsers against identical bytes. Treat all mismatches/one-sided missing values as audit findings; never choose a parser based on strategy outcome.

Optuna/purgedcv work remains available for the next genuinely new family, but no rejected or outcome-opened family is being reopened here.
