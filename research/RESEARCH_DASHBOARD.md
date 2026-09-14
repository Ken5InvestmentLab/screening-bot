# TV-Free スコアリングBot研究ダッシュボード

> **最終更新基準:** 2026-09-14 16:08 JST  
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
| 最大の歴史的参考値 | **旧Cloud Monster: n=63 / 5BD平均 +9.86%（forensic上は現行候補に非該当）** |
| 最終判定 | **NO-GO / 研究継続** |

### 全体進捗
`███████████░░░░░░░░░` **約56%**

- 基盤・評価契約・リーク防止: かなり完了
- 本命候補のrawデータ受入: 未完
- 本命候補H1/H2評価: 未開封
- EDINETは実データ取得前のacquisition/snapshot/selector境界までCI固定済み
- 最終比較 / GO-NO-GO: 未実施

---

## 1. レーン別ステータス

| レーン | 状態 | 目安進捗 | 現在地 | 次アクション |
|---|---:|---:|---|---|
| **Consensus V47** | 🟡 本命 / RAW RETRY ACTIVE | **66%** | Daily PIT PASS、初回raw acceptance FAIL、hardened retryで2 shardが実取得中 | retry `34810592135` 完了後、同じfrozen verifierを再実行 |
| **V20 Session-Impulse** | 🟡 本命 / COVERAGE BLOCKED | **55%** | 1,810銘柄×82セッション凍結済み、734 symbol/date不足 | V47でaccepted rawができたら734件だけ監査・修復 |
| **Core** | 🔴 現候補REJECT | **評価自体は90%** | Fixed Core等を正式評価し棄却 | 新しい独立機構が無い限りcoordination/consumerのみ |
| **OSS / Validation** | 🟢 基盤進行 | **65%** | Purged/DSR/Optuna + EDINET acquisition/snapshot/selector境界をCI固定 | 2023-2025 raw metadata取得→snapshot hash freeze→同一ZIP比較 |
| **Shadow / Data Integrity** | 🟢 基盤 | **80%** | calendar/integrity/immutable receipt CI成功 | real shadow launchは未承認 |

---

## 2. 有望候補ランキング

| 順位 | 条件 / family | 判定 | バックテスト | コメント |
|---:|---|---|---|---|
| **1** | **Consensus V47 — NOCAP / CAP1000_PIT** | 🟡 未評価 | **未開封** | 最もクリーンなPIT pipeline。raw retry実行中 |
| **2** | **V20 Session-Impulse Continuation** | 🟡 未評価 | **未開封** | 4H/intraday主軸のEvent/Monster候補。734欠損が blocker |
| **3** | **旧Cloud Monster** | 🟠 Historical / Forensic only | **n=63 / 平均 +9.86%（歴史値）** | 完全再現性を確認できず、現行promotion候補ではない |
| 4 | Canonical Monster v2 | 🔴 REJECT | 2025 locked 平均 **+2.19%** | frozen 0.5% cost Top1-winner-excluded mean **-0.21%**で棄却 |
| 5 | Fixed Core | 🔴 REJECT | DEV +0.712% / 2025H2 **-0.452%** | 2025H2中央値 -0.745%、勝率41.43% |
| 6 | Failed-Breakdown Reclaim | 🔴 REJECT | DEV **-0.766%** / Internal +0.331% | median/win rateがgate未達 |
| 7 | Prior-Close Reclaim | 🔴 REJECT | DEVELOPMENT gate FAIL | H2未開封 |
| 8 | Precision 3-family | 🔴 REJECT | DEVELOPMENTで全family負 | 隣接retune禁止 |

---

## 3. 既知バックテスト結果

### 旧Cloud Monster
**歴史的ヘッドライン**
- n = **63**
- 5BD平均 = **+9.86%**
- 現在の扱い = **historical signal / forensic only / 現行promotion候補ではない**
- 近縁条件 / surrogate の結果を「完全再現」とは扱わない

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

## 4. 本命候補の進捗

### Consensus V47
`█████████████░░░░░░░` **66%**

- **最新HEAD:** `70ca3ca4d04d9ea9bc864e3133163ffe5199ea96`
- **最新関連Action:** retry `34810592135`
- **Action実体:** run-level表示はqueuedだが、job-levelでは `fetch(0)` / `fetch(1)` が `Fetch raw 1H shard` でin_progress、残り10 shardは意図した `max-parallel: 2` によりqueued
- ✅ PIT universe
- ✅ split evidence 3,700 / 3,700
- ✅ Daily PIT coverage = PASS
- ✅ NOCAP / CAP1000_PIT の2armに固定
- ✅ rate-limit/backoff contract CI
- ❌ 初回raw 1H frozen acceptance
- ⏳ missing-universe targeted retry `34810592135` = **active acquisition**
- 🔒 clean features = 未開封
- 🔒 DEV H1 performance = 未開封
- 🔒 H2 performance = 未開封
- 🔒 2026 selection outcome = 未開封
- **NOCAP vs CAP1000_PIT比較段階:** raw acceptance前、performance比較未開始

**Daily acceptance:** PASS (`34799835035`)  
**直近formal raw acceptance:** FAIL (`34810234454`) — `raw_unique_symbol_dates=0`、両arm pair coverage=0%。  
**targeted retry:** ACTIVE (`34810592135`)。日足artifact取得・daily gate verification・fetcher contractはactive shardで通過済み。  
**blocker:** retry完了後のfrozen raw acceptance。  
**候補ランキングへの影響:** 1位維持。ただしraw acceptance PASSまでは成績評価・promotion判断を一切行わない。

### V20 Session-Impulse
`███████████░░░░░░░░░` **55%**

- ✅ spec freeze
- ✅ evaluator / contract test
- ✅ 1,810 symbols / 82 sessions freeze
- ✅ raw gap診断
- ❌ exact raw acceptance
- ⏳ 734 missing symbol/date
  - 476 = predecessor identity / HTTP 404
  - 258 = successful queryだが0 rows
- 🔒 H1
- 🔒 H2
- 🔒 2026 report

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

## 5. 現在の残タスク

### P0 — 最優先
- [ ] Consensus retry `34810592135` を完了まで監視（重複起動禁止）
- [ ] V47 frozen raw coverage verifier 再実行
- [ ] PASSなら clean features materialize
- [ ] V47 DEV H1で NOCAP vs CAP1000_PIT 比較
- [ ] DEV winnerだけH2を開く

### P1 — V20
- [ ] accepted V47 raw artifactをV20修復ソースとして監査
- [ ] exact 734 gapだけ修復
- [ ] V20 raw verifier再実行
- [ ] PASSならH1評価
- [ ] H1 PASS policyだけH2へ

### P2 — OSS / Validation
- [x] EDINET metadata acquisition helper / fail-closed CI
- [ ] external API keyで2023-2025全calendar day raw JSONを取得
- [ ] `edinet_metadata_snapshot.py` でper-day SHA256 + hash-chain freeze
- [ ] selected doc IDs freeze
- [ ] ZIP hash freeze
- [ ] custom parser vs edinet-tools same-ZIP比較
- [ ] Purged CV / PSR / DSRをpromotion評価へ接続

### 最終
- [ ] V47 / V20 / benchmarkを同じ比較表へ
- [ ] performance + robustness + availability比較
- [ ] GO / NO-GO
- [ ] 本番移行はユーザー明示承認後のみ

---

## 6. ブロッカー

1. **Consensus V47 raw 1H**
   - Dailyはクリーン。
   - 初回formal raw acceptanceは0%でFAIL。
   - hardened targeted retry `34810592135` は現在2 shard実取得中、10 shard待機中。
   - 完了後に同じfrozen verifierを通すまでfeatures/performanceは開かない。
2. **V20 raw 1H**
   - 734 symbol/date不足。
3. **Core**
   - 現在の正式候補はすべてREJECT。
4. **旧Cloud Monster**
   - 歴史値+9.86%は再現性不足のためcurrent promotion candidateではない。
5. **EDINET**
   - acquisition/snapshot/selector境界はCI-greenだが、2023-2025実raw metadata取得とsame-ZIP parser comparisonは未実行。

---

## 7. 自動更新ルール

このダッシュボードはSupervisor/各lane workerが以下を最新STATE/各laneから再計算して更新する。

- 最終更新時刻
- レーン数 / 状態
- マイルストーン型進捗率
- Active / Blocked / Rejected / Passed
- 候補ランキング
- 最新HEAD
- 最新Actions run ID / status
- Daily/raw acceptance
- targeted retry
- clean features / H1 / H2開封状態
- NOCAP / CAP1000_PIT比較段階
- バックテスト結果
- 残タスク
- ブロッカー
- 次アクション
- 候補ランキングへの影響
- 最終GO/NO-GO

**成績をまだ開けてはいけない候補は「未開封」と表示し、推測値を載せない。**
