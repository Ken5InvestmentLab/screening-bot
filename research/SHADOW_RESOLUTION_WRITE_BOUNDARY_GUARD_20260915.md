# Shadow resolution write-boundary chain guard — 2026-09-15

Research-only Canonical/Event + Shadow/Data integrity work.

## Scope
- No production/main or production workflow changes.
- No Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes.
- No strategy threshold, TopN, ranker, cooldown, or rejected-family retune.
- No new performance, H1/H2, or 2026 outcome was opened.

## Change
The existing cross-run resolution chain guard is now enforced before the resolved JSONL replace boundary.

The verified resolver now supports a pre-replace guard over the staged resolved bytes and provisional resolve result. The CLI uses that hook to:
1. load and verify the existing append-only resolution chain;
2. build the prospective immutable resolution receipt against the staged output;
3. build the next chain link against the prior chain head;
4. verify the complete prospective chain;
5. allow `staged.replace(output_path)` only after the prospective chain is valid.

An invalid/tampered existing chain fails closed before daily resolution can mutate the resolved output.

## Persistence
After a successful guarded replace, the CLI writes the immutable resolution receipt and appends the verified chain link to the resolution-chain JSONL. The default chain path is derived from the resolved output path, so separate resolution receipt files still participate in one cross-run chain.

## Regression coverage
- pre-replace guard denial leaves no resolved output write;
- successful CLI resolution emits a valid persisted chain link;
- an invalid pre-existing chain blocks before resolved output write;
- prior continuity, endpoint completeness, daily provenance, XTKS calendar, and resolution receipt tests remain green.

## Evidence
Implementation commits:
- `033efe2cd4f196548e0929936efec355ab480746`
- `f2b17e6b35f881ee631af476d64d516de7059140`
- `abbeb338696cb1a0ab4ab5c9d18049d385c913f1`
- `90f0863b0b061353c70a6394f2eb3d6e9dac294a`

GitHub Actions:
- `34943281926` — **SUCCESS**

## Status
`RESOLUTION_CHAIN_ENFORCED_AT_PREWRITE_BOUNDARY_CI_GREEN`
