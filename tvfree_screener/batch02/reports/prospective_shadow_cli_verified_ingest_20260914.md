# Prospective shadow CLI verified-ingest audit — 2026-09-14

## Scope
Research-only hardening of the Prospective Shadow/Data-integrity lane. No strategy returns, model scores, thresholds, cooldowns, production Discord/Sheets, or 2026 outcome tuning are involved.

## Finding
The legacy `prospective_shadow_cli.py ingest` path directly called `append_candidates()` and therefore could bypass the newer unified admission gate, admission receipt, eligibility/data-sufficiency proof, and verified-append boundary.

## Fix
The existing `ingest` command is now verified-only:

1. load and SHA-check the immutable freeze manifest;
2. normalize candidate identity from the freeze manifest;
3. require `--admission` and `--receipt`;
4. replay the live admission gate on the exact current candidate batch;
5. require byte-equivalent logical admission output;
6. call `verified_append()`, which replays admission again and verifies the exact receipt before writing;
7. fail closed with no shadow write on any mismatch.

The loader-only `freeze_manifest_sha256` transport field is removed before admission/receipt hashing so a receipt created from the immutable on-disk manifest is not falsely invalidated by CLI bookkeeping.

## Commits
- `a8e455998832cd35800c7ba27da3429e205f288d` — require verified admission receipt in CLI ingest.
- `c9243484448c4645ee6452f0a5f5874ef3db6d19` — align receipt hashing with the raw immutable manifest.
- `7d54d14a172b9fba3ae6e926eb18989253c2713a` — add focused verified-ingest boundary tests.

## Verification
Direct git clone was unavailable in the execution sandbox because external DNS/network access is disabled. The exact current contracts were re-read through the GitHub connector and a logic-equivalent local execution covered five focused cases:

1. valid manifest + eligible causal post-freeze row + matching admission + matching receipt -> append allowed;
2. tampered receipt -> blocked before write;
3. `data_sufficient` changed to false after receipt -> blocked before write;
4. source changed to `POSTCLOSE_RECON_ONLY` after receipt -> blocked before write;
5. transport-only `freeze_manifest_sha256` is excluded from receipt manifest hashing.

Result: **5/5 PASS**.

The committed unit-test file additionally asserts that the old CLI invocation without `--admission` and `--receipt` is rejected by argparse.

## Disposition
`CLI_DIRECT_INGEST_BYPASS_CLOSED`

A future real prospective-shadow start still requires freshly re-fetched source-branch HEADs, current supervisor-contract authorization, an immutable model freeze, and a model-specific eligible candidate export. This change does not itself authorize prospective-shadow collection or production use.
