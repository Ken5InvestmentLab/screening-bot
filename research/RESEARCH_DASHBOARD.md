# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 04:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🟢 calendar gate修復 | 76% | repaired causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 transfer ledger監査完了 | 92% | 375 listing/delisting + 81 transfer → conflict-checked PIT receipt |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 crash-consistency監査 | 90% | recovery/two-phase protocol + regression tests |
| Core endpoint provenance | 🟢 PIT replay直前 | 99% | corrected PIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Core24 今回の前進 — transfer ledger 81件 / 375 audit復元
Immutable artifact `10411777912` を直接取得して、pinned JPX transfer current / 2025 / 2024 bytesを再解析した。`2024-09-17..2026-08-31` のreverse-replay対象は **81 transfers = 2024:5 + 2025:35 + current:41**。normalized/sorted ledgerのlocal SHA-256は `b2f838727d57499792a95a33b26c768e9ee96b94af909b20713c73b132fbe332`。`277A Globe-ing Inc.` の `2026-04-30 Growth -> Prime` もexactに回収した。

重要なparser correction: exploratoryな75件はpandas vectorized mixed-date inferenceが異なる月略称を`NaT`へcoerceしたことによる過少計数で、canonical evidenceから除外。row-wise exact date parseをfreezeした。

同じimmutable artifactで旧375-vs-395も再監査。New Listingsのrowspan展開をissue単位でpair/dedupするとlisting 134、Delistedは241、`2024-09-17..2026-09-10` 合計 **375** で旧375 receiptと完全一致した。したがってexploratory `395 = 134 + 261` はsuperseded。375自体はcount-consistentへ復帰した。ただしlisting/delistingだけではsegment state不完全なのでPITはFAIL-CLOSED継続。

次P0は2026-08-31 anchorから、pinned listing/delisting + 81 transfersを統合してstrict conflict-checked reverse replayし、membership count/SHA/quarantine receiptをfreezeすること。PASS後のみindependent exact-hour activity evidenceへ進む。

## STALE / BLOCKED / CLOSED
Cloud exact forensicはCLOSED。`HISTORICAL_EXACT_REPRO_UNAVAILABLE`を維持し、新証拠なしのmodel-family guessingは禁止。既reject family retune禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
