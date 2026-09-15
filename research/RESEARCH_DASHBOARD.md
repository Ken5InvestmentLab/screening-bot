# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 03:29 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🟢 calendar gate修復 | 76% | repaired causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 JPX transfer exact-byte PASS | 91% | transfer ledger + 375-vs-395 audit → corrected PIT receipt |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 crash-consistency監査 | 90% | recovery/two-phase protocol + regression tests |
| Core endpoint provenance | 🟢 transfer bytes pinned | 99% | corrected PIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Core24 今回の前進 — JPX transfer exact-byte capture PASS
Research-only capture run `35007416840` がsuccess。artifact `10411777912`、digest `sha256:2d1b761e51a8cd70ba8501a5c1ed0df8a09ad4b17fa5456483967108728df7e7` を固定した。transfer current / 2025 / 2024 はすべてHTTP 200で、exact bytes・SHA-256・retrieval timestampをartifact receiptから確認済み。

transfer SHA-256: current `85be65e0669f7a54891de41616715a5cebcc6d291f000487720ac1d067d53a2a`; 2025 `ade2457928577e98849ac23dfb5779ea14600d4bb7d89d5a87f377b121319145`; 2024 `dcd590122107f5632d4880b3d58ab38605f0b5bd11e6df51a90c9d56d3c35f71`。

これはtransfer source provenanceのみPASS。PITはFAIL-CLOSED継続。次はpinned bytesのみからdeterministic transfer ledgerを作り、旧375-event receiptとforensic 395-event listing/delisting差分20件をrow-level監査し、その後にconflict-checked reverse replay/PIT receiptを固定する。

## STALE / BLOCKED / CLOSED
Cloud exact forensicはCLOSED。`HISTORICAL_EXACT_REPRO_UNAVAILABLE`を維持し、新証拠なしのmodel-family guessingは禁止。既reject family retune禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
