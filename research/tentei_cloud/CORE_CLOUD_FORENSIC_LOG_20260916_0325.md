# Core + Cloud forensic log — 2026-09-16 03:25 JST

## Scope / guardrails
Research-only Core24 + historical Cloud forensic lane. No production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater changes. No rejected-family retune. No new costed performance. Cloud exact forensic remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing without new evidence.

## Coordination / duplicate gate
Coordination STATE v100 recorded Core last processed SHA `eaabfde1501e695907c25207a95e51302b0bed9a`. Actual `research/tentei-cloud-mtf` HEAD at start was `960c4dbfc1a15696db53108bf7de8d1a96fd9174`, the prior handoff commit verifying the JPX segment-transfer source family. This run therefore continued from that unprocessed HEAD rather than redoing the earlier SHA.

## Work completed
Extended the existing research-only exact-byte JPX capture script to include the three frozen official segment-transfer sources:
- current: `/english/listing/stocks/transfers/index.html`
- 2025: `/english/listing/stocks/transfers/00-archives-01.html`
- 2024: `/english/listing/stocks/transfers/00-archives-02.html`

The receipt contract now explicitly covers listing + delisting + segment-transfer + listed-issues anchor bytes. The existing fail-closed current `data_e.xlsx` selector and correction-workbook exclusion remain unchanged.

Commit: `7457709559f35f7cae1c2488998bcbeae0d37083` (`research(core): byte-pin JPX segment transfer sources`). This path-triggered the research-only capture workflow; run `35007416840` was queued at collection time. Do not claim byte-pin PASS until that run completes successfully and its immutable artifact/receipt is inspected.

## Next P0
1. Collect run 35007416840 terminal result and immutable artifact.
2. Verify all three transfer source rows HTTP 200, exact byte size, SHA-256, retrieval timestamp.
3. Build deterministic transfer ledger only from those pinned bytes.
4. Audit the legacy 375 vs forensic 395 listing/delisting delta row-by-row; legacy 375 remains non-canonical meanwhile.
5. Only after both repairs, perform conflict-checked reverse replay from the pinned 2026-08-31 anchor and freeze PIT membership count/SHA/quarantine receipt.

PIT remains FAIL-CLOSED until these gates pass.
