# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 13:00 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約84%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 候補維持 | 100% | 2022単年warningだが2022 computable + 2023-25 aggregateはプラス。retune禁止 |
| **DUAL+G3 2026 / 年別表** | 🔴 **P0** | 70% | frozen per-trade rowsのSHA pinまたはexact reproducer一致確認 → 2026を同条件で開く |
| Parallel Wave-1 | 🟡 P1へ一時降格 | 78% | P0結果確定まで周辺監査を増やさない |
| Core24 OHLCV completeness | 🟡 **P0 endpoint先行** | 97% | まずDUAL+G3 entry/exit O/C true-missing件数を確定。全市場監査はその後 |
| Consensus V47 | 🟢 P1 / formal raw BLOCKED | 84% | P0結果確定までmonitoring優先度を下げる |
| Canonical/Shadow endpoint integrity | 🟢 P1へ一時降格 | 93% | P0結果確定まで追加recovery拡張を止める |
| Core endpoint provenance | 🟡 source semantics確定 | 99% | independent raw execution/activity bytesのpin |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 P1へ一時降格 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## 🎯 結果優先P0 — 13:00切替
ユーザー向け成果物を次の3つに限定して最短で閉じる。
1. **DUAL_TOP1_AGREEMENT + G3** の2026成績（5BD exit確定済みのみ、report-only）
2. 同一凍結条件の **2022 / 2023 / 2024 / 2025 / 2026 年別表 + 2022-26 aggregate**（n/mean/median/win/+10/+20/-10/-20/max up/max down/Top3-ex）
3. **OHLCV欠損のDUAL+G3 endpoint影響件数**を先に確定し、その後に全体missing ledgerを閉じる

今回の具体的前進：既存の `tvfree-v13-frozen-2026` runnerを確認したが、これは `med_ret5<=0` + 4-feature rank の別V13ロジックであり、**DUAL+G3の代用には使えない**と確定。誤った2026数値を出す近道を排除した。次は、凍結済み2023-25 n117を生成したexact DUAL+G3 trade rowsをhistorical branch/Actions artifactから回収し、SHA pinする。回収不能なら凍結定義+preserved causal datasetからdeterministic reproducerを作り、**2023-25が n117 / mean+7.98% / median+1.74% / win53.85% / Top3-ex+5.14% に完全一致した場合のみ**2026を開く。

## Core24 OHLCV実数監査
全市場のraw corpus確定を2026年次表の前提にしない。まずDUAL+G3全tradeの `next XTKS open` と `fifth XTKS close` に必要なO/Cだけを既存取得rawと照合し、true missingと影響tradeをreceipt化する。ここが0なら「年次performance endpointへのOHLCV直接影響0」を先に確定する。上場前/廃止後/売買停止等の正常no-dataとtrue missingは分離。exact-hour/activityは別項目SEALEDで、daily endpoint監査を止める理由にしない。

## Phase-2 frozen順位 / ユーザー評価基準
首位は **DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF**。G3 threshold `med_ret1>=-1%` は固定、結果を見たretuneは禁止。
- 2023-25: n117 / mean +7.98% / median +1.74% / win 53.85% / +10 31.62% / +20 18.80% / -10 28.21% / -20 9.40% / Top3-ex +5.14%
- 2022 fresh computable block: n17 / mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%
- 2022 computable + 2023-25 aggregate: n134 / mean +7.74% / median +1.06% / win 50.75% / Top3-ex +5.17%

## Core24 frozen PIT
PIT membership receiptは固定済み：anchor 3,707 → target 3,834、476 replay events（listing134 / delisting261 / transfer81）、quarantine 0、membership SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。Phase-2 Round2 CLOSED。新規条件探索・retune禁止。

## GO / NO-GO
**Phase-2研究候補は維持。production GOではなく研究継続。** 今は周辺研究より2026年次結果・年別表・endpoint OHLCV欠損実数を優先する。