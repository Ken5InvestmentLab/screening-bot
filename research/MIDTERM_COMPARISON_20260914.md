# TV-Free研究 中締め比較 — 2026-09-14

## 方針変更
ユーザー明示承認により、未開封H1/H2/outcomeは中締め診断目的で開封可とする。
開封済み期間は以後 untouched holdout と扱わず、診断結果を見て同familyをretuneしない。
正式promotion判定と `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` は分離する。

## コスト方針
ユーザー明示指示により、**今後の全バックテスト・比較・ランキングは取引コスト0%で統一**する。過去に0.5% costで記録された値は監査用legacy evidenceとしてのみ残し、新しい順位付けには使わない。

## 暫定ランキング（実観測performance優先）

### 1. weak+early + body_pct LOW
- 母集団: preserved causal V7 extreme-Tail
- fixed gate: med_ret5 <= 0, candidate ret10 <= 0.5735294117647058
- same-day rank: body_pct ascending, Tail score tie-break
- 1 candidate/day, 1 XTKS business-day same-symbol cooldown
- endpoint: next XTKS open -> fifth XTKS close
- **cost: 0%**
- 2023-2024: n=128, mean **+6.46%**, median **+1.25%**, win **52.34%**, +10 **29.69%**, +20 **17.97%**, +50 **7.81%**, -10 **28.12%**, -20 **7.81%**, Top1-ex **+5.64%**, Top3-ex **+4.03%**
- 2025 descriptive: n=44, mean **+6.78%**, median **-3.76%**, win **45.45%**, +10 **36.36%**, +20 **20.45%**, +50 **6.82%**, -10 **31.82%**, -20 **6.82%**, Top1-ex **+3.92%**, Top3-ex **+0.03%**
- 2023-2025 total: n=172, mean **+6.54%**, median **+0.99%**, win **50.58%**, +10 **31.40%**, +20 **18.60%**, +50 **7.56%**, -10 **29.07%**, -20 **7.56%**, Top1-ex **+5.82%**, Top3-ex **+4.60%**
- Midterm disposition: CURRENT BEST OBSERVED IMPLEMENTABLE CONDITION pending direct comparison with combined-rank stability.

### 2. weak+early + volr20 LOW
- same base/gate/cooldown/endpoint; rank volr20 ascending.
- **cost: 0%**
- 2023-2024: n=128, mean **+6.24%**, median **+1.06%**, win **52.34%**, +10 **29.69%**, +20 **18.75%**, +50 **8.59%**, -10 **25.78%**, -20 **7.81%**, Top1-ex **+5.41%**, Top3-ex **+3.81%**
- 2025 descriptive: n=44, mean **+6.58%**, median **+0.37%**, win **50.00%**, +10 **36.36%**, +20 **18.18%**, +50 **6.82%**, -10 **31.82%**, -20 **6.82%**, Top1-ex **+3.71%**, Top3-ex **-0.19%**
- 2023-2025 total: n=172, mean **+6.33%**, median **+1.06%**, win **51.74%**, +10 **31.40%**, +20 **18.60%**, +50 **8.14%**, -10 **27.33%**, -20 **7.56%**, Top1-ex **+5.60%**, Top3-ex **+4.38%**
- Midterm disposition: VERY CLOSE SECOND; 2025 win/median are stronger than body_pct LOW, but tail-exclusion is slightly weaker.

### 3. weak+early + mean-rank(volr20, body_pct)
- same base/gate/cooldown/endpoint; within-day rank(volr20 ascending)とrank(body_pct ascending)の平均が小さい順。
- **cost: 0%**
- 2023-2024: n=128, mean **+7.16%**, median **+1.81%**, win **54.69%**, +10 **31.25%**, +20 **19.53%**, +50 **8.59%**, -10 **25.78%**, -20 **7.81%**, Top1-ex **+6.35%**, Top3-ex **+4.75%**
- half-year means: 2023H1 +9.07%, 2023H2 +0.21%, 2024H1 +10.41%, 2024H2 +6.92%
- 2025: n=44, mean **+6.09%**, median **-4.04%**, win **45.45%**, +10 **34.09%**, +20 **18.18%**, +50 **6.82%**, -10 **34.09%**, -20 **6.82%**, Top1-ex **+3.20%**, Top3-ex **-0.71%**
- 2023-2025 total: n=172, mean **+6.89%**, median **+1.45%**, win **52.33%**, +10 **31.98%**, +20 **19.19%**, +50 **8.14%**, -10 **27.91%**, -20 **7.56%**, Top1-ex **+6.17%**, Top3-ex **+4.95%**
- Midterm disposition: strongest gross average and 2023-24 win rate; 2025 central tendency/Top3 robustness is weaker than volr20 LOW.

### 4. V29 fixed_min98_both
- historical non-annual reference: n=35, mean +4.86%, median +2.90%, win 55.88%, +10 31.43%
- target/population differs (signal-close -> fifth close; historical 350-name watchlist) and inputs are no longer replayable.
- Midterm disposition: strong historical reference, not current directly deployable winner.

### 5. Old Cloud Monster Priority A
- full historical: n=63, mean +9.86%, median +3.33%, win 57.1%, +20 30.2%, +30 19.0%, -10 22.2%, Top5-ex +4.03%
- development era Mar-Jun 2026: n=46, mean +11.99%
- later Jul-Aug block: n=17, mean +4.09%, median +1.95%, win 52.9%, +20 11.8%, -10 17.6%, Top1-ex +0.86%, Top3-ex -2.13%
- exact probability model is lost; 2025 frozen surrogate A-like selection n=69 mean -1.36%.
- Midterm disposition: useful clue, not implementable as-is.

### 6. weak+early × V31 full-JPX
- pre-2026 Next Open->5BD: n=69, mean +3.77%, robust +3.43%, median +0.88%, win 54.5%, +10/+20/+50 26.1/14.5/1.45%, -10/-20 14.5/2.90%, Top1/Top3-ex +2.97/+1.76%
- severe regime concentration: April 2025 n=20 mean +12.92%; excluding April overall mean about +0.04%.
- Midterm disposition: aggregate attractive but too regime-dependent.

### 7. V12 Emergency Reversal
- 2025 H1: n=1,874, mean +2.13%, median +1.82%, win 62.06%, Top1-ex +2.09%
- H2 frozen-path diagnostic: n=2,475, mean -1.249%, median -1.197%, win 35.92%, Top3-ex -1.363%
- Midterm disposition: rejected by cross-half degradation.

### 8. V20 Session-Impulse — newly unsealed midterm diagnostic
Source:
- raw repaired artifact id 10327932766 from run 34791959735
- canonical daily artifact id 10264205130 from run 34599959356; SHA 6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0
- exact frozen signal/rank/selection/label semantics reproduced; only raw coverage acceptance gate bypassed.
- known missing active symbol/date pairs: 734.

0% cost diagnostics:
- Top1: n=156, mean **-1.346%**, median **-2.627%**, win **35.90%**, +10 14.74%, +20 7.69%, +50 2.56%, -10 24.36%, -20 10.26%, Top1-ex -1.860%, Top3-ex -2.669%
- Top2: n=307, mean **-1.573%**, median **-1.294%**, win **40.07%**, +10 11.40%, +20 4.89%, +50 1.30%, -10 19.87%, -20 8.14%, Top1-ex -1.834%, Top3-ex -2.241%
- Top3: n=442, mean **-1.118%**, median **-1.289%**, win **40.05%**, +10 11.54%, +20 3.85%, +50 1.13%, -10 17.19%, -20 5.88%, Top1-ex -1.298%, Top3-ex -1.613%
- Top5: n=705, mean **-0.538%**, median **-0.955%**, win **41.84%**, +10 10.07%, +20 3.55%, +50 1.13%, -10 14.33%, -20 3.97%, Top1-ex -0.650%, Top3-ex -0.854%
- Midterm disposition: DEPRIORITIZE. Missing coverage could change exact ranking, but all TopN remain negative even at 0% cost. Missing coverage could change exact ranking, but all TopN are sufficiently negative that V20 no longer deserves rank #2 based only on pipeline cleanliness.

### V47
- clean Daily PIT PASS.
- original raw1H run has zero usable symbol-dates; performance is physically not computable from that artifact.
- retry 34810592135 is active.
- Midterm disposition: NOT_COMPUTABLE_NO_INPUT_DATA until retry emits real raw data. Once available, diagnostic performance may be opened even if formal coverage acceptance fails.

## Midterm decision
1. Broad blind exploration should STOP.
2. Current observed winner: weak+early + body_pct LOW.
3. Keep volr20 LOW as the simple comparator; combined rank is high-upside but less 2025 Top3-robust.
4. Continue only high-information checks:
   - compare body_pct LOW / volr20 LOW / combined rank under the already-reproduced 0% cost canonical row-level metrics;
   - finish V47 retry and open diagnostic performance immediately when input data exists;
   - old Cloud exact recovery only if genuinely new source evidence makes exact reconstruction possible.
5. V20 is deprioritized by the newly opened diagnostic.
6. Core rejected families and new adjacent heuristic generation stay closed.
