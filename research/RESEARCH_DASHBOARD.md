# TV-Free スコアリングBot研究ダッシュボード

> **最終更新基準:** 2026-09-14 18:12 JST  
> **更新元:** coordination STATE + active research branch HEADs + Phase-2 fresh validation  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpointは next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| Phase-2 | **2022 fresh validationを開封。弱点確認のためNO-GO / root-cause auditへ** |
| 2023-25暫定首位 | **DUAL_TOP1_AGREEMENT**、勝率改善候補 **G3 NO_ACUTE_SELLOFF** |
| Consensus V47 | clean Daily PIT PASS / formal raw retry中 / midterm diagnostic実行中 |
| V20 | cost0 coverage-bypassed診断が全TopN負、DEPRIORITIZE |
| Cloud exact forensic | **HISTORICAL_EXACT_REPRO_UNAVAILABLE**。歴史値n=63/+9.86%は再現値ではない |
| OSS / EDINET | selected-ZIP exact-byte freezeまでCI固定、real EDINETは外部key待ち |
| 最終判定 | **NO-GO / 研究継続** |

---

## 1. Weak+Early Phase-2

### Frozen 2023-2025 results — cost 0%

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% |
| volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% |
| mean-rank(volr20, body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% |
| **DUAL_TOP1_AGREEMENT** | **140** | **+7.17%** | **+1.25%** | **52.14%** | **+4.79%** |
| **DUAL + G3 NO_ACUTE_SELLOFF** | **117** | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** |

G3は `med_ret1 >= -1%`。この閾値は2025開封前にfreeze済みで、結果を見た後のretuneは禁止。

### 2022 fresh validation — OPENED / FAILED ROBUSTNESS

Exact sourceを復元できたためfallback Round2へは進まず、条件無変更でfresh validationを実施した。

- source: frozen run-80 preserved artifact `10264205130`
- source run: `34545440155`
- raw date range: 2022-01-04 -> 2026-09-11
- 2022 raw rows: **825,735**
- same V7/V9 full-45-feature monthly causal Tail generator
- existing minimum training history `>=30,000` を維持
- 2022 Jan-Mayはhistory不足でNO MODEL、first computable month = June
- June-Dec extreme Tail pool = **89 rows**
- frozen weak+early gate後 = **29 rows / 23 signal dates**

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 23 | +1.77% | -6.37% | 26.09% | -7.51% |
| volr20 LOW | 23 | +1.95% | -6.19% | 26.09% | -7.31% |
| mean-rank | 23 | +1.73% | -6.37% | 26.09% | -7.56% |
| DUAL_TOP1_AGREEMENT | 21 | +2.62% | -6.19% | 28.57% | -7.55% |
| **DUAL + G3** | **17** | **+6.08%** | **-6.00%** | **29.41%** | **-6.26%** |

**Fresh-validation decision:** FAIL ROBUSTNESS。平均プラスは大当たり依存で、中央値・勝率・Top3-exは全候補で弱い。2022を見て `ret10`、`med_ret5`、G3 -1%、Tail gate、ranker weightを調整しない。

### Descriptive 2022 computable block + 2023-2025

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 195 | +5.98% | -0.39% | 47.69% | +4.20% |
| volr20 LOW | 195 | +5.81% | 0.00% | 48.72% | +4.03% |
| mean-rank | 195 | +6.28% | 0.00% | 49.23% | +4.51% |
| DUAL_TOP1_AGREEMENT | 161 | +6.57% | 0.00% | 49.07% | +4.43% |
| **DUAL + G3** | **134** | **+7.74%** | **+1.06%** | **50.75%** | **+5.17%** |

G3はdescriptive aggregateでは最上位だが、fresh 2022 win 29.41%のためproduction候補へpromotionしない。

詳細: `research/WEAK_EARLY_PHASE2_2022_FRESH_VALIDATION_20260914.md`

### Phase-2 next action

**追加の勝率ゲート探索を一旦停止。** まず2022と2023-25の差をoutcome-blindに監査する。優先対象は model warm-up、candidate population、market regime availability。2022の損失を見て新閾値を作らない。新しいgate familyを試す場合は監査後に別途preregisterする。

---

## 2. Active lane status

| Lane | HEAD / state | Status | Next |
|---|---|---|---|
| Canonical/Event | `480bc9b5...` | V20 DEPRIORITIZE | V47 accepted rawが自然に得られた場合だけ734 gap repair |
| Core/Cloud | `da67fe92...` | Core families REJECT / Cloud exact replay unavailable | 新しい同時代identity evidenceが出た場合だけ再開 |
| Consensus V47 | `8a461bf9...` | raw retry + midterm diagnostic ACTIVE | run完了後、cost0 diagnosticを回収。重複trigger禁止 |
| OSS/Validation | `faba5b48...` | CI-green through selected-ZIP exact-byte freeze | key利用可能時にreal EDINET acquisition |

---

## 3. Cloud exact forensic

新しいCore/Cloud HEAD `da67fe92e493504842babac108df8f2be45c2658` を回収済み。

- historical headline: n=63 / 5BD mean +9.86% / median +3.33% / win 57.1%
- exact-match contractをfreeze
- broad reconstruction: 696 rows
- original A timestamps: 62/63のみ復元
- identity-critical model / exact 575 Watch pool / transforms / training-calibration detailsが不足
- disposition: **HISTORICAL_EXACT_REPRO_UNAVAILABLE**
- model-family guessing禁止
- exact reproduction未成立なのでunused-period portabilityは実行しない

歴史値を現行候補ランキングのpromotion evidenceとして扱わない。

---

## 4. Consensus V47

- latest processed HEAD: `8a461bf987453422e705a08024c0f1a462068801`
- Daily PIT acceptance: PASS
- formal raw initial acceptance: FAIL (0 usable pair)
- targeted retry: `34810592135` active
- midterm diagnostic: `34824194221` **in progress** as of this scan
- preserved partial seed coverage: NOCAP 35.3898%, CAP1000_PIT 83.1124%, restored pair 0%
- performanceはまだ未出力。出るまで候補順位を推測しない
- diagnosticはcost0、missing補間なし、正式promotion evidenceとは分離

---

## 5. V20 cost0 midterm diagnostic

Coverage caveat: 1,810 symbols / 82 sessionsのうち734 active symbol/date gaps。coverage gateだけbypassし、補間・synthetic bars・threshold/ranker/TopN/cooldown変更なし。

| TopN | n | Mean | Median | Win | Top3-ex |
|---:|---:|---:|---:|---:|---:|
| 1 | 156 | -1.346% | -2.627% | 35.90% | -2.669% |
| 2 | 307 | -1.573% | -1.294% | 40.07% | -2.241% |
| 3 | 442 | -1.118% | -1.289% | 40.05% | -1.613% |
| 5 | 705 | -0.538% | -0.955% | 41.84% | -0.854% |

Disposition: **DEPRIORITIZE**。opened outcomeを見てretuneしない。

---

## 6. OSS / Validation

- HEAD `faba5b48f1831b16f08c74895f772ca0089f765c`
- purged/embargoed CV audit: ready
- PSR/DSR multiple-trial sensitivity: ready
- Optuna Discovery期間外 fail-closed + trial retention: ready
- EDINET metadata snapshot / deterministic selector: ready
- selected real-doc ZIP exact-byte freeze boundary: CI-green (`34819456421`)
- blocker: external `EDINET_API_KEY` for real acquisition

---

## 7. Current P0 / P1

### P0
- [x] 2022 frozen sourceを復元
- [x] same causal V7 generatorで2022 cacheを再構築
- [x] frozen Phase-2 5候補を無調整fresh validation
- [x] 2022 fresh blockのrobustness failureを記録
- [ ] **2022 vs 2023-25 outcome-blind structural audit**
- [ ] V47 diagnostic `34824194221` 完了時に結果回収
- [ ] V47 formal retry `34810592135` 完了監視

### P1
- [ ] structural audit後にのみ、必要なら新regime familyを事前登録
- [ ] 2022 observed lossesを使ったthreshold grid searchは禁止
- [ ] Cloud exact forensicは新しいidentity evidenceが無い限りclosed

---

## 8. GO / NO-GO

**NO-GO / 研究継続。**

2023-25ではWeak+Early + DUAL/G3が高い平均と右裾を維持する一方、fresh 2022 computable blockで勝率・中央値・tail-exclusion robustnessが崩れた。現段階では「平均+7%台」を理由にproductionへ進めない。次は勝率を後付けで上げるのではなく、期間差の構造原因を先に監査する。
