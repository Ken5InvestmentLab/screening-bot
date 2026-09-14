# Core endpoint source-receipt audit — 2026-09-15

## Scope

Research-only reproducibility work for the Core canonical endpoint path. No strategy threshold, candidate family, cooldown, ranker, entry/exit definition, production integration, or 2026 selection rule was changed.

## Start-state reconciliation

- Start Core/Cloud HEAD: `6e7dfa45e200dfa43e19a98ebc9b9110b4295b25`.
- Coordination STATE `last_seen_sha` / `last_processed_sha` matched that HEAD, so no previously processed Core SHA was duplicated.
- Cloud historical exact replay remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no contemporaneous exact-model evidence appeared and model-family guessing was not resumed.

## Reproducibility gap addressed

The pinned XTKS/vendor endpoint primitive already bound calendar identity and exact endpoint timestamps, but the raw vendor bytes consumed by a future formal evaluator were not yet independently bound to an immutable receipt. A future artifact replacement with the same filename could therefore escape the endpoint-calendar hash contract.

## Implementation

`endpoint_provenance.py` now provides an outcome-blind source receipt primitive:

- exact SHA-256 and byte size for every raw source file;
- exact source run ID;
- source artifact name;
- vendor identity string;
- pinned calendar SHA-256;
- deterministic canonical receipt SHA-256;
- explicit `performance_opened=false` marker;
- fail-closed verification for file-set drift, byte drift, size drift, calendar mismatch, receipt metadata tamper, missing files, or unsupported receipt version.

No return, score, or strategy outcome is needed to build or verify this receipt.

## Tests / CI

Dedicated workflow: `Tentei Cloud Core Endpoint Provenance Tests`.

Run `34868543771` completed **SUCCESS** on commit `941ae0c3cd0ed5f745f134dd2e3a2718eee4fae0`.

Synthetic coverage includes:

1. pinned next-XTKS-open / fifth-XTKS-close mapping;
2. missing exact endpoint fails closed with no nearby-row fallback;
3. calendar SHA tamper rejection;
4. duplicate endpoint-row rejection;
5. unsorted calendar rejection;
6. deterministic raw source receipt binding;
7. mutated raw bytes rejection;
8. receipt metadata tamper rejection.

## Performance policy

No performance was recomputed in this pass. Therefore there is no new n / mean / median / win / tail statistic and no ranking or GO/NO-GO change. When formal recomputation is eventually allowed, it remains cost 0% only with win = gross return > 0; 2026 remains report-only.

## Remaining formal blockers

Formal Core relabeling is still blocked until all of the following are true:

1. generate and freeze a real XTKS + raw-vendor endpoint manifest with explicit calendar version and SHA-256;
2. emit this immutable source receipt from the actual downloaded source artifact/run;
3. change `audit_core_canonical_endpoint.py` to verify the source receipt and consume `resolve_canonical_endpoints`, removing observed-date and first/last-row endpoint reconstruction;
4. make the canonical endpoint workflow fail closed on manifest/receipt/endpoint incompleteness;
5. pass dedicated CI before opening any newly recomputed returns.

This is infrastructure/reproducibility progress only, not evidence that a rejected Core family should be reopened.
