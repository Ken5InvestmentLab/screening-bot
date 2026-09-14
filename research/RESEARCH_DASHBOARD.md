# TV-Free スコアリングBot研究ダッシュボード

> **最終更新基準:** 2026-09-14 17:45 JST  
> **更新元:** `research/AUTOMATION_COORDINATION_STATE.json` + active lane handoff / Actions + `research/MIDTERM_COMPARISON_20260914.md`  
> **注意:** 進捗率は成功確率ではなく研究マイルストーン消化率。診断開封と正式promotion evidenceは分離する。**今後の全バックテスト・診断・比較・ランキングは取引コスト0%で統一**。既存0.5%/1%結果はlegacy audit evidenceのみで、新しい順位・判定には使わない。

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **まだ0件** |
| Active research branches | **4本** |
| 現在のPhase-2暫定首位 | **DUAL_TOP1_AGREEMENT（body_pct Top1 = volr20 Top1の日だけ採用）** |
| 正式promotion evidenceでGO可能な候補 | **0件** |
| V47 | **clean Daily PIT PASS / formal raw retry中 / partial-seed midterm diagnostic実行中** |
| V20 | **coverage-bypassed診断をcost 0%で開封、全TopN負でDEPRIORITIZE** |
| 旧Cloud Monster | **歴史値 n=63 / 5BD平均 +9.86%**。exact-repro forensicとは別扱い |
| OSS / EDINET | **metadata→selector→selected-ZIP exact-byte freezeまでCI固定** |
| 最終判定 | **NO-GO / 研究継続** |

### 全体進捗
`████████████░░░░░░░░` **約59%**

- 評価契約・リーク防止・監査基盤: 高進捗
- 有力な実観測条件: あり。ただし正式promotion evidenceへの統一評価が未完
- V47 raw正式受入: 未完
- V47中締め診断: pre-open contract/hash/coverage凍結済み、run `34824194221` 実行中
- EDINET real same-ZIP比較: 未実施
- 最終比較 / GO-NO-GO: 未実施

---

## 1. 重要な方針変更と開封状態

ユーザー明示承認により、未開封H1/H2/outcomeを**中締め診断目的では開封可**とする。開封済み期間は以後 untouched holdout と扱わず、診断値を見て同familyをretuneしない。正式promotion判定と `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` は分離する。

| 対象 | 診断開封 | 正式promotion evidence | 備考 |
|---|---|---|---|
| weak+early body_pct / volr20系 | ✅ row-level再計算済み | ❌ 未統一 | canonical endpoint / **cost 0%**で統一評価済み |
| V20 Session-Impulse | ✅ coverage-bypassed診断開封 | ❌ 不可 | 734 gapを残した診断。全TopN負、DEPRIORITIZE |
| Consensus V47 | ⏳ **診断run実行中、performance未出力** | ❌ raw acceptance未達 | pre-open spec/hash/coverage凍結済み。partial immutable seedのみ、欠損補間なし |
| Cloud exact forensic | 歴史値のみ既知 | ❌ | exact reproductionが先。歴史値を再現結果と混同しない |

Consensus V47については、run `34824194221` がH1 performanceを実際に出力した時点でH1を `OPENED_NOT_UNTOUCHED` と記録する。それまではperformance未開封。H2は引き続き未開封。

---

## 2. 暫定ランキング — 実観測performance

### 1位 DUAL_TOP1_AGREEMENT — Phase-2 primary challenger
- 定義: weak+early候補群で **body_pct ascending Top1 と volr20 ascending Top1 が同一symbolの日だけ採用**。不一致日はNO TRADE。
- 2023-2024: **n=103 / mean +6.88% / median +1.39% / win 53.40% / Top3-ex +3.86%**
- 2025: **n=37 / mean +7.97% / median -2.40% / win 48.65% / Top3-ex -0.06%**
- 2023-2025 total: **n=140 / mean +7.17% / median +1.25% / win 52.14% / Top3-ex +4.79%**
- cost **0%**
- **Disposition:** PHASE-2 PRIMARY CHALLENGER。平均は現基盤3条件を上回るが、2023H2/2025H2のregime弱点は残る。

### 2位 weak+early + mean-rank(volr20, body_pct)
- 2023-2025 total: **n=172 / mean +6.89% / median +1.45% / win 52.33% / Top3-ex +4.95%**
- cost **0%**
- **Disposition:** BASELINE LEADER

### 3位 weak+early + body_pct LOW
- 2023-2025 total: **n=172 / mean +6.54% / median +0.99% / win 50.58% / Top3-ex +4.60%**
- cost **0%**
- **Disposition:** RIGHT-TAIL BASELINE

### 4位 weak+early + volr20 LOW
- 2023-2025 total: **n=172 / mean +6.33% / median +1.06% / win 51.74% / Top3-ex +4.38%**
- cost **0%**
- **Disposition:** STABILITY COMPARATOR

### 共通弱点 / Phase-2方針
- 2023H2は全候補で弱い。
- 2025H2は平均プラスでも勝率/中央値が弱い。
- 次の主要課題はranker追加ではなく **causal market-regime / NO-TRADE判定**。
- 広いfeature/ranker探索は停止。
- `research/WEAK_EARLY_PHASE2_20260914.md` をfreeze basisにする。
- 可能なら **2022をfresh validation** として4候補を無調整で再評価。

**注意:** このランキングは中締め/Phase-2診断ランキングであり、production GO順位ではない。Consensus V47の診断値はまだ未出力なのでランキングへ未反映。

---

## 3. 正式promotion path / lane status

| レーン | 状態 | マイルストーン進捗 | 現在地 | 次アクション |
|---|---:|---:|---|---|
| **Consensus V47** | 🟡 RAW RETRY + MIDTERM DIAGNOSTIC ACTIVE | **69%** | Daily PIT PASS。初回raw acceptance FAIL。formal retry `34810592135` はfetch(0)/fetch(1)取得中・10 queued。preserved seed NOCAP 35.3898% / CAP1000_PIT 83.1124% / restored 0%。pre-open diagnostic spec/hash凍結済み、run `34824194221` 実行中 | diagnostic結果回収→cost0 H1 metrics記録（非promotion）。並行してformal retry完了→seedとprovenance付きmerge→frozen verifier |
| **V20 Session-Impulse** | 🟠 DEPRIORITIZE / COVERAGE BLOCKED | **55%** | 1,810 symbols / 82 sessions、734 gap。coverage bypass診断はcost 0%でも全TopN負 | formal repairはV47 accepted rawができた場合のみ。隣接retuneしない |
| **Core replacement** | 🔴 REJECT | **90%** | Fixed Core / reclaim / precision系を棄却 | closed。新規隣接heuristic探索停止 |
| **Cloud exact forensic** | 🟠 FORENSIC | **10%** | 歴史値 n=63/+9.86%のみ。exact spec未復元 | exact spec→元期間完全一致→成功時のみ未使用期間へ無調整展開 |
| **OSS / Validation** | 🟢 基盤進行 | **70%** | Purged/DSR/Optuna + EDINET metadata acquisition/snapshot/selector + selected-ZIP exact-byte freezeをCI固定 | external keyでreal metadata取得→snapshot→selector→ZIP freeze→same-ZIP parser比較 |
| **Shadow / Data Integrity** | 🟢 基盤 | **80%** | calendar/integrity/immutable receipt CI成功 | real shadow launchは未承認 |

### Consensus V47 詳細
- **最新HEAD:** `8a461bf987453422e705a08024c0f1a462068801`
- **Daily acceptance:** PASS — authoritative external daily run `34799835035`
- **Formal raw acceptance:** FAIL — acceptance run `34810234454`、初回V47 rawは0 usable pair
- **Formal targeted retry:** `34810592135` active。重複trigger禁止
- **Midterm diagnostic pre-open spec:** `research/CONSENSUS_V47_MIDTERM_DIAGNOSTIC_SPEC_20260914.json`
- **Midterm diagnostic run:** `34824194221` in progress
- **Diagnostic raw source:** preserved immutable Yahoo seed run `34592896202`
- **Coverage caveat:** NOCAP 301,897/853,061 = **35.3898%**、CAP1000_PIT 258,339/310,831 = **83.1124%**、restored pair **0%**。missingはそのまま欠損、補間・synthetic barなし
- **Features:** diagnostic run内でpartial PIT features materialization待ち
- **H1:** performance **未出力**。出力されたらH1は `OPENED_NOT_UNTOUCHED`
- **H2:** **未開封**
- **2026:** selection用途 **未開封**
- **NOCAP vs CAP1000_PIT比較:** **実行中 / performance未開封**
- **cost:** **0%のみ**。win = gross canonical return > 0
- **endpoint:** next official XTKS open -> D+5 close
- **候補ランキングへの影響:** まだなし。正式値/診断値が出るまで推測しない

---

## 4. V20中締め診断 — `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`

- period: frozen H1 diagnostic period represented by existing repaired raw artifact / 2026は不使用
- endpoint: **next XTKS open -> fifth XTKS close**
- cost: **0%**
- coverage caveat: frozen universe **1,810 symbols / 82 sessions**のうち **734 active symbol/date gaps** を欠損のまま残し、coverage gateだけをbypass。補間・synthetic bars・閾値低下・条件変更なし。
- raw source: repaired artifact id `10327932766` from run `34791959735`; canonical daily artifact id `10264205130` from run `34599959356`。

| TopN | n | mean | median | win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Top1 | 156 | **-1.346%** | -2.627% | 35.90% | 14.74% | 7.69% | 2.56% | 24.36% | 10.26% | -1.860% | -2.669% |
| Top2 | 307 | **-1.573%** | -1.294% | 40.07% | 11.40% | 4.89% | 1.30% | 19.87% | 8.14% | -1.834% | -2.241% |
| Top3 | 442 | **-1.118%** | -1.289% | 40.05% | 11.54% | 3.85% | 1.13% | 17.19% | 5.88% | -1.298% | -1.613% |
| Top5 | 705 | **-0.538%** | -0.955% | 41.84% | 10.07% | 3.55% | 1.13% | 14.33% | 3.97% | -0.650% | -0.854% |

**判定:** **DEPRIORITIZE**。missing coverageで厳密順位は変わり得るが、全TopNがcost 0%でも負。診断開封済み期間は今後 untouched holdout と呼ばず、この結果を見てV20のthreshold/TopN/ranker/cooldownをretuneしない。正式promotionには従来どおりexact raw acceptance PASSが必要。

---

## 5. 旧Cloud Monster — 歴史値とexact forensicを分離

### 歴史的ヘッドライン
- n = **63**
- 5BD平均 = **+9.86%**
- median +3.33%、win 57.1%、+20% 30.2%、Top5-ex +4.03%

### exact reproducibility forensic
1. 当時の実装・設定・score・学習/評価期間・selection・cooldown・endpoint・cost・確率帯を復元
2. exact-match specを凍結
3. 元期間で **n=63 / +9.86%** を完全一致再現
4. 成功した場合のみ条件無変更で未使用期間へ横展開
5. portabilityをn / mean / median / win / tails / Top1・Top3除外 / 月週依存で判定

**重要:** surrogateや近縁条件の好成績を「完全再現」と呼ばない。2026はreport-only。

---

## 6. OSS / Validation 詳細

- **最新HEAD:** `faba5b48f1831b16f08c74895f772ca0089f765c`
- ✅ purged/embargoed CV audit
- ✅ PSR / DSR multiple-trial sensitivity
- ✅ Optuna Discovery期間外fail-closed + trial retention
- ✅ EDINET real-sample preregistration / deterministic selector
- ✅ full-calendar metadata snapshot + SHA256/hash-chain validator
- ✅ official EDINET v2 resumable acquisition helper — CI `34816055006` SUCCESS
- ✅ selected real-doc ZIP exact-byte freeze helper + fail-closed tests — CI `34819456421` SUCCESS
- 🔒 real 2023-2025 metadata bytes = 未取得
- 🔒 selected real doc IDs = 未固定
- 🔒 selected real ZIP hashes = 未固定
- 🔒 custom vs edinet-tools real same-ZIP outputs = 未開封
- 🔒 strategy outcomes / 2026 outcomes = 未開封

**blocker:** real EDINET pathの実行には外部 `EDINET_API_KEY` が必要。キーが無い状態では実データを捏造せず、outcome-blind境界だけを先に固定済み。

---

## 7. Legacy reject evidence — 新しい順位・判定には不使用

以下は既存0.5% cost時代の監査記録であり、新規計算ではない。

### Fixed Core — canonical endpoint / legacy 0.5% cost
| 区間 | n | 平均 | 中央値 | 勝率 | Top3-ex |
|---|---:|---:|---:|---:|---:|
| DEV | 169 | +0.712% | +0.509% | 55.62% | +0.393% |
| 2025 H2 | 140 | **-0.452%** | -0.745% | 41.43% | -0.874% |

**既存判定:** REJECT

### Failed-Breakdown Reclaim — legacy evidence
| 区間 | n | 平均 | 中央値 | 勝率 |
|---|---:|---:|---:|---:|
| DEVELOPMENT | 5,252 | **-0.766%** | -0.832% | 41.09% |
| INTERNAL VALIDATION | 3,285 | +0.331% | -0.185% | 48.13% |

**既存判定:** REJECT / locked H2未開封

---

## 8. 残タスク

### P0
- [ ] Consensus formal retry `34810592135` 完了監視（重複起動禁止）
- [ ] **Consensus V47 midterm diagnostic `34824194221` 結果回収**。cost 0%、formal evidenceと分離、開封後retune禁止
- [ ] retry + preserved raw seedをprovenance付きmergeしてfrozen verifier再実行
- [ ] diagnostic成功時、NOCAP/CAP1000_PITの期間・n・平均・中央値・勝率・+10/+20/+50・-10/-20・Top1/Top3除外をcoverage caveat付きで追記
- [x] V47 midterm pre-open spec/hash/coverageをperformance前に凍結
- [x] body_pct LOW / volr20 LOW / combined rankをcanonical endpoint・cost 0%・row-level metricsで統一比較
- [x] V20 existing midterm diagnosticをcost 0%へ統一し、tails/Top1/Top3-ex/endpoint/coverage caveatを反映

### P1
- [ ] V47 accepted rawが得られた場合のみV20 exact 734 gap repair / verifier再実行
- [ ] Cloud exact-match reconstruction spec freeze
- [ ] Cloud元期間 n=63/+9.86% exact reproduction
- [ ] exact reproduction成功時のみ未使用期間へ無調整portability確認

### P2 — OSS
- [ ] external API keyで2023-2025全calendar day raw JSON取得
- [ ] metadata snapshot per-day SHA256 + hash-chain freeze
- [ ] preregistered selectorを1回だけ実行してdoc IDs freeze
- [ ] selected ZIPsをexact-byte freeze helperでSHA256固定
- [ ] custom parser vs edinet-toolsを同一ZIP bytesで比較
- [ ] Purged CV / PSR / DSRを将来の正式promotion評価へ接続

### 最終
- [ ] 実装可能候補を同一endpoint / cost / selection policyで比較
- [ ] performance + robustness + availability比較
- [ ] GO / NO-GO
- [ ] 本番移行はユーザー明示承認後のみ

---

## 9. 現在のブロッカー / next action

1. **V47 formal:** retry `34810592135` はfetch(0)/fetch(1)取得中、10 queued。重複起動しない。
2. **V47 diagnostic:** `34824194221` はpre-open contract確認/partial raw準備まで進行。performanceはまだ未出力。結果が出るまで候補順位を推測しない。
3. **V20:** 734 gap。cost 0%診断は負でDEPRIORITIZE、retuneしない。
4. **Cloud:** exact implementation未復元。歴史値はpromotion evidenceではない。
5. **EDINET:** external API keyが無いためreal acquisition未実行。ただしselected-ZIP byte identity boundaryまでCI-green。
6. **最優先の高情報量チェック:** V47 diagnostic結果回収 → V47 formal retry回収 → Cloud exact source evidence → EDINET real metadata acquisition（キー利用可能時）。

**GO/NO-GO:** **NO-GO / 研究継続**。広いblind explorationは停止し、上記high-information checksへ集中する。