# TV-Free スコアリングBot研究ダッシュボード

> **最終更新基準:** 2026-09-14 16:26 JST  
> **更新元:** `research/AUTOMATION_COORDINATION_STATE.json` + 各active laneのhandoff / Actions  
> **目的:** 研究の進捗・候補・バックテスト・ブロッカーを1ページで把握する。  
> **注意:** 進捗率は「研究の成功確率」ではなく、各レーンで事前定義したマイルストーン消化率の目安。

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **まだ0件** |
| Active research branches | **4本** |
| 定期worker | **5枠 (:00 / :12 / :24 / :36 / :48)** |
| 現在の本命 | **1位 Consensus V47 / 2位 V20 Session-Impulse** |
| 成績まで正式に開けた本命 | **まだ無し** |
| 最大の歴史的参考値 | **旧Cloud Monster: n=63 / 5BD平均 +9.86%** |
| Cloud完全一致再現 | **再検証を正式に再開。現在は exact spec復元待ち** |
| 未完了タスク | **24項目**（P0:5 / P1 V20:5 / P1 Cloud:4 / P2 OSS:6 / 最終:4） |
| 最終判定 | **NO-GO / 研究継続** |

### 全体進捗
`███████████░░░░░░░░░` **約56%**

- 基盤・評価契約・リーク防止: かなり完了
- 本命候補のrawデータ受入: 未完
- 本命候補H1/H2評価: 未開封
- Cloud Monster完全一致forensic: 再開、元条件spec復元前
- EDINET: 実データ取得前のacquisition/snapshot/selector境界までCI固定済み
- 最終比較 / GO-NO-GO: 未実施

---

## 1. 5 worker状態

| Worker | 担当 | 現在の状態 | 最新確認 |
|---|---|---|---|
| **:00 Supervisor** | 横断監督 / 未割当lane / Dashboard | 🟢 **監査完了** | 16:24 — 全research/*を再列挙、OSS handoff-only差分をSTATEへ同期、新規laneなし |
| **:12 Canonical** | V20 / Shadow | 🟡 **WAITING** | V47 accepted raw待ち。V20は734 gap、H1/H2未開封 |
| **:24 Core** | Core + Cloud exact forensic | 🟠 **FORENSIC PENDING** | Core rejectは維持。Cloud n=63/+9.86%完全一致spec復元→元期間再現が次 |
| **:36 Consensus** | V47 | 🟡 **RAW RETRY ACTIVE** | retry `34810592135`: fetch(0)/fetch(1) raw取得中、10 shard queued |
| **:48 Cross-lane + OSS** | 結果回収 / OSS | 🟢 **PROGRESSED** | EDINET official-v2 acquisition boundary + CI `34816055006` SUCCESS |

---

## 2. レーン別ステータス

| レーン | 状態 | 目安進捗 | 現在地 | 次アクション |
|---|---:|---:|---|---|
| **Consensus V47** | 🟡 本命 / RAW RETRY ACTIVE | **66%** | Daily PIT PASS、初回raw acceptance FAIL、hardened retryで2 shard実取得中 | retry `34810592135` 完了後、同じfrozen verifierを再実行 |
| **V20 Session-Impulse** | 🟡 本命 / COVERAGE BLOCKED | **55%** | 1,810銘柄×82セッション凍結済み、734 symbol/date不足 | V47でaccepted rawができたら734件だけ監査・修復 |
| **Core replacement** | 🔴 現候補REJECT | **評価自体は90%** | Fixed Core等を正式評価し棄却 | reject familyはretuneしない |
| **Cloud exact forensic** | 🟠 再現性監査 | **10%** | 歴史値 n=63/+9.86%は既知。完全一致実装は未復元 | exact-match spec凍結→元期間完全再現→成功時のみ別期間へ無調整横展開 |
| **OSS / Validation** | 🟢 基盤進行 | **65%** | Purged/DSR/Optuna + EDINET acquisition/snapshot/selector境界をCI固定 | 2023-2025 raw metadata取得→snapshot hash freeze→同一ZIP比較 |
| **Shadow / Data Integrity** | 🟢 基盤 | **80%** | calendar/integrity/immutable receipt CI成功 | real shadow launchは未承認 |

---

## 3. 有望候補ランキング

| 順位 | 条件 / family | 判定 | バックテスト | コメント |
|---:|---|---|---|---|
| **1** | **Consensus V47 — NOCAP / CAP1000_PIT** | 🟡 未評価 | **未開封** | 最もクリーンなPIT pipeline。raw retry実行中 |
| **2** | **V20 Session-Impulse Continuation** | 🟡 未評価 | **未開封** | 4H/intraday主軸のEvent/Monster候補。734欠損が blocker |
| **3** | **旧Cloud Monster exact reconstruction** | 🟠 Historical forensic | **歴史値 n=63 / 平均 +9.86%** | 完全一致再現を再検証中。元期間を完全再現できた場合だけ、無調整で未使用期間へ横展開 |
| 4 | Canonical Monster v2 | 🔴 REJECT | 2025 locked 平均 **+2.19%** | frozen 0.5% cost Top1-winner-excluded mean **-0.21%**で棄却 |
| 5 | Fixed Core | 🔴 REJECT | DEV +0.712% / 2025H2 **-0.452%** | 2025H2中央値 -0.745%、勝率41.43% |
| 6 | Failed-Breakdown Reclaim | 🔴 REJECT | DEV **-0.766%** / Internal +0.331% | median/win rateがgate未達 |
| 7 | Prior-Close Reclaim | 🔴 REJECT | DEVELOPMENT gate FAIL | H2未開封 |
| 8 | Precision 3-family | 🔴 REJECT | DEVELOPMENTで全family負 | 隣接retune禁止 |

---

## 4. 既知バックテスト結果

### 旧Cloud Monster — 歴史値と再現性監査を分離
**歴史的ヘッドライン**
- n = **63**
- 5BD平均 = **+9.86%**
- この数値自体は historical headline であり、現時点のpromotion evidenceではない

**完全一致forensicの現在地**
1. ⏳ 当時の実装・設定・score・学習/評価期間・candidate selection・cooldown・entry/exit・cost・A/B確率帯を復元
2. 🔒 exact-match specを凍結
3. 🔒 元期間で **n=63 / +9.86%** を完全再現
4. 🔒 成功した場合のみ、条件をretuneせず未使用期間へ横展開
5. 🔒 n / 平均 / 中央値 / 勝率 / +10/+20/+50 / -10/-20 / Top1・Top3除外 / 月週依存でportability判定

**重要:** 近縁条件 / surrogate の好成績を「完全再現」とは扱わない。2026はreport-only。

### Fixed Core — canonical endpoint
| 区間 | n | 平均 | 中央値 | 勝率 | Top3除外 |
|---|---:|---:|---:|---:|---:|
| DEV | 169 | **+0.712%** | +0.509% | 55.62% | +0.393% |
| 2025 H2 | 140 | **-0.452%** | -0.745% | 41.43% | -0.874% |

**判定:** REJECT

### Failed-Breakdown Reclaim
| 区間 | n | 平均 | 中央値 | 勝率 |
|---|---:|---:|---:|---:|
| DEVELOPMENT | 5,252 | **-0.766%** | -0.832% | 41.09% |
| INTERNAL VALIDATION | 3,285 | +0.331% | -0.185% | 48.13% |

**判定:** REJECT / locked H2未開封

---

## 5. 本命候補の進捗

### Consensus V47
`█████████████░░░░░░░` **66%**

- **最新HEAD:** `70ca3ca4d04d9ea9bc864e3133163ffe5199ea96`
- **最新関連Action:** retry `34810592135`
- **16:26 JST確認:** run-level表示はqueuedだが、job-levelでは `fetch(0)` / `fetch(1)` が `Fetch raw 1H shard` でin_progress、残り10 shardは意図した `max-parallel: 2` によりqueued
- ✅ PIT universe / Daily PIT coverage PASS
- ✅ split evidence 3,700 / 3,700
- ❌ 初回raw 1H frozen acceptance
- ⏳ targeted retry = **active acquisition**
- 🔒 clean features / DEV H1 / H2 / 2026 selection = **未開封**
- **NOCAP vs CAP1000_PIT:** raw acceptance前、performance比較未開始

**blocker:** retry完了後のfrozen raw acceptance。候補ランキングは1位維持。

### V20 Session-Impulse
`███████████░░░░░░░░░` **55%**

- **最新HEAD:** `480bc9b5b62270f13f7e7de0accda008e6757bf9`
- ✅ spec/evaluator/contract freeze
- ✅ 1,810 symbols / 82 sessions freeze
- ❌ exact raw acceptance
- ⏳ **734 missing symbol/date**（476 predecessor identity/HTTP404、258 query success/0 rows）
- 🔒 H1 / H2 / 2026 report = **未開封**
- **次:** V47 retry artifactがfrozen acceptance PASSした場合のみ734件を監査・修復し、V20 verifierを変更せず再実行。

### OSS / Validation
`█████████████░░░░░░░` **65%**

- **最新HEAD:** `0837d299eff60698d0e2ec36c659a36bbc078542`
- ✅ purged/embargoed CV audit layer
- ✅ PSR / DSR multiple-trial sensitivity
- ✅ Optuna discovery period fail-closed contract
- ✅ EDINET real-sample selector preregistration
- ✅ full-calendar metadata snapshot/hash-chain validator
- ✅ official EDINET v2 acquisition helper + resume/fail-closed contract
- ✅ acquisition CI `34816055006` = **SUCCESS**
- 🔒 real 2023-2025 metadata bytes = 未取得
- 🔒 selected real doc IDs = 未固定
- 🔒 same-ZIP custom vs edinet-tools comparison = 未開封
- 🔒 strategy outcomes = 未開封

---

## 6. 現在の残タスク — 24 open

### P0 — 最優先（5）
- [ ] Consensus retry `34810592135` を完了まで監視（重複起動禁止）
- [ ] V47 frozen raw coverage verifier 再実行
- [ ] PASSなら clean features materialize
- [ ] V47 DEV H1で NOCAP vs CAP1000_PIT 比較
- [ ] DEV winnerだけH2を開く

### P1 — V20（5）
- [ ] accepted V47 raw artifactをV20修復ソースとして監査
- [ ] exact 734 gapだけ修復
- [ ] V20 raw verifier再実行
- [ ] PASSならH1評価
- [ ] H1 PASS policyだけH2へ

### P1 — Cloud Monster exact forensic（4）
- [ ] exact-match reconstruction specを凍結
- [ ] 元期間で n=63 / +9.86% を完全再現
- [ ] 完全再現できた場合のみ未使用期間へ無調整横展開
- [ ] portabilityを期間別統計・tail・Top1/Top3除外・月週依存で判定

### P2 — OSS / Validation（6）
- [ ] external API keyで2023-2025全calendar day raw JSONを取得
- [ ] `edinet_metadata_snapshot.py` でper-day SHA256 + hash-chain freeze
- [ ] selected doc IDs freeze
- [ ] ZIP hash freeze
- [ ] custom parser vs edinet-tools same-ZIP比較
- [ ] Purged CV / PSR / DSRをpromotion評価へ接続

### 最終（4）
- [ ] V47 / V20 / reproducible Cloud / benchmarkを同じ比較表へ
- [ ] performance + robustness + availability比較
- [ ] GO / NO-GO
- [ ] 本番移行はユーザー明示承認後のみ

---

## 7. ブロッカー

1. **Consensus V47 raw 1H:** retry `34810592135` は16:26 JST時点で2 shard取得中・10 queued。acceptance前。
2. **V20 raw 1H:** 734 symbol/date不足。
3. **Core replacement:** 現在の正式候補はすべてREJECT。
4. **旧Cloud Monster:** 歴史値 n=63/+9.86% はあるが、完全一致実装の復元→元期間完全再現→未使用期間portabilityが未完。
5. **EDINET:** acquisition/snapshot/selector境界はCI-greenだが、2023-2025実raw metadata取得とsame-ZIP parser comparisonは未実行。

---

## 8. 自動更新ルール

各lane workerは終了時に最終更新時刻、5 worker状態、進捗率、HEAD、Actions、raw acceptance、H1/H2開封状態、Cloud exact forensic段階、blocker、次アクション、候補ランキング影響を更新する。正式バックテストが新規に開封された場合のみ期間・n・平均・中央値・勝率・+10/+20/+50・-10/-20・Top1/Top3除外・endpoint/costを可能な範囲で追記する。

**成績をまだ開けてはいけない候補は「未開封」と表示し、推測値を載せない。**
