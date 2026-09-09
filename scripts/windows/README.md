# Premium 定時実行を Codex CLI で動かす

13:05 / 15:36 JST の既存 Premium worker を、Codex デスクトップアプリに依存せず実行する。分析は従来の `gpt-5.6-terra` / `xhigh`、既存のスキル・指示・投稿検証を引き継ぐ。ChatGPT の保存済み認証を使い、API キーによる追加課金へ切り替えない。

## 事前条件

- 対応する Codex CLI、Node.js、ChatGPT の CLI ログインが必要。CLI はデスクトップアプリとは別に更新する。
- Windows タスクは本人の S4U トークンで動かす。登録には管理者権限が必要。Windows パスワードや自動ログオンは設定しない。
- ログオン不要でも PC の電源とインターネット接続は必要。`WakeToRun` はスリープから復帰できるが、電源断からは起動できない。
- ローカルの worker・認証・状態ファイルはログオン前にも読める必要がある。OneDrive 上の必須ファイルは「このデバイス上で常に保持する」にする。
- Plus の利用上限や認証期限切れを回避する仕組みではない。失敗はローカル結果ファイルと Windows タスク履歴に残す。

## 検証と切り替え

```powershell
node --test scripts/windows/test-premium-runner.mjs
node --check scripts/windows/premium-runner.mjs
powershell.exe -NoProfile -File scripts/windows/test-powershell.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install-premium-task.ps1 -RepoPath '<weekly_report_gas の絶対パス>' -CliJs '<対応 CLI の bin/codex.js>' -Mode Probe
```

インストーラーは `~/.codex/premium-runner/bin/` に実行ファイルを配置し、`PremiumAlertCliProbe` を登録・起動する。Probe は Google Sheets の少量読取、Discord webhook の GET、CLI による既存資料の読取と公式 Web 検索だけを行う。収集・投稿・HTML 更新は行わない。

`~/.codex/premium-runner/probe-latest.json` の `ok=true`、`sessionId=0`、`cli=true`、`sheetsRead=true`、`discordRead=true` を確認し、CLI ログで実際の読取・検索の成功も確認する。

確認後、同じコマンドの `-Mode Scheduled` で本番タスクを無効状態で登録する。登録成功を確認してから、Codex アプリの管理ツールで既存の 13:05 / 15:36 の **両方**の Premium automation を PAUSED にし、`Enable-ScheduledTask -TaskName PremiumAlertCli` で有効にする。切り替えに失敗したら既存 automation を ACTIVE に戻す。テスト・登録完了前に旧 automation を停止しない。

本番タスク `PremiumAlertCli` は 12:55 / 15:26 に PC を起こし、13:05 / 15:36 まで回復時間を確保してから実行する。遅延起動時はすぐ実行する。2つの時刻は同じ Windows タスクで直列化し、共有 mutex でも多重実行を防ぐ。PC のスリープ抑止は最大4時間の実行中だけに限定する。

## 投稿と復旧

- 収集はラッパーが一度だけ行い、実行ごとの `claim.json` を保存する。CLI は再収集しない。
- 投稿済み ID は既存 state を正として除外する。銘柄コードでは重複除外しない。
- CLI は既存の `post --dry-run` → 全エラー修復 → 本投稿 → `status` / `self-test` を使う。
- HTML 更新は既存 GitHub Actions の待機処理・デプロイ・重複防止通知を使う。CLI から追加の workflow_dispatch や完了メッセージを送らない。
- 中断時に未投稿 claim が残れば自動再投稿を止める。Discord の送信結果が不明なまま再送せず、以前の実行ログ・Discord の受信結果・state を突き合わせてから、その claim を引き継ぐ。手動で state を書き換えない。
- `scheduled-latest.json` に `ok=true` があっても、実行対象が0件だった結果と12件などを処理した結果を区別する。`claimed` / `posted` と終了時刻を確認する。
- タスクを登録しただけで未ログオン復旧を検証済みとしない。Session 0 テストに加え、実際の再起動後・未ログオンでの初回予定実行を履歴から確認する。

公式資料: [非対話 CLI](https://learn.chatgpt.com/docs/non-interactive-mode)、[認証](https://learn.chatgpt.com/docs/auth)、[ChatGPT のスケジュール](https://learn.chatgpt.com/docs/automations)。Web版 ChatGPT Workへ移す場合は、ローカル worker・認証・状態をクラウドから扱う仕組みと同等の投稿検証が別途必要。
