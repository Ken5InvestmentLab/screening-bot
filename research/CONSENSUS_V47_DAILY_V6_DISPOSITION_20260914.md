# Consensus V47 daily v6 disposition — 2026-09-14

## Scope
Research-only. No production writes. No strategy returns or model scores were opened.

## Authoritative run
- Workflow: Consensus V47 Daily PIT Materialization
- Run: `34788533946`
- Trigger SHA: `90de49e24c0085b01f4a2944b298e84dbfa46c62`
- Workflow conclusion: SUCCESS
- V47 data acceptance: **FAIL CLOSED**

## Outcome-blind receipt
- PIT union symbols: 3,920
- Restored/delisted union symbols requiring direct historical daily recovery: 251
- Direct Yahoo daily requested: 251
- Usable restored symbols: 0
- Restored daily coverage: 0.0%
- `daily_coverage_pass`: false
- Every recorded direct-fetch failure is `http_429`.
- Strategy returns opened: false
- Model scores opened: false

## Interpretation
This is a provider-rate-limit failure, not evidence that all 251 historical codes lack Yahoo history and not evidence for or against the Consensus strategy. Because direct Yahoo retrieval did not complete successfully, the frozen repair order has not advanced to identity-alias substitution. Do **not** infer successor/predecessor aliases from this run and do not silently drop restored names.

## Frozen next action
1. Keep raw 1H, clean features, DEV arm comparison, H2, and performance closed.
2. Retry only the same direct Yahoo daily recovery step under a rate-limit-safe launch; preserve the exact 251-symbol required population and all PIT price/volume/listing-epoch semantics.
3. A transient `429` remains retryable provider failure. It must not be reclassified as `historical_code_unavailable`.
4. Only symbols that return a terminal/unavailable result after a valid direct-provider attempt may proceed to the official JPX/company identity-continuity step in `research/consensus_v47_restored_data_repair_spec.json`.
5. No threshold relaxation, survivor intersection, interpolation, provider choice from returns, price-cap search, or 2026 outcome use.

## Promotion state
V47 remains the only promotion-relevant Consensus path, but is blocked at restored/delisted daily coverage. `RUN_V47_RAW1H_FETCH` must not be triggered until restored daily coverage is 100% and `daily_coverage_pass=true`.
