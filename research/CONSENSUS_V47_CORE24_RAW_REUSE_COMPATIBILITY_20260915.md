# Consensus V47 Core24 raw1H reuse compatibility — 2026-09-15

Status: **COMPATIBLE AS PARTIAL PROVENANCE SEED ONLY AFTER DETERMINISTIC PRICE-BASIS NORMALIZATION**

Scope: outcome-blind transport/data-integrity work. No strategy threshold, ranker, price arm, cooldown, target, 2026 selection rule, or production path changed.

## Identity match

The Core24 SHA-pinned observed bundle is the same Yahoo source already audited by V47 as preserved seed raw:

- source run: `34592896202`
- workflow: `Tentei Cloud 1H Research Fetch`
- source HEAD: `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`
- artifacts: `tentei-cloud-1h-shard-{0..7}`
- artifact IDs and ZIP digests exactly match the V47 existing-seed audit
- Core24 now additionally pins every raw CSV SHA-256 and deterministic bundle SHA `de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`
- observed rows: 4,019,524
- observed symbols with data: 1,315
- timestamp envelope: 2024-09-17 09:00:00+0900 .. 2026-09-10 15:00:00+0900

This closes the previous source-identity gap. Reuse is not a new provider substitution; it is reuse of already-observed immutable Yahoo bytes with stronger provenance.

## Session / volume compatibility

Core uses Yahoo `interval=1h` explicit-period requests; stalled V47 fetch uses Yahoo `range=730d&interval=1h`.

Existing outcome-blind split audit established on 89 overlapping selected symbol-sessions:

- session volume exact match: 89/89
- session return/range/body/close-location differ only at floating-point noise scale
- raw-bin timestamp/session reconstruction is compatible
- raw 1H volume is already on PIT share-count scale and must remain unchanged

Therefore timestamps/session shapes and raw volume are compatible with the frozen V47 raw-volume contract.

## Price-basis mismatch and deterministic repair

Direct ingestion into the current V47 clean-feature materializer is **not** compatible.

Core explicit-period raw prices preserve historical PIT nominal split scale. V47's materializer assumes incoming raw prices are split-normalized/adjusted and computes:

`entry_pit = entry_adjusted * cumulative_future_split_factor`.

Feeding Core nominal prices directly applies the future split factor twice to `log_price` on pre-split rows.

Frozen outcome-blind repair:

- Core seed OHLC only: divide `open/high/low/close` by the exact V47 cumulative future split factor for that symbol/date.
- Keep raw 1H `volume` unchanged.
- Preserve timestamps and symbol identity exactly.
- Hash source bytes and normalized output.
- Then the unchanged V47 materializer multiplies adjusted close by the same factor and recovers PIT nominal `log_price`.
- Relative intraday technicals remain invariant to this uniform split scaling.

No return or model score is used.

## Frozen V47 coverage from this source

### NOCAP
- required pairs: 853,061
- present pairs: 301,897
- pair coverage: 35.3898%
- monthly minimum: 33.9002%
- completely missing required symbols: 2,592
- restored-pair coverage: 0.0%

### CAP1000_PIT
- required pairs: 310,831
- present pairs: 258,339
- pair coverage: 83.1124%
- monthly minimum: 77.3420%
- completely missing required symbols: 642
- restored-pair coverage: 0.0%

Core24 raw cannot pass formal V47 acceptance by itself. It is admissible only as a provenance-compatible partial seed after deterministic price-basis normalization. Formal thresholds remain unchanged.

## Midterm diagnostic correction

The H1 diagnostic workflow `34824194221` converted Core seed columns/timestamps but did not normalize price basis before invoking the V47 materializer. The NOCAP H2 diagnostic used the same source preparation.

Those printed results are therefore reclassified:

`MIDTERM_DIAGNOSTIC_INVALID_SOURCE_PRICE_BASIS`

Retain them for audit history, but do not use them for arm ranking, GO/NO-GO, or promotion discussion.

Holdout consequences are not reset:
- H1 remains opened.
- NOCAP H2 remains opened.
- same-family retuning remains forbidden.
- CAP1000_PIT H2 remains unopened unless the unchanged frozen H1 chooser, rerun on corrected inputs, selects it.

A corrected diagnostic may recompute the exact same frozen family/threshold/ranker/cooldown at cost 0% after the normalization contract passes. No parameter may change.

## Formal reuse gate

Before this seed enters the formal merged pool:

1. artifact identity must match the Core24 pin exactly;
2. raw CSV SHA-256 values must match the Core24 receipt;
3. deterministic price-basis normalizer tests must pass;
4. normalized outputs must carry source/output SHA receipts;
5. merge exact `(symbol, ts_jst)`; conflicting duplicates fail closed;
6. rerun the unchanged formal V47 coverage verifier;
7. missing pairs remain missing; no interpolation or threshold relaxation.

Formal clean features and formal H1/H2 remain unopened until both arms pass frozen raw acceptance.
