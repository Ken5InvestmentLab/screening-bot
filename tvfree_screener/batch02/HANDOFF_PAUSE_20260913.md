# TV-Free research pause handoff — 2026-09-13

この文書は、週間Codex使用量が残り45%に達した時点で研究を止めるための引継ぎ記録である。再開はユーザーの明示指示後に限る。次のAIは、ここに書かれた停止状態を尊重し、独自判断で研究・データ取得・GitHub更新を再開しないこと。

## 1. ゴールと停止条件

目標はTradingViewを使わず、東証個別株向けに現行Stable/Sniper/Megaと成績勝負できる独立スクリーニングを完成させること。旧システムとの銘柄一致は不要。CoreとMonsterは別目的として評価する。複数銘柄/日を許し、候補プール全体、Top1/2/3/5を別々の時系列シミュレーションで比較する。

この作業中にユーザーは、週間使用量の残りが45%に到達したら停止し、そこで明示指示があるまで中断するよう指定した。停止時には成果をこのファイルへ追記し、研究専用ブランチだけへpushする。main、本番Bot、Discord、Sheets、GAS、production workflow、秘密情報は変更しない。現時点の直近使用量取得では週間used=54%、remaining=46%だったため、45%停止点にはまだ達していない。停止時の正確な残量を再取得して追記する。

## 2. 現在地

- checkout / branch: `screening-bot-tvfree-batch01`, `research/tvfree-canonical-batch02`
- 前回確認したHEAD: `0547456 Add 4H provenance source receipt`。これ以降の変更は4Hデータ品質レポート、実験台帳、`EXECUTION_CONTROL.json`に限られ、未コミット状態。
- 研究ブランチのoriginは同名のresearch branch。変更はここだけに保存する。
- main checkoutには変更なし。作業中の無視対象キャッシュは `.cache/` のみで、Gitへ追加しない。
- 自動実行・workflow dispatch・新規Yahoo取得・有料データ取得はいずれも行っていない。

## 3. 重要な従来研究の状態

ユーザー提供の完全引継ぎは研究台帳として扱い、数字はcanonical evaluatorで再現するまで確定成績とみなさない。より新しいローカル監査がある項目はそちらを優先する。

- **V29 / Consensus:** 旧limited universeの好成績（n=35、mean +4.859%、median +2.899%、+10% 31.43%）は全Universeへ一般化しなかった。full-universe V40はmin97でn=41/mean -3.051%、min98でn=32/mean -3.955%。2026 V42も負。現Core候補としてREJECT、3-head/consensusは設計上の手掛かりとしてKEEP。実際の実装ではderived `stable_score`（6つの技術booleanの合計）がV29 fitへ渡されることを確認したが、TradingView本番Stable★ラベルと同一とは断定しない。
- **Monster weak + early + low volr20:** 提供履歴では最有望仮説だったが、新しいcanonical pool監査がそのまま合格を示したわけではない。2023 frozen poolはrequested 69 / resolved 68、51 dates、41 symbols。gross mean +2.70%、median -1.80%、win 40.9%、+20% 17.65%、-10% 33.82%、Top1除外 +1.15%、Top3除外 -1.58%。0.5% cost後leaderboardはmean +2.20%、median -2.30%、Top3除外 -2.08%。登録済みTop1/2/3/5は全て不合格、選択N未解決。2024はpool診断専用、2025/2026の戦略結果は開いていない。このためMonsterをpass済み/運用可能と呼ばず、探索候補として保持する。
- `ret10 <= 0.5735294117647058` は2023 V18 consensus collectionのmedian由来とコードで再構築済み（V20との差1e-12以内）。由来確認であり、閾値の予測優位性や2023以前のサンプルを意味しない。
- **First Reversal:** 2023H1/2024H1で強い半期がある一方、2024H2と2025H1で劣化し、Core leaderではない。低volr20 vetoは一部再現したが2025H1を救えていない。Breadth vetoは撤回済み。
- **REJECT済み系統:** global threshold micro-tuning、safety-first moderate-tail classifier、quiet accumulation/ignition、単純breakout、pre-break expansion、strongest relative strength、過去regime成績に基づくstrategy switch、Expansion。新しい本質的仮説がない限り名前だけ変えて再試行しない。
- **まだ完了していない4H/daily構成監査:** 無料でCodexなしに運用できる4Hデータが全Universe・長期で取れるかは未確定。Daily-onlyに固定しない。新規4Hはraw intradayから別の仕様で再構築する。日足から4Hバーを生成しない。
- **Fundamental V2:** scorerの再現性と予測力を混同しない。point-in-timeソース、公開時刻、cutoff、ソースhashが揃うまで過去予測へ投入しない。

詳細な履歴・個別ゲートは `EXPERIMENT_LEDGER.md` と `reports/` の該当実験レポートを先に確認する。

## 4. 4Hデータの新しい監査結果

### 4.1 legacy `ohlcv_4h` のカバレッジ

読み取り専用でSheetsの `ohlcv_4h` を日足パネル・XTKSカレンダーと照合した（2025-12-23〜2026-09-11）。645,187 daily symbol/session pairsのうち、439,557には有効な09:00/13:00両方のlegacy足が揃わず、そのうち439,207（99.920%）に数値として有効な同日daily OHLCVがあった。これは欠損箇所へ日足行がある割合であり、dailyが正しい、4H値が誤り、または日足からセッションOHLCを復元できる、という証拠ではない。未観測キーが未追跡か取得失敗かも区別できない。

### 4.2 GAS生成ルールとprovenance

`weekly_report_gas/gas.txt` は別checkoutで読み取りだけ行った。`parseIntraResponse_` はYahoo timestampをinterval-startとして扱い、09/10/11/12時をAM、13/14/15/15:30/16時をPMへ入れる。12:00開始の1時間足は11:30–12:30の昼休み境界をまたぎ、真の前後場OHLCVに分割できない。15:30/16:00のflat zero-volume close snapshotはPM closeだけを更新し得る。

1d gap fallbackは同じ日足OHLCをAM/PM両行へ複製し、daily volumeを50/50で分ける。これはプレースホルダーであり、前場・後場の実値復元ではない。`alert_id=GAP_REPAIR`はYahoo 1h再取得行とdaily由来placeholderの双方で使われるためsource tagではない（8,610件）。このマーカーから両者を識別したり、flatな値を見て日足補完と断定したりしない。

結果: `INCONCLUSIVE_SOURCE_PROVENANCE_MIXED`。既存legacy sheetをスコア候補へ使用せず、書き戻さない。

### 4.3 保存済み8銘柄raw Yahoo 1h sampleとdailyの比較

既存Actions artifact run `34586861016`（2026-09-11作成、2026-09-18 09:58:52Z期限）からraw 1h CSVのみを読み取り、同じ8銘柄・期間の既存daily cacheと比較した。2026年データだが、銘柄はMonster例として事前選定された8銘柄であり、母集団代表性はない。strategy outcomes/returns、`cloud_1h_monster_precursors.csv`は開いていない。workflow dispatchもYahoo新規requestもなし。

- Raw 1h: 8,709 rows / 8 symbols / 2026-01-05〜2026-09-11。daily subset: 1,353 rows。
- 1,360 symbol-session pairs中1,324 comparable、36 unassessable。全7つの期待開始時刻が存在したのは1,087/1,324 session。15:30 closing snapshots 8件はgeneric runnerでセッション外扱いになり、GAS型close overrideは未適用。
- hourly aggregateとdailyのOHLCが1%以内だった件数: open 830/1,324 (62.7%)、high 1,142 (86.3%)、low 1,203 (90.9%)、close 1,076 (81.3%)。median absolute pct diffはopen .41%、high 0%、low 0%、close .34%。同じ提供元の内部整合性であってdaily真値への比較ではない。
- Volumeは2/1,324が完全一致、76/1,324が5%以内、median absolute pct diff 37.7%。部分hour slot、intraday volume semantics、調整基準の差を解決できていない。
- 6085で2026-01-05〜03-31の47 sessionsが概ね10x price scale mismatch、38ではOHLCすべてに同じ倍率。発行会社の開示は2026-04-24効力の1:10株式分割を示すが、日付パターンだけでは過去47日の倍率差を説明できない。事後補正・除外はしない。詳細は監査レポートのリンク先開示を参照。

結論 `INCONCLUSIVE_ADJUSTMENT_AND_VOLUME_SEMANTICS`。ユーザーの目的は1時間足を正解にして日足との一致度を競うことではなく、信頼性が低い可能性のある1時間足を日足でざっくり補完・修正する妥協案を作ること。今回の照合は差異の把握に留まり、その妥協案をまだ試していない。

ユーザーは「ざっくりでよい」と明確化した。全日daily fallbackだけに固定せず、近似的な補正と退避を順に試す。まずraw hourlyを保存したまま、(1) 1日内OHLC比率が共通する明白なスケール不一致の補正、(2) daily open/closeを使った日初・日終値の補正、(3) daily high/lowを既存時間足のextremaへアンカーする補正、(4) 全hour slotが揃い調整基準・単位が合う場合に限りhourly出来高配分を日足総量へ比例補正、(5) それでも信頼できない日を一件のdaily-resolution fallbackへ退避、を比較する。補正済み行には方式・補正係数・confidence/source tagを記録しraw値を上書きしない。欠けた時刻へdailyの高安値を推測配置したり、daily一行を前場・後場二本へ複製したりはしない。

追加の簡易diagnostic（補正値は作らず、2026 strategy outcomeも開かない）では、全7 hourly startが揃う1,087 symbol-sessionsを調べた。daily/hourlyのOHLC比率が共通倍率から1%以内だったのは478 (44.0%)、2%以内は770 (70.8%)。4つの比率の中央値をscale factorにして全OHLCへ掛けると、日足OHLCと1%以内に揃うのは574 (52.8%)、2%以内は891 (82.0%)。daily close/hourly closeだけのfactorでは1%以内が522 (48.0%; closeは式上完全一致)。これは丸一日の価格レベルを近似補正できる候補があることを示すが、個々の時間足時刻・価格経路の正しさは検証していない。日足総volume / hourly summed volumeの倍率はmedian 1.606、p10 1.131、p90 2.541。1,360 sessionsのうちdaily数値有効は1,352、7 hourly slot完全は1,087。日足fallbackは全日coverageを改善し得るが時間帯の経路は復元しない。8銘柄・同一providerの診断であって、価格真値や成績改善の証拠ではない。

この近似補正は日足の方が常に真値と証明されたという意味ではない。まず8銘柄の既存キャッシュでデータ品質・coverage変化のみを見る。2026のstrategy returnは開かず、閾値・モデル選択にも使わない。完成済み日足はその日の終値より前のsignal-time featuresへ使えない。場中シグナルの検証では特徴時点のcutoffを守る。

なお5BD endpointは「シグナル翌XTKS営業日の始値で入り、その日を1日目として5営業日目の日足終値」。strict path/actionability評価とは別集計する。

## 5. 証跡・ファイル

- Main feasibility report: `reports/4h_data_feasibility_audit_20260913.md`
- Legacy coverage report: `reports/intraday_daily_coverage_audit_20260913.md`
- Ledger: `EXPERIMENT_LEDGER.md`
- Run control: `EXECUTION_CONTROL.json`
- Rule/spec docs: `4H_DATA_FEASIBILITY_AUDIT_SPEC.json`, `HOURLY_DAILY_CONSISTENCY_AUDIT_SPEC.json`, `INTRADAY_BAR_DEFINITION_STUDY_SPEC.json`
- Frozen audit runner: `audit_hourly_daily_consistency.py`
- Raw/cache inputs and comparison rows are ignored under `.cache/audits/hourly_daily_sample_20260913/`; never commit them.
- Raw 1h SHA-256 `cb33bb893291a31d57973d981a5db8f010ca34f2db80804a92e7be5ad5e7776b`; selected daily subset SHA-256 `e8a7225469217a1c496b8f83a0bc66325541bde48025956f01bdb30158780d67`; full cached daily panel SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`; XTKS sessions SHA-256 `74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68`; audit runner SHA-256 `e88ec2888a83bff4b537da5c93f463be8ae8c5695a642d219fd60884d1955dae`.
- Read-only legacy GAS receipt: repo SHA `f2fb9df22565e29890a91c16c5063acb2f5d4cb1`; `gas.txt` SHA-256 `0ab6326c0eeca1090fc9cbbc116794481982db0e5fdf45afccd6a138a1ee9b46`; legacy projection SHA-256 `32c5e53f77487d17545abdbe80205289a53af532f37ae8f517c29c5f8b86402a`; XTKS calendar SHA above.

## 6. Next work after user explicitly resumes

1. First re-check weekly usage and repo branch/status; user instruction requires explicit resume before continuing.
2. Verify/push this pause handoff and the report/ledger/control edits to **only** `research/tvfree-canonical-batch02`; ensure no `.cache` rows were staged. Record final commit SHA and remote confirmation below.
3. Re-read the current active `EXECUTION_CONTROL.json` and frozen specs before doing more model work; do not auto-open 2025/2026 outcomes.
4. Continue the user's approximate daily-led repair study on authorized cached data. The first coarse diagnostic found common OHLC scale alignment within 2% for 70.8% of complete sessions, but close-derived rescaling put all O/H/L within 1% for only 48.0%; the median daily/hourly volume factor was 1.606. Apply the correction ladder separately and compare coverage/data quality, not returns. Preserve raw rows; do not fabricate AM/PM bars, use same-day completed values early, or silently normalize split-scale anomalies.
5. Use only free, Codex-independent paths. For any broader 4H audit, use an already-authorized raw export or ask the user for one; do not fetch Yahoo or scrape from this task.
6. Candidate research should retain the entire candidate pool and evaluate Top1/2/3/5 with independent cooldown state and same frozen endpoint; identify a genuinely new, preregistered hypothesis before outcome access. Do not re-run rejected families under a renamed label.

## 7. 停止時記録

- 45% remaining threshold observed at: `2026-09-13 21:02 JST` (`2026-09-13 12:02:06 UTC`)
- Account weekly usage snapshot: `55% used / 45% remaining`; current 5-hour window `27% used`.
- Final handoff is saved at the research branch HEAD; the exact commit SHA is reported in the assistant's pause message and can be confirmed with `git log -1` on this branch.
- Validation run: `git diff --check`; `EXECUTION_CONTROL.json` parse; report hash verification; cached audit summary JSON parse; cached detailed output retained 1,361 lines. Re-run attempt of the generic SQLite audit was cancelled after prolonged CPU use; the separate `.cache` output-folder attempt was denied and created no repo artifact. Raw inputs were not changed.
- Work status: `PAUSED; wait for explicit user resume`.
