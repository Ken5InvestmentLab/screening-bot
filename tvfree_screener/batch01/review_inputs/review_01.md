現在作成済みの「TV-Free研究の再監査と初版構築計画 — Luna xhigh・最初のgoal」は基本方針として採用する。

ただし、Goal実行前に以下の修正を反映し、修正版を研究計画の正式版とすること。

この修正は研究範囲を無制限に拡大するものではない。過学習・仕様混在・候補取りこぼしを防ぎ、Core / Monsterの最終運用仕様を研究結果から決められるようにするための変更である。

---

# 1. V29の扱いを修正

現在の計画ではV29について、

「stable_scoreが入力にあり、旧Stable依存なので独立Core条件に合わない」

という趣旨が含まれているが、これは実際のモデル入力・特徴量利用を確認するまで断定しないこと。

最新HANDOFFから確実に言えるV29降格の主要根拠は、

* 350銘柄制限下のV29/V31では高い成績が出ていた
* しかし候補母集団制限を外したV40 full-universe fixedでは大幅に悪化した
* V29 min98の歴史的成績約+4.86%を、独立したfull-universe Coreの成績として継承できない

ことである。

したがってV29は、

**「歴史的に有用な研究証拠・アーキテクチャ参考」**

として保存・再現する。

`stable_score` 等のStable由来列については、

1. データ上存在するだけなのか
2. 特徴量としてモデルへ入力されたのか
3. ラベル・フィルタ・ranking・Meta等へ利用されたのか

をコードと成果物から監査すること。

実使用されていなければ「Stable依存」を降格理由にしない。

---

# 2. 「1日最大1銘柄」の固定を撤回

現在の共通仕様にある、

「Core・Monsterそれぞれ1日最大1銘柄」

は研究段階では固定しない。

これは今回の重要な修正点。

Core・Monsterともに、まず各判定日に条件を満たした

**全候補銘柄**

を順位付きで保存する。

候補生成と実運用上の選出数決定を完全に分離する。

研究時点でTop1だけを残してTop2以下を捨ててはいけない。

---

# 3. 全候補保存仕様

各判定日の全候補について最低限、

* candidate_id
* strategy / candidate family
* spec hash
* date / decision timestamp
* symbol
* rank
* raw score
* component scores
* tie-break情報
* signal-time features
* inclusion reason
* exclusion flags
* planned next trading day entry
* candidate count on that day

を保存する。

将来リターンはcandidate生成JSONへ書かず、評価工程の別成果物へ分離する。

selection hashには将来情報を含めない。

後日targetが成熟してもselection hashが変化しないことをテストする。

---

# 4. 選出数そのものを研究対象にする

全候補保存後、事前登録した以下の運用ポリシーを比較する。

最低限：

* Top1
* Top2
* Top3
* Top5
* 全候補
* 候補固有の固定score / rank gate

必要以上にTop Nの種類を増やさない。

結果を見てTop4、Top7、Top8等を追加し続けることは禁止。

Top1 / Top2 / Top3 / Top5 / 全候補を基本セットとして評価する。

---

# 5. 2種類の成績を必ず出す

複数候補を許容した場合、以下を分ける。

## Signal-level

各銘柄を1signalとして集計する。

例：

同日に3銘柄なら3件として扱う。

## Daily cohort-level

同一日に選出された銘柄を等ウェイトした1日分のポートフォリオとして集計する。

例：

3銘柄の5BDが

+30%
-10%
+10%

ならその日のcohort returnは+10%。

これにより、候補数が多い特定日だけが全体成績を過剰に支配することを防ぐ。

Core / Monsterとも両方表示する。

---

# 6. 順位品質を分析する

単純にTop1とTop3の平均だけ比較して終わらない。

最低限、

* Rank1
* Rank2
* Rank3
* Rank4
* Rank5
* Rank6+

について、

* n
* 5BD mean
* median
* win
* +10
* +20
* +50
* -10
* -20

を確認する。

特に、

**順位が下がるほど将来期待値が低下しているか**

を見る。

理想はRank1 > Rank2 > Rank3…という形。

順位別成績がランダムなら、ranking functionそのものが弱い可能性として記録する。

---

# 7. 「何銘柄採用するか」の判定もモデル選択扱いにする

Top1 / Top2 / Top3 / Top5 / 全候補のどれを最終採用するかも研究パラメータである。

したがって、

2025や2026を見てから最適Top Nを決めない。

選出数決定は原則、

2022H2〜2023 discovery

で候補を絞る。

2024でpseudo-OOS / directional confirmation。

2025はlocked historical replay。

2026はreporting only。

仕様凍結後の未来営業日を真正forwardとする。

選出数が2024で再現しない場合は固定しない。

---

# 8. CoreとMonsterの選出数は別でよい

最終的に、

Core Top1
Monster Top3

でも、

Core Top3
Monster Top1

でも構わない。

CoreとMonsterは目的が違うため、同じ最大銘柄数を強制しない。

またMonsterについては、

Rank1が外れてRank2/3に大化け銘柄が存在するケース

を重要視する。

Monsterの「候補集合としての右尾捕捉能力」と「Rank1精度」を分けて評価する。

---

# 9. 候補数そのものも特徴として分析

各日のcandidate_countと将来成績の関係を見る。

例えば、

* 候補1件だけの日
* 2〜3件の日
* 4〜5件の日
* 6件以上の日

で成績が違う可能性がある。

候補数が少ない日の方が強い場合、

「候補希少性」

がsignal confidenceとして使える可能性がある。

ただし2024/2025を見て細かいcandidate count閾値を最適化しない。

まず粗いbandで診断する。

---

# 10. 同日候補間の相関も確認

Top3やTop5を採用しても、全部同じテーマ・業種・値動きなら実質1銘柄と変わらない。

可能な範囲で、

* 同日候補の5BD return correlation
* 業種集中
* 同一テーマ集中
* market beta的集中

を確認する。

業種データがpoint-in-timeで安全に利用できない場合、その項目はINCONCLUSIVEでよい。

無理に現在の業種分類を過去へ適用しない。

---

# 11. 市場指標を一律「前営業日」に固定しない

現在の共通仕様にある、

「市場指標は前東証営業日の対象銘柄から計算」

は全候補共通ルールから外す。

今回の運用前提は、

**引け後に判定し、翌営業日始値でエントリー**

である。

したがって判定日の引けが確定しているなら、

* 当日close
* 当日volume
* 当日breadth
* 当日market median
* 当日cross-sectional statistics

は利用可能であり、因果的に問題ない。

新しい共通ルールは、

**「判定時刻までに確定した情報だけ利用可能」**

とする。

各candidate specに、

* market_feature_lag = 0
* market_feature_lag = 1

等を明示する。

---

# 12. Monster canonicalは前営業日仕様を維持

上記変更はMonsterの既存canonical specificationを勝手に変更するという意味ではない。

現在のMonster研究で重要な、

previous-business-day market `median_ret5 <= 0`

は、その候補仕様の一部として維持する。

旧Monsterの再現では必ずt-1市場情報を使用する。

新Core等では、仮説上必要なら判定日tの確定済み市場情報を利用してよい。

仕様ごとに明示すること。

---

# 13. 期間の名称を修正

2024もこれまでの研究で多数回参照されているため、「完全な未観測validation」と表現しない。

正式には：

* 2022H1：warm-up / feature preparation
* 2022H2〜2023：discovery
* 2024H1/H2：pseudo-OOS / directional confirmation
* 2025：locked historical replay / robustness confirmation
* 2026：reporting only
* spec freeze後の新しい営業日：true forward

とする。

2024や2025で良い結果が出ても、

「将来優位性を証明」

とは表現しない。

---

# 14. ただし各新仮説内部ではblind protocolを維持

既に2024/2025を人間が見ていることと、今回の新実験でデータリークしてよいことは別。

今回登録する新規Core仮説については、

2022H2〜2023で仕様決定
→
2024を開く
→
仕様変更禁止
→
2025を開く
→
仕様変更禁止

の順を機械的に守る。

結果ファイル生成順も可能ならこの順序を強制する。

---

# 15. Monster ret10閾値provenanceの扱い

`ret10 <= 0.5735294117647058`

は単なる由来不明値として扱わない。

既存コード `v20_consensus_early.py` には、

「2023 V18 consensus median ret10」

由来と明記されている。

したがって今回行うべきことは、

V18の2023 consensus candidate集合を再生成し、

`median(ret10)`

を再計算し、

0.5735294117647058

と一致するか確認することである。

一致したらprovenance VERIFIED。

一致しなければ、

UNVERIFIED / implementation drift

として扱う。

2025/2026を見てこの閾値を変更しない。

また、2023由来閾値を2022へ遡及適用した結果は正式な時間順validationとして扱わない。

---

# 16. Fundamental V2との受け渡しを機械化

現在の、

「各研究段階終了時にFundamental側branchを確認」

に加え、明示的なhandoff contractを導入する。

Fundamental側に可能なら、

`research/fundamental_v2/HANDOFF.json`

を作らせる。

最低限：

* status
* rubric_version
* commit_sha
* reproducibility_pass
* source_extraction_pass
* point_in_time_ready
* artifact paths
* source-data hashes
* updated_at
* blockers

を持たせる。

TV-Free側は各主要研究段階の終了時にこのファイルを確認する。

---

# 17. Fundamental統合開始条件

Fundamental predictive-value研究へ進むのは、

* reproducibility_pass = true
* source_extraction_pass = true
* point_in_time_ready = true
* 使用成果物SHA固定済み

の場合だけ。

採点器の再現性PASSだけでは予測研究へ入らない。

条件未達ならFundamental待ちでTV-Free研究全体を停止せず、

技術研究・CLI・評価器・候補監査を継続する。

---

# 18. Fundamental branchを勝手にmergeしない

別担当のFundamental branchを参照する場合、

* fetch/read
* SHA固定
* artifact参照

のみ。

TV-Free研究担当がFundamental branchのファイルを勝手に編集しない。

同じファイルを複数担当で編集しない。

必要ならcopy/import layerをTV-Free研究branch側に作る。

---

# 19. 新規Core最大3系統はそのまま維持

既存計画にある以下の3案は実行してよい。

1. 中型上昇期待値モデル
2. 同業群への遅行追随
3. 上昇トレンド中の秩序ある押し目

ただし候補生成後にTop1だけへ強制圧縮せず、全候補を保存した上でranking品質を評価する。

---

# 20. 中型上昇期待値モデルの注意

既存の安全性重視ML、

`P(+10%) - λ P(loss10)`

とは別系統として扱う。

今回の目的変数は、

上側のみ+30%程度でclip / winsorizeし、

大化け1銘柄がCore学習を支配することを防ぐ。

一方、負側は安易にclipしてリスク情報を消さない。

ただし目的変数の具体的定義は実験開始前に登録する。

結果確認後に+20%、+40%等へ変更しない。

---

# 21. Candidate universeとTop Nを混同しない

重要。

「候補生成条件を満たす全銘柄」

と

「運用で実際に採用するTop N」

を別物として扱う。

候補生成条件を厳しくして候補数を減らすことと、

ranking後にTop1へ絞ることは異なる。

両者の効果を混同しない。

---

# 22. ベースライン比較も候補集合単位で行う

Coreの比較対象として、

同じcandidate generation条件を満たした候補集合を等ウェイトした成績

を必ず出す。

これにより、

rankingが本当に価値を追加しているのか

を確認する。

例えば、

全候補等ウェイト +2.0%
Top1 +2.1%

ならrankingの付加価値はほぼない。

逆に、

全候補 +1%
Top1 +5%

ならranking functionに意味がある。

Monsterでも同様。

---

# 23. 研究通過基準へranking qualityを追加

既存のCore / Monster判定条件に加え、

**Ranking Value Add**

を別項目で記録する。

最低限：

* candidate pool equal-weight
* Top1
* Top3
* Top5

を比較。

Top Nが候補集合全体より改善しているかを見る。

ただしMonsterはRank2/3に巨大winnerを含むこと自体にも価値があるため、

Top1のみを唯一の成功条件にしない。

---

# 24. 最終的な通知銘柄数はGoal中に決めてよい

今回のGoal終了時には、

可能ならCore / Monsterごとに、

* 全候補内部保存
* ユーザー通知Top N
* 最大通知件数
* 見送り条件

の推奨仕様までまとめる。

ただし研究結果が弱ければ、

`SELECTION_COUNT_UNRESOLVED`

として次段階へ持ち越してよい。

無理にTop1/Top3等を決めない。

---

# 25. 全候補保存は本番通知件数を意味しない

研究データベース・JSONへ全候補を保存することと、

将来Discord等で全候補を通知することは別。

本番では最終的に選択されたpolicyだけ表示する。

研究では全候補を残し、後からランキング性能を監査可能にする。

---

# 26. 既存成果との整合

これまでの重要な知見は維持する。

### Monster

現時点の最重要方向：

* V7 extreme Tail detector
* weak market
* early / not overextended
* lower relative volr20
* lower relative ret1
* pre-exhaustion selection

特に、

`weak + early + volr20 LOW`

は引き続き重要な候補。

ただし新共通仕様へ移す際は旧成績をそのまま継承せず、canonical再評価する。

### Core

これまで弱かった／棄却した主な系統：

* global threshold micro-tuning
* safety-first linear ML
* simple Expansion
* simple Breakout
* quiet accumulation→ignition
* maximum Relative Strength chasing
* historical-performance Regime Switch

同じものを名前だけ変えて再試行しない。

### First Reversal

引き続き原実装回収を優先。

回収不能なら、

`first_reversal_reconstructed_v1`

として別ID。

low-volr VETOは固定0.39ではなく、過去データ分布のlower percentile方式で扱う。

---

# 27. 成果物の最終比較表

最終レポートでは最低限、

Candidate / Versionごとに：

* status
* provenance
* independent from Stable?
* discovery period
* pseudo-OOS
* locked replay
* reporting-only
* signal n
* active days
* candidates/day
* Top1 performance
* Top3 performance
* Top5 performance
* all-candidate performance
* daily cohort performance
* rank monotonicity
* mean
* median
* win
* +10
* +20
* +50
* -10
* -20
* Top1 winner exclusion
* Top3 winner exclusion
* best month exclusion
* best week exclusion
* symbol concentration
* bootstrap interval
* cost sensitivity
* complexity
* reproducibility
* data limitations

を比較できるようにする。

---

# 28. Goal終了条件を修正

既存6条件に加えて、以下を満たすこと。

7.

各成立候補について、全候補集合が保存され、Top1/Top2/Top3/Top5/全候補の比較が完了している、またはデータ不足理由が明記されている。

8.

Core / Monsterごとに最終的な1日選出数の推奨が決定されている、または `SELECTION_COUNT_UNRESOLVED` が明示されている。

9.

ランキングが候補集合に対してどれだけ付加価値を持つかが定量評価されている。

10.

Fundamental V2とのhandoff状態と、予測性能研究へ進めるかどうかが機械判定可能な形で保存されている。

---

# 29. 実行姿勢

この修正を反映した後は、再度ユーザー確認を求めず研究Goalを開始してよい。

ただし、

* 本番変更
* mainへのmerge
* production workflow変更
* production Discord送信
* production Spreadsheet書込み
* 新規課金
* secretのコード直書き

は引き続き禁止。

候補不成立も正常な研究結果として認める。

良い数字を出すためにTop N、閾値、期間、特徴量数を後付けで増やさない。

最終目的はバックテスト数字を最大化することではなく、

**TradingViewなしで、将来運用可能な独立したCore / Monster候補と、その再現可能な研究・実行基盤を完成させること。**

以上を既存計画へ反映し、修正版を正式な最初のTV-Free Goalとして実行してください。
