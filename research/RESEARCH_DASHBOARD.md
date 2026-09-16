# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 12:11 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約84%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 候補維持 | 100% | 2022単年warningだが2022 computable + 2023-25 aggregateはプラス。retune禁止 |
| Parallel Wave-1 | 🟡 ACTIVE | 78% | outcome-blind OHLC integrity audit。source-grounded disposition後にledger再実行 |
| Core24 OHLCV completeness | 🟡 実数監査P0 | 97% | **欠損ゼロ未確認**。exhaustive daily raw corpusの取得済み/pin証拠を先に確定し、XTKS×PITでO/H/L/C/V field監査。hourlyは独立activity raw未取得のためSEALED |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 append-only recovery evidence追加 | 93% | resolver startup wiring + end-to-end sidecar-ahead crash regression |
| Core endpoint provenance | 🟡 source semantics確定 | 99% | independent raw execution/activity bytesのpin |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Canonical/Shadow — 今回の前進
既存のoutcome-blind recovery classifierに、`committed / sidecar_ahead_interrupted / invalid_tampered / uninitialized` 判定をappend-only evidenceとして固定する recovery protocol を追加した。recordはstrategy outcomeを開かず、gross returnを計算せず、production authorizationを与えず、immutable chainを書換えない。exact replayのみidempotent、既存recordと内容が競合する場合はfail-closedする regression test を追加した。

Canonical HEADは `9fde775bac3449c5f5cf0cbbfc7babf9dc38ecfc`。次はこのclassifier + immutable recovery recordをresearch-only resolver startupへ配線し、sidecar永続化後・resolved replace前のcrashを実際に模擬して、再起動時にsidecar-aheadを識別してappend-only recovery/abort evidenceを残すend-to-end regressionを閉じる。performance/H1/H2/2026 outcomeはこの工程では開かない。

## Core24 OHLCV実数監査
P0はprovider候補探索ではなく**実データcompleteness audit**。現時点では研究期間全体を覆う取得済みdaily raw corpusが確定していないため、daily true-missing件数は未確定でmissing=0とは扱わない。exact-hour/activityは独立raw witness未取得のためSEALED。

## Phase-2 frozen順位 / ユーザー評価基準
首位は **DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF**。G3 threshold `med_ret1>=-1%` は固定、結果を見たretuneは禁止。
- 2023-25: n117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%
- 2022 fresh computable block: n17 / mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%
- 2022 computable + 2023-25 aggregate: n134 / mean +7.74% / median +1.06% / win 50.75% / Top3-ex +5.17%

## Core24 frozen PIT
PIT membership receiptは固定済み：anchor 3,707 → target 3,834、476 replay events（listing134 / delisting261 / transfer81）、quarantine 0、membership SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**Phase-2研究候補は維持。production GOではなく研究継続。** Canonical/Shadowはperformance sealedのままprovenance recovery integrityを継続する。
