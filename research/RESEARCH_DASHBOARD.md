# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 08:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🔴 STALE再昇格 | 76% | run 34998500020はsource/calendar PASS後step8 causal ledger生成FAIL。step8修正 → endpoint completeness |
| Core24 OHLCV補完 | 🟡 J-Quants候補 / coverage確認待ち | 97% | J-Quants tick/minuteの2024-09-17以降coverage確認→raw pin。不可ならFLEX Historical |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 recovery classifier実装 | 92% | resolver wiring + append-only recovery evidence + crash regression |
| Core endpoint provenance | 🟡 source semantics確定 | 99% | independent raw execution/activity bytesのpin |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Phase-2 frozen順位
首位は **DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF**。2023-25 total: n117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。G3 threshold `med_ret1>=-1%` は固定。2022 fresh validationはROBUSTNESS FAIL固定。regime Round2はCLOSED。

## Core24 今回の前進 — J-Quants高頻度データを低コスト公式候補として追加
JPX/JPXIは2026-01-19からJ-Quants APIへ株式のtick/minute-bar dataを追加しており、Light Plan以上向けadd-onは税込5,500円/月と公式発表されている。FLEX Historicalより大幅に低コストで、Yahooから独立した公式activity witness候補になる。

ただし今回確認できた公開JPXページだけでは、必要な研究開始日 **2024-09-17** までhigh-frequency履歴が遡れることを証明できない。よって状態は `LOWER_COST_OFFICIAL_CANDIDATE_HISTORY_COVERAGE_UNVERIFIED`。次P0は公式J-Quants tick/minute API仕様・history retentionをpinし、coverageが足りる場合のみraw sample→SHA→activity semanticsを検証する。formal expected keysはSEALED維持。

## Core24 frozen PIT
PIT membership receiptは固定済み：anchor 3,707 → target 3,834、476 replay events（listing134 / delisting261 / transfer81）、quarantine 0、membership SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`。

## 自動研究ハートビート
2026-09-16 08:24 JST確認。Core laneは継続稼働。90分超停止疑いなし。

## STALE / BLOCKED / CLOSED
🔴 Parallel: step8 causal ledger failureでSTALE再昇格。🟡 Core: J-Quants history coverage確認待ち、FLEX Historical fallback。Consensus: formal raw BLOCKED。Cloud exact forensic / V20 / Phase-2 Round2はCLOSED。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
