# Core raw1H PIT lineage findings — 2026-09-14 JST

Research-only, outcome-free data-lineage audit. No Core rule, threshold, return, production path, Discord, Spreadsheet, or V20 strategy logic was changed.

## Why this mattered

A separate PIT audit correctly established that frozen Yahoo **daily** historical price/volume can be retrospectively transformed by future stock splits. That means any historical absolute daily gate must be reconstructed on a point-in-time basis.

However, the fixed reconstructed Core on this branch does **not** source its absolute prior-close / prior-volume gates from that frozen daily panel.

Its lineage is:
- raw Yahoo explicit-period 1H rows;
- prior daily close = last raw 1H close on prior date;
- prior daily volume = sum of raw 1H volume on prior date;
- session volume = sum of raw 1H volume inside the reconstructed session.

Shared V47 data receipts independently established:
- raw 1H volume is already on point-in-time share-count scale;
- explicit-period raw 1H prices preserve historical nominal split scale on audited split-affected rows relative to the split-normalized range-query/frozen-daily basis.

Therefore applying the frozen-daily split transform again to this raw-1H Core path would be wrong.

## Automated receipt

Valid run:
- workflow run: `34798921728`
- artifact: `10330772110`
- artifact SHA-256: `8680e7a2a8a503b356d75a6b62fc7d6f67fe0b684eb87d6291c125666e6c093d`
- source SHA-256: `fd084c24a65960cd736e19b98d8be54dae472f5da3e5b685935c9a08f79656d9`

All lineage guards passed:
- raw symbol/date aggregation confirmed;
- daily close = last raw close;
- daily volume = summed raw volume;
- previous daily close/volume = shifted raw-derived daily values;
- session volume = summed raw volume;
- no split-factor transform exists in the reconstruction path.

Synthetic fixture also reproduced:
- expected prior close 915 -> actual 915;
- expected prior volume 11,000 -> actual 11,000.

## Important interpretation

This finding does **not** promote or rescue the current fixed Core.

The current fixed Core remains rejected as a replacement candidate under its already-opened canonical performance evidence, especially the essentially flat 2025H2 block.

What this audit changes is the **reasoning about data lineage**:
- do not classify this specific raw1H reconstructed Core as contaminated by the frozen-daily volume adjustment issue;
- do not apply PIT daily split correction a second time to raw1H volume;
- do not replace raw1H-derived absolute gates with frozen daily fields without an explicit PIT-normalization layer.

## Contract

For this reconstructed Core implementation:
- keep raw1H volume unchanged;
- keep raw explicit-period price semantics unchanged for the existing absolute gates;
- fail closed if future code swaps those fields to frozen-daily sources without explicit PIT reconstruction;
- current replacement rejection status remains unchanged.

External semantic dependencies:
- `CONSENSUS_RAW1H_SPLIT_ADJUSTMENT_AUDIT_2026-09-14.md`
- `CONSENSUS_V47_SPLIT_VOLUME_AUDIT_2026-09-14.md`
- `CONSENSUS_V47_RAW1H_VOLUME_CONTRACT_CORRECTION_20260914.md`
