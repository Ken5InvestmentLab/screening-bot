# Codex → ChatGPT Cloud Monster / weak+early handoff — 2026-09-18

## 1. 今回実施したこと

`research/cloud-monster-recovery` を `origin/research/automation-coordination` の `cc08da7523e5037ff5575427fbf4b57bb590f4fd` から作成し、Git全ref/history、Actions、旧ChatGPT会話/Libraryまで調査した。weak+earlyは5 selectorを実行可能なexact packへ固定。Cloud Monsterは歴史的63行、19行saved-score比較、最終generatorを回収し、commit `bb597947`でhash固定した。repo/automation/productionには影響していない。

## 2. Cloud Monster exact復元状況

**`EXACT_ROWS_AND_FINAL_SELECTOR_RECOVERED / FULL_PIPELINE_REPRO_BLOCKED`**。63行は全headlineへexact一致し、19 saved-score rows、Watch式、52 feature順、imputer/scaler/logit、walk-forward objective、最終fit期間、threshold、tie/dedup/cooldownをsourceから回収した。合わせ込みはしていない。未回収は`cloud4h_frame_dedup_sep.pkl`のbuilder、上流1,314-symbol universe構築、next-open canonical bridge。

## 3. weak+early exact復元状況

**`WEAK_EARLY_EXACT_V1 / EXACT_REPRODUCED`**（保存済み2023-2025 causal V7 Tailに対する5 selector）に加え、明示的なユーザー指示で固定5候補だけを2026 reporting-onlyへ無調整延長した。2026 daily cutoffは2026-09-11、成熟済みsignal cutoffは2026-09-03。固定gate、3 base ranker、DUAL、DUAL+G3、tie-break、cooldown無し、next official XTKS open→fifth official XTKS close、実価格、全canonical rows、年次/aggregate metrics、入出力SHAを保存した。

## 4. 確定したweak+earlyルール

- population: artifact `10264251140` の保存済み因果V7 Tail（`tail_cdf >= 0.999` materialized済み）。
- causal training: month start前に`target_end_date`がmatureしたlabelだけ、最低30,000 training rows。
- gate: `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`。
- per signal dateで1件選択。rankerは`volr20 LOW`、`body_pct LOW`、両者のascending percentile mean-rank。
- tie-breakは`tail_cdf DESC`。winning tieは全rankerで0件。legacy headline比較のcooldownは無し。
- DUALはvolr20 LOW Top1とbody_pct LOW Top1のdate+symbol一致日のみ採用。不一致日はNO TRADE。
- G3は2025 open前に固定された`previous-session med_ret1 >= -0.01`。DUALへそのまま適用。
- 2023-2024 combined mean-rank: n=128, mean 7.1635478563%, median 1.8087917367%, win 54.6875%, +20 19.53125%, -10 25.78125%, Top3-ex 4.7521093456%。
- 2025は全ranker n=44。meanはvolr20 6.5762%、body 6.7813%、combined 6.0859%。
- 2023-2025 DUAL: n=140, mean +7.17%, median +1.25%, win 52.14%, Top3-ex +4.79%。
- 2023-2025 DUAL+G3: n=117, mean +7.98%, median +1.74%, win 53.85%, Top3-ex +5.14%。
- 2026単年: volr20 n42/+3.20%、body n42/+4.90%、mean-rank n42/+5.08%、DUAL n36/+3.26%、DUAL+G3 n32/+2.58%。
- Exact 2023-2026総合順位: 1 mean-rank、2 DUAL+G3、3 body、4 DUAL、5 volr20。順位契約は2026開封前のcommit `26653f45`で固定。

## 5. 未確定部分

- Cloud: `cloud4h_frame_dedup_sep.pkl` builder、上流1,314-symbol universe構築、歴史的feature frameまたは全決定論的predecessor、entry/exit prices付きnext-open canonical bridge。63 rowsとfinal selectorは欠落ではない。
- weak+early 2022: 固定specをそのまま実行してもWindows=94/30/22、Linux=95/25/20で旧89/29/23と不一致。runtime/model artifact不足のためhistorical row identityは`EXACT_NOT_YET_RECOVERED`。近さでruntimeを選ばないこと。
- 現行production scoringとのapples-to-apples勝敗: 未確定。母集団と観測契約が異なるため、保存済み過去成績だけで「現行超え」とは判定しない。`research/TVFREE_REPLACEMENT_READINESS_20260918.md`のforward shadow bridgeが必要。

## 6. 発見artifact一覧

- daily corpus: artifact `10264205130`, run `34599959356`, original run `34545440155`, `tse_daily.csv`, SHA `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`。
- causal Tail: artifact `10264251140`, run `34600083474`, `v7_causal_tail_cache_2023_2025.csv`, SHA `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`。
- Cloud teacher raw 4H: artifact `10266329903`, run `34608845800`, `teacher_ohlcv_4h_raw.csv`, SHA `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`。
- Cloud exact union: `research/repro_packs/cloud_monster_legacy_exact_v1/artifacts/cloud_two_lane_union_jpx.csv`, SHA `91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62`, Monster=63。
- Cloud saved scores: `research/repro_packs/cloud_monster_legacy_exact_v1/artifacts/cloud_priorityA_monsters_compare_teacher.csv`, SHA `1920e2e69b89feee473cd2e6f6542fe1766f754c3ff60397b65d026614037d54`, 19 rows。
- V7 blob `f7f49ab2e09496494adfb365c94e969973c4070c`; V9 blob `45a1272fe49c526bbf69956419e34e96d696f7d6`。

## 7. canonical trade rows一覧

- `research/repro_packs/weak_early_exact_v1/output/canonical_trade_rows_volr20_low.csv` — 172 rows — SHA `580ed355e27e8c25b13e1db0ac603d21640ddabf7e31cce8de228ae955c13474`。
- `research/repro_packs/weak_early_exact_v1/output/canonical_trade_rows_body_pct_low.csv` — 172 rows — SHA `2fdba3e3b5670dcb4c96eca491274adb33bf05529aed6c1c35b90610148740f5`。
- `research/repro_packs/weak_early_exact_v1/output/canonical_trade_rows_mean_rank_volr20_body_pct.csv` — 172 rows — SHA `424a9cb70a2834d2002d3e664ab75e1cde0c0509be34ba3c5c6e23316a810cbb`。
- `research/repro_packs/weak_early_exact_v1/output/canonical_trade_rows_dual_top1_agreement.csv` — 140 rows — SHA `b4f9fff630577492198732c91275f2fafb0114e78a519074393d13e03ab88031`。
- `research/repro_packs/weak_early_exact_v1/output/canonical_trade_rows_dual_top1_agreement_g3_no_acute_selloff.csv` — 117 rows — SHA `e98d4d82e81d05ac3b3ffae7f6dc91fa1bcd567d58c24403ae5568406ec8de27`。
- 2026 canonical rows 5本、causal Tail、normalized metrics、完全比較表は`research/repro_packs/weak_early_exact_v1/output/full_period_2026/`。各content SHAは`full_period_report.json`に固定。
- Cloud legacy exact rows: recovered in the 210-row union CSV (lane=`Monster`, 63 rows)。ただし元CSVはentry/exit date/open/closeを持たないため、requested canonical next-open bridgeは別成果として未作成。

## 8. REPRO_PACK完成度

- `research/repro_packs/weak_early_exact_v1/`: A-H complete for preserved 2023-2025 five-selector comparison。`reproduce.py`はinput SHA、ties、row/metric drift、official-session endpoint driftをfailする。`select_shadow_candidates.py`はoutcome列を読まず、5 selectorのcandidate identityだけを生成する。
- `research/repro_packs/cloud_monster_legacy_exact_v1/`: exact row identity + final selector complete。`verify_recovered_rows.py`がheadlineを独立再計算。full raw-input pipelineのみbase-frame builder不足でblocked。
- `research/repro_packs/weak_early_exact_v1/2022_runtime_sensitivity/`: 2 runtimeの未調整ledgersとSHAを保存。

## 9. 作成commit SHA一覧

- `3ad2ed92821e1111abbc15341f3bd9fce8026d82` — weak+early exact REPRO_PACK。
- `01a667da` — Cloud fail-closed recovery pack + 2022 runtime sensitivity evidence。
- `6e151853a50b154bc49a417ac2407ee790b6e3b4` — 初版handoff。
- `38edc77234e5bc283a55e14028a2b88e136c1ec4` — DUAL / DUAL+G3 exact rowsとreproducer固定。
- `d801da30f731e2d174d347770551bba17e564512` — outcome-blind shadow selectorとTV-free readiness契約。
- `26653f45` — 2026開封前の5候補ranking contractとfull-period generator固定。
- `c84b0de2` / `3012fc2b` — endpoint joinとfloat round-tripのfail-closed修正。
- `bb597947` — Cloud Monster exact 63 rows、19 saved-score rows、final selector、metrics verifier。
- この更新handoff自体のcommitはbranch tipを`git rev-parse origin/research/cloud-monster-recovery`で取得すること。

## 10. branch名

`research/cloud-monster-recovery`。作成元SHAは`cc08da7523e5037ff5575427fbf4b57bb590f4fd`。mainへmergeしていない。

## 11. 変更ファイル一覧

今回の差分は `research/CLOUD_MONSTER_RECOVERY_LEDGER_20260918.md`、`research/RESEARCH_DASHBOARD.md`、`research/TVFREE_REPLACEMENT_READINESS_20260918.md`、本handoff、`research/repro_packs/cloud_monster_legacy_exact_v1/**`、`research/repro_packs/weak_early_exact_v1/**` のみ。production code/workflowは変更なし。

## 12. 絶対に再実行不要な探索

- 指定research refsに対するdefault-branch限定を超えたGit path/content/history検索。
- 現在の非expired Actions artifact名一覧に対するCloud/Monster/teacher検索。
- repo/Product/Downloads/Documentsの同一filename検索、および旧ChatGPT Libraryからの2 CSV再download。
- current 1H Cloud artifacts、696-row broad reconstruction、代理modelをlegacy 63 exactと見なす試行。
- 2022を89/29/23へ寄せるruntime/threshold/feature選択。

## 13. 次にChatGPTがやる最短作業

Cloudの最短作業は旧会話のより早いtool logから`cloud4h_frame_dedup_sep.pkl` builderを回収し、raw teacher→base frame→MTF→JPX relabel→final selectorを再実行すること。2 CSVと最終generatorの探索は繰り返さない。その後、entry/exit pricesを付けたnext-open→fifth-close bridgeをlegacy headlineと別名で作る。TV-free系はmean-rankとDUAL+G3を新しいoutcome未成熟forward shadowで並走させる。

## 14. production無変更確認

main checkout、本番コード、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder、watchlist-updaterは変更していない。差分はresearch-only pathのみ。

## 15. 2026の取扱い

明示的なユーザー指示により、既に固定済みのWeak+Early 5候補だけ2026をreporting/robustness用途で開封した。2026をthreshold/feature/gate/candidate変更やretuneには使用していない。Meta mappingおよび他の2026 research laneはSEALEDのまま。Cloud headline/rowsの既知情報もartifact同定用にのみ扱っている。

## ChatGPTへ貼るプロンプト

あなたは`Ken5InvestmentLab/screening-bot`のCloud Monster exact復元を引き継ぎます。repoは`Ken5InvestmentLab/screening-bot`、branchは`research/cloud-monster-recovery`です。最初に`git fetch origin`して`origin/research/cloud-monster-recovery`をcheckoutし、最新SHAを`git rev-parse HEAD`で記録してください。Cloud exact-row成果commitは`bb597947`、weak+early packは`3ad2ed92821e1111abbc15341f3bd9fce8026d82`、完全handoffは`research/CODEX_TO_CHATGPT_CLOUD_MONSTER_HANDOFF_20260918.md`です。

weak+earlyは`research/repro_packs/weak_early_exact_v1/`に`WEAK_EARLY_EXACT_V1 / EXACT_REPRODUCED`として固定済みです。入力はActions artifact `10264205130`と`10264251140`、2023-2025 canonical rowsは5本の`output/canonical_trade_rows_*.csv`です。固定5候補の2026 reporting-only延長は`output/full_period_2026/`、完全表は`FULL_PERIOD_COMPARISON_20260918.md`、machine-readable結果は`full_period_report.json`と`normalized_yearly_and_total_metrics.csv`です。Exact 2023-2026順位は1 mean-rank、2 DUAL+G3、3 body、4 DUAL、5 volr20です。2022はsummary-onlyでexact総計から除外しています。

Cloud Monsterは`research/repro_packs/cloud_monster_legacy_exact_v1/`に`EXACT_ROWS_AND_FINAL_SELECTOR_RECOVERED / FULL_PIPELINE_REPRO_BLOCKED`として固定済みです。exact rowsは`artifacts/cloud_two_lane_union_jpx.csv`（SHA `91f1f956...`, lane Monster=63）、saved scoresは`artifacts/cloud_priorityA_monsters_compare_teacher.csv`（SHA `1920e2e6...`, 19 rows）、final sourceは`recovered_selector.py`です。raw入力はartifact `10266329903`の`teacher_ohlcv_4h_raw.csv`（SHA `f28bcb45...`）。未解決blockerは`cloud4h_frame_dedup_sep.pkl` builder、上流universe construction、next-open canonical bridgeです。

次の具体的actionは、旧会話の早いtool logにあるbase 4H frame生成スクリプトを回収し、保存済みraw入力からfull pipelineを再実行することです。2 CSVと最終selectorは再探索不要です。合わせ込み、新model作成、2026を使ったretuneは禁止です。並行してTV-freeはmean-rankとDUAL+G3だけを新しいoutcome未成熟期間でshadowし、候補ledgerをendpoint成熟前にSHA固定してください。

`main`、production、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder、watchlist-updaterは変更禁止です。research-only branch/artifact/scriptだけを変更してください。Weak+Early固定5候補以外の2026はSEALEDのまま維持し、開封済み2026も復元条件の選定・調整・推測へ使わないでください。探索の重複を避けるため、先に`research/CLOUD_MONSTER_RECOVERY_LEDGER_20260918.md`の「Do not repeat」を読んでください。
