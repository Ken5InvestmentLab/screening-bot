# TV-Free スコアリングBot研究ダッシュボード

> **最終更新基準:** 2026-09-14 18:38 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| Weak+Early Phase-2 | **2022 fresh validation FAILED ROBUSTNESS**。outcome-blind構造監査まで完了 |
| 2023-25暫定首位 | **DUAL_TOP1_AGREEMENT**、勝率改善候補 **G3 NO_ACUTE_SELLOFF** |
| Consensus V47 | formal raw retry `34810592135` は12-shard構成で180分timeout発生。現runは重複triggerせず継続監視。future retryは48-shardへ修復済み。midterm diagnostic `34824194221` はH1 cost0比較実行中 |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Core/Cloud forensic | Core既reject維持 / Cloud **HISTORICAL_EXACT_REPRO_UNAVAILABLE** |
| OSS / EDINET | selected-ZIP exact-byte freezeまでCI固定、real EDINETは外部key待ち |
| 最終判定 | **NO-GO / 研究継続** |

---

## 1. Weak+Early Phase-2

### Frozen 2023-2025 — cost 0%

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% |
| volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% |
| mean-rank | 172 | +6.89% | +1.45% | 52.33% | +4.95% |
| **DUAL_TOP1_AGREEMENT** | **140** | **+7.17%** | **+1.25%** | **52.14%** | **+4.79%** |
| **DUAL + G3** | **117** | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** |

G3 = `med_ret1 >= -1%`。freeze済みでretune禁止。

### 2022 fresh validation — exact preserved source

- preserved run-80 artifact: `10264205130`
- raw 2022 rows: **825,735**
- same V7/V9 full-45-feature monthly causal Tail generator
- existing `train >= 30,000` rule unchanged
- Jan-May: history不足でNO MODEL
- first computable month: June 2022
- June-Dec extreme Tail pool: **89 rows**
- frozen weak+early gate後: **29 rows / 23 signal dates**

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 23 | +1.77% | -6.37% | 26.09% | -7.51% |
| volr20 LOW | 23 | +1.95% | -6.19% | 26.09% | -7.31% |
| mean-rank | 23 | +1.73% | -6.37% | 26.09% | -7.56% |
| DUAL_TOP1 | 21 | +2.62% | -6.19% | 28.57% | -7.55% |
| **DUAL + G3** | **17** | **+6.08%** | **-6.00%** | **29.41%** | **-6.26%** |

**判定:** fresh blockはFAIL ROBUSTNESS。平均プラスは右裾依存で、中央値・勝率・Top3-exが全候補で弱い。2022を見て既存閾値を変更しない。

### Descriptive 2022 computable block + 2023-2025

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body | 195 | +5.98% | -0.39% | 47.69% | +4.20% |
| volr20 | 195 | +5.81% | 0.00% | 48.72% | +4.03% |
| mean-rank | 195 | +6.28% | 0.00% | 49.23% | +4.51% |
| DUAL | 161 | +6.57% | 0.00% | 49.07% | +4.43% |
| **DUAL + G3** | **134** | **+7.74%** | **+1.06%** | **50.75%** | **+5.17%** |

G3はdescriptive aggregateでは最上位だが、2022 win 29.41%のためpromotionしない。

### 2022 vs 2023-25 outcome-blind structural audit — COMPLETE

Target/outcomeを使わず、frozen weak+early候補集団のsignal-time分布だけを比較した。

| Signal-time feature | 2022 median | 2023-25 median | Shift / 2023-25 IQR |
|---|---:|---:|---:|
| range_pct | 0.1377 | 0.1820 | -0.512 |
| med_ret1 | -0.0029 | 0.0000 | -0.349 |
| gap | -0.0179 | +0.0050 | -0.331 |
| breadth_ret1_pos | 0.3382 | 0.4299 | -0.317 |
| volr5 | 1.0839 | 1.5111 | -0.317 |
| breadth_ma20 | 0.3602 | 0.4332 | -0.316 |
| ret1 | -0.0036 | +0.0526 | -0.292 |
| rsi14 | 69.38 | 64.85 | +0.272 |

Candidate scarcity:
- 2022: 23 signal dates, candidates/day mean **1.26**, single-candidate days **73.9%**
- 2023-25: 172 dates, mean **1.59**, single-candidate days **62.2%**

**Outcome-blind interpretation:** 2022は市場breadth・即時momentum・gap・volume acceleration・rangeが弱く、rankerが選べる候補数も少ない。一方tail_pは低くなくRSIはむしろ高い。単純な「Tail score不足」ではなく、**population/regime mismatch**の可能性が高い。

この差から新しい閾値は作らない。次は model warm-up/calibration、candidate scarcity、2023H2/2025H2にも同じ構造差が現れるかをoutcome-blindで監査する。

---

## 2. Active lanes

| Lane | HEAD | Status | Next |
|---|---|---|---|
| Canonical/Event | `480bc9b5...` | V20 DEPRIORITIZE | V47 accepted rawが自然に得られた場合のみgap reconciliation |
| Core/Cloud | `0886fd65...` | Core reject / Cloud exact replay unavailable | 新しい同時代identity evidenceがある場合だけCloud再開 |
| Consensus V47 | `1eb0408c...` | formal retry ACTIVEだが初期2 shardが180分timeout。midterm diagnostic ACTIVE | diagnostic完了後cost0結果回収。formal現runはduplicate trigger禁止。次回formal retryは48 shard構成 |
| OSS/Validation | `faba5b48...` | selected-ZIP byte freeze CI-green | external key利用可能時にreal EDINET acquisition |

---

## 3. Core + Cloud forensic

最新HEAD `0886fd65f9413dc2591a47475364e736516dbf93`。

- current fixed Core: REJECT
- Failed-Breakdown Reclaim: REJECT
- Prior-Close Reclaim: REJECT
- Precision 3-family batch: REJECT
- 旧Cloud Monster historical evidence: n=63 / mean +9.86% / median +3.33% / win 57.1%
- exact reproduction disposition: **HISTORICAL_EXACT_REPRO_UNAVAILABLE**
- model-family guessing / surrogate replayは禁止

候補ランキングへの影響: **なし**。

---

## 4. Consensus V47

### Formal promotion path

- latest HEAD: `1eb0408cd3ad2d44c2e0c3feb12551857f325be6`
- Daily PIT acceptance: **PASS**
- formal raw initial acceptance: **FAIL**
- formal raw retry: `34810592135` — **ACTIVE / PARTIALLY TIMED OUT**
- retry trigger SHA: `6fcf600245e0a04b3d8bc9c3f6c566a81c9fa03d`
- `fetch (0)` / `fetch (1)`: 180分timeoutでcancel。uploadされたartifactはtimeout時点の極小artifactで、正式coverage evidenceとしては不足
- `fetch (2)` / `fetch (3)`: 18:38 JST時点で取得中。他8 shardはqueued
- duplicate trigger: **禁止継続**
- future-only transport repair: commit `7aa230a0434136cf33589a2fdda010113d57db62` で12 -> 48 deterministic shards、max-parallel=2を維持。現runはtrigger SHA固定なので影響なし
- preserved partial seed: NOCAP **35.3898%**、CAP1000_PIT **83.1124%**、restored pair **0%**
- formal raw acceptance: **未PASS**
- formal clean features / H1 / H2: **未開封**
- formal NOCAP vs CAP1000_PIT comparison: **未開封**

### MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE — cost 0%

- run `34824194221`: **in_progress**
- pre-open contract/hash/coverage freeze: **PASS**
- partial PIT feature materialization: **PASS**
- frozen H1 cost0 comparison: **実行中**
- H1 performance fields: **未出力**
- H2: **未開封**
- endpoint: next XTKS open -> fifth XTKS close
- cost: **0%**
- coverage caveat: preserved partial rawのみ。formal acceptance未達。診断値はpromotion evidenceではない
- opened diagnosticを見た同family retune: **禁止**

### Blocker / next action

1. `34824194221` のH1診断完了を回収し、NOCAP/CAP1000_PITを同じfrozen contract・cost0で記録する。
2. `34810592135` は重複起動せず完走/timeoutを待つ。
3. 現run + preserved seedをmergeしてfrozen verifierを再実行する。
4. FAILならemitted missing symbol/dateだけをtargeted refetchする。次回retryは48-shard transport layoutを使う。
5. threshold緩和・補間・追加price-cap grid searchは禁止。

候補ランキングへの影響: **まだなし**。H1 performance未出力のため推測しない。

---

## 5. V20 cost0 diagnostic

| TopN | n | Mean | Median | Win | Top3-ex |
|---:|---:|---:|---:|---:|---:|
| 1 | 156 | -1.346% | -2.627% | 35.90% | -2.669% |
| 2 | 307 | -1.573% | -1.294% | 40.07% | -2.241% |
| 3 | 442 | -1.118% | -1.289% | 40.05% | -1.613% |
| 5 | 705 | -0.538% | -0.955% | 41.84% | -0.854% |

734 active symbol/date gaps remain。opened diagnosticを見てretuneしない。

---

## 6. Current P0

- [x] frozen 2022 source recovery
- [x] unchanged causal V7 generator reconstruction
- [x] frozen Phase-2 candidates fresh validation
- [x] 2022 robustness failure recording
- [x] 2022 vs 2023-25 signal-time structural audit
- [x] Cloud exact-repro spec freeze / exact evidence availability判定
- [x] Core/Cloud cost0 + canonical endpoint labeling audit
- [x] **V47 formal retry 180分timeout原因を確定し、future retryを48 shardへtransport-only修復**
- [ ] model warm-up / calibration effect audit
- [ ] candidate-scarcity structure audit
- [ ] 2023H2 / 2025H2で同じoutcome-blind shiftsが再現するか確認
- [ ] **V47 diagnostic `34824194221` completion collection**
- [ ] **V47 formal retry `34810592135` completion/timeout collection -> seed merge -> exact acceptance**

## 7. GO / NO-GO

**NO-GO / 研究継続。** Consensus V47は正式raw acceptance未PASS。中締めH1診断はまだ実行中で、performance未出力。formalとdiagnosticを混同せず、診断値を見たretuneは禁止する。