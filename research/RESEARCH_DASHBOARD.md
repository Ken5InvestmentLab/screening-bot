# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-14 20:20 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **固定リンク:** https://github.com/Ken5InvestmentLab/screening-bot/blob/research/automation-coordination/research/RESEARCH_DASHBOARD.md

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| Weak+Early Phase-2 | **2022 fresh validation FAILED ROBUSTNESS**。構造監査＋model maturity監査まで完了 |
| 2023-25暫定首位 | **DUAL_TOP1_AGREEMENT**、勝率/平均改善候補 **DUAL + G3 NO_ACUTE_SELLOFF** |
| Phase-2 Round2 | **NOT ACTIVATED**。単純weak-market gateも単純warm-up不足も共通原因として不十分 |
| Consensus V47 | H1 cost0中締め診断済み。NOCAP-only H2診断 `34832358609` は**step 11/13: H2 opening実行中**。formal raw acceptanceは未PASS |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Core / Cloud | Core reject維持 / Cloud exact replay **HISTORICAL_EXACT_REPRO_UNAVAILABLE** |
| OSS / Validation | **Optuna cost0契約と実装に不一致を検出。新規Optuna実行はfail-closed**。EDINET real pathは外部key待ち |
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

### 2022 model maturity audit — NEW

保存済みrawからV7/V9の月次causal学習母数と`y_top025`正例数をoutcome-blindで再構築した。

| Model period | Train rows | Top0.25 positives | Positive rate | Computable |
|---|---:|---:|---:|---|
| 2022-05 | 17,532 | 48 | 0.274% | NO |
| **2022-06** | **40,602** | **116** | **0.286%** | YES |
| 2022-07 | 67,528 | 198 | 0.293% | YES |
| 2022-08 | 91,462 | 265 | 0.290% | YES |
| 2022-09 | 117,301 | 335 | 0.286% | YES |
| 2022-10 | 141,014 | 403 | 0.286% | YES |
| 2022-11 | 165,509 | 475 | 0.287% | YES |
| **2022-12** | **189,183** | **541** | **0.286%** | YES |

**新しい結論:** Juneは確かにearly-stageだが、Sepで117k、Decで189kまで学習行が増え、正例数も335→541まで増える。positive rateも約0.286〜0.293%で安定。したがって、**2022 Jun-Decの弱さを単純な「学習件数不足」で説明する仮説は弱い。**

詳細: `research/WEAK_EARLY_PHASE2_MODEL_MATURITY_AUDIT_20260914_2000.md`

### Structural audit summary

- 2023H2は2022型の「弱breadth + 小range + 候補不足」に近い。
- 2025H2は候補不足はあるがbreadthはむしろ強い。
- tail_pは不調halfだけ低いわけではない。
- candidate scarcityは一部説明するが全てではない。
- body_pctは両不調halfで高いがcandidate-level clueなので新gate/rankerへ昇格しない。

**Round2 disposition:** **CLOSED / NO NEW GATE**。

### Phase-2 next action

1. 既存frozen 2022 picksを**model_period別に診断表示**し、弱さがJun-Julだけか、training rows >100kのSep-Decにも残るか確認する。
2. 月別`tail_p` / `tail_cdf` / candidate count / single-candidate shareをtraining maturityと並べる。
3. これは原因診断のみ。結果を見てthreshold、G3、ranker、candidate gateは変更しない。
4. 2025H2を説明する別のmarket-level仮説は、outcomeを見る前に理論付け/preregisterできる場合のみRound2へ進む。

---

## 2. Active lanes

| Lane | HEAD | Status | Next |
|---|---|---|---|
| Canonical/Event | `480bc9b5...` | V20 DEPRIORITIZE | V47 accepted rawが自然に得られた場合のみgap reconciliation |
| Core/Cloud | `291cbdd4...` | Core reject / Cloud exact replay unavailable | stale cost/endpoint contract監査。rejected familyは再実行しない |
| Consensus V47 | `008fd873...` | H1 diagnostic済 / **NOCAP H2 step11実行中** / formal raw未PASS | run `34832358609`完了後に診断回収。CAP1000 H2 rescue禁止 |
| OSS/Validation | `6e9045e9...` | **Optuna cost0 implementation gap BLOCKED** | API/CLI/testsをcost0-onlyへ修正→isolated CI green後のみ再開 |

---

## 3. Consensus V47 — diagnostic only

### H1 cost0 midterm diagnostic

| Arm | Coverage | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|
| **NOCAP** | 35.3898% | 50 | **+0.1074%** | -2.7270% | 36.00% | -2.0148% |
| CAP1000_PIT | 83.1124% | 60 | -1.1568% | -0.4011% | 46.67% | -2.0601% |

- H1は`MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`。
- H1 leaderは平均値基準でNOCAP。
- NOCAP-only H2 run `34832358609`: pre-open contract PASS、feature materialization PASS、**H2 opening step実行中**。
- H2結果が出るまで推測しない。
- CAP1000_PIT H2をrescueとして開かない。
- Formal promotion pathはraw acceptance PASSまで別管理。

---

## 4. OSS / Validation — NEW BLOCKER

最新HEAD `6e9045e91323b3cc25d88dedd3a7e9e943f8ae58`。

Outcome-blind source auditで、frozen Optuna contractと実装の不一致を検出:
- contract: 新規discovery/performanceは**cost 0%のみ**
- implementation: `optuna_discovery.py` がまだ `round_trip_cost=0.005` defaultで、非ゼロ値も受理
- tests: `0.001` costをまだ使用

**Disposition:** `IMPLEMENTATION_GAP_BLOCKED`。新規Optuna discovery/performanceは実行禁止。

解除条件:
1. API default = 0.0
2. CLI default = 0.0
3. 非ゼロcostをreject
4. testsでcost0-onlyをassert
5. isolated OSS CI green

EDINET real-data pathは別件で外部 `EDINET_API_KEY` 待ち。

---

## 5. Core / Cloud / V20

- Fixed Core: REJECT
- reclaim / precision families: REJECT維持
- Cloud historical headline: n=63 / mean +9.86% は歴史値のみ
- Cloud exact reconstruction: **HISTORICAL_EXACT_REPRO_UNAVAILABLE**
- model-family guessing禁止
- V20 cost0 diagnostic: 全TopN負、DEPRIORITIZE
- V20の734 gapはV47 accepted rawが自然に得られた場合だけrepair候補

---

## 6. Current ranking / GO-NO-GO

### Performance-oriented Phase-2 ranking
1. **DUAL + G3** — 2023-25 mean +7.98%, win 53.85%, Top3-ex +5.14%。ただし2022 fresh fail。
2. **DUAL_TOP1_AGREEMENT** — mean +7.17%, win 52.14%, Top3-ex +4.79%。
3. mean-rank — mean +6.89% / win 52.33% / Top3-ex +4.95%。
4. body_pct LOW / volr20 LOW — comparator。

**重要:** これはproduction GO順位ではない。2022 fresh robustnessを通過した候補はまだ0件。

### Current decision

**NO-GO / 研究継続**

理由:
- Weak+Earlyは2023-25で魅力的だが2022 fresh blockで安定性FAIL。
- simple weak-market gateでは2023H2/2025H2を同時説明できない。
- simple warm-up不足でも2022全体を説明できない。
- Consensus formal raw acceptance未PASS。
- Core/V20はreject/deprioritize済み。
- OSS Optunaはcost0実装ギャップ修正待ち。

次の高情報量チェックは **Phase-2 model-period診断** と **Consensus NOCAP H2診断回収**。
