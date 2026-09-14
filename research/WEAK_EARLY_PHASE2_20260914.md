# WEAK+EARLY Phase 2 — 2026-09-14

## Purpose

中締めで選出した以下3条件を基盤に、広い新規探索を止めて低自由度の構造改善だけを行う。

- body_pct LOW
- volr20 LOW
- mean-rank(volr20, body_pct)

共通固定条件:
- market: previous-session med_ret5 <= 0
- candidate: ret10 <= 0.5735294117647058
- one candidate/day
- endpoint: next XTKS open -> fifth XTKS close
- transaction cost: **0%**
- 2026 outcomeは選択に使わない

## Frozen baselines

| Candidate | 2023-2025 n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% |
| volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% |
| mean-rank(volr20, body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% |

## First Phase-2 structural candidate

### DUAL_TOP1_AGREEMENT

Definition:
1. 固定weak+early gateを通過した同日候補を作る。
2. body_pct ascendingでTop1を決める。
3. volr20 ascendingでTop1を決める。
4. **2つのTop1が同一symbolの時だけ採用**。
5. 不一致日はNO TRADE。
6. tie-breakは既存tail_p descendingをそのまま使用。
7. threshold / feature weighting / cooldown / endpointは変更しない。

Rationale:
- 既存の強い2 rankerの同意だけを使う低自由度confidence gate。
- 追加の連続閾値探索をしない。
- 既存結果を見て不一致日に別ルールを差し込まない。

### Result — cost 0%

| Period | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 | 103 | +6.88% | +1.39% | 53.40% | 29.13% | 18.45% | 8.74% | 27.18% | 8.74% | +5.86% | +3.86% |
| 2025 | 37 | +7.97% | -2.40% | 48.65% | 37.84% | 18.92% | 8.11% | 29.73% | 8.11% | +4.58% | -0.06% |
| **2023-2025** | **140** | **+7.17%** | **+1.25%** | **52.14%** | **31.43%** | **18.57%** | **8.57%** | **27.86%** | **8.57%** | **+6.28%** | **+4.79%** |

Comparison:
- mean-rank baseline mean +6.89% -> agreement +7.17%
- body baseline mean +6.54% -> agreement +7.17%
- 2025 mean-rank +6.09% -> agreement +7.97%
- signal count 172 -> 140

Interpretation:
- performance-firstでは有力なPhase-2候補。
- ただし2025 medianは依然negativeで、2025H2 win rateは低い。
- よって「銘柄順位の一致」は改善するが、regime問題は完全には解決しない。

## Half-year stability

| Half | n | Mean | Median | Win |
|---|---:|---:|---:|---:|
| 2023H1 | 24 | +11.34% | +4.11% | 62.50% |
| 2023H2 | 22 | +0.21% | -2.91% | 36.36% |
| 2024H1 | 26 | +8.29% | +4.86% | 65.38% |
| 2024H2 | 31 | +6.97% | -0.65% | 48.39% |
| 2025H1 | 22 | +8.05% | +5.84% | 59.09% |
| 2025H2 | 15 | +7.85% | -7.29% | 33.33% |

Key finding:
- 共通弱点は2023H2 / 2025H2。
- 次の主題は「rankerの追加探索」より**causal market-regime / NO-TRADE判定**。

## Exploratory regime check

Outcomeを見た後の探索なのでpromotion evidenceではなく、方向確認のみ。

- DUAL_TOP1_AGREEMENT + breadth_ma20 <= 0.5:
  - 2023-2025 n=95 / mean +6.39% / median +0.97% / win 50.53% / Top3-ex +2.83%
- mean-rank + breadth_ma20 <= 0.5:
  - 2023-2025 n=113 / mean +6.98% / median +1.12% / win 51.33% / Top3-ex +4.02%

Disposition:
- breadth_ma20<=0.5単独overlayは全期間で明確な改善ではないためPROMOTEしない。
- threshold grid searchもしない。

## Next frozen actions

P0:
1. DUAL_TOP1_AGREEMENTをPhase-2 primary challengerとしてfreeze。
2. body / volr20 / mean-rank / DUAL_TOP1_AGREEMENTの4本を0% costでdashboard比較。
3. 可能なら**2022をfresh validation期間として再構築**し、4本を一切retuneせず適用する。
4. 2022生成に必要なpreserved causal generatorが無い場合はfail-closedし、別ロジックで代用しない。

P1:
- 2023H2/2025H2の共通不調を説明できるoutcome-blind causal regime featuresを少数だけ監査する。
- gate候補は事前に少数固定し、連続threshold searchをしない。
- candidate-level featureの追加ranker探索は停止。

P2:
- V47が実rawを出した場合は0% cost diagnosticだけ比較表へ追加。

## Current Phase-2 rank

1. **DUAL_TOP1_AGREEMENT** — primary challenger, mean +7.17%
2. mean-rank(volr20, body_pct) — baseline leader, mean +6.89%
3. body_pct LOW — right-tail baseline
4. volr20 LOW — central-tendency/stability comparator

これはfinal production GOではない。
