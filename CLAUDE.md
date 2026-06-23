# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Retired modes

Moonshot was removed because it overlaps with Mega40. Do not recreate `/scan moonshot`, `current_logic_moonshot.json`, `pending_logic_moonshot.json`, or Moonshot optimizer paths. Use the report-only Mega40 modes instead.

# 天底極致スコアリングBot — プロジェクト概要

TradingViewのBOTTOMシグナル銘柄を複数のテクニカル指標でスコアリングし、
Discordにスクリーニング結果をDM送信するBotです。

## システム構成

| コンポーネント | 場所 | 役割 |
|---|---|---|
| Bot本体 | VM `ubuntu@168.110.60.126` / `~/screening-bot/` | pm2で常時稼働（Node.js） |
| スコア最適化 | GitHub Actions `.github/workflows/optimize.yml` | GASの`runDailyMaintenance`完了後に自動起動 |
| 承認デプロイ | GitHub Actions `.github/workflows/deploy.yml` | `/approve-update` コマンドから手動起動 |
| 否決ワークフロー | GitHub Actions `.github/workflows/reject.yml` | `/reject-update` コマンドから手動起動 |
| データソース | Google Sheets（`alerts_raw`, `signals_archive`, `ohlcv_4h`） | バックテスト用シグナル・OHLCVデータ。`signals_archive` はバックテスト母数拡張用（365日保持）、`optimize_screener.py` 内部のみで使用 |
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
    │ optimize_screener.py --win-threshold-sweep "0.05,0.07,0.08,0.10" --propose --yes
    │ （複数の +X% 閾値で並列バックテスト → ゲートクリアした最良を自動採用）
    ▼
候補なし → SCP + pm2 restart（Bot を再起動して統計キャッシュ更新、通知なし）
候補あり → pending_logic.json / pending_logic_sniper.json をコミット + Discord承認チャンネルに通知
    ▼
管理者が Discord で /approve-update を実行
    │ → GitHub Actions deploy.yml 起動
    ▼
optimize_screener.py --apply-pending
    │ screener.js + current_logic.json + current_logic_sniper.json + index.js 更新 → SCP → pm2 restart
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

# レスキューモードを自動承認して実行（GitHub Actionsの --yes フラグ）
PYTHONIOENCODING=utf-8 py optimize_screener.py --propose --yes

# +X% 閾値の単発上書き（Method Bリフト分析・composite・採用ゲート全てに伝播）
PYTHONIOENCODING=utf-8 py optimize_screener.py --dry-run --win-threshold 0.07

# +X% 閾値スイープ（各値で自身を再帰実行して比較表を表示。dry-run強制）
PYTHONIOENCODING=utf-8 py optimize_screener.py --win-threshold-sweep "0.05,0.07,0.08,0.10"

# +X% 閾値スイープ＋自動採用（GitHub Actionsで使う本番フロー。最良閾値で --propose 実行）
PYTHONIOENCODING=utf-8 py optimize_screener.py --win-threshold-sweep "0.05,0.07,0.08,0.10" --propose --yes
```

## 主要ファイルとアーキテクチャ

- **`screener.js`** — スコアリングロジック本体。**`optimize_screener.py` によって自動上書きされる**。`calculateScore()` / `calculateScoreSniper()` を手動変更する場合は `current_logic.json` / `current_logic_sniper.json` との整合性に注意。`.gitattributes` により `merge=ours` が設定済み。
- **`index.js`** - Discord command handler. `/scan [stable|aggressive|sniper|code]`, `/help`, `/approve-update`, and `/reject-update` are implemented here.
- **`sheets.js`** — Google Sheets APIクライアント。`alerts_raw`（ヘッダーが4行目）と `ohlcv_4h` の2シートを読み取る。`alerts_raw` からは `perf_5bd / perf_10bd / perf_20bd / perf_40bd` を含む全パフォーマンスカラムを取得。`premium_alert_log` シートからトリガー理由も取得。`cleanSymbol()` で `TYO:4074` → `4074` に変換。
- **`config.js`** — フィルター定数（下記参照）。**数値は変更禁止**。
- **`optimize_screener.py`** — 指標の組み合わせを全探索し、`screener.js` を更新してSCP転送→pm2 restart まで自動実行。**VMで直接実行しない**（RAM 1GB でOOMクラッシュする）。バックテスト評価時は `alerts_raw` と `signals_archive` を統合して使用（`alert_id` ベースで重複除去・Walk-forward 70/30 分割）。`signals_archive` はバックテスト内部のみで使用し、`/scan` 結果・Discord 通知・`index.js` には一切影響しない。
- **`current_logic.json`** — デプロイ済みのStableスコアロジック。次回最適化のベースラインとして使用される。`.gitattributes` で `merge=ours`。
- **`current_logic_sniper.json`** — デプロイ済みのSniperモードロジック（バックテスト統計付き）。`.gitattributes` で `merge=ours`。
- **`pending_logic.json`** — `--propose` が見つけた候補Stableロジック。承認待ち状態。`--apply-pending` がデプロイ後に削除する。gitignoreされていないため、GitHub Actions経由でコミット・参照される。
- **`pending_logic_sniper.json`** — `--propose` が見つけた候補Sniperロジック。`pending_logic.json` と並行して生成される。
- **`rescue_state.json`** — オプティマイザーの劣化検知状態を追跡するファイル。連続ブリーチストリーク数・プロジェクション統計・待機状態を保存する。

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
  "conditions": ["vol15", "vol12", "atr5", "atr7", "stoch75", "pre_down3"],
  "updated_at": "ISO8601",
  "thresholds": {
    "vol20": 2.0,
    "body1": 2.0,
    "atr5": 5.0,
    "stoch75": 65
  }
}
```

利用可能な条件キー（`optimize_screener.py` の `INDICATORS` / `BOOL_CONDS` で定義）:
`ema25`, `ema75`, `vol20`, `vol15`, `vol12`, `sbull`, `body1`, `macdgc`, `macdpos`, `atr5`, `atr3`, `atr7`, `hb20`, `stoch75`, `stoch60`, `rsi5070`, `rsi4060`, `bb80`, `pre_down3`, `smbull_seq2`, `smbull_seq3`

### `current_logic_sniper.json` スキーマ

```json
{
  "method": "sniper",
  "conditions": ["ema25", "sbull", "atr5", "atr7", "hb20", "rsi4060"],
  "updated_at": "ISO8601",
  "thresholds": {},
  "backtest": { "source": "all", "n": 18, "wr": 77.8, "avg": 1.8 },
  "wr_raw": 0.778
}
```

- **`updated_at`** はロジック採用日。Sniperレスキュー判定の「採用後ライブ実績」集計の起点として参照される。
- **`backtest` / `wr_raw`** は `optimize_screener.py` 実行時に `alerts_raw + signals_archive` 全体で毎回再計算され上書きされる。ロジックが同一でも統計だけ最新化される（`updated_at` は据え置き）。


### `screener.js` の処理フロー

1. `aggregateToDailyBars(bars)` — 4h足 → 日次バーに集約（同日はvolume合算・high/low更新・closeは最後）
2. `computeIndicators(dailyBars, signalIdx)` — EMA/ATR/MACD/RSI/Stoch/BB/Ichimoku/RCI/CCIなど20以上の指標を `signalIdx` 時点で計算
3. `calculateScore(ind)` — Stableモード: 現行ロジックで0〜6点スコアを付与（各条件1点）
4. `calculateScoreSniper(ind)` — Sniperモード: 高精度6条件で厳密スコアを付与（全条件通過のみ採用）
5. `screenSymbol(...)` — 上記関数をラップし、シグナル日・現在変化率・futurePrice等を付けて返す

### `optimize_screener.py` の評価指標

- **採用基準①**: `composite > baseline`（ベースラインを上回ること）
- **採用基準②**: `wr_raw >= baseline.wr_raw`（勝率を下回らないこと、`STRICT_WR=False` で等号許可。同率なら avg / win10 / composite の優劣で勝てば採用）
- **採用基準③**: `win10_raw >= baseline.win10_raw × 0.80`（★6件数の20%以内の減少）
- **compositeスコア**: `COMPOSITE_VARIANT = "rate_adjusted"` — `wr×50 + avg×100 + (win10−lose10)/total×150`（recency半減期90日の加重）
- **Method A**: 6条件の組み合わせ全探索（各1点）
- **Method B**: lift分析による重み付きスコア（各1〜2点）
- **閾値チューニング**: Stage 2でグリッドサーチ（訓練/テスト分割あり）。組み合わせ数が20万超の場合は独立最適化に切り替え
- **Sniperモード採用基準**: `SNIPER_WR_MIN = 0.65`（勝率65%以上）。レスキュー時は `SNIPER_RESCUE_WR_MIN = 0.55` に緩和され、現行 strict 超え条件も免除される
- **Stableモード採用基準**: `STABLE_WR_MIN = 0.60`、`STABLE_AVG_MIN = 0.05`

### レスキューモード（Rescue Mode）

`optimize_screener.py` は現行ロジックのパフォーマンスを継続監視し、2日連続で劣化（ブリーチ）を検知すると自動的にレスキューモードに入る。レスキューモードでは採用基準を緩和し、より広い条件から候補を探す。`rescue_state.json` に状態が永続化される。

- **Stable レスキュー**: `detect_rescue_mode()` が `STABLE_WR_MIN = 0.60` 等を割り込むと breach。状態は `rescue_state.json` トップレベル（`status` / `streak` / `current_stats6` ...）に保存。
- **Sniper レスキュー**: `detect_rescue_mode_sniper()` が以下を判定。状態は `rescue_state.json` の `sniper` キー配下に独立保存（Stableとは別ストリーク）。
  - 全件再計算の勝率が `SNIPER_RESCUE_TRIGGER_WR = 0.60` 未満
  - または採用日以降のライブ実績（`SNIPER_RESCUE_TRIGGER_N = 10` 件以上）が同じく60%未満
  - 「健全スキップ」(`SNIPER_HEALTHY_SKIP_WR = 0.75 / n ≥ 15`) もライブ実績が `SNIPER_LIVE_HEALTH_WR = 0.60` を下回ると無効化される
  - レスキュー発動中は採用最低勝率を `SNIPER_RESCUE_WR_MIN = 0.55` に緩和し、現行 strict 超え条件も免除
  - 候補なしのときは Discord 承認チャンネルに通知（`notify_discord_sniper_rescue_no_candidate`）

## デプロイ構成

- **SSH key**: `C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key`（自宅PC）/ `~/ssh-key-2026-03-08.key`（Cloud Shell）
- **VM**: `ubuntu@168.110.60.126`、pm2プロセス名 `screening-bot`
- **自動実行トリガー**: GASの `runDailyMaintenance` 完了 → `triggerGitHubActionsOptimize_()` → GitHub Actions `workflow_dispatch`
- **承認フロー**: `optimize.yml`（`--win-threshold-sweep ... --propose --yes`: 複数閾値スイープ→ゲートクリアした最良を自動採用、候補なしでも SCP + pm2 restart で Bot 再起動）→ Discord通知 → 管理者が `/approve-update` → `deploy.yml`（`--apply-pending`）→ デプロイ
- **否決フロー**: 管理者が `/reject-update` → `reject.yml` → `pending_logic.json` / `pending_logic_sniper.json` を削除してコミット
- **GitHub Actions コミット対象**: `current_logic.json` / `current_logic_sniper.json` / `screener.js` / `index.js` の4ファイル（deploy.yml実行時）。`pending_logic.json` / `pending_logic_sniper.json` / `rescue_state.json`（optimize.yml実行時）
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
| `GITHUB_TOKEN` | Classic PAT（`workflow` スコープ）。`/approve-update` / `/reject-update` から `deploy.yml` / `reject.yml` を起動するために使用 |
| `GITHUB_REPO` | `Ken5InvestmentLab/screening-bot` |

### GAS Script Properties

| キー | 内容 |
|---|---|
| `SPREADSHEET_ID` | Google SheetsのID |
| `GAS_SHARED_SECRET` | Webhook署名検証用シークレット |
| `DISCORD_STATS_WEBHOOK_URL` | 週次レポート送信先 |
| `DISCORD_WEBHOOK` | OHLCV同期完了通知先 |
| `GITHUB_PAT` | Classic PAT（`workflow` スコープ）。GASから `optimize.yml` を起動するために使用 |

## 自動生成ファイル一覧

| ファイル | 生成元 | 役割 |
|---|---|---|
| `screener.js` | `optimize_screener.py` | スコアリングロジック本体 |
| `current_logic.json` | `optimize_screener.py` | デプロイ済みStableロジック |
| `current_logic_sniper.json` | `optimize_screener.py` | デプロイ済みSniperロジック |
| `pending_logic.json` | `optimize_screener.py --propose` | 承認待ちStableロジック候補 |
| `pending_logic_sniper.json` | `optimize_screener.py --propose` | 承認待ちSniperロジック候補 |
| `rescue_state.json` | `optimize_screener.py` | レスキューモード状態追跡 |

これらは `.gitattributes` で `merge=ours` に設定済み。`git merge` 時に外部変更で上書きされることはない。

## 重要な注意事項

- **`optimize_screener.py` をVM上で直接実行しない** — RAM 1GB のVMでOOMが発生してVMごとクラッシュする。
- VMクラッシュ時はOracle Cloudコンソールから強制リブート → `pm2 restart screening-bot` で復旧。
- Discord Webhook送信時は `User-Agent: DiscordBot (screening-bot, 1.0)` ヘッダーが必須（ないとCloudflareに403）。
- `optimize_screener.py` 実行時は `PYTHONIOENCODING=utf-8` が必要（Windows文字化け防止）。
- `screener.js` の `calculateScore()` / `calculateScoreSniper()` を手動編集しても、次回 `optimize_screener.py` 実行時に上書きされる。手動変更は `current_logic.json` / `current_logic_sniper.json` も同時に更新すること。
- `screener.js` / `current_logic.json` / `current_logic_sniper.json` / `index.js` は `.gitattributes` で `merge=ours` に設定済み。

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

### Stable / Sniper mode separation
- `calculateScore()` and `calculateScoreSniper()` use independent condition sets.
- `current_logic.json` and `current_logic_sniper.json` are managed separately.
