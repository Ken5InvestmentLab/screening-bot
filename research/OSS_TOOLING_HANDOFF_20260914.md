# OSS/Validation handoff — 2026-09-14 16:06 JST

Branch: `research/oss-validation-tooling`  
Scope: research-only. Production/main and all production integrations remain untouched.

## Current frozen contracts

- `research/OPTUNA_DISCOVERY_CONTRACT_20260914.json`: Optuna is discovery-only, 2022-07-01..2023-12-31 selection period, later periods excluded from selection, one optimized parameter (`LogisticRegression C`), all trial Sharpes retained for PSR/DSR sensitivity.
- `research/EDINET_OSS_CROSSCHECK_CONTRACT_20260914.json`: same-ZIP custom-vs-edinet-tools parser audit, parser disagreement fail-closed for research admission, issued-share semantic priority fixed before outcome inspection.

## EDINET real-sample boundary

The real historical sample was preregistered before opening any real parser comparison:

- 2023-01-01 through 2025-12-31;
- document types 120 and 130;
- calendar-quarter x doc-type strata;
- first two unique doc IDs by submit datetime ascending then doc ID ascending;
- metadata only may select rows;
- full-period metadata coverage is required;
- selected filings are not replaced because a parser fails or disagrees;
- selected doc IDs and source ZIP hashes are frozen before mismatch review;
- strategy returns, ranks, labels, model scores, accounting values and 2026 market outcomes are forbidden sample-selection inputs.

Preregistration CI `34807402370` and deterministic selector CI `34807566909` completed **SUCCESS**.

## Metadata selector + snapshot audit layer

`tvfree_screener/edinet_metadata_snapshot.py` consumes exact raw daily EDINET JSON responses named `YYYY-MM-DD.json`, requires every calendar day in the frozen interval, hashes every raw response, builds a deterministic daily hash chain, normalizes only `docID` / `docTypeCode` / `submitDateTime` plus source date, and emits a manifest with `strategy_outcomes_opened=false` and `parser_outputs_used_for_selection=false`.

Snapshot/fail-closed CI `34811269556` completed **SUCCESS**. No real parser comparison or strategy outcome has been opened.

## Acquisition boundary added in this pass

To make the next step executable without contaminating the audit layer, this pass added a separate network acquisition helper:

- `tvfree_screener/edinet_metadata_acquire.py` calls the official EDINET v2 `documents.json` endpoint with `date`, `type=2`, and `Subscription-Key` query parameters;
- the API key is read only from an environment variable and is never written to repository files;
- one exact raw response is persisted per calendar day using atomic temp-file replacement;
- existing files are skipped by default so interrupted acquisitions can resume without silently overwriting prior bytes;
- malformed responses and non-200 EDINET metadata status fail closed;
- `tvfree_screener/test_edinet_metadata_acquire.py` locks required-query construction, fail-closed payload validation, resumability, and missing-key refusal;
- isolated OSS CI was extended to run these tests. CI run `34816055006` is currently in progress.

The acquisition helper still does **not** perform sample selection, parse accounting facts, inspect strategy outcomes, or read 2026 market outcomes. Acquisition bytes must pass `edinet_metadata_snapshot.py` before they are eligible for the frozen selector.

## Cross-lane follow-up

At this pass start, all STATE-registered branch HEADs matched their recorded processed state except for no new lane commits requiring duplicate work. Consensus retry run `34810592135` remains active at job level with `fetch (0)` and `fetch (1)` in the raw-1H fetch step and the other ten shards queued under the intentional max-parallel=2 constraint. No duplicate Consensus acquisition was triggered and V47 features/H1/H2 remain sealed.

## Next safe action

1. Wait for OSS CI `34816055006`; if green, treat the acquisition boundary as tested.
2. Run the acquisition helper with an externally supplied EDINET API key to materialize exact raw document-list JSON for every calendar day from 2023-01-01 through 2025-12-31. Do not commit the API key.
3. Run `edinet_metadata_snapshot.py` to freeze per-day SHA256 values, aggregate hash-chain receipt, and normalized metadata CSV.
4. Feed that frozen normalized metadata CSV to `edinet_oss_sample_selector.py` exactly once and freeze selected doc IDs plus input/sample hashes.
5. Fetch/materialize exact selected XBRL-to-CSV ZIP bytes without replacement around parser failures; freeze each ZIP SHA256 before opening parser comparison.
6. Run custom and `edinet-tools` parsers against identical bytes. Treat all mismatches/one-sided missing values as audit findings; never choose a parser based on strategy outcome.

Optuna/purgedcv work remains available for the next genuinely new family, but no rejected or outcome-opened family is being reopened here.
