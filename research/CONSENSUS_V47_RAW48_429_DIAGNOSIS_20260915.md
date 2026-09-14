# Consensus V47 Raw48 systemic HTTP 429 diagnosis — 2026-09-15

Scope: transport/data-integrity only. No strategy returns, model scores, thresholds, rankers, price-policy rules, cooldown rules, endpoints, or production paths were changed.

## Evidence
- GitHub Actions run: `34849054884` (`Consensus V47 Raw1H Freeze`)
- Trigger SHA: `7849ad975d1e0420e250ab4d5f411ce136f9d867`
- Configuration: 48 shards, max-parallel=2, 180-minute job timeout.
- Shard 0 job completed SUCCESS and uploaded artifact `10357093848`.
- Shard 1 job completed SUCCESS and uploaded artifact `10357611796`.
- Each shard requested 81 symbols.
- Shard 0: `ok_symbols=0`, `non_ok_symbols=81`, `total_rows=0`; all 81 receipts were `fetch_error,http_429,0`.
- Shard 1: `ok_symbols=0`, `non_ok_symbols=81`, `total_rows=0`; all 81 receipts were likewise HTTP 429 with zero raw rows.
- Therefore job SUCCESS means the workflow finished and preserved evidence; it does **not** mean raw data acquisition succeeded.

## Disposition
- Formal raw acceptance remains **NOT PASSED**.
- These two artifacts add **zero usable raw rows** and cannot advance formal feature materialization.
- On these retry artifacts alone, performance is `NOT_COMPUTABLE_NO_INPUT_DATA`.
- Existing midterm diagnostic results remain unchanged because they used previously preserved partial raw, not these zero-row shards.
- This is transport failure, not strategy evidence and not a reason to change NOCAP/CAP1000_PIT, V11 heads, threshold 0.95, strict5, endpoint, cooldown, or any model/family parameter.

## Acquisition-mechanics repair
A future missing-only retry is hardened with an outcome-blind fail-fast preflight in `research/no_tv_v47_intraday_fetch_shard.py`:
- probe the first two symbols against both Yahoo chart hosts (4 probes total);
- if all four probes are HTTP 429, record `systemic_http_429`, mark the shard receipts `transport_circuit_open`, and stop without spending hours on eight retries for every symbol;
- if the preflight is not unanimously 429, retain the existing fetch/retry behavior;
- no acceptance threshold is lowered and no interpolation is introduced.

This change affects only future runs. The currently executing run `34849054884` is pinned to its trigger SHA and is not duplicate-triggered.

## Next action
1. Preserve completed shard receipts from `34849054884`; do not treat zero-row artifacts as valid raw.
2. Allow the pinned run state to be observed without launching a duplicate retry.
3. After the current run is terminal, merge only genuinely observed raw rows with the preserved provenance-tagged seed raw.
4. Run the frozen coverage verifier.
5. Retry only missing symbol/date pairs after Yahoo transport is healthy, using the systemic-429 circuit breaker; never lower thresholds or interpolate.
