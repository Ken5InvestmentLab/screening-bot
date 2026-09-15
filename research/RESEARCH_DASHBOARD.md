# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 07:09 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🟢 calendar gate修復 | 76% | repaired causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 PIT receipt固定 | 95% | independent exact-hour activity evidence/receipt |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 recovery classifier実装 | 92% | resolver wiring + append-only recovery evidence + crash regression |
| Core endpoint provenance | 🟢 PIT membership確定 | 99% | exact-hour activity evidence |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Canonical/Shadow 今回の前進 — outcome-blind crash recovery classifier
`tvfree_screener/batch02/prospective_shadow_resolution_recovery.py` を追加し、immutable resolution chain と現在のresolved SHAだけから crash-consistency 状態を分類する純粋関数を固定した。performance/H1/H2/2026 outcomeは開いていない。

分類は `committed`（tail == current）、`sidecar_ahead_interrupted`（prior == current かつ tail != current）、`invalid_tampered`（chain verification失敗またはcurrentがtail/priorのどちらにも一致しない）、初期状態 `uninitialized`。sidecar-aheadだけを recovery candidate とし、classifier自身はchainを削除・truncate・rewriteしない。5 regression testsを追加し、committed / sidecar-ahead / invalid-chain / neither-match / input non-mutationを固定。Canonical HEAD `219405fe9922e9f5a1ce89d6aa44a7810bd54cc3`。現時点では当該HEADに紐づくActions runは未検出のためCI GREENとはまだ表現しない。

次P0はclassifierをresearch-only resolver startupへ配線し、sidecar-ahead時にappend-only recovery/abort evidenceを残す明示protocolとcrash simulation regressionを追加すること。immutable receipt/chainの削除・書換えは禁止、invalid/tamperedは引き続きfail-closed。

## Core24 既存状態 — machine-readable PIT membership receipt固定
`research/tentei_cloud/CORE_JPX_PIT_MEMBERSHIP_RECEIPT_20260916.json` をCore branchへ固定済み。Canonical値は anchor `2026-08-31` / **3,707**、reverse window `(2024-09-17, 2026-08-31]`、**134 listings + 261 delistings + 81 transfers = 476**、quarantine/conflict **0**、target **3,834**、sorted `CODE,SEGMENT\n` SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`。次P0はindependent exact-hour activity evidence/receipt。

## STALE / BLOCKED / CLOSED
Cloud exact forensicはCLOSED。`HISTORICAL_EXACT_REPRO_UNAVAILABLE`を維持し、新証拠なしのmodel-family guessingは禁止。既reject family retune禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
