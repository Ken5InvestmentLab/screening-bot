# Prospective shadow immutable resolution receipt — 2026-09-14

Research-only Shadow/Data integrity work. No strategy outcome was used for model/threshold/candidate selection and no production path was modified.

## Purpose

Bind each successful prospective-shadow 5BD resolution event to the exact inputs and output that produced it. This prevents a resolved JSONL from being detached from the freeze, shadow candidates, daily endpoint dataset, or XTKS session calendar that generated it.

## Receipt contract

`prospective_shadow_resolution_receipt.py` creates an immutable, self-hashed receipt only after `VERIFIED_RESOLUTION_WRITE_COMPLETE`.

The receipt pins:

- experiment_id / model_freeze_id;
- exact freeze-manifest file SHA256;
- exact append-only shadow input SHA256;
- exact daily endpoint CSV SHA256;
- exact daily endpoint manifest SHA256;
- exact XTKS session CSV SHA256;
- exact XTKS session manifest SHA256;
- exact resolved JSONL SHA256;
- canonical SHA256 of the verified resolve result;
- timezone-aware creation timestamp;
- production_authorized = false;
- self `receipt_sha256`.

The receipt verifier recomputes all hashes from the current files and fails if any input, output, metadata bundle, or receipt field has changed.

## CLI enforcement

`prospective_shadow_cli.py resolve` now requires a unique `--resolution-receipt` path.

- An already-existing receipt path causes `BLOCK_CLI_RESOLUTION_RECEIPT_ALREADY_EXISTS` before resolution work begins.
- A receipt is created only after the continuity-safe resolver succeeds.
- Failed or blocked resolution attempts do not create a receipt.
- The resolve summary records the receipt SHA and path.

## Commits

- `5eef0e7a642a879875f1624f075b6c3e02163fcc` — immutable resolution receipt builder/verifier.
- `70ce5c16a6a34a9f6209cec8948bc3d6d1fd7997` — receipt contract tests.
- `26a9332e7ba5f4319da2ca78437f42c8bf48cb2e` — CLI integration.
- `9ef5b59835324a3d87fac8b359f100d44399a464` — CLI receipt immutability tests.
- `8a821a7325313b82307f48da594436447ae15fab` — integrated CI coverage.

## Verification

GitHub Actions run `34799006401` completed SUCCESS:

- 42 tests run;
- 42 passed;
- daily source change invalidates the receipt;
- resolved output change invalidates the receipt;
- receipt self-hash tampering is detected;
- an existing receipt file cannot be overwritten;
- failed resolution cannot produce a receipt;
- prior daily provenance, XTKS calendar, continuity, staged-write, and CLI contracts still pass.

## Resulting resolution evidence chain

The prospective resolution path is now:

`validated freeze -> verified append-only shadow -> pinned daily endpoint manifest -> pinned XTKS calendar -> staged continuity-safe resolution -> immutable resolution receipt`.

## Isolation

This work does not alter Event/V20 logic, Core, Consensus V47, ranking, thresholds, model training, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, production workflows, or main.
