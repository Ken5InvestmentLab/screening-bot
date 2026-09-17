# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-17 22:00 JST  
> **進捗率の見方:** heartbeatや再確認では上げない。trade rows / SHA pin / 比較表セル / 候補採否など、実成果マイルストーンだけで更新する。  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。2026はMeta freezeまでSEALED。

## 📈 現在地

**研究全体: 約84%**  
**P0 historical比較: 68%**  
**Meta地合い切替: 10%（事前登録済み、performance未開封）**

21:01以降、research branchに新しいtrade rows / comparison cell / admissibility milestone commitは増えていないため率は据え置き。これはheartbeatではなく実成果だけで率を更新する運用による。

## 🧭 22:00 JST Supervisor scan

直近research branch substantive HEADは `9770eed1...`（21:01 dashboard更新）で、その後のworker runから新しいresearch commitは0。worker last_runは :12=21:14、:24=21:26、:36=21:38、:48=21:50 JST。

| Worker | 判定 | Supervisor判断 |
|---|---|---|
| :12 2022 exact回収 | **NONE x1** | 2022 pathを継続。次runもNONEならartifact回収方法を変更 |
| :24 新規rows endpoint監査 | **NONE x1** | 新規rowsなし。次runは2022 artifact回収支援へ転用 |
| :36 比較表＋Meta準備 | **NONE x1** | 次runは既存rowsから100株P/Lまたはlabel coverageを必須成果化 |
| :48 別系統rows正規化 | **NONE x2** | **即再配分済み：Meta causal label実装へ切替** |
| :00 Supervisor | REASSIGNMENT | heartbeatは進捗に数えない |

`core_bollinger_reclaim` historical rows正規化は2 run連続で実成果が増えなかったためPARKED。:48を、2023-2025 exact rowsへpreregistered causal regime labelsを付ける独立P0準備へ切り替えた。これにより2022 blockerと独立してMeta準備を進める。

## ✅ 確定済み

- primary 5候補の2023-2025は exact/deterministic recovery 済み。
- 2023-2025のcanonical endpoint true missing = 0、既知797 invalid OHLC rowsとのendpoint交差 = 0。
- `strict_3pt` は **REFERENCE_ONLY / PARKED**。
- `core_bollinger_reclaim` は SOURCE_POOL_EXACT だがcanonical historical rows化が停滞したため一時PARKED。
- Meta地合い切替は `breadth / candidate scarcity / range` で事前登録済み。2026を見る前に2022-2025だけでruleをfreezeする。

## 🚀 現在の独立P0経路

1. **2022 exact path** — :12主担当、:24支援。primary 5候補の2022-computable trade rows + generator/input SHAを固定。
2. **historical table path** — :36。既確定rowsから未充足metrics / 100株P&Lを埋める。
3. **Meta prep path** — :48。2023-2025 exact rowsへoutcome-blind causal labelsを付与しcoverage receiptを作る。Meta performanceはまだ開かない。

## 🎯 最短クリティカルパス

1. 2022-computable primary 5候補のexact trade rowsを回収・SHA pin
2. 2022-2025の候補×年比較表を完成（n/mean/median/win/+10/+20/-10/-20/max up/max down/Top3-ex/100株P&L）
3. causal regime labelsを完成
4. exact再現可能な別系統候補は、明示chainが回収できたものだけ比較へ追加。停滞候補の探索をクリティカルパスにしない
5. 2022-2025だけでMeta cross-tab + LOYO、mapping SHA freeze
6. **最後に2026を一回だけ開封**し、static候補とfrozen Metaを同時評価

## Primary 5 — 2023-2025 endpoint coverage

Actions artifact `10264251140` の `v7_causal_tail_cache_2023_2025.csv`（1306 rows、SHA-256 `0398969e...849d`）から既存anchorへexact一致。

- body_pct LOW: 172 trades / true missing 0
- volr20 LOW: 172 / 0
- mean-rank: 172 / 0
- DUAL_TOP1: 140 / 0
- DUAL+G3: 117 / 0

固定daily corpus artifact `10264205130`（4,061,361 rows、SHA-256 `6adfb626...107ba0`）。

## Meta regime-switching

`research/META_REGIME_SWITCHING_PREREG_20260917.md` / commit `a586e98d...`。

- 初期軸: market breadth / candidate scarcity / range
- 最大2軸・3 branches
- actionは既存exact候補またはNO TRADEのみ
- continuous weight / ML / tree / threshold grid search禁止
- :48はperformanceを開かずlabel generator / label artifact / coverage receiptだけを作る
- 2022-2025でfreeze → 2026 one-shot holdout

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。2026 outcomeによるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO。** 今回は停滞を検知して:48を自律再配分。次scanで :12/:24/:36 がNONE x2になった場合も即座に担当を変更する。