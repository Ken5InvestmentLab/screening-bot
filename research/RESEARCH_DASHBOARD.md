# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 09:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約84%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 候補維持 | 100% | 2022単年warningだが2022 computable + 2023-25 aggregateはプラス。retune禁止 |
| Parallel Wave-1 | 🟡 ACTIVE | 78% | outcome-blind OHLC integrity audit。source-grounded disposition後にledger再実行 |
| Core24 OHLCV completeness | 🟡 実数監査P0 | 97% | **欠損ゼロ未確認**。exhaustive daily raw corpusの取得済み/pin証拠を先に確定し、XTKS×PITでO/H/L/C/V field監査。hourlyは独立activity raw未取得のためSEALED |
| Consensus V47 | 🟢 formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 recovery classifier実装 | 92% | resolver wiring + append-only recovery evidence + crash regression |
| Core endpoint provenance | 🟡 source semantics確定 | 99% | independent raw execution/activity bytesのpin |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Core24 OHLCV実数監査 — 今回の前進
P0をprovider候補探索から**実データcompleteness audit**へ切替。`CORE_OHLCV_COMPLETENESS_AUDIT_SPEC_20260916.md`を追加し、daily expected/observed/missing(symbol,date,field,class)、年/月集計、source補完matrix、trade-impact、2022-2026 DUAL+G3 endpoint影響、receipt hashを必須化した。

現時点では、repository/Actions証拠から研究期間全体を覆う取得済みdaily raw corpusをこのrun内で確定できていないため、**daily true-missing件数は未確定、missing=0とは扱わない**。上場前/廃止後/独立証拠付きno-activityのみ正常欠損、その他unknownはfail-closed。Google Finance / Alpha Vantage / J-Quants / FLEXはraw取得・pin済みでない限り補完済みに数えない。

exact-hour/activityは独立raw witness未取得のため引き続きSEALED。membership×calendar×hourの期待行捏造は禁止。次は実際のCore daily raw artifactを特定・SHA固定してfield-level ledgerを実行し、そのconfirmed missingだけをcanonical entry/exitとDUAL+G3 endpointへintersectionする。

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
**Phase-2研究候補は維持。production GOではなく研究継続。** Core OHLCVについては実数receiptが出るまで欠損ゼロ判定を保留する。
