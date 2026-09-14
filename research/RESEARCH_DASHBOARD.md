# TV-Free スコアリングBot研究ダッシュボード

> **最終更新基準:** 2026-09-14 19:36 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| Weak+Early Phase-2 | **2022 fresh validation FAILED ROBUSTNESS**。2023H2/2025H2横断のoutcome-blind構造監査まで完了 |
| 2023-25暫定首位 | **DUAL_TOP1_AGREEMENT**、勝率改善候補 **G3 NO_ACUTE_SELLOFF** |
| Phase-2 Round2 | **NOT ACTIVATED**。2023H2と2025H2を同時説明する単純なmarket weakness gateは未発見 |
| Consensus V47 | 中締めH1 cost0診断完了。**NOCAPが平均で暫定リード**。NOCAP-only H2 cost0中締め診断 `34832358609` はpre-open contract検証を通過し、partial PIT feature materialization中。formal raw acceptanceは未PASS |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Core/Cloud forensic | Core既reject維持 / Cloud **HISTORICAL_EXACT_REPRO_UNAVAILABLE** / Core canonical endpoint監査スクリプトを**cost0-onlyへ修復済み** |
| OSS / EDINET | selected-manifest/ZIP exact-byte境界＋cost0 Optuna契約までCI固定、real EDINETは外部key待ち |
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

### 2023H2 / 2025H2 mechanism audit — NEW

不調halfを良好halfとoutcome-blindに比較した。詳細は `research/WEAK_EARLY_PHASE2_STRUCTURAL_AUDIT_20260914_1900.md`。

| Half | candidates/day | single-candidate | breadth_ma20 | breadth_ret1_pos | range_pct | volr5 | tail_p |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023H1 | 2.17 | 60.00% | 0.459 | 0.384 | 0.117 | 1.224 | 0.821 |
| **2023H2** | **1.27** | **81.82%** | **0.416** | **0.378** | **0.068** | **1.029** | 0.820 |
| 2024H1 | 2.62 | 34.48% | 0.558 | 0.421 | 0.093 | 1.172 | 0.820 |
| 2024H2 | 2.61 | 39.39% | 0.519 | 0.422 | 0.070 | 1.187 | 0.828 |
| 2025H1 | 2.82 | 39.29% | 0.592 | 0.464 | 0.089 | 1.195 | 0.847 |
| **2025H2** | **1.79** | **63.16%** | **0.633** | **0.499** | **0.073** | **1.190** | 0.834 |

**Key finding:**
- 2023H2は2022型の「弱breadth + 小range + 候補不足」にかなり近い。
- 2025H2は候補不足はあるが、breadthはむしろ全halfで最強側。よって同じmarket-weakness原因ではない。
- tail_p中央値は各halfで約0.82-0.85と安定。不調halfだけscore levelが低い証拠はない。
- body_pctは両不調halfで高いがcandidate-level clueなので、現在のfreeze方針では新gate/rankerへ昇格しない。
- **Round2は未起動。** 2023H2/2025H2を同時説明するmarket-level因子を後付けで捏造しない。

---

## 2. Active lanes

| Lane | HEAD | Status | Next |
|---|---|---|---|
| Canonical/Event | `480bc9b5...` | V20 DEPRIORITIZE | V47 accepted rawが自然に得られた場合のみgap reconciliation |
| Core/Cloud | `291cbdd4...` | Core reject / Cloud exact replay unavailable / cost0 endpoint contract repaired | stale cost/endpoint契約監査を継続。新Cloud evidenceが無ければexact replayは閉鎖維持 |
| Consensus V47 | `008fd873...` | H1 diagnostic SUCCESS / NOCAP H2 diagnostic IN PROGRESS (feature materialization) / formal retry partial timeout | H2 run `34832358609` 完了後にcost0診断回収。formalは現run完了後seed merge→exact acceptance |
| OSS/Validation | `91831b03...` | selected-manifest/ZIP byte freeze + cost0 Optuna contract hardening CI-green | external key利用可能時にreal EDINET acquisition |

---

## 3. Core + Cloud forensic

最新HEAD `291cbdd41f98d24da29a5b2f0195893c5b8ae884`。

- current fixed Core: REJECT
- Failed-Breakdown Reclaim: REJECT
- Prior-Close Reclaim: REJECT
- Precision 3-family batch: REJECT
- 旧Cloud Monster historical evidence: n=63 / mean +9.86% / median +3.33% / win 57.1%
- exact reproduction disposition: **HISTORICAL_EXACT_REPRO_UNAVAILABLE**
- model-family guessing / surrogate replayは禁止
- forensic進捗段階: **spec凍結 → 元期間 exact replay unavailable で停止**。別期間横展開は未実施
- cross-lane reproducibility audit: `audit_core_canonical_endpoint.py` に残っていた0.5%/1%再計算経路を検出し、`f1a1bd23...` で**新規計算cost0-only**へ修復
- 同修復で +50% / -20% / Top1・Top3除外 / 月別・週別依存の出力契約も追加
- 修復はコード契約のみで、新バックテストは起動していない。最新Action run/status: **該当なし（trigger未変更）**

候補ランキングへの影響: **なし**。

---

## 4. Consensus V47

### Formal promotion path

- latest HEAD: `008fd87386f252cb5f7289ef4e303604d8f56c76`
- Daily PIT acceptance: **PASS**
- formal raw initial acceptance: **FAIL**
- formal raw retry: `34810592135` — **ACTIVE / PARTIALLY TIMED OUT**
- `fetch (0)` / `fetch (1)`: 180分timeoutでcancel
- duplicate trigger: **禁止継続**
- future-only transport repair: commit `7aa230a0434136cf33589a2fdda010113d57db62` で12 -> 48 deterministic shards、max-parallel=2維持。現runには影響なし
- preserved partial seed: NOCAP **35.3898%**、CAP1000_PIT **83.1124%**、restored pair **0%**
- formal raw acceptance: **未PASS**
- formal clean features / H1 / H2: **未開封**

### MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE — H1 cost 0%

Workflow `34824194221`: **SUCCESS**  
Artifact SHA256: `c46e90cba472c291a7db068ff1dadb0959764dcef97eb006dd6c3b918779f866`

- period: **2025-01-06..2025-06-30**
- endpoint: next XTKS open -> D+5 close
- cost: **0%**
- strict same-symbol cooldown: **5 XTKS sessions**
- replacement: **false**
- V11 frozen 3-head / min consensus / threshold 0.95 / guard none / sessions both

| Arm | Coverage | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **NOCAP** | **35.3898%** | 50 | **+0.1074%** | -2.7270% | 36.00% | 16.00% | 8.00% | 0.00% | 12.00% | 2.00% | -0.7566% | -2.0148% |
| CAP1000_PIT | **83.1124%** | 60 | **-1.1568%** | -0.4011% | 46.67% | 13.33% | 0.00% | 0.00% | 11.67% | 3.33% | -1.4639% | -2.0601% |

Coverage caveat:
- NOCAP monthly minimum 33.9002%、completely missing required symbols 2,592、restored pair 0%
- CAP1000_PIT monthly minimum 77.3420%、completely missing required symbols 642、restored pair 0%
- missing pairは補間・synthetic化していない

**H1 diagnostic decision:** frozen primary criterionのdevelopment meanでは **NOCAP leader**。ただしformal acceptance未達でpopulation coverageもarm間で大きく異なるため、これはpromotion evidenceではない。

Robustness diagnosis: NOCAPもmedian / Top1-ex / Top3-exが負。CAP1000_PITはmean / Top1-ex / Top3-exが負。両armとも強い正式候補と判断できる状態ではない。結果を見たprice-cap grid searchや同family retuneは禁止。

Holdout state:
- H1: **開封済み・untouchedではない**
- H2: **診断開封処理中**（NOCAPのみ、run `34832358609`）
- 2026: **未開封（このdiagnostic）**

### MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE — NOCAP H2 cost 0%

Pre-open contract was frozen before H2 outcomes at `research/CONSENSUS_V47_MIDTERM_H2_DIAGNOSTIC_SPEC_20260914.json`。H1 leaderは **NOCAP** に固定済みで、CAP1000_PIT H2は開かない。threshold 0.95 / V11 3-head / strict5 / no replacement / H1 cooldown carry / endpointは不変。

- workflow: `34832358609`
- status: **IN PROGRESS — pre-open contract PASS; partial PIT feature materialization running**
- current job step: **10 / 13 — Materialize partial PIT features without promotion acceptance**
- period to open: **2025-07-01..2025-12-30**
- cost: **0%**
- formal promotion evidence: **false**
- coverage: preserved partial raw seed only; missing pairはmissingのまま、補間・synthetic barなし
- post-open same-family retune: **禁止**

### Blocker / next action

1. H2 diagnostic `34832358609` のfeature materialization完了後、NOCAP H2を固定契約のまま開き、cost0 n/mean/median/win/+10/+20/+50/-10/-20/Top1-ex/Top3-exを回収する。
2. H2が開いた時点で2025H2はuntouched holdoutとは呼ばない。CAP1000_PIT H2をrescue目的で開かない。
3. formal `34810592135` は重複起動せず終了まで監視。
4. valid retry artifacts + preserved seedをmergeしてfrozen acceptanceを再実行。
5. FAILならemitted missing symbol/dateだけtargeted refetch。次回transport layoutは48 shard。
6. threshold/ranker/cooldown/price arm/model familyのretuneは禁止。

候補ランキングへの影響: **NOCAPがConsensus内の中締めH1診断で暫定1位**。H2診断はfeature materialization中で、正式候補ランキングにはまだ昇格なし。

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
- [x] candidate-scarcity structure audit
- [x] 2023H2 / 2025H2 outcome-blind shift audit
- [x] Cloud exact-repro spec freeze / exact evidence availability判定
- [x] Core/Cloud cost0 + canonical endpoint labeling audit
- [x] **Core stale 0.5%/1% recomputation path removal + cost0 endpoint output contract hardening**
- [x] **V47 formal retry timeout原因確定 / future retry 48 shard修復**
- [x] **V47 midterm H1 cost0 comparison completion collection**
- [x] **V47 NOCAP-only H2 diagnostic pre-open contract freeze + launch**
- [ ] model warm-up / calibration metadata audit
- [ ] V47 diagnostic H2 NOCAP-only result collection
- [ ] V47 formal retry completion/timeout collection -> seed merge -> exact acceptance
- [ ] Phase-2 Round2 prereg（同時説明可能なcausal market variableが理論的に得られた場合のみ）

## 7. GO / NO-GO

**NO-GO / 研究継続。** Weak+Earlyは2022 fresh blockで安定性FAIL。2023H2は2022型のmarket weakness/scarcityだが、2025H2は高breadthのため単一の弱地合いgateでは共通原因を説明できない。Round2は後付け探索を避けるため未起動。Consensus V47のH1中締めではNOCAPが平均で勝ったが、coverage-bypassed diagnosticでありformal promotion evidenceではない。NOCAP H2 cost0中締め診断は固定契約のままpartial PIT feature materialization中。正式raw acceptanceは未PASS。Core/Cloudは既reject / exact replay unavailableを維持し、今回のcost0 endpoint修復は再現性契約の修正であって新しいperformance evidenceではない。
