# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 02:02 JST  
> **進捗率の見方:** heartbeatや再確認では上げない。trade rows / SHA pin / 比較表セル / 候補採否 / Meta labelなど、実成果マイルストーンだけで更新する。  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。2026はMeta freezeまでSEALED。

## 📈 現在地

**研究全体: 約84%**  
**P0 historical比較: 68%**  
**Meta地合い切替: 10%（事前登録済み、performance未開封）**

直近の実成果は 00:48 JST の Meta label coverage fail-closed receipt（commit `de8a74fa3a153f73e653e651914e595edd308059`）。2023-2025について、exact primary rows SHAと同一universeのcausal breadth/range/pre-rank-count input chainがまだ結合されていないため、Meta labelは全件fail-closed。2026は未開封。

## 🧭 02:00 JST Supervisor scan

worker last_runは :12=01:10、:24=01:25、:36=01:38、:48=01:51 JST。01:00再配分後、research branchに新しいsubstantive commitはまだない。`:36` はmanifest作業でfully blockedとなり自動停止していたため、Supervisorが即再起動し成果物を **G3 1候補だけ**へ縮小した。

| Worker | 実成果判定 | Supervisor判断 |
|---|---|---|
| :12 2022 summary固定案 | **NONE x1（新方式）** | 継続。次もNONEなら2022 summary境界はSupervisor側で固定し別P0へ転用 |
| :24 別系統再開判定 | **NONE x1（新方式）** | 継続。次もNONEならalternate familyを全PARKEDとしてprimary 5へ集中 |
| :36 historical manifest | **BLOCKED / 自動停止** | **再起動・再配分済み**。全5候補manifestをやめG3 1候補の既存確定値manifestへ縮小 |
| :48 Meta入力manifest | **NONE x1（新方式）** | 継続。次もNONEなら3軸を分割しcandidate-count軸だけ先にchain固定 |
| :00 Supervisor | **REASSIGNMENT** | disabled laneを回収し、成果単位をさらに縮小 |

## 今回の重要判断

Meta labelを直接生成する前提が早すぎた。00:48 receiptで、2023-2025 exact rowsとcausal regime inputのSHA/path結合が未成立と確定したため、近似データで進めずfail-closedを維持する。

また、workerが『全候補を一度にmanifest化』するだけでもblockedになるため、今後は成果物を **candidate単位 / axis単位** まで縮小する。小さな確定成果を積み上げ、1 runで巨大な完成物を要求しない。

## 🚀 現在の独立P0経路

1. **2022 summary-only decision** — :12。row-level chainの無期限探索を止め、利用可能/不可metricの境界を固定。
2. **alternate-family admissibility** — :24。既存証拠だけでGO/PARKEDを判定。
3. **G3 historical manifest** — :36。まず1候補だけ確定し、成功後に他4候補へ横展開。
4. **Meta input manifest** — :48。3軸のsource/path/SHA/column chainを固定。次回停滞なら軸単位へ分割。

## 🎯 最短クリティカルパス

1. G3 1候補manifestを完成しmanifest方式自体を成立させる
2. 同方式をprimary 5へ横展開しhistorical comparison coverageを実セル基準で固定
3. 2022はSUMMARY_ONLYとexact-row層を混同せず境界固定
4. Meta input chainは完全に結べる軸だけlabel化。近似禁止
5. exact再現可能な別系統候補だけ追加。再現不能ならPARKEDのままprimary 5で先へ進む
6. Meta mapping SHA freeze
7. **最後に2026を一回だけ開封**しstatic候補とfrozen Metaを同時評価

## 確定済み

- primary 5候補の2023-2025は exact/deterministic recovery 済み。
- 2023-2025 canonical endpoint true missing = 0、既知797 invalid OHLC rowsとのendpoint交差 = 0。
- strict_3pt は REFERENCE_ONLY / PARKED。
- Metaはbreadth / candidate scarcity / rangeで事前登録済み。
- Meta labelは入力chain未結合のため現状FAIL_CLOSED。近似値で埋めない。

## 最大blocker

**historical/Metaの元になるrow-level artifact SHAとsignal-date causal input SHAの結合が不足。** ただし全研究をこの1点で止めず、summary境界固定・candidate単位manifest・alternate admissibilityを並列で進める。

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。2026 outcomeによるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO。2026 SEALED。**
