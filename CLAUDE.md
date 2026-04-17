# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 天底極致スコアリングBot — プロジェクト概要

TradingViewのBOTTOMシグナル銘柄を複数のテクニカル指標でスコアリングし、
Discordにスクリーニング結果をDM送信するBotです。

## システム構成

| コンポーネント | 場所 | 役割 |
|---|---|---|
| Bot本体 | VM `ubuntu@168.110.60.126` / `~/screening-bot/` | pm2で常時稼働（Node.js） |
| スコア最適化 | ローカル `optimize_screener.py` | 毎日19:30にタスクスケジューラーで自動実行 |
| データソース | Google Sheets（`alerts_raw`, `ohlcv_4h`） | バックテスト用シグナル・OHLCVデータ |

## データフロー（全体像）

```
TradingView アラート
    │ alert() / alertcondition
    ▼
Google Apps Script (GAS) Webhook
    │ alerts_raw シートに書き込み + ohlcv_4h に4h足OHLCVを追記
    ▼
Google Sheets（SPREADSHEET_ID）
    │ googleapis で読み取り
    ▼
screener.js — calculateScore()
    │ 4h足 → 日次バー集約 → 指標計算 → スコアリング
    ▼
Discord DM（/scan コマンドのレスポンス）
```

## コマンド

### ローカル開発

```bash
npm start          # 本番起動（node index.js）
npm run dev        # ホットリロード起動（nodemon）
```

### デプロイ（PowerShellから）

```powershell
# VMにファイル転送
scp -i C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key ".\screener.js" ubuntu@168.110.60.126:~/screening-bot/
scp -i C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key ".\index.js" ubuntu@168.110.60.126:~/screening-bot/

# VM接続 → pm2 再起動
ssh -i C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key ubuntu@168.110.60.126
pm2 restart screening-bot
```

### optimize_screener.py の実行

```bash
# 通常実行（分析→確認プロンプト→デプロイ）
py optimize_screener.py

# 自動承認・自動デプロイ（タスクスケジューラーはこちら）
PYTHONIOENCODING=utf-8 py optimize_screener.py --yes

# 分析のみ（ファイル更新・デプロイなし）
py optimize_screener.py --dry-run
```

## 主要ファイルとアーキテクチャ

- **`screener.js`** — スコアリングロジック本体。**`optimize_screener.py` によって自動上書きされる**。`calculateScore()` の条件を手動変更する場合は `current_logic.json` との整合性に注意。
- **`index.js`** — Discordコマンドハンドラー。`/scan [stable|aggressive]`・`/help` の2コマンドを実装。起動時と24時間ごとに `refreshStats()` でライブ実績を集計しキャッシュする。
- **`sheets.js`** — Google Sheets APIクライアント。`alerts_raw`（ヘッダーが4行目）と `ohlcv_4h` の2シートを読み取る。
- **`optimize_screener.py`** — C(18,6)=18,564通りの指標組み合わせを全探索し、`screener.js` を更新してSCP転送→pm2 restart まで自動実行。
- **`current_logic.json`** — デプロイ済みのスコアロジック。次回最適化のベースラインとして使用される。

### `current_logic.json` スキーマ

```json
{
  "method": "A",
  "conditions": ["ema25", "vol20", "sbull", "atr5", "atr7", "stoch75"],
  "updated_at": "ISO8601",
  "thresholds": {
    "vol20": 2.5,
    "sbull": 2.0,
    "atr5": 5.0,
    "atr7": 5.0,
    "stoch75": 65
  }
}
```

`conditions` に指定できるキーは `optimize_screener.py` の `INDICATORS` 辞書で定義されている（`ema25`, `ema75`, `vol20`, `sbull`, `macdGC`, `macdPos`, `atr5`, `atr7`, `rsi50`, `stoch65`, `stoch75`, `bbPct30`, `hiBrk20` など）。

### `screener.js` の処理フロー

1. `aggregateToDailyBars(bars)` — 4h足 → 日次バーに集約（同日のbarsはvolume合算、high/low更新、closeは最後）
2. `computeIndicators(dailyBars, signalIdx)` — シグナル日時点のEMA/ATR/MACD/RSI/Stoch/BBを計算
3. `calculateScore(ind)` — 現行ロジックで0〜6点スコアを付与
4. `screenSymbol(...)` — 上記3関数をラップし、シグナル日・現在変化率・futurePrice等を付けて返す

## デプロイ構成

- **SSH key**: `C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key`
- **VM**: `ubuntu@168.110.60.126`、pm2プロセス名 `screening-bot`
- **タスクスケジューラー**: `screening-bot-daily-optimize`（毎日19:30、`--yes` フラグ付き）
- **バックアップ**: `backups/screener_backup_YYYYMMDD_HHMMSS.js`（最大30件）

## 重要な注意事項

- **`optimize_screener.py` をVM上で直接実行しない** — RAM 1GB のVMでOOMが発生してVMごとクラッシュする。最適化はローカルPCで実行し、結果をSCPでVMに転送する設計。
- VMクラッシュ時はOracle Cloudコンソールから強制リブート → `pm2 restart screening-bot` で復旧。
- Discord Webhook送信時は `User-Agent: DiscordBot (screening-bot, 1.0)` ヘッダーが必須（ないとCloudflareに403で弾かれる）。
- `optimize_screener.py` 実行時は `PYTHONIOENCODING=utf-8` が必要（Windowsでの文字化け防止）。
