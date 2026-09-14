# OSS/Validation handoff — 2026-09-14 16:48 JST

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

## Acquisition boundary

`tvfree_screener/edinet_metadata_acquire.py` calls the official EDINET v2 `documents.json` endpoint with `date`, `type=2`, and `Subscription-Key` query parameters. The API key is read only from an environment variable and is never written to repository files. One exact raw response is persisted per calendar day using atomic replacement; existing files are skipped by default for resumability; malformed/non-success responses fail closed.

Acquisition CI `34816055006` completed **SUCCESS**. The acquisition helper still does not perform sample selection, parse accounting facts, inspect strategy outcomes, or read 2026 market outcomes. Acquisition bytes must pass `edinet_metadata_snapshot.py` before they are eligible for the frozen selector.

## Selected ZIP exact-byte freeze boundary — 16:48 JST

A separate pre-parser boundary is now implemented in `tvfree_screener/edinet_selected_zip_freeze.py` and frozen in `research/EDINET_SELECTED_ZIP_FREEZE_SPEC_20260914.md`.

Before either custom parser or `edinet-tools` may inspect a selected filing, this boundary requires the exact `<doc_id>.zip` set from the frozen selector receipt and fails closed on missing files, extra file drift, duplicate selected IDs, invalid/corrupt/empty ZIPs, a receipt with `strategy_outcomes_opened != false`, or a receipt that drops the no-replacement rule. For accepted bytes it records each raw ZIP SHA256, byte size, sorted member names, and a deterministic aggregate digest. The receipt explicitly keeps both strategy outcomes and parser outputs unopened.

Synthetic fail-closed tests are included in `tvfree_screener/test_edinet_selected_zip_freeze.py`. Isolated OSS CI run `34819456421` completed **SUCCESS**, including the existing custom EDINET synthetic self-check.

This does not mean real EDINET data has been opened: complete 2023-2025 metadata bytes, selected real doc IDs, selected real ZIPs, real parser outputs, strategy returns and 2026 outcomes all remain unopened.

## Cross-lane follow-up

At this pass start, Canonical/Event HEAD `480bc9b5...`, Core HEAD `7d195335...`, Consensus HEAD `01299302...`, and OSS HEAD `0837d299...` matched their STATE processed SHAs, so no duplicate cross-lane experiment was performed. Consensus retry run `34810592135` remains active at job level with `fetch (0)` and `fetch (1)` in the raw-1H fetch step and the other ten shards queued under the intentional max-parallel=2 constraint. No duplicate Consensus acquisition was triggered and V47 features/H1/H2 remain sealed.

## Next safe action

1. Run the acquisition helper with an externally supplied EDINET API key to materialize exact raw document-list JSON for every calendar day from 2023-01-01 through 2025-12-31. Do not commit the API key.
2. Run `edinet_metadata_snapshot.py` to freeze per-day SHA256 values, aggregate hash-chain receipt, and normalized metadata CSV.
3. Feed that frozen normalized metadata CSV to `edinet_oss_sample_selector.py` exactly once and freeze selected doc IDs plus input/sample hashes.
4. Fetch/materialize exactly those selected XBRL-to-CSV ZIP bytes without replacement around parser failures and pass them through `edinet_selected_zip_freeze.py` to freeze per-file and aggregate hashes.
5. Run custom and `edinet-tools` parsers against those identical frozen bytes. Treat all mismatches/one-sided missing values as audit findings; never choose a parser based on strategy outcome.

The only current external blocker for executing the real EDINET path is access to an EDINET API key in the runtime. Optuna/purgedcv work remains available for the next genuinely new family, but no rejected or outcome-opened family is being reopened here.
