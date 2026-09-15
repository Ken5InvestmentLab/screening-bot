# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 05:23 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🟢 calendar gate修復 | 76% | repaired causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 PIT replay PASS | 94% | membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 crash-consistency監査 | 90% | recovery/two-phase protocol + regression tests |
| Core endpoint provenance | 🟢 PIT membership確定 | 99% | machine-readable receipt → exact-hour evidence |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Core24 今回の前進 — May date parser修正 / strict PIT replay 0 conflict
Immutable artifact `10411777912` を再度exact-byte解析し、JPX英語ページが `Apr.` 等の略称と、ピリオド無しの `May` を混在させることを確認。前回transfer側ではrow-wise修正済みだったが、listing/delisting count監査側にperiod-required parserが残り、2025/2026年5月の有効なdelisting rowsを落としていた。

修正後、`2024-09-17..2026-09-10` は **134 listings + 263 delistings = 397**。したがって前回復帰させた375は再度superseded。reverse replay対象 `(2024-09-17, 2026-08-31]` は **134 listings + 261 delistings + 81 transfers = 476 events**。

2026-08-31 anchor 3,707銘柄からstrict reverse replayを実行し、**quarantine/conflict 0、target membership 3,834**。sorted `CODE,SEGMENT\n` SHA-256は `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`。

次P0はsource SHA/parser/event counts/target count+SHA/zero-quarantineをmachine-readable PIT receiptへ固定。その後のみindependent exact-hour activity evidenceへ進む。membershipからhourly expected keysを捏造しない。

## STALE / BLOCKED / CLOSED
Cloud exact forensicはCLOSED。`HISTORICAL_EXACT_REPRO_UNAVAILABLE`を維持し、新証拠なしのmodel-family guessingは禁止。既reject family retune禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
