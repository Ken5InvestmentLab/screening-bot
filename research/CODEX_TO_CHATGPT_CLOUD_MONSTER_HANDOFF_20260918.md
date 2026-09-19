# Codex → ChatGPT Cloud Monster / weak+early handoff — 2026-09-19

## 1. 今回実施したこと

research-only branch `research/cloud-monster-recovery` でGit全ref/history、Actions artifact、旧ChatGPT会話/Library、保存ソースを追跡した。weak+early 5候補をexact packへ固定し、Cloud Monsterは63行だけでなくraw入力から4段pipelineを再実行して完全一致を確認した。さらに同じ63 signal identityへcanonical next-open endpointを付与し、6候補の年別/total比較を作成した。

## 2. Cloud Monster exact復元状況

**`CLOUD_MONSTER_LEGACY_EXACT_V1 / EXACT_REPRODUCED_FROM_RAW`**。Actions artifact `10266329903`から、回収した`build_cloud4h_dedup_sep.py` → `build_mtf_fast.py` → `relabel_jpx_5bd.py` → final Monster selectorを順に実行。base=245,334行/1,314 symbols、最終 expected=63 / actual=63、symbol+timestamp+date一致、close bitwise一致、`ret5`最大差0.0。閾値・feature・fractionの合わせ込みはない。

Legacy endpointはsignal snapshot close→fifth official XTKS close。n=63、mean +9.8569%、median +3.3333%、win 57.1429%、+20 30.1587%、+30 19.0476%、-10 22.2222%、Top5-ex +4.0269%。

## 3. weak+early exact復元状況

**`WEAK_EARLY_EXACT_V1 / EXACT_REPRODUCED`**。保存済みcausal V7 Tailへ固定gateを適用し、volr20 LOW、body_pct LOW、mean-rank、DUAL、DUAL+G3の5 selectorを2023-2025でexact再現。固定5候補だけをユーザー明示指示により2026 reporting-onlyへ無調整延長した。2022は旧89/29/23 row identityが未回収で、summary-onlyのままexact total/rankから除外。

## 4. 確定ルール

- Cloud Watch: `2026-03-01 <= date < 2026-09-01 AND d_pre3 AND d_gap AND ret3 >= .06 AND ret3 < 5`、first symbol-day。
- Cloud model: exact 52-feature order、median imputer、StandardScaler、balanced LogisticRegression `C=.15/max_iter=500/random_state=1`。
- Cloud walk-forward: April/May/June prior-only folds、fixed fractions `.10/.20/.30`、原objectiveで`.10`選択。final fitは`date < 2026-07-01`、training-score 90th percentile `0.7480177317229793`。cooldown/per-day quotaなし。
- Cloud base universe: `prev_close <= 1000`、`prev_volume >= 10000`、current 4H `volume >= 5000`、歴史runは`2026-01-01 <= timestamp < 2026-09-11`。
- Weak+Early gate: `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`。
- Weak rankers: signal dateごとにvolr20 LOW、body_pct LOW、両ascending percentileのmean-rank。tie-break=`tail_cdf DESC`、legacy cooldownなし。
- DUAL: volr20/body Top1のdate+symbol一致のみ。G3: previous-session `med_ret1 >= -0.01`。
- Canonical endpoint: signal T → next official XTKS session open → fifth official XTKS session close、cost 0%、win=`gross > 0`。

## 5. 未確定部分

- Cloud/weak+earlyの復元自体は完了。未完は現行production scoringとの真のforward apples-to-apples勝敗。
- Cloud historical modelは2026 outcomeで開発された旧モデルなので、2026成績は復元確認/記述だけ。promotion evidenceにはできず、次の未成熟期間でprospective shadowが必要。
- Weak+Early 2022 exact historical identityは`EXACT_NOT_YET_RECOVERED`。Windows固定run=94/30/22、Linux固定run=95/25/20で旧89/29/23と不一致。近いruntimeへ寄せない。

## 6. 発見artifact / source

- Weak daily: artifact `10264205130`, `tse_daily.csv`, SHA `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`。
- Weak causal Tail: artifact `10264251140`, SHA `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`。
- Cloud raw: artifact `10266329903`, run `34608845800`, SHA `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`。
- Cloud union: `research/repro_packs/cloud_monster_legacy_exact_v1/artifacts/cloud_two_lane_union_jpx.csv`, SHA `91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62`。
- Cloud saved scores: `artifacts/cloud_priorityA_monsters_compare_teacher.csv`, SHA `1920e2e69b89feee473cd2e6f6542fe1766f754c3ff60397b65d026614037d54`。
- Original Cloud sources: `research/repro_packs/cloud_monster_legacy_exact_v1/source/` の4本。source SHAとruntimeは`output/raw_reproduction_receipt.json`。

## 7. canonical trade rows

- Cloud canonical 63 rows: `research/repro_packs/cloud_monster_legacy_exact_v1/output/canonical_next_open_fifth_close/canonical_trade_rows_next_open_fifth_close.csv`, SHA `e8022da46af85fa249e0815768682fe0ccc7730485f9494268bebd8e961a6a17`。
- Cloud canonical metrics/receipt: 同directory。2026/TOTAL mean +4.5821%、median -0.1406%、win 49.2063%、Top3-ex +1.3913%、100株P/L ¥153,500。
- Weak 2023-2025 canonical 5本: `research/repro_packs/weak_early_exact_v1/output/canonical_trade_rows_*.csv`。
- Weak 2026 rows/metrics: `research/repro_packs/weak_early_exact_v1/output/full_period_2026/`。
- Cross-system year/rank/total: `research/comparisons/cloud_weak_early_20260919/`。

## 8. REPRO_PACK完成度

- Cloud A-H: complete。`reproduce_from_raw.py`がinput SHA、全4 stage、63 identity、close、ret5をfail-closed検証。`build_canonical_bridge.py`が固定63件だけへcanonical endpointを付与。
- Weak A-H: complete for exact 2023-2025 + fixed-candidate 2026 reporting。`reproduce.py`と`select_shadow_candidates.py`がcanonical endpoint/identity/outcome-blind selectionを検証。
- Cloud legacyとcanonical bridgeを混ぜていない。canonical identityは`CLOUD_MONSTER_CANONICAL_NEXT_OPEN_FIFTH_CLOSE_V1`。

## 9. 作成commit SHA

- `3ad2ed92821e1111abbc15341f3bd9fce8026d82` — weak+early exact pack。
- `38edc77234e5bc283a55e14028a2b88e136c1ec4` — DUAL / DUAL+G3 exact。
- `d801da30f731e2d174d347770551bba17e564512` — outcome-blind weak shadow boundary。
- `26653f45` — 2026開封前ranking contract。
- `bb597947` — Cloud historical 63 rows / final selector。
- `ed871081c2847457b438d4b1cb9939a1b44cb999` — Cloud raw→63 exact reproduction。
- `7b57dc84320a27bccb3ffb23433fa67edace54ba` — Cloud canonical bridge + 6-candidate comparison（latest result SHA）。

## 10. branch

`research/cloud-monster-recovery`。作成元は`origin/research/automation-coordination@cc08da7523e5037ff5575427fbf4b57bb590f4fd`。mainへmergeしていない。

## 11. 変更ファイル

変更は`research/**`だけ。主要追加はCloud pack `source/`, `reproduce_from_raw.py`, `build_canonical_bridge.py`, canonical rows/receipt、Weak pack、recovery ledger/dashboard/readiness、`research/comparisons/cloud_weak_early_20260919/`、本handoff。本番コード/workflow/configは変更なし。

## 12. 再実行不要な探索

- 旧Cloud 63 CSV / 19-score CSVのGit/Library再探索。
- base builder / MTF / JPX relabel / final selectorの旧会話再抽出。
- artifact `10266329903`からraw→63を再証明する探索。
- default branchだけのCloud/Monster検索、既列挙Actions artifacts、repo/Product/Downloads/Documentsの同一filename検索。
- 2022を89/29/23へ寄せるruntime/threshold/feature探索。

## 13. 次の最短作業

1. 最優先は`research/HIGH_WIN_MULTI_LANE_PREREG_20260919.json`と`research/experiments/high_win_multi_lane_v1/discovery/FROZEN_FINALISTS_BEFORE_2025.json`を読み、commit `a61cd763`でfreeze済み3 finalistだけを2025 holdoutへ一度通す。条件追加/緩和禁止。0件通過なら`NO_VIABLE_NEW_LANE`。
2. Cloud exact model freeze/outcome-blind scorerは完成済み。次はlabel不要のcausal future feature-frame builderを歴史feature identity test付きで作る。
3. Weak固定候補、holdout通過新lane、Cloud固定モデル、現行production候補をendpoint未成熟時点で別々のappend-only ledgerへSHA固定する。
4. 観測月が違う現在の2026順位をpromotionには使わない。2026を見て条件を変更しない。

## 14. production無変更

`main`、production、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder、watchlist-updaterは変更していない。research-only commitのみ。

## 15. 2026 SEALED確認

ユーザー明示指示により固定Weak 5候補と復元Cloudの2026をreporting/reproduction用途だけ開封した。2026をthreshold/feature/gate/candidate family/retuneへ使用していない。Meta mappingおよび他laneの2026はSEALEDのまま。

## ChatGPTへ貼るプロンプト

あなたは`Ken5InvestmentLab/screening-bot`のTradingView非依存研究を引き継ぎます。repoは`Ken5InvestmentLab/screening-bot`、branchは`research/cloud-monster-recovery`、latest result SHAは`7b57dc84320a27bccb3ffb23433fa67edace54ba`です。最初に`git fetch origin`し、`origin/research/cloud-monster-recovery`をcheckoutしてbranch tipを記録してください。完全handoffは`research/CODEX_TO_CHATGPT_CLOUD_MONSTER_HANDOFF_20260918.md`、探索ledgerは`research/CLOUD_MONSTER_RECOVERY_LEDGER_20260918.md`です。

Cloud Monsterは`CLOUD_MONSTER_LEGACY_EXACT_V1 / EXACT_REPRODUCED_FROM_RAW`です。packは`research/repro_packs/cloud_monster_legacy_exact_v1/`。rawはActions artifact `10266329903`、SHA `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`。4 original sourcesは`source/`、full reproducerは`reproduce_from_raw.py`、receiptは`output/raw_reproduction_receipt.json`。expected/actual 63、identity/close完全一致、ret5最大差0.0です。canonical rowsは`output/canonical_next_open_fifth_close/canonical_trade_rows_next_open_fifth_close.csv`、SHA `e8022da46af85fa249e0815768682fe0ccc7730485f9494268bebd8e961a6a17`です。

Weak+Earlyは`WEAK_EARLY_EXACT_V1 / EXACT_REPRODUCED`。packは`research/repro_packs/weak_early_exact_v1/`、2026 reportingは`output/full_period_2026/`。Cross comparisonは`research/comparisons/cloud_weak_early_20260919/`。2026年内の記述順位は1 mean-rank、2 body_pct LOW、3 Cloud Monster canonical、4 DUAL+G3、5 DUAL、6 volr20 LOWですが、Cloud=3〜8月、Weak=1〜9月初旬で完全apples-to-applesではありません。Weak 2023-2026順位は1 mean-rank、2 DUAL+G3、3 body、4 DUAL、5 volr20です。2022はrow identity不足でsummary-onlyです。

未解決blockerは復元ではなくforward比較です。Cloudのfrozen modelは`artifacts/cloud_monster_frozen_shadow_model_v1.json`と`cloud_monster_frozen_pipeline_v1.joblib`、outcome-blind scorerは`select_cloud_shadow_candidates.py`です。歴史assertionはlegacy評価63件を全包含し、endpoint欠損だけで旧評価から落ちた6217を加えた64件です。加えて高勝率研究は`HIGH_WIN_MULTI_LANE_RESEARCH_V1`として事前登録済みで、2025未開封の3 finalistがcommit `a61cd763a2b5e7a2f3875c74cc57f8774b0fa505`に固定されています。次のactionはこの3件だけを2025 holdoutへ一度通し、その後にlabel不要Cloud feature builderとappend-only forward ledgerへ進むこと。2026を見てrule、threshold、feature、gate、candidate familyを選び直してはいけません。

`main`、production、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder、watchlist-updaterは変更禁止。research-only branch/artifact/scriptだけ変更してください。Meta/他laneの2026はSEALED。`research/CLOUD_MONSTER_RECOVERY_LEDGER_20260918.md`のDo not repeatを先に読み、Cloud復元探索を繰り返さないでください。
