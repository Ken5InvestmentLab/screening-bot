# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

# 天底極致スコアリングBot — プロジェクト概要

TradingViewのBOTTOMシグナル銘柄を複数のテクニカル指標でスコアリングし、
Discordにスクリーニング結果をDM送信するBotです。

## システム構成

| コンポーネント | 場所 | 役割 |
|---|---|---|
| Bot本体 | VM `ubuntu@168.110.60.126` / `~/screening-bot/` | pm2で常時稼働（Node.js） |
| スコア最適化 | GitHub Actions `.github/workflows/optimize.yml` | GASの`runDailyMaintenance`完了後に自動起動 |
| 承認デプロイ | GitHub Actions `.github/workflows/deploy.yml` | `/approve-update` コマンドから手動起動 |
| データソース | Google Sheets（`alerts_raw`, `ohlcv_4h`） | バックテスト用シグナル・OHLCVデータ |
| GAS | Google Apps Script | TradingViewアラート受信・OHLCV取得・日次メンテ・GitHub Actions起動 |

## データフロー（全体像）

```
TradingView アラート
    │ alert() / alertcondition
    ▼
GAS doPost() Webhook
    │ alerts_raw シートに書き込み
    ▼
GAS fetchOHLCVForNewAlerts() → PHASE4完了
    │ runDailyMaintenance() 呼び出し
    ▼
GAS runDailyMaintenance() 完了
    │ triggerGitHubActionsOptimize_() → GitHub API workflow_dispatch
    ▼
GitHub Actions optimize.yml
    │ optimize_screener.py --propose
    ▼
候補なし → 自動終了（通知なし）
候補あり → pending_logic.json をコミット + Discord承認チャンネルに通知
    ▼
管理者が Discord で /approve-update を実行
    │ → GitHub Actions deploy.yml 起動
    ▼
optimize_screener.py --apply-pending
    │ screener.js + current_logic.json + index.js 更新 → SCP → pm2 restart
    ▼
Discord /scan コマンドで結果確認
```

## コマンド

### ローカル開発初回セットアップ

```bash
cp .env.example .env   # DISCORD_TOKEN / SPREADSHEET_ID などを埋める
# credentials.json をプロジェクト直下に配置（Google サービスアカウントJSON）
npm install
```

```bash
npm start          # 本番起動（node index.js）
npm run dev        # ホットリロード起動（nodemon）
```

### デプロイ（PowerShellから）

```powershell
scp -i C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key ".\screener.js" ubuntu@168.110.60.126:~/screening-bot/
scp -i C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key ".\index.js" ubuntu@168.110.60.126:~/screening-bot/
ssh -i C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key ubuntu@168.110.60.126
pm2 restart screening-bot
```

### デプロイ（Oracle Cloud Shell経由）

```bash
chmod 600 ~/ssh-key-2026-03-08.key
scp -i ~/ssh-key-2026-03-08.key ~/screener.js ubuntu@168.110.60.126:~/screening-bot/
ssh -i ~/ssh-key-2026-03-08.key ubuntu@168.110.60.126 "pm2 restart screening-bot"
```

### optimize_screener.py の実行

```bash
# 候補を提案のみ（ファイル更新・デプロイなし。GitHub Actionsはこちら）
PYTHONIOENCODING=utf-8 py optimize_screener.py --propose

# 承認済み pending_logic.json を読み込んでデプロイ（deploy.yml はこちら）
PYTHONIOENCODING=utf-8 py optimize_screener.py --apply-pending

# 分析のみ（ファイル更新・デプロイなし・通知なし）
py optimize_screener.py --dry-run
```

## 主要ファイルとアーキテクチャ

- **`screener.js`** — スコアリングロジック本体。**`optimize_screener.py` によって自動上書きされる**。`calculateScore()` を手動変更する場合は `current_logic.json` との整合性に注意。`.gitattributes` により `merge=ours` が設定済み。
- **`index.js`** — Discordコマンドハンドラー。`/scan [stable|aggressive|code]`、プレミアム通知の `premium_scan:<symbolCode>` ボタン、`/approve-update`（管理者専用）を実装。ボタンは既存のコード検索処理へ流し、3秒以内に interaction へ応答する。起動時と24時間ごとに `refreshStats()` でライブ実績を集計しキャッシュ。stable=スコア5以上、aggressive=4以上。
- **`sheets.js`** — Google Sheets APIクライアント。`alerts_raw`（ヘッダーが4行目）と `ohlcv_4h` の2シートを読み取る。`cleanSymbol()` で `TYO:4074` → `4074` に変換。
- **`config.js`** — フィルター定数（下記参照）。**数値は変更禁止**。
- **`optimize_screener.py`** — C(18,6)=18,564通りの指標組み合わせを全探索し、`screener.js` を更新してSCP転送→pm2 restart まで自動実行。**VMで直接実行しない**（RAM 1GB でOOMクラッシュする）。
- **`current_logic.json`** — デプロイ済みのスコアロジック。次回最適化のベースラインとして使用される。`.gitattributes` で `merge=ours`。
- **`pending_logic.json`** — `--propose` が見つけた候補ロジック。承認待ち状態。`--apply-pending` がデプロイ後に削除する。gitignoreされていないため、GitHub Actions経由でコミット・参照される。

### `config.js` のFILTER定数（変更禁止）

```js
VOL_RATIO_MIN: 0.80      // 出来高 >= 5日平均 × 0.80
EMA_GAP_MIN: -3.00       // EMA5-EMA25乖離(%) >= -3.00
EMA25_SLOPE_MIN: -0.50   // EMA25傾き(5日,%) >= -0.50
RANGE_POS_MAX: 0.95      // 5日レンジ位置 >= 0.95なら強制除外
CUMUL3D_MAX: 4.00        // 直近3日上昇率(%) > 4.00なら強制除外
SCORE_STABLE: 4          // /scan stable の最低スコア
SCORE_AGGRESSIVE: 4      // /scan aggressive の最低スコア
RECENT_SIGNAL_DAYS: 30   // シグナル検索期間（日）
MIN_4H_BARS: 30          // 最低4h足本数
```

### `current_logic.json` スキーマ

```json
{
  "method": "A",
  "conditions": ["ema75", "vol20", "body1", "atr5", "stoch75", "rsi5070"],
  "updated_at": "ISO8601",
  "thresholds": {
    "vol20": 2.0,
    "body1": 2.0,
    "atr5": 5.0,
    "stoch75": 65
  }
}
```

利用可能な条件キー（`optimize_screener.py` の `BOOL_CONDS` で定義。Stable/Sniper共通）: `ema25`, `ema75`, `vol20`, `vol15`, `vol12`, `sbull`, `body1`, `macdgc`, `macdpos`, `atr5`, `atr3`, `atr7`, `hb20`, `stoch75`, `stoch60`, `rsi5070`, `rsi4060`, `bb80`, `ich_tk`, `ich_price_tenkan`, `ich_price_kijun`, `ich_cloud_above`, `ich_cloud_green`, `ich_chikou`, `ich_kumo_break`

### `screener.js` の処理フロー

1. `aggregateToDailyBars(bars)` — 4h足 → 日次バーに集約（同日はvolume合算・high/low更新・closeは最後）
2. `computeIndicators(dailyBars, signalIdx)` — EMA/ATR/MACD/RSI/Stoch/BB を `signalIdx` 時点で計算
3. `calculateScore(ind)` — 現行ロジックで0〜6点スコアを付与（各条件1点）
4. `screenSymbol(...)` — 上記3関数をラップし、シグナル日・現在変化率・futurePrice等を付けて返す

### `optimize_screener.py` の評価指標

- **採用基準①**: `composite > baseline`（ベースラインを上回ること）
- **採用基準②**: `wr_raw > baseline.wr_raw`（勝率を上回ること、strict `>`）
- **採用基準③**: `win10_raw >= 5` かつ `win10_raw / n >= (baseline.win10_raw / baseline.n) × 0.90`（少数精鋭ロジックを絶対件数だけで弾かない）
- **Stable品質ゲート**: 通常時の全件★6最低件数は25件、rescue mode時のみ20件に緩和する。閾値最適化は上位候補に限定し、最終採用判定は広い候補プールを全件再評価する。
- **compositeスコア**: `COMPOSITE_VARIANT = "rate_adjusted"` — `wr×50 + avg×100 + (win10−lose10)/total×150`（recency半減期90日の加重）
- **Method A**: 6条件の組み合わせ全探索（各1点）
- **Method B**: lift分析による重み付きスコア（各1〜2点）
- **閾値チューニング**: Stage 2でグリッドサーチ（訓練/テスト分割あり）。組み合わせ数が20万超の場合は独立最適化に切り替え

## デプロイ構成

- **SSH key**: `C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key`（自宅PC）/ `~/ssh-key-2026-03-08.key`（Cloud Shell）
- **VM**: `ubuntu@168.110.60.126`、pm2プロセス名 `screening-bot`
- **自動実行トリガー**: GASの `runDailyMaintenance` 完了 → `triggerGitHubActionsOptimize_()` → GitHub Actions `workflow_dispatch`
- **承認フロー**: `optimize.yml`（`--propose`）→ Discord通知 → 管理者が `/approve-update` → `deploy.yml`（`--apply-pending`）→ デプロイ
- **GitHub Actions コミット対象**: `current_logic.json` / `screener.js` / `index.js` の3ファイル（deploy.yml実行時）
- **バックアップ**: `backups/screener_backup_YYYYMMDD_HHMMSS.js`（最大30件）

### GitHub Actions 必要Secrets

| Secret名 | 内容 |
|---|---|
| `GOOGLE_CREDENTIALS` | サービスアカウントJSONの中身 |
| `SSH_PRIVATE_KEY` | VMへのSSH秘密鍵 |

### VM 環境変数（`~/screening-bot/.env`）

| キー | 内容 |
|---|---|
| `DISCORD_TOKEN` | Discord BotトークN |
| `SPREADSHEET_ID` | Google SheetsのID |
| `ADMIN_USER_ID` | `/approve-update` を実行できるDiscordユーザーID |
| `GITHUB_TOKEN` | Classic PAT（`workflow` スコープ）。`/approve-update` から `deploy.yml` を起動するために使用 |
| `GITHUB_REPO` | `Ken5InvestmentLab/screening-bot` |

### GAS Script Properties

| キー | 内容 |
|---|---|
| `SPREADSHEET_ID` | Google SheetsのID |
| `GAS_SHARED_SECRET` | Webhook署名検証用シークレット |
| `DISCORD_STATS_WEBHOOK_URL` | 週次レポート送信先 |
| `DISCORD_WEBHOOK` | OHLCV同期完了通知先 |
| `GITHUB_PAT` | Classic PAT（`workflow` スコープ）。GASから `optimize.yml` を起動するために使用 |

## 重要な注意事項

- **`optimize_screener.py` をVM上で直接実行しない** — RAM 1GB のVMでOOMが発生してVMごとクラッシュする。
- VMクラッシュ時はOracle Cloudコンソールから強制リブート → `pm2 restart screening-bot` で復旧。
- Discord Webhook送信時は `User-Agent: DiscordBot (screening-bot, 1.0)` ヘッダーが必須（ないとCloudflareに403）。
- `optimize_screener.py` 実行時は `PYTHONIOENCODING=utf-8` が必要（Windows文字化け防止）。
- `screener.js` の `calculateScore()` を手動編集しても、次回 `optimize_screener.py` 実行時に上書きされる。手動変更は `current_logic.json` も同時に更新すること。
- `screener.js` / `current_logic.json` / `index.js` は `.gitattributes` で `merge=ours` に設定済み。`git merge` 時にこれらのファイルが外部変更で上書きされることはない。

## コードの落とし穴（Gotchas）

### 日付フォーマットの不一致
- `alerts_raw` シート: `"2026/03/18"`（スラッシュ区切り）
- `ohlcv_4h` シート: `"2026-03-18"`（ハイフン区切り）
- 比較時は必ず `replace(/\//g, '-').slice(0, 10)` で正規化すること
- **絶対やってはいけない**: `String(new Date(...)).slice(0, 10)` → `"Wed Mar 18"` になる（v14.0のバグ）
- **正しい方法**: `new Date(...).toISOString().slice(0, 10)`

### インジケーター計算の注意点
- EMA25は25本以上のバーが必要。不足時は `null` を返す。`if (!ind) return null` の null チェックが全関数に必須。
- **出来高20日平均は当日を除外**する（前20日間のみ）。当日を含めると循環参照になる。
- `aggregateToDailyBars()` はバーがソート済みであることを前提とする。未ソートだと20日ルックバックウィンドウが壊れる。
- `screenSymbol()` はシグナル日**以前**で最も近いバーを探す（完全一致不要）。シグナル日がバーの最終日より新しい場合は `null` を返す。

## Future Work

- **Moonshot mode is deferred**: the medium-term double-bagger mode should be revisited only after enough `perf_20bd` / `perf_40bd` outcomes accumulate. The current sample is still too thin and likely to overfit.
