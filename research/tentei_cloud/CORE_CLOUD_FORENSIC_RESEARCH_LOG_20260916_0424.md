# Core + Cloud forensic research log — 2026-09-16 04:24 JST

Started by explicitly reading `research/automation-coordination` coordination state/README/dashboard/latest Supervisor work order and `research/tentei-cloud-mtf` HEAD/handoff/tree. Starting Core HEAD `cbe1586d24dd5178da0979c7807155c80b7706a9` was newer than the coordination state's last processed Core SHA; work continued from the live branch without reprocessing older processed SHAs.

## Core24 work completed
Downloaded immutable Actions artifact `10411777912` from successful JPX source capture run and inspected its exact files locally. Artifact contains the pinned New Listings, Delisted, Segment Transfers, current listed-issues page/workbook, and receipt.

Reparsed the three pinned Segment Transfers pages using row-wise exact date parsing. Reverse-replay window `2024-09-17..2026-08-31` contains **81** transfers: 2024=5, 2025=35, current=41. Deterministic normalized/sorted ledger bytes produced local SHA-256 `b2f838727d57499792a95a33b26c768e9ee96b94af909b20713c73b132fbe332`. The known `277A Globe-ing Inc.` transition is recovered exactly as `2026-04-30 Growth -> Prime`.

A forensic discrepancy was found in the prior exploratory transfer count 75: pandas vectorized mixed-date inference silently coerced valid rows from other month abbreviations to `NaT`. That exploratory 75 count is invalid; the immutable source tables contain 81 in-window rows under the frozen row-wise parser.

## 375 vs 395 audit
The same immutable artifact was used to independently audit the listing/delisting count through report-only end `2026-09-10`. New Listings tables are rowspan-expanded and therefore produce two physical rows per issue; pairing/deduplicating those rows yields 134 listings. Delisted pages yield 241 delistings. Combined exact count = **375**, difference versus original 375 receipt = 0.

Therefore the later exploratory `395 = 134 + 261` claim is superseded as a parsing/counting error; there is no immutable-artifact evidence for 261 delistings in this window. The original 375 count is restored as count-consistent evidence. It is still insufficient alone for PIT segment reconstruction because the 81 segment-transfer events must be replayed.

## Cloud Monster
No new exact-model evidence. Status remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`. No model-family guessing, surrogate promotion, or retuning was performed.

## Guardrails
No current fixed Core retune; no Failed-Breakdown/Prior-Close/Precision-3-family reopening; no production/main/workflow/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes. No new performance backtest and no 0.5%/1% cost calculation.

## Next P0
Integrate 134 listing + anchor-relevant delisting events + 81 transfer events into conflict-checked reverse replay from the exact `2026-08-31` listed-issues workbook. Produce membership count/SHA/quarantine receipt. Only after PIT membership PASS proceed to independent exact-hour activity evidence.