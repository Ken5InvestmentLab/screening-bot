# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-14 21:xx JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **固定リンク:** https://github.com/Ken5InvestmentLab/screening-bot/blob/research/automation-coordination/research/RESEARCH_DASHBOARD.md

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| Weak+Early Phase-2 | **2022 fresh validation FAILED ROBUSTNESS**。model-period診断まで完了し、単純warm-up不足を主因として棄却 |
| 2023-25暫定首位 | **DUAL_TOP1_AGREEMENT**、勝率/平均改善候補 **DUAL + G3 NO_ACUTE_SELLOFF** |
| Phase-2 Round2 | **NOT ACTIVATED**。後付けgate探索は停止 |
| Consensus V47 | **中締めH1/H2 diagnostic完了**。NOCAP H2 cost0 = n37 / mean +3.03% / median +0.38% / win 51.35% / Top3-ex -0.54%。formal raw acceptanceは未PASS |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Core / Cloud | Core reject維持。cost0-only契約整合済み / Cloud exact replay **HISTORICAL_EXACT_REPRO_UNAVAILABLE** |
| OSS / Validation | **Optuna cost0契約と実装に不一致。新規Optunaはfail-closed**。EDINET real pathは外部key待ち |
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

- preserved artifact: `10264205130`
- **correct source run: `34599959356`**
- artifact digest: `sha256:095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`
- raw 2022 rows: **825,735**
- same V7/V9 full-45-feature monthly causal Tail generator
- existing `train >= 30,000` rule unchanged
- first computable month: **2022-06**
- frozen weak+early後: **29 rows / 23 signal dates**

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 23 | +1.77% | -6.37% | 26.09% | -7.51% |
| volr20 LOW | 23 | +1.95% | -6.19% | 26.09% | -7.31% |
| mean-rank | 23 | +1.73% | -6.37% | 26.09% | -7.56% |
| DUAL_TOP1 | 21 | +2.62% | -6.19% | 28.57% | -7.55% |
| **DUAL + G3** | **17** | **+6.08%** | **-6.00%** | **29.41%** | **-6.26%** |

**判定:** fresh blockはFAIL ROBUSTNESS。2022を見て既存thresholdを変更しない。

### 2022 model maturity + model-period audit

月次causal training rowsはJun 40,602 → Sep 117,301 → Dec 189,183、Top0.25%正例は116 → 335 → 541まで増加。正例率は約0.286〜0.293%で安定。

さらに同じfrozen 2022 picksをmodel_period別に分解し、既存集計を**完全一致再現**したうえで成熟前後を比較した。

| Frozen candidate | Block | n | Mean | Median | Win | Top3-ex |
|---|---|---:|---:|---:|---:|---:|
| DUAL | Jun-Aug | 8 | **-8.95%** | -7.69% | **0.00%** | -11.96% |
| DUAL | **Sep-Dec (train >100k from Sep)** | **13** | **+9.75%** | **-0.39%** | **46.15%** | **-6.43%** |
| G3 | Jul-Aug | 6 | **-7.85%** | -7.69% | **0.00%** | -11.67% |
| G3 | **Sep-Dec (train >100k from Sep)** | **11** | **+13.67%** | **-0.39%** | **45.45%** | **-5.07%** |

重要な反証:
- Sep-Decでは平均だけは大化け銘柄でプラス化するが、**中央値は負・勝率50%未満・Top3除外も大幅マイナス**。
- **2022-12**はtrain **189,183行 / positive 541件**まで育っているのに、DUAL n8 / mean -4.00% / median -6.09% / win 25%、G3 n7 / mean -6.21% / median -6.19% / win 14.29%。
- `tail_p` は悪化月でも概ね0.83前後で崩れておらず、単純なscore-confidence低下でも説明しにくい。

**結論:** `simple warm-up / undersized training` は**主因としてREJECT**。2022は成熟後も「少数の大当たりで平均が持ち上がる一方、通常pickの中央性能が弱い」右裾依存が残る。

詳細:
- `research/WEAK_EARLY_PHASE2_MODEL_MATURITY_AUDIT_20260914_2000.md`
- `research/WEAK_EARLY_PHASE2_MODEL_PERIOD_AUDIT_20260914_2100.md`

### Structural audit summary

- 2023H2は2022型の「弱breadth + 小range + 候補不足」に近い。
- 2025H2は候補不足はあるがbreadthはむしろ強い。
- candidate scarcityは一部説明するが全てではない。
- 2022 mature blockでも候補poolは薄く、Sep/Octは実質1候補/day、Decも13 rows / 9 dates・single-candidate約55.6%。
- ただしopened outcomeを見た後なので、**candidate countをそのまま新gateへ昇格しない**。

**Round2 disposition:** **CLOSED / NO NEW GATE**。

### Phase-2 next action

1. outcome-blindで2022 / 2023H2 / 2025H2のcandidate-count分布、forced-choice比率、symbol concentration、market structureを横並び監査。
2. 2025H2を説明するqualitatively differentなmarket-level仮説は、理論付けして**outcomeを見る前にpreregisterできる場合のみ**Round2へ進む。
3. threshold、G3、ranker、candidate gateの後付け変更は禁止。

---

## 2. Active lanes

| Lane | HEAD | Status | Next |
|---|---|---|---|
| Canonical/Event | `480bc9b5...` | V20 DEPRIORITIZE | V47 accepted rawが自然に得られた場合のみgap reconciliation |
| Core/Cloud | `48987e82...` | Core reject / Cloud exact replay unavailable / cost0 contract audit前進 | stale cost/endpoint契約監査のみ。rejected family再実行禁止 |
| Consensus V47 | `263b91af...` | **H1/H2 diagnostic完了 / formal raw未PASS** | formal retry `34810592135`を重複起動せず監視→終了後merge+frozen acceptance |
| OSS/Validation | `6e9045e9...` | **Optuna cost0 implementation gap BLOCKED** | API/CLI/testsをcost0-onlyへ修正→isolated CI green後のみ再開 |

21時台の横断HEAD再確認では4レーンとも前回STATEから変更なし。processed SHAの重複処理なし。

---

## 3. Consensus V47 — diagnostic only

### Formal path

- Daily PIT acceptance: **PASS** (`34799835035`)
- Raw frozen acceptance: **FAIL / NOT PASS** (`34810234454`)
- Formal retry: `34810592135` active。fetch (2)/(3)進行、fetch (0)/(1)は180分境界でcancelled。重複起動禁止。
- future retry layout: **48 shards / max-parallel 2**
- formal clean features/H1/H2: **未開封**

### Midterm diagnostic — cost 0%

| Arm/Period | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NOCAP H1 | 50 | +0.1074% | -2.7270% | 36.00% | 16.00% | 8.00% | 0.00% | 12.00% | 2.00% | -0.7566% | -2.0148% |
| CAP1000_PIT H1 | 60 | -1.1568% | -0.4011% | 46.67% | 13.33% | 0.00% | 0.00% | 11.67% | 3.33% | -1.4639% | -2.0601% |
| **NOCAP H2** | **37** | **+3.0295%** | **+0.3817%** | **51.35%** | **27.03%** | **16.22%** | **2.70%** | **13.51%** | **2.70%** | **+1.5562%** | **-0.5393%** |

- H1/H2は`MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`。
- CAP1000_PIT H2はrescueとして開かない。
- NOCAP H2はmean/median/winが正でもTop3-ex負、partial coverageのwinner依存警告あり。
- production/formal ranking変更なし。

---

## 4. OSS / Validation — BLOCKER

最新HEAD `6e9045e91323b3cc25d88dedd3a7e9e943f8ae58`。

Frozen cost0 contractに対し、`optuna_discovery.py` がまだ非ゼロround-trip costを許している実装ギャップを検出済み。

**Disposition:** `IMPLEMENTATION_GAP_BLOCKED`。新規Optuna discovery/performanceは禁止。

解除条件:
1. API/CLI default = 0.0
2. 非ゼロcost reject
3. testsでcost0-only assert
4. isolated OSS CI green

EDINET real-data pathは外部 `EDINET_API_KEY` 待ち。

---

## 5. Core / Cloud / V20

- Fixed Core / reclaim / precision: REJECT維持
- Core/Cloud HEAD: `48987e8268799d4d7d0c915e8dd8ae6f1f6b8153`
- endpoint / forward / final comparison contract: cost0-onlyへ整合済み
- Cloud historical headline **n=63 / mean +9.86%** は歴史値のみ
- Cloud exact reconstruction: **HISTORICAL_EXACT_REPRO_UNAVAILABLE**
- model-family guessing禁止
- V20 cost0 diagnostic: 全TopN負、DEPRIORITIZE
- V20 734 gapはV47 accepted rawが自然に得られた場合のみrepair候補

---

## 6. Current ranking / GO-NO-GO

### Performance-oriented Phase-2 ranking
1. **DUAL + G3** — 2023-25 mean +7.98%, win 53.85%, Top3-ex +5.14%。ただし2022 fresh fail。
2. **DUAL_TOP1_AGREEMENT** — mean +7.17%, win 52.14%, Top3-ex +4.79%。
3. mean-rank — mean +6.89%, win 52.33%, Top3-ex +4.95%。
4. body_pct LOW / volr20 LOW — comparator。

Consensus diagnosticはformal raw acceptance前・coverage-bypassedのためproduction-oriented順位には昇格させない。

### Current decision

**NO-GO / 研究継続**

理由:
- Weak+Earlyは2023-25で魅力的だが2022 freshで安定性FAIL。
- 2022 failureは初期warm-upだけではなく、train>100kの成熟後も中央値/勝率/Top3-exが弱い。
- simple weak-market gateでは2023H2/2025H2を同時説明できない。
- Consensusはformal raw acceptance未PASS。
- Core/V20 reject/deprioritize、Cloud exact replay closed。
- OSS Optunaはcost0実装ギャップ修正待ち。

次の高情報量チェックは **Phase-2 outcome-blind population/scarcity横断監査** と **Consensus formal retry終了→raw merge→frozen acceptance**。後付けの勝率最適化は行わない。
