# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 01:00 JST  
> **進捗率の見方:** heartbeatや再確認では上げない。trade rows / SHA pin / 比較表セル / 候補採否 / Meta labelなど、実成果マイルストーンだけで更新する。  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。2026はMeta freezeまでSEALED。

## 📈 現在地

**研究全体: 約84%**  
**P0 historical比較: 68%**  
**Meta地合い切替: 10%（事前登録済み、performance未開封）**

直近1時間もresearch branchに新しいtrade rows / comparison cell / admissibility / Meta label commitは0。したがって進捗率は据え置き。再配分自体は進捗率へ加算しない。

## 🧭 01:00 JST Supervisor scan

worker last_runは :12=00:10、:24=00:23、:36=00:38、:48=00:48 JST。新方式へ切替後も :12/:24/:48 は2 run連続で実成果0。:36はmanifest方式へ切替後1 run目でまだcommitなし。

| Worker | 実成果判定 | Supervisor判断 |
|---|---|---|
| :12 2022コード経路復元 | **NONE x2** | **再配分済み**。2022 generator探索を打切り、既開封summary-onlyを正式decision receipt化 |
| :24 2022 Actions逆引き | **NONE x2** | **再配分済み**。Actions探索を打切り、別系統候補の再開可否manifestへ転用 |
| :36 historical manifest | **NONE x1（新方式）** | 継続。次もNONEなら成果物をcandidate単位へ縮小 |
| :48 Metaラベル実装 | **NONE x2** | **再配分済み**。直接実装を止め、Meta入力provenance manifestへ縮退 |
| :00 Supervisor | **REASSIGNMENT** | 3 laneを即時軌道修正 |

### 今回の軌道修正

2022 exact rows/generatorを追い続けること自体がクリティカルパスを固定化していたため、探索を無期限継続しない方針へ変更。2022は既開封frozen summaryを `SUMMARY_ONLY` として正式に固定するdecision receiptを作り、exact rowsが無いmetric/Meta labelは明示BLOCKEDとする。これによりhistorical比較はsummary層とexact-row層を混同せず先へ進める。

同時に :24 は別系統候補の再開可否を既存証拠だけで判定、:48 はMeta入力のsource/path/SHA/columnをmanifest化する。どちらも広範囲探索やperformance計算を禁止し、次に実装可能な1点を固定する。

## 🚀 現在の独立P0経路

1. **2022 summary-only decision** — :12。利用可能metricとrows必須BLOCKED metricを正式固定。
2. **alternate-family admissibility** — :24。既存証拠だけで再開GO/PARKEDを判定。
3. **historical comparison manifest** — :36。candidate×year×metricの確定/PENDING/source SHAを固定。
4. **Meta input manifest** — :48。breadth/candidate-count/rangeのcausal input chainを固定。

## 🎯 最短クリティカルパス

1. historical comparison manifest + 2022 summary-only decisionを完成
2. 2022 rows欠落を理由に全研究を止めず、exact-row期間とsummary-only期間を明確に分離
3. Meta input manifestから完全chainのある軸を先にlabel化
4. exact再現可能な別系統候補はadmissibility GOのものだけ追加
5. Meta discoveryに必要なrow-level期間が不足する場合は、2022を混ぜず2023-2025 exact rowsだけで年holdout設計が成立するか事前に判断・固定
6. Meta mapping SHA freeze
7. **最後に2026を一回だけ開封**しstatic候補とfrozen Metaを同時評価

## 確定済み

- primary 5候補の2023-2025は exact/deterministic recovery 済み。
- 2023-2025のcanonical endpoint true missing = 0、既知797 invalid OHLC rowsとのendpoint交差 = 0。
- strict_3pt は REFERENCE_ONLY / PARKED。
- core_bollinger_reclaim は SOURCE_POOL_EXACT。再開可否を:24が判定。
- Metaはbreadth / candidate scarcity / rangeで事前登録済み。

## 最大blocker

**2022 row-level exact chainが回収できていない。** 今runから無期限探索は止め、SUMMARY_ONLYとして境界を固定し他P0を前進させる。

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。2026 outcomeによるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO。2026 SEALED。**
