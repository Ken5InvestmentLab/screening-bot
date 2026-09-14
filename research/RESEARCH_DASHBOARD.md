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
- n = **63**
- 5BD平均 = **+9.86%**
- 現在の扱い = **historical signal / forensic only / 現行promotion候補ではない**

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
- **16:26 JST確認:** run-levelはqueuedのまま。job-levelは `fetch(0)` / `fetch(1)` が `Fetch raw 1H shard` でin_progress、残り10 shardは `max-parallel: 2` によりqueued。状態変化なし。
- ✅ PIT universe / Daily PIT coverage PASS
- ❌ 初回raw 1H frozen acceptance
- ⏳ targeted retry = **active acquisition**
- 🔒 clean features / DEV H1 / H2 / 2026 selection = **未開封**

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

### Shadow / Data Integrity
`████████████████░░░░` **80%**

- **最新HEAD:** `25b0ae42b0e3a8de80599405ae1bee235d4b3e28`
- resolution continuity `34795293067` SUCCESS
- XTKS calendar guard `34795620704` SUCCESS
- immutable resolution receipt `34799006401` SUCCESS
- real shadow launch = **未承認**

---

## 5. 現在の残タスク

- Consensus retry `34810592135` を重複起動せず完了まで監視し、完了後に同一frozen raw coverage verifierを再実行。
- PASS時のみclean features→DEV H1→winner H2。V20はaccepted rawを使ってexact 734 gapだけ監査・修復。
- V20 H1 Top1/2/3/5 frozen gateは変更しない。全FAILならH2未開封REJECT、PASS policyのみH2へ。
- Shadow/Dataはappend-only/integrity/staleness/temporal guardのみ。production/main、本番系は変更しない。

---

## 6. ブロッカー

1. **Consensus V47 raw 1H:** retry `34810592135` は16:26 JST時点でも2 shard取得中・10 queued。acceptance前。
2. **V20 raw 1H:** 734 symbol/date不足。
3. **V20 performance:** raw acceptance未達のためH1/H2とも未開封。
4. **Shadow:** integrity CIはgreenだがreal launch未承認。

---

## 7. 自動更新ルール

各lane workerは終了時に最終更新時刻、進捗率、HEAD、Actions、raw acceptance、H1/H2開封状態、blocker、次アクション、候補ランキング影響を更新する。正式バックテストが新規に開封された場合のみ期間・n・平均・中央値・勝率・+10/+20/+50・-10/-20・Top1/Top3除外・endpoint/costを可能な範囲で追記する。

**成績をまだ開けてはいけない候補は「未開封」と表示し、推測値を載せない。**
