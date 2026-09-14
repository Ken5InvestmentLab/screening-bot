# Prospective shadow daily endpoint provenance guard — 2026-09-14

Research-only Shadow/Data integrity work. No strategy outcome was used for model, threshold, or candidate selection. No production path was modified.

## Gap closed

The prospective-shadow resolver already pinned the XTKS session calendar and protected previously resolved rows from mutation, but the daily endpoint CSV itself had no mandatory provenance manifest. A caller could therefore supply an unpinned or silently replaced daily file while still producing a first resolution snapshot.

## New contract

`prospective_shadow_daily_endpoint_guard.py` requires an explicit immutable manifest for every daily endpoint dataset. The manifest pins:

- manifest_version = 1;
- purpose = `PROSPECTIVE_SHADOW_5BD_ENDPOINTS`;
- non-placeholder dataset_id;
- non-placeholder source_name;
- non-placeholder source_kind;
- timezone-aware acquired_at;
- explicit price_adjustment_semantics;
- exact daily CSV SHA256;
- row_count;
- symbol_count;
- first_date / last_date;
- immutable_input = true;
- production_authorized = false.

The CSV itself must contain symbol/date/open/close, unique symbol+date keys, valid ISO dates, and finite positive prices whenever prices are present. Blank prices may remain explicitly unresolved; the resolution layer will not impute them.

## CLI enforcement

`prospective_shadow_cli.py resolve` now requires `--daily-manifest`.

Before reading the daily rows for 5BD resolution it validates the exact CSV against that manifest. Any provenance or hash failure returns `BLOCK_CLI_DAILY_ENDPOINT_DATASET`, exits nonzero, and does not create/replace the resolved output.

The resolve summary now records both the daily CSV SHA and daily manifest SHA plus the validated provenance payload.

## Commits

- `0e19e0ad2f569cc76b208566ecc83570099a024c` — daily endpoint provenance guard + manifest builder.
- `6486ab23df953f579ddea30d458e5b50442b0a77` — guard tests.
- `4648766986a9b1ad106139a2204917162bd8a9b0` — CLI enforcement.
- `2008770698a336e2bca1001f715dd1fde5774a33` — CLI regression tests.
- `bf06de0be5cd40eae982b93691909335ebf6756c` — integrated CI coverage.

## Verification

GitHub Actions run `34798839174` completed SUCCESS:

- 35 tests run;
- 35 passed;
- exact CSV SHA mismatch blocks;
- manifest row-count mismatch blocks;
- duplicate symbol/date blocks manifest creation;
- naive/non-timezone-aware acquisition timestamps block;
- placeholder provenance blocks;
- nonpositive present prices block;
- explicit blank/unresolved source rows remain representable;
- CLI blocks tampered daily manifests before any resolved output is written;
- prior resolution continuity and pinned XTKS calendar contracts still pass.

## Isolation

This work does not alter V20 Event logic, Core, Consensus V47, candidate ranking, price/volume thresholds, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, production workflows, or main.
