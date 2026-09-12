先ほどの修正指示を採用するが、Goal開始前に以下をさらに反映すること。以下は前の指示より優先する。

## 1. Candidate Poolの定義

「全候補保存」とは東証全銘柄を毎日候補として保存するという意味ではない。

各candidate familyについて、結果を見る前に定義したeligibility / prefilterを通過した集合を `candidate_pool` とする。

以下を明確に区別する。

* scanned_universe
* eligible_universe
* candidate_pool
* ranked_candidates
* actually_selected

ML等でeligible universe全体へscoreを付与する場合も、UniverseとCandidate Poolを混同しない。

候補本体の大量データは原則Parquet等の再現可能な表形式で保存し、JSONはmanifest、spec、hash、summary、decision等へ使用する。

---

## 2. Top N比較は研究対象だが、自由探索にしない

選出数は事前固定しない。

ただし比較するpolicyは以下に限定する。

* Top1
* Top2
* Top3
* Top5
* Candidate Pool equal-weight reference

結果を見た後にTop4、Top6、Top7等を追加しない。

候補ロジック自体に事前登録されたscore gateが存在しない限り、結果を見て新しいscore thresholdを追加してはならない。

「固定score/rank gateを後から探す」という選択肢は削除する。

---

## 3. 選出数決定もモデル選択として凍結する

Top1/2/3/5の比較はdiscovery期間で実施し、最終selection policyを決定する。

決定後は2024以降の結果を見て変更しない。

2024で明確に再現しなければ、

`SELECTION_COUNT_UNRESOLVED`

としてよい。

2025/2026を使ってTop Nを選び直さない。

---

## 4. Top Nごとにcooldownを独立シミュレーションする

重要。

Top1運用とTop3運用では選出された銘柄集合が異なるため、翌営業日のcooldown stateも異なる。

したがって、

「同じ日のranked candidate tableから単純に上位N件を切り出して全期間評価する」

だけでは不十分。

Top1 / Top2 / Top3 / Top5それぞれについて、営業日順に独立したportfolio-selection stateを持ち、

1. 当日のcandidate pool生成
2. cooldown適用
3. ranking
4. Top N選択
5. 選択されたsymbolだけcooldown state更新
6. 次営業日へ進む

という因果的simulationを行う。

candidate poolそのものはpolicy間で保存・比較可能にする。

---

## 5. Ranking診断とSelection Policy評価を分ける

cooldownとは独立して、raw candidate pool上の順位品質も診断する。

Rank1 / Rank2 / Rank3 / Rank4 / Rank5 / Rank6+について将来成績を集計する。

ただし、

Rank1 > Rank2 > Rank3 > ...

という完全な単調性を合格条件にはしない。

Coreでは順位単調性を重要指標とする。

Monsterでは、

* Top1精度
* Top3内への+20/+50%以上winner包含率
* winnerの平均rank
* Top Nを広げた時のloss増加

を別途評価する。

MonsterはRank2/3に巨大winnerを継続的に含む構造でも成立し得る。

---

## 6. Candidate Pool baselineを同条件で比較する

rankingの価値を評価する際は、

同じstrategy family、同じactive date、同じcandidate generation条件

から得たcandidate poolと比較する。

異なる日・異なるeligibilityの母集団と比較しない。

最低限、

* candidate pool equal-weight
* Top1 policy
* Top2 policy
* Top3 policy
* Top5 policy

を比較する。

これを `Ranking Value Add` として記録する。

---

## 7. Signal-level / Daily cohort / Portfolioを区別する

以下を混同しない。

### Signal-level

各選出銘柄を独立signalとして評価。

### Daily cohort

同日に選出したTop N銘柄の5BD returnを等ウェイトして、その日の候補品質を評価。

これは候補数の多い日によるsample dominationを確認する診断。

### Portfolio simulation

資金、同時保有、5BDのポジション重複、売買コストを考慮した実運用シミュレーション。

Daily cohortをportfolio returnと呼ばない。

今回の研究バッチではSignal-levelとDaily cohortを全候補へ算出する。

Portfolio simulationは、最終的に凍結候補とselection policyが成立したものについてのみ行う。

---

## 8. Candidate Count診断は探索に使いすぎない

候補数、

* 1
* 2〜3
* 4〜5
* 6+

等と将来成績の関係は診断してよい。

ただし、この結果から新しいcandidate-count gateを今回の同じバッチ内で作成しない。

有望なら次の事前登録実験の仮説として残す。

今回の候補成績を救済するための後付けfilterにはしない。

---

## 9. market_feature_lagは実験前に固定

共通原則：

判定時刻までに確定済みの情報だけ使用できる。

ただし `t` と `t-1` のどちらを使うかを結果確認後に選んではならない。

各candidate familyのexperiment spec作成時に、

`market_feature_lag = 0`

または

`market_feature_lag = 1`

を固定してから実行する。

Monster canonical再現は既存仕様どおりprevious-business-dayを使用する。

---

## 10. 歴史データの証拠レベルを明確化

今回の期間名称は以下とする。

* 2022H1: warm-up
* 2022H2〜2023: discovery
* 2024: pseudo-OOS / directional confirmation
* 2025: locked historical replay
* 2026: reporting only
* spec freeze後の新規営業日: true forward

ただし、今回の新仮説自体が過去の研究結果を踏まえて考案されているため、2024/2025を統計的に完全な未観測OOSとは表現しない。

この実行内でのblind opening protocolは厳守するが、

`true out-of-sample evidence`

という表現はspec freeze後の未来データにのみ使用する。

---

## 11. Fundamental連携は技術研究をブロックしない

Fundamental V2 HANDOFF contractの導入は維持する。

ただしFundamentalのpoint-in-timeデータが未完成なら、TV-Free技術研究を待機させない。

今回Goal内では、

* handoff interface
* readiness判定
* provenance
* blocker一覧

まで完成すればよい。

`point_in_time_ready=true`になった場合だけFundamental predictive-value研究を開始する。

Fundamental研究の都合でCore / Monsterのcanonicalizationを遅延させない。

---

## 12. GoalをMilestone化する

1つのGoal内で以下の順序を固定する。

### M1 — Canonical foundation

データ、timestamp、target、membership、hash、evaluator、selection/evaluation分離を完成。

M1がPASSするまで新規モデル研究へ進まない。

### M2 — Existing candidate audit

V29、Monster、First Reversalを監査。

旧仕様結果とcanonical結果を分離。

### M3 — Registered Core Batch

事前登録した最大3系統だけを実行。

失敗した枠を別名で追加しない。

### M4 — Selection-count study

M2/M3でKEEP以上となったcandidate familyだけについてTop1/2/3/5を比較。

REJECTされたモデルについて選出数最適化を行わない。

### M5 — Freeze and dry run

候補・selection policyを凍結。

候補がなければ `NO_VIABLE_CANDIDATE`。

### M6 — Fundamental readiness / migration plan

Fundamental handoff状態、forward記録方式、将来比較、本番移行・切戻し計画を完成。

各Milestone終了時にcommit、artifact、ledger、resume pointを保存する。

---

## 13. 選出数研究を弱いモデルの救済に使わない

重要。

candidate family自体がCore / Monsterの最低研究基準を満たさない場合、

「Top3なら良いかもしれない」
「Top5なら大化けが入る」

として延命しない。

まずcandidate generation / ranking architectureそのものに一定の信号があることを確認する。

選出数研究は、

**有望候補の運用方法を決める二次研究**

であり、

**失敗した候補を救う最適化手段ではない。**

---

## 14. 最終的な設計思想

研究段階では情報を捨てない。

そのためcandidate poolは全件保存する。

しかし運用policyは無制限探索しない。

Candidate generation
→ Ranking
→ Selection count
→ Portfolio construction

を別レイヤーとして評価する。

最終目標は、

「バックテストで一番良くなるTop Nを探すこと」

ではなく、

**候補集合そのものに予測力があり、rankingに付加価値があり、その上で再現可能な選出数policyを決められるかを確認すること。**

以上を正式計画へ反映してから最初のTV-Free Goalを開始すること。
