# WEAK+EARLY Phase 2 Model Maturity Audit — 2026-09-14 20:00 JST

## Purpose

2022 fresh validation failureが、V7/V9 monthly causal Tail modelの単純なwarm-up不足・training sample不足で説明できるかを、**outcome-blind**に監査する。

この監査ではcandidate returnや2026 outcomeを見てthreshold/ranker/gateを選ばない。Phase-2のfrozen条件、G3=-1%、canonical endpoint、cost0契約は変更しない。

## Source / exact implementation

- preserved run-80 artifact: `10264205130` / source run `34545440155`
- raw daily rows in artifact: 2022 rows **825,735**（artifact自体は2022-01-04..2026-09-11）
- feature/eligibility contract: `tvfree_screener/run.py`
  - 45 signal-time features
  - prev_volume >= 10,000
  - signal volume >= 5,000
  - close >= 20
  - previous close <= 1,000
- V7/V9 causal training contract:
  - month start `a`に対し `target_end_date < a` の行だけで学習
  - target = same-day cross-sectional future-rank top 0.25% (`y_top025`)
  - minimum training rows = **30,000**
  - monthly expanding retrain
- model parameters/label definition/thresholdは変更していない。

## Monthly model maturity — 2022

以下は戦略performanceを使わず、各月開始時点で利用可能なcausal training rows / positive labelsだけを再計算したもの。

| Model period | Train rows | y_top025 positives | Positive rate | Pred rows | Computable |
|---|---:|---:|---:|---:|---|
| 2022-04 | 0 | 0 | — | 23,506 | NO |
| 2022-05 | 17,532 | 48 | 0.274% | 23,209 | NO (<30k) |
| **2022-06** | **40,602** | **116** | **0.286%** | 26,838 | **YES** |
| 2022-07 | 67,528 | 198 | 0.293% | 23,720 | YES |
| 2022-08 | 91,462 | 265 | 0.290% | 25,785 | YES |
| 2022-09 | 117,301 | 335 | 0.286% | 24,333 | YES |
| 2022-10 | 141,014 | 403 | 0.286% | 24,033 | YES |
| 2022-11 | 165,509 | 475 | 0.287% | 23,719 | YES |
| **2022-12** | **189,183** | **541** | **0.286%** | 27,296 | **YES** |

## Findings

### 1. June is genuine early-stage, but the entire Jun-Dec failure cannot be called “barely warm”

最初の評価可能月2022-06は40,602 training rows / 116 positive labelsで、30k minimumを超えた直後ではある。

しかし学習母数はその後急増し、
- Jul: 67.5k / 198 positives
- Sep: 117.3k / 335 positives
- Dec: 189.2k / 541 positives

まで成長する。

したがって、**2022 Jun-Dec全体のrobustness failureを単純なtraining-row不足だけで説明する仮説は弱い。**

### 2. Top-0.25% label base rate is stable, not degenerate

2022-06以降の`y_top025` positive rateは約 **0.286%〜0.293%** に収まり、月を追って極端に希薄化/膨張していない。

少なくとも「初期月だけlabel構造が壊れていた」という一次説明は支持されない。

### 3. Existing population/regime mismatch hypothesis remains more plausible

既存のoutcome-blind structural auditでは2022候補群が2023-25より、
- breadth weaker
- range smaller
- volume acceleration weaker
- immediate momentum/gap weaker
- candidate scarcity stronger

という構造差を持つことが確認済み。

training sampleがQ4まで十分大きくなっても、このpopulation mismatch自体は消えない可能性がある。

## Disposition

- **Simple warm-up / undersized-training explanation: WEAKENED, not sufficient.**
- 2022 fresh validation: FAIL ROBUSTNESSの判定を維持。
- G3 `med_ret1 >= -1%`: freeze維持、retuneしない。
- Regime Round2: **CLOSED / NOT ACTIVATED**。
- 2023H2と2025H2を後付けで1本のmarket weakness gateにまとめない。
- Production: **NO-GO**。

## Next high-information checks

1. 2022 fresh blockの既存frozen picksを**model_period別に診断表示**し、弱さがJun-Julだけに集中するのか、training rowsが100k超のSep-Decにも残るのかを確認する。これは原因診断のみで、結果を見てthresholdを変更しない。
2. outcome-blindに、月別の`tail_p` / `tail_cdf` / candidate count / single-candidate shareをtraining rowsと並べ、model maturityとpopulation scarcityを分離する。
3. 2025H2についてはweak breadth以外のmarket-level説明を**結果を見る前に理論付け・preregisterできる場合のみ**Round2へ進む。
