# WEAK+EARLY Phase 2 Structural Audit — 2026-09-14 19:00 JST

## Purpose

2022 fresh validation failureと、既知の弱点である2023H2 / 2025H2が同じ構造要因で説明できるかを、**outcome-blindな候補集合・市場特徴量だけ**で監査する。

この監査では新しいthreshold/ranker/gateを選ばない。performanceを見て連続threshold searchもしない。

## Frozen basis

- previous-session `med_ret5 <= 0`
- candidate `ret10 <= 0.5735294117647058`
- one candidate/day
- canonical endpoint: next XTKS open -> fifth XTKS close
- transaction cost: 0%
- DUAL_TOP1_AGREEMENT / G3の既存条件は変更しない
- 2026 outcomeは使用しない

## 2022 fresh-validation reference

Preserved run-80 rawを既存V7/V9 generatorで再生成し、30k training-row minimumを維持したため、2022はJUN-DECのみ評価可能。

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 48 | -2.27% | -4.53% | 37.50% | -7.20% |
| volr20 LOW | 48 | -1.42% | -4.86% | 31.25% | -5.94% |
| mean-rank | 48 | -0.48% | -4.04% | 37.50% | -5.36% |
| DUAL_TOP1_AGREEMENT | 21 | +2.62% | -6.19% | 28.57% | -7.55% |
| DUAL + G3 | 17 | +6.08% | -6.00% | 29.41% | -6.26% |

G3は平均だけ正でも中央値・勝率・Top3-exが崩れており、fresh validationとしてNO-GO。

## Outcome-blind 2022 structural reference

Weak+Early candidate population medians, 2022 vs 2023-2025:

| Feature | 2022 | 2023-2025 |
|---|---:|---:|
| range_pct | 0.0624 | 0.0829 |
| med_ret1 | -0.0067 | -0.0028 |
| gap | 0.0000 | +0.0082 |
| breadth_ret1_pos | 0.3484 | 0.4222 |
| volr5 | 0.8708 | 1.1713 |
| breadth_ma20 | 0.3484 | 0.5191 |
| ret1 | +0.0056 | +0.0247 |
| rsi14 | 56.07 | 53.53 |
| tail_p | 0.8448 | 0.8272 |
| candidates/day | 1.95 | 2.27 |
| single-candidate share | 58.33% | 50.84% |

2022はbreadth・gap・same-day momentum・volume acceleration・rangeが弱く、候補数も少ない。一方、tail_pは低くなくrsi14はむしろ高い。

## 2023-2025 half-year structural audit

Weak+Early gate通過candidate populationの中央値。

| Half | range_pct | med_ret1 | gap | breadth_ret1_pos | volr5 | breadth_ma20 | ret1 | rsi14 | tail_p | volr20 | body_pct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023H1 | 0.1167 | -0.0024 | 0.0193 | 0.3837 | 1.2237 | 0.4592 | 0.1023 | 55.61 | 0.8208 | 0.8926 | 0.1765 |
| **2023H2** | **0.0683** | **-0.0041** | **0.0085** | **0.3776** | **1.0288** | **0.4158** | **0.0183** | 51.67 | 0.8202 | 0.9299 | **0.4453** |
| 2024H1 | 0.0932 | -0.0032 | 0.0097 | 0.4211 | 1.1721 | 0.5584 | 0.0225 | 55.43 | 0.8196 | 0.9158 | 0.2105 |
| 2024H2 | 0.0700 | -0.0038 | 0.0068 | 0.4220 | 1.1870 | 0.5191 | 0.0145 | 51.61 | 0.8282 | 0.8811 | 0.2667 |
| 2025H1 | 0.0885 | -0.0014 | 0.0046 | 0.4643 | 1.1951 | 0.5922 | 0.0191 | 53.40 | 0.8465 | 0.8216 | 0.2792 |
| **2025H2** | **0.0733** | **-0.0025** | **0.0164** | **0.4989** | **1.1902** | **0.6327** | **0.0220** | 56.43 | 0.8335 | 0.9179 | **0.3548** |

### Candidate scarcity

| Half | Signal dates | Candidates/day | Single-candidate share |
|---|---:|---:|---:|
| 2023H1 | 30 | 2.17 | 60.00% |
| **2023H2** | **33** | **1.27** | **81.82%** |
| 2024H1 | 29 | 2.62 | 34.48% |
| 2024H2 | 33 | 2.61 | 39.39% |
| 2025H1 | 28 | 2.82 | 39.29% |
| **2025H2** | **19** | **1.79** | **63.16%** |

## Findings

### 1. 2023H2は2022型の構造に近い

2023H2は候補数1.27/day、single-candidate 81.82%と極端に候補不足。breadth_ma20 0.416、range 0.068、volr5 1.03も良好期より弱い。

これは2022の「弱いbreadth / 小さいrange / 低いvolume acceleration / 少ない選択肢」と方向が一致する。

### 2. 2025H2は同じ原因ではない

2025H2のbreadthはむしろ全halfで最も強い側:
- breadth_ret1_pos 0.499
- breadth_ma20 0.633
- volr5 1.19

candidate scarcityは悪化しているが、2023H2ほど極端ではない。

したがって、**単一の“市場が弱い時はNO TRADE” gateで2023H2と2025H2を同時に説明する仮説は支持されない。**

### 3. tail_p水準は不調期を分離していない

half-year median tail_pは約0.820-0.847に収まり、2023H2 / 2025H2だけ明確に低いわけではない。

少なくとも2023-2025内では「tail scoreの絶対水準が低いから負ける」という一次的calibration driftの証拠は弱い。

### 4. Candidate scarcityは一部を説明するが全てではない

- 2023H2: single-candidate 81.82% → 非常に強いscarcity
- 2025H2: 63.16% → 悪化しているが、これだけで高breadth下の弱さを説明するには不足

よってscarcityはdiagnostic clueとして維持するが、outcomeを見て「候補1件日は切る」というgateへ昇格しない。

### 5. body_pctは両不調halfで高いが、新gateには使わない

bad-half averageはgood-half averageよりbody_pctが約+0.18高い。これは共通clueだがcandidate-level featureであり、現在のPhase-2では新ranker/candidate gate探索を停止しているため、**監査所見に留める**。

## Round2 disposition

**NOT ACTIVATED / NO NEW GATE.**

2023H2と2025H2を同時に説明できる単純なcausal market-level variableがまだ見つかっていない。結果を見た後に別thresholdを追加するのは避ける。

次のhigh-information check:
1. preserved model metadata / training counts / model_periodがあれば、2022 warm-up/calibration差をoutcome-blindで監査。
2. candidate count / single-candidate shareとmodel_period/tail_p分布を月次で監査し、scarcityがmodel maturity由来かpopulation由来か切り分ける。
3. 2025H2についてはbreadth弱化とは別タイプのmarket-level regime候補が事前に理論付けできる場合のみRound2 preregへ進む。

## Current decision

- DUAL_TOP1_AGREEMENT: primary structural baseline
- G3 NO_ACUTE_SELLOFF: right-tail / mean改善候補だが勝率解決策ではない
- 2022 fresh validation: FAIL for stability
- Round2: CLOSED pending causal explanation
- Production: **NO-GO**
