# TV-Free研究の再監査と初版構築計画 — 正式改訂版 R2

更新: 2026-09-12。review_inputs/review_01.md、review_02.mdの全文を採用し、後者を優先する。本書は以前の計画・全件選出の固定仕様を置き換える。以下は実装のための整合補足。研究担当はgpt-5.6-luna / xhigh。

## 実行範囲・使用量停止

専用worktree screening-bot-tvfree-batch01、branch research/tvfree-canonical-batch01だけで作業。起点SHA 1dbad32e7e8030cb25a3864ef77d1b6cca6207a7、V29参照SHA 46ee456bc30a33fd98f8b642b364431d60badd6f。本番main/Discord/Sheets/GAS/TradingView/本番workflow/既存スケジュール/secretsは変更禁止。新規課金・外部送信・自動再開automation禁止。重い計算はローカル1ジョブずつ。旧再現コードを改造して旧結果の意味を変えない。

最優先: 週次残量が50%未満になったら停止・報告し、本人の明示再開指示まで中断。境界の超過を避け50%ちょうどでも次の単位を始めない。EXECUTION_CONTROL.jsonのbudget_pause_latchedを永続化する。枠リセットや自動goal継続で解除しない。

開始・継続ターン冒頭、計算単位/各milestoneの前後、作業中は原則60秒以内ごとにCodex app get_usage_limitsを読む。10080分週次窓のremaining=100-usedPercentを使い、複数の適用週次枠では最小値を採る。取得不能なら推測せず新しい重い単位を保留。停止時は自分のジョブをcheckpoint/停止し、再開位置保存と報告だけを行う。usage中断を研究完了や候補不成立と呼ばない。goalツールはpause/resumeを提供しないため、状態をcomplete/blockedに偽装せず永続ラッチで継続ターンも止める。

## M1 — Canonical foundation

まずartifact 10148332198（V29、確認時期限2026-09-24）、10264205130（run80日足）、10264251140（V7 Tail cache）を保全し、run/SHA/zipとmember hash/範囲/取得日時を保存する。実行中Actionsを中断・重複実行しない。データはignored .cache/へ。時点別membership、上場廃止価格、分割調整、コード再利用、営業日欠損、価格/volume単位を監査し、無料取得範囲を全東証検証完了と呼ばない。

レイヤーはscanned_universe → eligible_universe → candidate_pool → ranked_candidates → actually_selected。candidate_poolはfamilyが結果前に登録したprefilter通過集合。MLで全eligible銘柄にscoreを付けてもpoolと混同しない。後付けgate禁止。poolはcooldown前の全件をParquet等で保存する。JSONはmanifest/spec/hash/summary/decisionに使う。

保存項目はcandidate_id、family、spec hash、date/decision timestamp、symbol、raw rank/score、component scores、tie-break、signal-time features、inclusion reason、exclusion flags、planned entry、daily candidate_count。将来価格/return/label成熟情報は別テーブル。selection hashにfuture列を含めない。

entryは判定日の次の東証営業日open、exitはentryを1日目とする5営業日目close。銘柄の観測行5行shiftで代用しない。欠損・未約定・売買停止・価格制限は明示し、後から候補削除/差替えしない。未解決行を除いた平均だけでPASSにしない。

情報は判定時刻までに確定・利用可能な値。引け後には当日close/volume/市場統計も利用可。market_feature_lagはfamily登録時に固定: Monster canonical=1、再構成First Reversal=1、新Core3系統=0。結果を見てlagを選び直さない。旧ソースlag0の再現は別IDとしlag1 canonicalと混同しない。新volume ratioの分母は前完了営業日の平均（当日除外）、旧inclusive式は旧再現専用。

evaluatorはSignal-level、Daily cohort（同日選出を等ウェイトした5BD品質）、Portfolio simulationを別物として出す。cohortをportfolio returnと呼ばない。欠損labelのcohortを黙って残存銘柄だけへ再加重しない。portfolioは凍結candidate+policy成立時のみ、レバレッジなし/5つの日次資金枠/当日枠を選出に等配分/未約定分は現金/同銘柄別lotで追跡。

全poolとpolicyにn、active days、候補数/日、mean/median/win、draw件数、+10/+20/+50/-10/-20、Top1/Top3 winner除外、最良月/週/銘柄除外、集中度、週block bootstrap、purged WF、費用0/0.5/1%往復、再現性と計算複雑性を出す。win分母は0%draw除外。0.5%は研究仮定で実測費用ではない。

raw poolのRank1/2/3/4/5/6+品質とpolicy評価を分ける。完全なrank単調性は必須にしない。MonsterはTop3内+20/+50 winner包含率、winner平均rank、N拡大時loss増加も評価。candidate_count帯1/2–3/4–5/6+は診断のみ、新count gateを同バッチで作らない。相関には時系列サンプル/定義が必要で、各銘柄に1つだけの5BD値から相関を捏造しない。PIT業種/テーマ不足はINCONCLUSIVE。

M1のtestsはfuture perturbation/hash、2026探索拒否、calendar/年越/cooldown、poolとselection分離、独立policy state、raw/policy rank、欠損no replacement、分割/identity/cost/draw、partial cohort、restart同値、認証無しlocal dry-run。現存selection.py/test_selection.pyはR2前の未検証試作。誤ったcooldown期待値と日本の休日fixtureを修正してからPASSとする。M1 PASSまで新規モデル研究を始めない。

## M2 — Existing candidate audit

V29: 350銘柄制限を外したV40悪化が降格の主要証拠。+4.86%をfull-universe成績へ継承しない。Stable列の存在、実際のfit/predict入力、label/filter/rank/meta利用を分け、呼出経路と成果物/モデル特徴名で監査する。列の存在だけで依存と断定しない。歴史的証拠とarchitecture参考として保全する。

Monster: V7 extreme Tail、lag1市場median_ret5<=0、ret10<=0.5735294117647058、volr20 ASC→tail_cdf DESC→tail_p DESC→symbol ASC。poolはTop1や旧top4に切らない。ret10は小数リターンの約+57.35%。既存v20に記載された2023 V18 consensus集合を当時の仕様で再生成してmedianを照合し、一致ならVERIFIED、不一致ならUNVERIFIED/implementation drift。由来の復元とlag1新canonicalを混同しない。2023閾値を2022へ遡及した値は時間順検証にしない。

First Reversal: 原実装/成果物を一巡探索、未回収ならfirst_reversal_reconstructed_v1。prefilterはmarket lag1 median_ret5<=-0.01、ret5∈[-0.08,0]、ret1∈[0.005,0.08]、ret10<=0.12、volr20<=1.8。rank=ret1-ret5/5 DESC。discoveryの>=+10% winner対<=-10% loserを判定時点featuresで分析し、最大2特徴をdiscoveryで固定。2024は方向確認のみ。low-volume vetoは過去分布下位20%、固定0.39への合わせ込み禁止。

family一次判定はdiscovery pool自体のsignal/cohort品質で行う。Core KEEPは費用0.5%でsignal/cohort平均・中央値とTop3 winner除外平均が正。Monster KEEPはsignal/cohort平均が正、+20 winnerが2銘柄以上、同条件eligible-universe参考比mean/+20改善。poolを自分自身より厳密に上回るという不可能なゲートにはしない。データ/由来不足はINCONCLUSIVE。これらは結果前にspec化し、REJECT familyをM4で救済しない。

## M3 — Registered Core Batch

最大3family、各1登録仕様。prefilter/features/model/lag/target/rank/tie-breakを結果前に保存する。
1. 中型期待値: target=min(return5,0.30)の低複雑度回帰、負側clipなし。結果後に上限20/40%へ変えない。
2. PIT業種先行と個別遅行追随。PIT業種不足はINCONCLUSIVEで枠消費。
3. ret20>0かつret5<0の秩序ある押し目。先行上昇経路効率とvolume収縮を等ウェイトrank。
既棄却と同等ならREJECT_DUPLICATE、別案を補充しない。M3もdiscoveryだけでfamily仮判定。

## M4 — Selection-count study / 開封順

KEEP以上のfamilyだけTop1/2/3/5を比較する。Candidate Pool equal-weightはreferenceであり、後付けscore/rank gateや追加Top Nは作らない。Nごと・laneごとに独立stateで営業日順にpool→cooldown→ranking→Top N→選出symbolのみstate更新。前東証営業日にそのpolicyで選ばれたsymbolを除外、年/foldをまたいで状態維持。raw rankとcooldown後rankを分ける。候補ゼロは見送り。

Ranking Value Addは同family/generation条件/active datesのpool全件等ウェイトと比較。raw pool active dates、policy active dates、cooldown見送り日を別記録し、直接比較は共通active datesで行う。baseline poolをTop Nの件数に合わせて切らない。policy自身の全期間成績も併記する。

milestone順とblind順の整合: M2/M3はdiscoveryでKEEP仮判定 → M4もdiscoveryでN/仕様をlockしhash保存 → 2024確認（仕様変更禁止）→ 2025 locked replay → 2026 reporting。M2/M3で2024/2025を見てからM4でNを選ばない。旧保存成果の監査は新実験の開封から区別する。

policy通過: Coreはnet signal/cohort平均・中央値・Top3除外が正、同active-date pool比cohort平均改善、loss10/loss20悪化なし。Monsterはnet平均正、pool比mean/+20改善、+20 winner2銘柄以上。Monster median/Top3/局面依存は必須vetoにしない。通過policyはdiscovery cohort平均DESC、同値は小Nで1つlock。未通過ならSELECTION_COUNT_UNRESOLVED。2024で再現しなくても別Nへ切替しない。Core平均月5件は全月分母の別フラグ。

2022H1 warm-up、2022H2–2023 discovery、2024 pseudo-OOS/directional confirmation、2025 locked historical replay、2026 reporting only、freeze後の新営業日 true forward。過去期間は露出済み、true OOSと呼ばないが実行内開封順を厳守する。fit/transforms/imputation/feature/policy selectionはtrain側のみ、purgeはlabel利用可能時刻。登録済み月次更新を2025で使う場合は過去成熟labelのみ、仕様選択は禁止。2026は2025末までの成熟labelで係数/CDF固定しfitしない。

## M5 — Freeze and dry run

成立candidate+policyを凍結、固定過去日/最新利用可能日でローカル実行。未成立ならNO_VIABLE_CANDIDATE/SELECTION_COUNT_UNRESOLVEDを明示して基盤を納品。実装PASS、研究成績、データ/由来の完全性、頻度、RETROSPECTIVE_PROVISIONAL証拠レベルを別列にする。本番適格と呼ばない。成立時だけportfolio simulationを実行する。

CLIはaudit/experiment/screen/evaluate/report。全必要テスト、再開時同値、本番差分なしを検証。候補データと評価を分離し、認証不要のローカル試運転を提供する。

## M6 — Fundamental readiness / migration plan

別Fundamental branchはread/fetch/SHA固定/artifact参照のみ、編集/merge禁止。research/fundamental_v2/HANDOFF.jsonがあれば読む。無ければTV-Free側のimport/snapshot contractで対応。fields: status/rubric_version/commit_sha/reproducibility_pass/source_extraction_pass/point_in_time_ready/artifact_paths/source_data_hashes/updated_at/blockers。

3 readinessが全てtrue、SHA固定と証拠確認済みの場合だけ予測研究へ進む。固定facts 3x3PASSを独立抽出PASSにしない。不足ならinterface/readiness/provenance/blockersまで完成させ技術研究を継続。条件成立時は事前登録したfinancial-risk veto、dilution veto、score rankingを単独で最大3比較、後付け複合探索禁止。

true-forward記録、将来Stable比較（実在first-FINALのみ、異なるtimingは参考表）、本番移行/切戻し、残データ不足を設計する。本番移行は実行しない。

## 完了条件

各milestoneでcommit、artifact manifest、追記ledger、resume pointを保存し研究branchへpushする。台帳にID/SHA/data/spec hashes/仮説/期間/params/全結果/decision/reason/commandを記録する。最終比較はレビュー01の項目一覧を満たす。pool/rank/policy比較、選出数推奨または未確定、Ranking Value Add、Fundamental readiness機械判定を含める。必要なengine/tests/全登録実験判定/保存/同期が未完了ならgoal完了にしない。利用残量による中断は未完了のままラッチ保存する。
