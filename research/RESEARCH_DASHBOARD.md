# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-17 20:48 JST  
> **進捗率の見方:** heartbeatや再確認では上げない。trade rows / SHA pin / 比較表セル / 候補採否など、実成果マイルストーンだけで更新する。  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。2026はMeta freezeまでSEALED。

## 📈 現在地

**研究全体: 約84%**  
**P0 historical比較: 68%**  
**Meta地合い切替: 10%（事前登録済み、performance未開封）**

84%が朝から変わっていないのは、研究停止ではなく**完了マイルストーンがまだ次の閾値を越えていないため**。本日17:46 JSTには別系統forensicの実成果commit `d02eaef8...` が追加されている。

## ✅ 今日確定したこと

- primary 5候補の2023-2025は exact/deterministic recovery 済み。
- 2023-2025のcanonical endpoint true missing = 0、既知797 invalid OHLC rowsとのendpoint交差 = 0。
- `strict_3pt` は現時点で source artifact / trade rows / code definition / SHA chain を回収できず、**REFERENCE_ONLY / PARKED**。同じ探索を繰り返さない。
- `core_bollinger_reclaim` は immutableなSOURCE_POOL_EXACT証拠あり。次はhistorical rowsをcanonical endpointへ正規化できるかを調べる。
- Meta地合い切替は `breadth / candidate scarcity / range` の事前登録済み。2026を見る前に2022-2025だけでruleをfreezeする。

## 🚀 20:48 JST 効率化後の5ワーカー

| 時刻 | 担当 | やること | やらないこと |
|---|---|---|---|
| :00 | Supervisor | 新成果SHA確認、重複停止、Dashboard/STATE更新、即再配分 | 広範囲探索 |
| :12 | 2022 exact回収 | primary 5候補の2022 trade rows + generator/input SHA固定 | 2023-25再計算 |
| :24 | 新規rows endpoint監査 | **新しいrowsが出た時だけ**O/C監査 | 全市場OHLCV再監査、797行再確認 |
| :36 | 比較表＋Meta準備 | 未充足metrics/100株P&L、causal label生成 | Meta performance先行開封 |
| :48 | 別系統rows正規化 | `core_bollinger_reclaim`等をhistorical canonical rows化 | strict_3pt同一検索、legacy Cloud先行 |

### 無駄打ち防止ルール

- 同じblockerを2 run続けて調べない。
- 新SHA / rows / receipt / 比較表セル / 採否確定が無ければ別P0へ切替。
- `strict_3pt`は明示artifactが新規に見つかるまでPARKED。
- 2023-25 primary 5候補は既にexactなので再生成しない。
- OHLCV監査は新しいcandidate/year rowsが追加された時だけ実施。
- heartbeatだけでは進捗率を上げない。

## 🎯 最短クリティカルパス

1. **2022-computable primary 5候補のexact trade rowsを回収・SHA pin**
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
`SOURCE_POOL_EXACT / PERFORMANCE_COMPARISON_NOT_ELIGIBLE_YET`。pool reproductionはexactだが、2022-computable/2023/2024/2025のcanonical trade-row chainが未回収。ここを次の別系統実働対象とする。

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

**研究継続 / production NO-GO。** いまの最大blockerは「2022 primary 5候補のexact rows」と「別系統候補のcanonical historical rows化」。ここへ計算資源を集中する。
