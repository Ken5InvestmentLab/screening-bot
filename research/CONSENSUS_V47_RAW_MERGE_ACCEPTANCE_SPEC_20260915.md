# Consensus V47 raw merge + formal acceptance specification — 2026-09-15

Status: FROZEN TRANSPORT/DATA CONTRACT; no strategy outcomes used.
Branch: `research/consensus-atr-regime-gate`
Scope: Consensus specialist lane only.

## Purpose
After the currently pinned raw1H run `34849054884` becomes terminal, combine only genuinely observed Yahoo raw rows from accepted shard artifacts with the already preserved seed raw, retain source provenance, and rerun the unchanged V47 formal raw-coverage verifier. This document does not authorize performance interpretation before formal raw acceptance.

## Frozen inputs
- authoritative Daily PIT materializer: run `34788533946` (Daily coverage PASS required)
- active raw run: `34849054884`, trigger SHA `7849ad975d1e0420e250ab4d5f411ce136f9d867`
- preserved seed raw: previously audited historical Yahoo raw1H artifacts only
- price arms remain exactly `NOCAP` and `CAP1000_PIT`
- endpoint remains next official XTKS open -> D+5 close
- no 2026 selection/tuning

## Merge rules
1. Never treat workflow `success` as data success. A shard contributes rows only when its raw CSV contains observed rows and the shard receipt identifies corresponding symbols as `ok`.
2. Zero-row artifacts, `http_429`, `transport_circuit_open`, timeout/cancel, and other fetch failures contribute no market rows. Preserve their receipts as provenance only.
3. No interpolation, synthetic intraday bars, forward/back fill, threshold reduction, or substitution from Daily bars.
4. For duplicate `(symbol, ts_jst)` observations, values must agree exactly after canonical type normalization. Conflicting duplicates fail closed and are reported; do not choose a preferred value using outcomes.
5. Every retained row must carry provenance sufficient to recover source class (`seed` or `run34849054884`), run/artifact/shard identity where applicable, and source-file SHA-256.
6. Raw Yahoo 1H volume remains unadjusted. PIT split correction applies only to Daily historical volume according to the frozen V47 contract.
7. Listing-identity epoch isolation remains mandatory downstream; this merge must not reconnect prelisting history to a later listing identity.

## Formal acceptance thresholds — unchanged
The merged raw panel passes only if all frozen checks pass:
- required symbol-date pair coverage >= **99.5%**;
- every required month coverage >= **99.0%**;
- completely missing required symbols = **0**;
- among symbols requiring >=20 days, symbol-level coverage >= **95%**;
- restored-historical required pair coverage >= **99.0%**.

No threshold may be relaxed because Yahoo transport is degraded.

## Failure disposition
If any formal threshold fails, generate the exact missing `(symbol,date)` set and retry only those missing pairs after Yahoo transport health is restored. The retry must use the already implemented systemic-429 fail-fast preflight. Do not refetch complete symbols/dates that are already valid unless needed to resolve a detected data conflict.

## Performance firewall
Formal clean features and formal H1/H2 remain unopened until this acceptance passes. The separately authorized `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` results remain diagnostics only and cannot satisfy this gate.

## Current evidence at freeze time
Run `34849054884` has two visible artifacts from shards 0 and 1. Both completed mechanically but each contains zero usable raw rows (`0/81` ok symbols, `81/81` HTTP 429). Therefore those two artifacts contribute provenance/failure receipts only and are `NOT_COMPUTABLE_NO_INPUT_DATA` by themselves.

## Next executable step
Wait for the pinned run to become terminal without duplicate-triggering it. Then enumerate all 48 shard artifacts/receipts, admit only observed raw rows under the rules above, merge with preserved seed raw, hash the merged inputs/output, and rerun the frozen formal coverage verifier before any promotion performance is opened.
