# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 08:57 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約84%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 候補維持 | 100% | 2022単年warningだが2022 computable + 2023-25 aggregateはプラス。retune禁止 |
| Parallel Wave-1 | 🟡 ACTIVE | 78% | 新SHA `5a5a22f1…` outcome-blind OHLC integrity audit追加。source-grounded disposition後にledger再実行 |
| Core24 OHLCV補完 | 🟡 J-Quants候補 / coverage確認待ち | 97% | J-Quants tick/minuteの2024-09-17以降coverage確認→raw pin。不可ならFLEX Historical |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 recovery classifier実装 | 92% | resolver wiring + append-only recovery evidence + crash regression |
| Core endpoint provenance | 🟡 source semantics確定 | 99% | independent raw execution/activity bytesのpin |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Phase-2 frozen順位 / ユーザー評価基準更新
首位は **DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF**。G3 threshold `med_ret1>=-1%` は固定、結果を見たretuneは禁止。

- 2023-25: n117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%
- 2022 fresh computable block: n17 / mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%
- **2022 computable + 2023-25 aggregate: n134 / mean +7.74% / median +1.06% / win 50.75% / Top3-ex +5.17%**

2022は明確なrobustness warningだが、単年FAILを自動失格にはしない。凍結条件の全期間aggregateがプラスなので **Phase-2候補は維持**。2022救済のsurrogate/threshold変更は禁止。regime Round2はCLOSEDのまま。

次のPhase-2補完は同じ凍結rowsから +10/+20/-10/-20/max up/down を追加し、全期間分布を完成させること。条件探索・retuneではない。

## Parallel Wave-1 今回の前進
旧HEAD `500093a9…` から `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` へ前進。`research/parallel_wave1_ohlc_integrity_audit.py` が追加され、step8 failureをperformanceを開かずに調べるため、frozen daily sourceのSHA/schema/row countとOHLC ordering invariantを監査する。silent repair/dropは禁止。次はaudit receiptを実行・固定し、source-generation causeとfail-closed dispositionを先に確定してからcausal ledgerへ戻る。

## Core24 frozen PIT
PIT membership receiptは固定済み：anchor 3,707 → target 3,834、476 replay events（listing134 / delisting261 / transfer81）、quarantine 0、membership SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`。

## 自動研究ハートビート
2026-09-16 08:57 JST確認。5本すべてenabled。Supervisor current / Canonical 08:11 / Core 08:26 / Consensus 08:35 / OSS+Parallel 08:49。**90分超停止疑いなし。**

## STALE / BLOCKED / CLOSED
Parallelは新しいoutcome-blind integrity audit commitが入ったためSTALE解除しACTIVEへ。CoreはJ-Quants history coverage確認待ち、FLEX Historical fallback。Consensusはformal raw BLOCKED。Cloud exact forensic / V20 / Phase-2 Round2はCLOSED。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**Phase-2研究候補は維持。production GOではなく研究継続。** 2022単年warningだけを理由にNO-GOにはしない。残るP0は全期間分布表完成、Parallel source integrity disposition、Core exact-hour evidence。
