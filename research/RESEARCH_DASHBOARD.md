# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 00:00 JST  
> **進捗率の見方:** heartbeatや再確認では上げない。trade rows / SHA pin / 比較表セル / 候補採否 / Meta labelなど、実成果マイルストーンだけで更新する。  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。2026はMeta freezeまでSEALED。

## 📈 現在地

**研究全体: 約84%**  
**P0 historical比較: 68%**  
**Meta地合い切替: 10%（事前登録済み、performance未開封）**

22:00以降、research branchに新しいtrade rows / comparison cell / admissibility / Meta label commitはまだ増えていないため率は据え置き。Supervisorの再配分commitは進捗率へ加算しない。

## 🧭 00:00 JST Supervisor scan

直近research branch HEADは `250d95d6...`（22:00 supervisor再配分）。その後のworker runから新しいresearch substantive commitは0。worker last_runは :12=23:13、:24=23:25、:36=23:34、:48=23:51 JST。

| Worker | 実成果判定 | Supervisor判断 |
|---|---|---|
| :12 2022コード経路復元 | **NONE x1（新方式）** | commit/diff provenance逆引きを継続。次もNONEならsummary-only二層比較案を正式receipt化 |
| :24 2022 Actions逆引き | **NONE x1（新方式）** | Actions provenanceを継続。次もNONEなら2022 blockerを固定し別P0へ転用 |
| :36 100株P/L | **BLOCKED / 自動停止** | **即再起動・再配分済み**。artifact計算依存を外し、GitHub既存receiptからhistorical comparison manifestを作る |
| :48 Metaラベル実装 | **NONE x1（新方式）** | label generator/coverage receiptを継続。次もNONEならMeta input provenance manifestへ縮退 |
| :00 Supervisor | **REASSIGNMENT** | heartbeatは進捗に数えない |

### 今回の軌道修正

`:36` が100株P/L計算でfully blockedとなり自動停止していたため、そのまま放置せず再有効化。ローカルartifact計算を成果条件から外し、**既存GitHub receiptだけで candidate × year × metric の確定/未確定/source SHA を一覧化する historical comparison manifest** 専任へ変更した。これにより、2022 rowsが未回収でも「本当に残っているセル」を固定でき、今後の進捗率を実セル基準へ移せる。

## ✅ 確定済み

- primary 5候補の2023-2025は exact/deterministic recovery 済み。
- 2023-2025のcanonical endpoint true missing = 0、既知797 invalid OHLC rowsとのendpoint交差 = 0。
- `strict_3pt` は **REFERENCE_ONLY / PARKED**。
- `core_bollinger_reclaim` は SOURCE_POOL_EXACT だがcanonical historical rows化が停滞したためPARKED。
- Meta地合い切替は `breadth / candidate scarcity / range` で事前登録済み。2026を見る前に2022-2025だけでruleをfreezeする。

## 🚀 現在の独立P0経路

1. **2022 code provenance** — :12。fresh-validation summary commitからgenerator entrypoint/input SHAを逆引き。
2. **2022 Actions provenance** — :24。同summary commitからworkflow run/job/artifact/generator commandを逆引き。
3. **historical manifest** — :36。既存receiptから確定セル/PENDING_ROWS/source SHAを固定し、比較表の実coverageを数値化。
4. **Meta prep** — :48。2023-2025 exact rowsへoutcome-blind causal labelsを付与しcoverage receiptを作る。

## 🎯 最短クリティカルパス

1. 2022-computable primary 5候補のexact trade rowsまたはgenerator/input chainを回収・SHA pin
2. historical comparison manifestで2022-2025の確定セル/不足セルを固定
3. rowsが必要な不足metrics（+20/-20/max up/max down/Top3-ex/100株P/L）を埋める
4. causal regime labelsを完成
5. exact再現可能な別系統候補は、明示chainが回収できたものだけ比較へ追加。停滞候補をクリティカルパスにしない
6. 2022-2025だけでMeta cross-tab + LOYO、mapping SHA freeze
7. **最後に2026を一回だけ開封**し、static候補とfrozen Metaを同時評価

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

## 最大blocker

**2022 primary 5候補のexact trade rows / generator / input artifact chain未回収。** ただし全workerをこのblockerへ集中させず、historical manifestとMeta prepを独立並列で進める。

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。2026 outcomeによるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO。2026 SEALED。**
