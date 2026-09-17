# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-17 21:01 JST  
> **進捗率の見方:** heartbeatや再確認では上げない。trade rows / SHA pin / 比較表セル / 候補採否など、実成果マイルストーンだけで更新する。  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。2026はMeta freezeまでSEALED。

## 📈 現在地

**研究全体: 約84%**  
**P0 historical比較: 68%**  
**Meta地合い切替: 10%（事前登録済み、performance未開封）**

進捗率は据え置き。20:47-20:48 JSTにワーカーを重複防止型へ再配分した直後で、21:01 scan時点では新しいtrade rows / comparison cell / admissibility milestoneはまだ未確定。coordination heartbeatだけでは率を上げない。

## 🧭 21:01 JST Supervisor scan

最新scan receipt: `research/SUPERVISOR_SCAN_20260917_2101.md` / commit `f0f0df30...`。

| Worker | 新配分後の判定 | Supervisor判断 |
|---|---|---|
| :12 2022 exact回収 | 新prompt後のrun待ち | failed run扱いしない |
| :24 新規rows endpoint監査 | 新prompt後のrun待ち | failed run扱いしない |
| :36 比較表＋Meta準備 | 新prompt後のrun待ち | failed run扱いしない |
| :48 別系統rows正規化 | **NONE x1** | 次runもNONEなら即再配分 |
| :00 Supervisor | coordination | heartbeatは進捗に数えない |

現時点では `NONE x2` に達したworkerはまだ0。ここで再度担当を変えるとchurnになるため、**新配分を1 full cycleだけ維持**する。次scanでNONE x2 / 同一blocker反復 / 完成済み2023-25再計算を検知したworkerはユーザー確認なしで即別P0へ切り替える。

## ✅ 確定済み

- primary 5候補の2023-2025は exact/deterministic recovery 済み。
- 2023-2025のcanonical endpoint true missing = 0、既知797 invalid OHLC rowsとのendpoint交差 = 0。
- `strict_3pt` は source artifact / trade rows / code definition / SHA chain を回収できず、**REFERENCE_ONLY / PARKED**。同じ探索を繰り返さない。
- `core_bollinger_reclaim` は immutableなSOURCE_POOL_EXACT証拠あり。historical rowsのcanonical endpoint正規化待ち。
- Meta地合い切替は `breadth / candidate scarcity / range` で事前登録済み。2026を見る前に2022-2025だけでruleをfreezeする。

## 🚀 独立P0経路

1. **2022 exact path** — primary 5候補の2022-computable trade rows + generator/input SHAを固定。
2. **alternate-family path** — `core_bollinger_reclaim`等SOURCE_POOL_EXACT familyをcanonical historical trade rows化。
3. **non-blocking prep path** — 既確定2023-25 rowsから未充足metrics / 100株P&L / prereg causal regime-label coverageを追加。Meta performanceはまだ開かない。

同じblockerへ全workerを集中させない。

## 🎯 最短クリティカルパス

1. 2022-computable primary 5候補のexact trade rowsを回収・SHA pin
2. 別系統候補を最低1本、canonical historical rowsまで正規化できるか確定
3. 2022-2025の候補×年比較表を完成（n/mean/median/win/+10/+20/-10/-20/max up/max down/Top3-ex/100株P&L）
4. causal regime labelsを付与し、2022-2025だけでMeta cross-tab + LOYO
5. Meta mappingをSHA freeze
6. **最後に2026を一回だけ開封**し、static候補とfrozen Metaを同時評価

## Primary 5 — 2023-2025 endpoint coverage

Actions artifact `10264251140` の `v7_causal_tail_cache_2023_2025.csv`（1306 rows、SHA-256 `0398969e...849d`）から既存anchorへexact一致。

- body_pct LOW: 172 trades / true missing 0
- volr20 LOW: 172 / 0
- mean-rank: 172 / 0
- DUAL_TOP1: 140 / 0
- DUAL+G3: 117 / 0

固定daily corpus artifact `10264205130`（4,061,361 rows、SHA-256 `6adfb626...107ba0`）。

## 別系統候補

### strict_3pt
**REFERENCE_ONLY / PARKED**。明示artifact/source/code/trade rows/SHA chainが見つかるまで再探索しない。近いlegacyロジックを代用しない。

### core_bollinger_reclaim
`SOURCE_POOL_EXACT / PERFORMANCE_COMPARISON_NOT_ELIGIBLE_YET`。pool reproductionはexactだが、2022-computable/2023/2024/2025のcanonical trade-row chainが未回収。

### legacy Cloud Monster
最後。exact forensic再現できた場合のみ比較pool復帰。

## Meta regime-switching

`research/META_REGIME_SWITCHING_PREREG_20260917.md` をcommit `a586e98d...` で事前登録。

- 初期軸: market breadth / candidate scarcity / range
- 最大2軸・3 branches
- actionは既存exact候補またはNO TRADEのみ
- continuous weight / ML / tree / threshold grid search禁止
- 2022-2025でfreeze → 2026 one-shot holdout

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。2026 outcomeによるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO。** 最大blockerは2022 primary exact rowsとalternate-family canonical rows。次scanから新しい自律再配分ルールを実運用する。
