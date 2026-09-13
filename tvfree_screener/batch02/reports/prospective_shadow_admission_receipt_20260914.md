# Prospective Shadow Admission Receipt — 2026-09-14

## Scope
Research-only integrity work for the Prospective Shadow + data-integrity lane. No production paths, model thresholds, strategy returns, or 2026 tuning were changed or opened.

## Supervisor reconciliation
The current supervisor contract adds a promotion-grade blocker for run80 experiments that rely on absolute historical price thresholds because Yahoo/yfinance historical OHLC is split-adjusted using later corporate actions. V46 owns the outcome-free point-in-time split reconstruction. This lane did **not** implement or retune any split correction.

Current non-overlap observations before this change:
- Event/Shadow branch had advanced to quantified PIT split-contamination reconciliation.
- Core branch had advanced to a frozen Cloud architecture decision snapshot.
- Consensus branch had advanced to cross-validated PIT-universe reconstruction.

This change stays within Shadow/Data-integrity ownership only.

## Added artifact
`prospective_shadow_admission_receipt.py`

The receipt is created only after `ADMIT_PROSPECTIVE_SHADOW_BATCH` and pins:
- exact freeze manifest SHA256,
- exact candidate-row batch SHA256,
- exact admission-result SHA256,
- experiment/model-freeze identity,
- row count,
- receipt self-SHA256.

`production_authorized` is hard-pinned to `false`. A blocked admission cannot produce an append-authorizing receipt.

The verifier returns `ADMISSION_RECEIPT_VERIFIED` only when all pinned inputs still match. Any mismatch returns `BLOCK_APPEND_RECEIPT_INVALID`.

## Verification
`test_prospective_shadow_admission_receipt.py`

Equivalent local execution: **7/7 PASS**.

Covered cases:
1. unchanged receipt verifies;
2. any candidate-row change invalidates the receipt;
3. manifest change invalidates the receipt;
4. admission-result change invalidates the receipt;
5. receipt body tampering invalidates self-hash;
6. blocked admission cannot create a receipt;
7. changing `production_authorized` to true invalidates verification.

## Decision
`PROSPECTIVE_SHADOW_ADMISSION_RECEIPT_READY`

Operational rule: an admitted candidate batch should be appended only after its admission receipt verifies against the exact manifest, exact candidate rows, and exact admission result used at admission time.
