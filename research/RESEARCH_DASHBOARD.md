# TV-Free スコアリングBot研究ダッシュボード

> **最終更新基準:** 2026-09-14 14:59 JST  
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
| 最大の歴史的参考値 | **旧Cloud Monster: n=63 / 5BD平均 +9.86%（完全再現性を再検証中）** |
| 最終判定 | **NO-GO / 研究継続** |

### 全体進捗
`███████████░░░░░░░░░` **約55%**

- 基盤・評価契約・リーク防止: かなり完了
- 本命候補のrawデータ受入: 未完
- 本命候補H1/H2評価: 未開封
- 最終比較 / GO-NO-GO: 未実施

---

## 1. レーン別ステータス

| レーン | 状態 | 目安進捗 | 現在地 | 次アクション |
|---|---:|---:|---|---|
| **Consensus V47** | 🟡 本命 / DATA BLOCKED | **65%** | Daily PITはPASS、raw 1H acceptanceはFAIL | retry `34810592135` 完了後、同じfrozen verifierを再実行 |
| **V20 Session-Impulse** | 🟡 本命 / COVERAGE BLOCKED | **55%** | 1,810銘柄×82セッション凍結済み、734 symbol/date不足 | V47でaccepted rawができたら734件だけ監査・修復 |
| **Core** | 🔴 現候補REJECT | **評価自体は90%** | Fixed Core等を正式評価し棄却 | 旧Cloud Monster完全一致再現性のforensicを優先 |
| **OSS / Validation** | 🟢 基盤進行 | **60%** | Purged/DSR/Optuna/EDINET provenance整備 | 2023-2025 metadata凍結→同一ZIP比較 |
| **Shadow / Data Integrity** | 🟢 基盤 | **80%** | calendar/integrity/immutable receipt CI成功 | real shadow launchは未承認 |

---

## 2. 有望候補ランキング

| 順位 | 条件 / family | 判定 | バックテスト | コメント |
|---:|---|---|---|---|
| **1** | **Consensus V47 — NOCAP / CAP1000_PIT** | 🟡 未評価 | **未開封** | 最もクリーンなPIT pipeline。raw coverage PASS待ち |
| **2** | **V20 Session-Impulse Continuation** | 🟡 未評価 | **未開封** | 4H/intraday主軸のEvent/Monster候補。734欠損が blocker |
| **3** | **旧Cloud Monster 完全一致復元** | 🟠 Forensic | **n=63 / 平均 +9.86%（歴史値）** | 元期間で完全再現→無調整で別期間検証する作業を開始 |
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
- 現在の扱い = **完全一致条件の復元・横展開を再検証中**
- 近縁条件 / surrogate の結果を「完全再現」とは扱わない

**これから確認すること**
1. 当時の実装・設定・スコアリングを復元
2. 元期間で n=63 / +9.86% を再現
3. 再現できた場合のみ条件固定
4. 未使用の別期間へ無調整で横展開
5. n / 平均 / 中央値 / 勝率 / +10/+20/+50 / -10/-20 / Top1・Top3除外 / 月週依存を比較

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
`█████████████░░░░░░░` **65%**

- ✅ PIT universe
- ✅ split evidence 3,700 / 3,700
- ✅ Daily PIT coverage = PASS
- ✅ NOCAP / CAP1000_PIT の2armに固定
- ✅ rate-limit/backoff contract CI
- ❌ raw 1H frozen acceptance
- ⏳ missing-universe retry `34810592135`
- 🔒 features
- 🔒 H1 performance
- 🔒 H2 performance
- 🔒 2026 report

**現在の失敗証拠:** formal acceptance `34810234454` で raw_unique_symbol_dates=0、両arm pair coverage=0%。

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

---

## 5. 現在の残タスク

### P0 — 最優先
- [ ] Consensus retry `34810592135` を回収
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

### P1 — Cloud Monster forensic
- [ ] 元のn=63/+9.86%の完全一致specを確定
- [ ] 元期間で完全再現
- [ ] 無調整で別期間へ横展開
- [ ] portability判定

### P2 — OSS / Validation
- [ ] 2023-2025 EDINET metadata full snapshot
- [ ] selected doc IDs freeze
- [ ] ZIP hash freeze
- [ ] custom parser vs edinet-tools same-ZIP比較
- [ ] Purged CV / PSR / DSRをpromotion評価へ接続

### 最終
- [ ] V47 / V20 / 再現Cloud / benchmarkを同じ比較表へ
- [ ] performance + robustness + availability比較
- [ ] GO / NO-GO
- [ ] 本番移行はユーザー明示承認後のみ

---

## 6. ブロッカー

1. **Consensus V47 raw 1H**
   - Dailyはクリーンだがraw 1H acceptanceがまだFAIL。
2. **V20 raw 1H**
   - 734 symbol/date不足。
3. **Core**
   - 現在の正式候補はすべてREJECT。
4. **旧Cloud Monster**
   - +9.86%の完全一致ロジックがまだ復元確定していない。
5. **EDINET**
   - 実historical same-ZIP parser comparison前。

---

## 7. 自動更新ルール

このダッシュボードはSupervisorが以下を最新STATE/各laneから再計算して更新する。

- レーン数 / 状態
- マイルストーン型進捗率
- Active / Blocked / Rejected / Passed
- 候補ランキング
- バックテスト結果
- H1/H2開封状況
- Actions run ID / 状態
- 残タスク
- ブロッカー
- 次アクション
- 最終GO/NO-GO

**成績をまだ開けてはいけない候補は「未開封」と表示し、推測値を載せない。**
