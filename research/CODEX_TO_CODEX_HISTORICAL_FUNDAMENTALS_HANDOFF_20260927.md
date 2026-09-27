# Cloud 過去ファンダ分析 — Codex引き継ぎ (2026-09-27)

## 再開地点

- Repository: `Ken5InvestmentLab/screening-bot`
- 対象remote branch: `research/weak-early-beta`
- 作業worktree: `C:\Users\ken5\AppData\Local\Temp\screening-bot-reconcile-27ac8e727fd24346bbdad46d98def141`
- 最新の公開データcheckpoint: `312a02d0c76499e49d3cc1ac0e0f407a53afa47d`
- 公開tag: `cloud-deploy-backfill-20260927-80`; GitHub Actions run `36302740442` は成功。
- 公開HTML: `https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/`。未認証rootの302は想定どおりで、Discordロール認証を維持。`/healthz` は200。
- 次のCodexは、再開前に `git fetch origin research/weak-early-beta`、remote HEAD、`git status`、最新manifest、lock/processを確認する。保存済みcheckoutの変更と既存untracked fileを保護し、mainへ移らない。
- この作業の2回のcommitでGit hookが保存checkout内の別worktree管理ディレクトリ3件の削除を試み、`Permission denied` と表示した。commit自体は成功し、読取専用で3件とも残存を確認済み。これらを掃除・削除・再試行しない。

## 完了・公開済み

- `2024-03-28|6276` シリウスビジョン: `weak_early_beta/fundamental_worker/out/historical_backfill_modelverified_20260927_20240328_6276.json` と同名`_generation_receipt.json`。Luna xhigh、候補SHA256 `18C98F930C59901A30F599CDDCF9A1B1CFE858B9260F47D699270FAE71DE58AB`。公式IRの決算、通期予想修正、完全子会社吸収合併、蘇州子会社清算資料を確認し、3/28 16:15 JST cutoff以内のみを使用。
- `2024-03-15|6659` メディアリンクス: `weak_early_beta/fundamental_worker/out/historical_backfill_modelverified_20260927_20240315_6659.json` と同名`_generation_receipt.json`。Luna xhigh、候補SHA256 `668AA258B8244F6E7F3A7FDAE5C1BE464C3C384D46A8806CDCB2EAA3C1E79471`。公式会社/JPXの4資料を使用。2/21大量行使資料は公式direct URLを確認できず、Yahoo mirrorのみだったため、記述・数字・リンクを完全に除外して再生成済み。
- Local manifest `weak_early_beta/fundamental_worker/out/historical_backfill_manifest.json`: 253 total, 80 complete, 173 pending。Receipt: `weak_early_beta/fundamental_worker/out/historical_backfill_receipts.json`。Canonical detections: `weak_early_beta/state/detections.csv`。
- 16 paid/free HTML pages were regenerated and deployed: `reports/weak_early_beta_latest.html`, analytics, five mode pages, guide, and matching `_free.html` pages.
- `py -B -m unittest tests.test_weak_early_beta tests.test_report_fundamental_html` passed, 45 tests. `weak-early-beta-gate/npm run check` passed types, TypeScript, Wrangler dry-run. Historical `discord_posts: 0`.

## 既に調べたこと・重複検索しないこと

- `2024-03-28|6276`: 公式IR PDF4件の本文、日付、receiptとのリンク整合を確認済み。再調査不要。
- `2024-03-15|6659`: 公式IR/JPX資料と2/21大量行使資料のホスト調査済み。公式direct URLは確認できずYahoo edge mirrorのみだったので除外済み。大量行使の数字を戻さない。再探索不要。
- `2024-03-14|2330`: 公式資料のsource researchは済みだが、Luna report candidate/receiptは未保存・未import。確認済み資料は2/1 AI子会社設立、2/13 決算短信・特別利益/予想差異、2/16 筆頭株主異動・代表取締役/監査等委員候補・剰余金処分/訂正、3/6 株主総会招集通知（2月のAI事業開始記載）。IRBANK上の2/1 15:00、2/13 15:10、2/16 15:00を確認。3/6資料は時刻表示なしだが日付がcutoffより8日前。まず既存の公式本文とcutoffで候補を完成できるか確認し、追加で広い検索を繰り返さない。
- `2023-05-19|3137`: 同日16:15前の公開時刻が証明できない既知hold。再探索しない。
- `2024-03-12|9704`: 公式一次資料の本文証拠が不足する既知hold。以前の同じ検索を繰り返さない。`2024-03-14|9704`は別identityなので、そのcutoffに新しい資料がある場合のみ確認する。
- untracked `weak_early_beta/fundamental_worker/out/historical_backfill_resume_20260927_g17_candidate.json` は既存ユーザー作業として残した。変更・stage・上書きしない。

## 次にやること

1. 使用量、branch/HEAD/status、manifest、lock/processを再確認。週次残量が30%以下なら分析停止前にpass分をHTMLへ反映し、beta deployとcheckpointを行う。
2. 既に確認した資料を使って `2024-03-14|2330` の候補とgeneration receipt（GPT-6 Luna xhigh、実ファイルSHA）を作る。公式本文/cutoffの根拠が不足するならpassにせずhold。
3. `validate_historical_report`、manifest identity/selectors、公式一次資料・本文確認・cutoff、direct disclosure URL集合、Premium準拠の7 fieldsと2–4 listing Sources、receipt SHAを独立検証。合格分だけ `py -B -m weak_early_beta.cli import-historical-fundamentals --input <candidate>` でimportする。
4. HTMLとledgerを確認し、45件テスト・gate check後にresearch branchだけへcommit/push。新しいユニークtag `cloud-deploy-backfill-<date>-<complete-count>` をpushし、Actions成功、`/healthz=200`、rootの認証redirectを確認。過去分はDiscordへ投稿しない。
5. 次のpendingはmanifest順に確認する。known holdsは飛ばし、当面 `2024-03-14|9704`、`2024-04-04|2330`、`2024-04-05|2330`、`2024-04-08|6659` が後続候補。

## 固定境界

- 各履歴分析はidentity固有の `signal_date 16:15 JST` cutoffまでに公表された公式会社IR/TDnet/JPX一次資料の本文だけを使用。cutoff後の事実、価格、実現リターン、将来推測を入れない。
- GPT-6 Luna xhighを使う。Premiumと同じ7項目、短く根拠に沿った日本語、2–4件の一覧/参照Sources、直接開示URLを維持。重要な開示だけを選ぶ。
- passした分から都度HTMLへ反映してbeta-only Webへdeploy。週次残量30%以下で安全checkpointをdeploy後に停止。5時間残量3%以下でも安全checkpointを作成。今回ユーザーが別アカウントへの移管を依頼したので、このthreadの自動再開heartbeatはpauseする。
- production/main、本番workflow/Discord/Sheets、Stable、Sniper、Mega、TradingView、watchlistは変更しない。2026の履歴分析は許可されているが、スコア条件選択/retuneには使わない。

## ChatGPT/Codexへそのまま渡す再開プロンプト

`Ken5InvestmentLab/screening-bot` の過去ファンダ分析を再開してください。対象remote branchは `research/weak-early-beta`、公開済みデータcheckpointは `312a02d0c76499e49d3cc1ac0e0f407a53afa47d`、公開tag `cloud-deploy-backfill-20260927-80` のActions run `36302740442` は成功済みです。作業前に使用量、remote HEAD、git status、manifest、lock/processを確認し、untrackedの `historical_backfill_resume_20260927_g17_candidate.json` を変更・stage・上書きしないでください。manifestは80/253 complete、173 pendingです。

最初の未完了 `2024-03-14|2330` はsource researchのみ完了しcandidate/receiptはありません。既確認一次資料（2/1 AI子会社設立、2/13決算/特別利益・予想差異、2/16筆頭株主・役員候補・剰余金処分/訂正、3/6株主総会招集通知にある2月AI事業開始）を使い、追加の広い検索を繰り返さず、検出日16:15 JST cutoffを守ってGPT-6 Luna xhigh candidate/receiptを作りauditしてください。pass分だけimportし、HTMLを更新後、45件テストと`weak-early-beta-gate/npm run check`、research branchへのcheckpoint push、beta-only tag deploy、live health/OAuth smokeまで行ってください。

続いてmanifest順に再開し、完了分は一括保留せず随時HTMLとWebへ反映してください。履歴receiptは既知holdを再探索しないでください（`2023-05-19|3137`、`2024-03-12|9704`）。2024-03-15|6659は2/21 Yahoo mirrorの大量行使内容を除外済み、2024-03-28|6276は公開済みなので重複分析しない。現行の公開URLと同じDiscordロールゲートを維持し、過去分のDiscord投稿は0件のままにしてください。production/main等の変更は禁止、2026は過去分析のみで条件選択やretuneに使わないでください。週次残量が30%以下になったら完成分のHTML+Web反映とcheckpoint後に停止し、5時間残量3%以下も安全停止してください。`
