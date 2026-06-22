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

### スコアリング検証レポート

```bash
# Bot本体・Discordコマンド・Moonshotロック状態は変更せず、検証用Markdown/HTMLだけを生成
PYTHONIOENCODING=utf-8 py generate_mega_validation_report.py
```

特定時刻時点の表示へ手動で戻す必要がある場合だけ、`MEGA_REPORT_ALERT_RECEIVED_CUTOFF="YYYY-MM-DD HH:mm"` または `--alert-received-cutoff "YYYY-MM-DD HH:mm"` を指定して再生成する。通常生成やGitHub Actionsではこのカットオフを指定しない。
`Mega Validation Report` を手動 `workflow_dispatch` でHTML再生成する場合、Discord完了通知は原則送らない。通知が本当に必要な通常運用だけ `notify_discord=true` を明示する。

BOTTOMシグナルのStable★数や各モード条件は、シグナル点灯足時点のOHLCVだけで特徴量を計算する。後から同日13:00足などが `ohlcv_4h` に追加されても、当該シグナルの採点を日足の「最後の4h足close」で再計算しない。13:00より前に受信した当日シグナルは09:00足まで、14:00以降に受信した当日シグナルは13:00足までを特徴量に使い、現在株価・将来騰落率の評価だけは後続OHLCVを使う。
本番ロジックへ反映する前の現行比較では、成績指標だけでなく現行銘柄・候補銘柄・追加/除外/共通の銘柄差分も提示する。スコアロジック更新候補をDiscordへ通知するときは、現行/候補の銘柄一覧、共通/追加/除外、成績比較を含むスプレッドシートを添付する。

サイトタイトルとトップH1は `天底極致 スコアリングBot レポート` にする。
レポート上の評価日後株価は騰落率から逆算せず、OHLCVの日足にある実際の終値を表示する。エントリー価格は銘柄セル内のボラティリティタグ右隣に表示し、列は増やさない。PCの表表示は左揃えを維持する。スマホカード表示では銘柄セル内に主要情報だけの概要を出し、詳細を見るボタンで操作ボタンや非対象評価日などの全情報を開く。

出力先はトップページ `reports/mega_validation_report_latest.html`、無料版トップページ `reports/mega_validation_report_latest_free.html`、Markdown互換出力 `reports/mega_validation_report_latest.md`、モード別ページ `reports/mega_validation_report_<mode>.html`、無料版モード別ページ `reports/mega_validation_report_<mode>_free.html`、使い方ページ `reports/mega_validation_report_guide.html`、無料版使い方ページ `reports/mega_validation_report_guide_free.html`、日付フィルターやテーマ切替などの外部スクリプト `reports/report-interactions.js`、保存済みテーマをCSS前に反映する `reports/report-theme-init.js`、Discordファンダ本文の再利用キャッシュ `reports/mega_report_fundamental_cache.json`。ユーザー向けレポートとして、Stable ★6、Sniper 勝率重視、Mega5 短期リバウンド、Mega40 深押し反転、Mega40 下ヒゲ回復だけを対象にし、候補スコアカードや実装判断ゲートなどの内部向けセクションは出さない。トップページは有料版では検出された銘柄一覧、モード別サマリー、全体成績の順、無料版では全体成績、モード別サマリー、検出された銘柄一覧の順に出し、モード別サマリーと重複するモード別リンク専用セクションは出さない。使い方・対象銘柄と検出モードの見方は独立した使い方ページに集約し、トップページや各モード詳細ページの下部へ長文ガイドを再配置しない。使い方ページには、TradingView用インジケーター「天底極致 - 蒼橙の審眼 -」の底シグナルを対象にすること、システム稼働開始日が2026年3月5日でありそれ以前の底シグナルは記録されていないこと、監視対象条件、ボラティリティタグ説明、検出モードの見方、ファンダ分析はシグナル検出時点の分析であり最新情報はユーザー自身でも確認することを載せる。各銘柄のボラタグにはhover/focus用の説明を持たせる。日別検出一覧は全BOTTOMシグナルを表示し、日付レンジ・証券コード・Stable条件の★数・現在株価・複数テクニカル条件で絞り込めるようにする。日付レンジは初期空欄のままにし、表示日の初期値は最新日にする。検索フォームの証券コード例は実在コードを避けて `1234` のような架空例にする。表示日を全期間にした場合でも一度に大量描画せず、100件ずつ追加表示する。該当モード外の銘柄もStable条件の★0〜6を付けて星の多い順に並べる。無料版では検出された銘柄一覧・銘柄検索結果、Megaモード3種の銘柄一覧、未確定ウォッチリストの実銘柄データをHTMLに含めず、「有料会員限定」「アクセス権を購入する」などユーザーに分かりやすい誘導文言を表示する。無料版のMegaモード詳細ページでは成績サマリーを表示し、条件詳細と銘柄一覧は有料会員限定にする。無料版のStable/Sniper確定済み銘柄は既存の並び順で上位10件ずつ、合計20件まで表示し、その無料サンプル分だけファンダ分析本文もHTML内で表示できるようにする。続きは有料会員への導線ボタンを表示する。銘柄一覧はモードごとの別ページへ分け、各モードページでは他モード重複を一目で分かるように表示し、Stable ★6以外ではStable条件の★数も表示する。全HTMLに固定ヘッダーナビを置き、主要セクションとモード別ページへのリンクを二段に分けて常時表示する。ヘッダー右端に初期ライト表示のダークモードトグルを置き、端末ブラウザの `localStorage` に保存する。保存済みダークモードのライト表示ちらつきを避けるため、`report-theme-init.js` を各HTMLのCSSより前に読み込ませる。全HTMLにコピーライトと X / Discord / ココナラへの外部リンク付きフッターを置く。モード別ページでは成績サマリー・確定済み銘柄一覧・未確定ウォッチリストへのページ内アンカーと使い方ページへのリンクを出す。ユーザー向け表示は過去1年分だけにし、通常表示とアーカイブ表示を分けない。見出しや説明文には `alerts_raw` や `signals_archive` など内部シート名を出さず、誰が見ても意味が分かる表現にする。勝率は0%の引き分け銘柄を分母から除外して計算する。各モードでは確定済み成績と未確定ウォッチリスト全件を表示し、未確定ウォッチリストの経過はカレンダー日数ではなくOHLCVの日足に基づく営業日数で表示し、銘柄ごとにTradingViewチャートを出す。銘柄一覧の騰落率セルには株価も小さく併記し、列数を増やして見づらくしない。Discord投稿済みファンダ分析へのリンクは同じシグナルIDに存在する場合だけ使い、同一銘柄の別シグナルへ使い回さない。未連携ラベルや代替ファンダリンクは出さない。ボタン順はファンダ分析、チャートの順にする。銘柄セルには証券コードと社名を併記する。操作ボタンは右端の専用列ではなく銘柄セル内に横並びで置き、チャート単独でも幅を広げない。Discord本文のHTML展開は `reports/mega_report_fundamental_cache.json` を優先して再利用し、`MEGA_REPORT_FETCH_DISCORD_MESSAGES=1` の明示時だけ未キャッシュURLと直近キャッシュ済みURLをDiscord APIから取得する。Discord投稿済みファンダ本文を編集した後のHTML再生成では、この取得を有効にして編集後本文をキャッシュへ反映してからHTMLへ静的に埋め込む。有料版HTMLと無料版Stable/Sniperサンプル分へ静的に埋め込み、ファンダ分析ボタンはDiscordチャンネルへ直接遷移させず必ずHTML内ポップアップとして表示する。GitHub Actions の `Mega Validation Report` はこの取得を有効にし、無料版HTMLではStable/Sniperサンプル以外にDiscord本文もDiscord URLも入れず、対象外のファンダ分析ボタンは `/purchase` へ誘導する。820px未満の通常スマホ幅では銘柄テーブルを銘柄セルだけの折り畳み概要表示に切り替え、概要には銘柄/社名、ボラ/Entry、日付、Stable★、該当モード、現在騰落、対象評価日の騰落だけを出し、詳細を見るボタンで非対象評価日、他モード、ファンダ分析/チャートボタンなど全情報を開く。40営業日評価では5・10・20営業日後を閉じた概要に出さず、5営業日評価では10・20・40営業日後を閉じた概要に出さない。ChromeのPC版サイト表示のような広めのモバイルviewportでは表レイアウトを維持する。GitHub Actions の `Mega Validation Report` は `Daily Screener Optimization` の optimizer 実行前、13:21先行OHLCV取得の完了時に同じレポートを再生成し、差分があれば `reports/` だけを自動コミットする。

銘柄検索モードの検索条件保存は端末ブラウザの `localStorage` だけで行い、保存対象は日付以外の条件に限定する。表示日・開始日・終了日は保存せず、次回表示時は常に最新日の通常初期表示へ戻す。保存チェックを外したら保存済み条件を削除する。

`Mega Validation Report` workflow はDiscord Bot tokenが無い環境でもHTML再生成自体を失敗させず、リンクのみのファンダ導線で生成・デプロイを継続する。

Mega5/Mega40 の承認済み条件は `current_logic_mega.json` を正とし、`Daily Screener Optimization` 内の `optimize_screener.py --propose-mega-report-logic-only` は `pending_logic_mega.json` への提案だけを行う。Mega提案は確定成績、検証期間、未確定ウォッチリスト銘柄の現在成績、件数低下による過学習リスクを見て、基準未満ならpendingを作らず自動却下する。承認済みMega条件を変更するのは `/approve-update target:<mega系>` で明示承認されたときだけで、却下は `/reject-update target:<mega系>` で対象モードを選ぶ。これはHTML/Markdownレポート専用で、Bot本体の `screener.js` / `index.js` や `/scan` コマンドにMegaモードを追加しない。

レポートヘッダーの二段ナビは、1段目に `天底スコアリングTop`、モード別ページ、使い方ページリンク、ダークモードトグル、2段目に銘柄検索などの主要セクションを置く。

### MegaレポートのDiscordロール制限配信

`report-gate/` は Cloudflare Worker `scoring-bot-report`（公開URL: `https://scoring-bot-report.ipo-ken5-5489.workers.dev/`）で `reports/mega_validation_report_latest.html` / `reports/mega_validation_report_<mode>.html` と対応する `_free.html` を出し分ける独立サブプロジェクト。既存リンク互換のため `screening-bot-report-gate` にも同じコードとアセットをデプロイする。`npm run sync-report` は `reports/mega_validation_report*.html`、`reports/report-interactions.js`、`reports/report-theme-init.js`、`reports/report-assets/*.png` を `report-gate/public/` に同期し、Workerは未ログインならDiscord OAuthへリダイレクトし、OAuth後に `DISCORD_ALLOWED_ROLE_IDS` のロール保持セッションならフルHTML、ロール未保持セッションなら対応する `_free.html` を返す。無料版HTMLには有料対象の実銘柄データを含めず、モード別サマリーなどの集計数値は無料版にも表示し、`/purchase` 経由で `ACCESS_PURCHASE_URL` へ誘導すること。WorkerのCSPはレポートで外部同一オリジンJSだけを許可するため、レポートの動的UIはインライン `<script>` にせず、同期対象の `reports/report-interactions.js` に置き、CSS前に必要なテーマ初期化だけ `reports/report-theme-init.js` に分けること。モード別リンクやレポート用JSを増やした場合は同期対象とWorkerの許可パスを揃え、生成済み `reports/mega_validation_report*.html` / `reports/report-interactions.js` / `reports/report-theme-init.js` の変更でも `report-gate-deploy.yml` が走るようにpathsを保つこと。Bot本体やDiscordコマンドに混ぜないこと。WorkerはDiscord OAuth2の `identify guilds.members.read` でログインしたユーザーのguild memberを取得し、OAuth `state` はcookie依存に戻さず署名付きstateパラメータで検証し、OAuth access token・refresh token・直近ロール確認結果は暗号化したHttpOnly session cookieにだけ保存する。セッションTTLは長期デバイス承認用に1年を基本とし、アクセストークン期限切れ時はrefresh tokenで裏側更新する。ロール不足時はsession cookieを消さず無料版表示に留め、ロール復帰時に同じデバイスで再OAuth承認を求めない。refresh tokenが無効な場合だけsession cookieを消して再OAuthへ戻す。フルHTMLには `/auth/guard.js` を注入し、開きっぱなしページも `/auth/check` で定期的にロール再確認するため、この仕組みを外す変更はしないこと。Discord APIの429回避として短時間のロールキャッシュと猶予を持たせている。
`report-gate` の `npm run check` はdry-runまでで公開Workerは更新しない。ローカルで即時反映する場合は `npm run deploy` と `npm run deploy:legacy` を実行し、`/report-interactions.js` などの公開アセットが更新済みか確認する。

```bash
cd report-gate
npm ci
npm run check
```

デプロイ前にDiscord Developer Portalへ `https://<worker-domain>/auth/callback` をRedirect URIとして登録し、Cloudflare Worker secretsに `DISCORD_CLIENT_ID`、`DISCORD_CLIENT_SECRET`、`SESSION_SECRET` を設定する。Worker名を変更した場合は新しいWorker側に同じsecretsを再設定し、Discord Redirect URIも新ドメインで追加する。GitHub Actionsから自動デプロイする場合は repo secrets に `CLOUDFLARE_API_TOKEN` と `CLOUDFLARE_ACCOUNT_ID` を設定する。`Mega Validation Report` workflow はCloudflare secretsがある場合だけ、レポート再生成後に保護Workerも再デプロイする。

## 主要ファイルとアーキテクチャ

- **`screener.js`** — スコアリングロジック本体。**`optimize_screener.py` によって自動上書きされる**。`calculateScore()` を手動変更する場合は `current_logic.json` との整合性に注意。`.gitattributes` により `merge=ours` が設定済み。
- **`index.js`** — Discordコマンドハンドラー。`/scan [stable|aggressive|code]`、プレミアム通知の `premium_scan:<symbolCode>` ボタン、`/approve-update`（管理者専用）を実装。ボタンは既存のコード検索処理へ流し、3秒以内に interaction へ応答する。`/scan` の標準対象は直近45営業日、`/help` の実績はHTMLに合わせて過去365日の確定済み `alerts_raw + signals_archive` を集計し、勝率は0%引き分けを分母から除外する。stable=スコア5以上、aggressive=4以上。DM表示で株価と騰落率を並べる場合は、表示上の丸め済み株価から `formatDisplayChange()` で騰落率を計算し、同じ表示株価なのにパーセントだけずれないようにする。
  `/scan` の `range` オプションはモード選択後に入力へ進めるため必須にし、autocompleteに「標準（直近45営業日）」の候補は出さない。未指定フォールバック用の内部デフォルト値は古いクライアント互換として残してよい。
- **`sheets.js`** — Google Sheets APIクライアント。通常スキャンは `alerts_raw`、`/help` 用バックテストは `alerts_raw` と `signals_archive`、OHLCVは `ohlcv_4h` を読み取る。`cleanSymbol()` で `TYO:4074` → `4074` に変換。
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
RECENT_SIGNAL_BUSINESS_DAYS: 45 // /scan 未指定時の標準対象（週末を除く営業日）
RECENT_SIGNAL_DAYS: 30   // 明示的な日数指定時の互換用カレンダー日数
HELP_BACKTEST_DAYS: 365  // /help 実績表示期間（HTMLレポートと揃える）
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

利用可能な条件キー（`optimize_screener.py` の `BOOL_CONDS` で定義。Stable/Sniper共通）: `ema75`, `ema25`, `vol20`, `vol15`, `vol12`, `vol30`, `sbull`, `body1`, `body2`, `macdgc`, `macdpos`, `atr5`, `atr3`, `atr7`, `hb20`, `lower_wick50`, `pre_decline15`, `stoch75`, `stoch60`, `rsi5070`, `rsi4060`, `bb80`, `ich_tk`, `ich_price_tenkan`, `ich_price_kijun`, `ich_cloud_above`, `ich_cloud_green`, `ich_chikou`, `ich_kumo_break`, `rci9_os`, `rci26_os`, `rci9_up`, `pre_down3`, `gap_up`, `bb_lower`, `cci_os`, `smbull_seq2`, `smbull_seq3`, `vp_support`, `vp_no_overhead`, `vp_near_poc`

### `screener.js` の処理フロー

1. `aggregateToDailyBars(bars)` — 4h足 → 日次バーに集約（同日はvolume合算・high/low更新・closeは最後）
2. `computeIndicators(dailyBars, signalIdx)` — EMA/ATR/MACD/RSI/Stoch/BB を `signalIdx` 時点で計算
3. `calculateScore(ind)` — 現行ロジックで0〜6点スコアを付与（各条件1点）
4. `screenSymbol(...)` — 上記3関数をラップし、シグナル日・現在変化率・futurePrice等を付けて返す

### `optimize_screener.py` の評価指標

- **採用基準①**: `composite > baseline`（ベースラインを上回ること）
- **採用基準②**: 現行実装は `STRICT_WR = False` のため `wr_raw >= baseline.wr_raw`。`STRICT_WR` を `True` に戻した場合のみ strict `>` で判定する。
- **採用基準③**: `win10_raw >= 5` かつ `win10_raw / n >= (baseline.win10_raw / baseline.n) × 0.90`（少数精鋭ロジックを絶対件数だけで弾かない）
- **Stable品質ゲート**: strict modeの全件★6最低件数は通常18件、rescue modeで15件。検証側は現行検証★6件数がある場合 `max(5, 現行検証★6件数 × 0.8)` を最低件数にする。閾値最適化は上位候補に限定し、最終採用判定は広い候補プールを全件再評価する。strict modeでは採用前にLockboxも事前確認し、OOSゲートに落ちた候補はスキップして次の品質通過候補を試す。
- **Sniper検証ゲート**: 訓練上位だけで採用せず、60%訓練・20%検証・20%Lockboxに分ける。Walk-forward候補を最大1000件まで広げ、検証側の最低件数5件を要求し、検証平均リターンがマイナスの候補は除外する。候補選択は検証勝率・検証平均リターン・Lockbox勝率・Lockbox平均リターンを優先し、全期間再評価では現行勝率未満、または現行平均リターンから許容幅を超えて悪化する候補を採用しない。
- **差分品質ゲート**: スコアロジック更新候補をpending保存・Discord通知する直前に、現行/候補の抽出銘柄差分を確認する。候補件数が現行比で大きく減り、候補のみ追加の件数や成績が弱く、現行のみ除外側に目標Hitや大勝ち銘柄がある場合は、見かけの成績改善として自動却下する。ただし検証/Lockbox、全体成績、未確定ウォッチリストの改善が十分に強い場合は通し、rescue modeでは必要な更新を逃さないため過度に抑制しない。
- **Sniper探査判断**: Sniper候補は固定銘柄や固定条件名で採用せず、十分な件数での全体勝率・検証勝率・目標到達率・-10%以下の少なさ・未確定ウォッチ悪化なしを優先する。件数を増やすだけで勝率や検証成績が落ちる候補は、見かけのサンプル数が多くても採用しない。
- **閾値スイープ**: `--win-threshold-sweep` の子プロセスはStable比較に絞るためSniperをスキップする。採用可能な閾値がない場合は `pending_logic.json` を作らず、SCPや `pm2 restart` も実行しない。
- **compositeスコア**: `COMPOSITE_VARIANT = "rate_adjusted"` — `wr×40 + avg×100 + ((win10_weighted / W) - (lose10_weighted / W)) × 250`（recency半減期90日の加重）
- **Method A**: 6条件の組み合わせ全探索（各1点）
- **Method B**: lift分析による重み付きスコア（各1〜2点）
- **閾値チューニング**: Stage 2でグリッドサーチ（訓練/テスト分割あり）。組み合わせ数が20万超の場合は独立最適化に切り替え

## デプロイ構成

- **SSH key**: `C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key`（自宅PC）/ `~/ssh-key-2026-03-08.key`（Cloud Shell）
- **VM**: `ubuntu@168.110.60.126`、pm2プロセス名 `screening-bot`
- **自動実行トリガー**: GASの `runDailyMaintenance` 完了 → `triggerGitHubActionsOptimize_()` → GitHub Actions `workflow_dispatch`
- **承認フロー**: `optimize.yml`（`--propose`）→ Discord通知 → 管理者が `/approve-update` → `deploy.yml`（`--apply-pending`）→ デプロイ → `Mega Validation Report` 再生成
- **GitHub Actions コミット対象**: `current_logic.json` / `screener.js` / `index.js` の3ファイル（deploy.yml実行時）
- **バックアップ**: `backups/screener_backup_YYYYMMDD_HHMMSS.js`（最大30件）

### GitHub Actions 必要Secrets

| Secret名 | 内容 |
|---|---|
| `GOOGLE_CREDENTIALS` | サービスアカウントJSONの中身 |
| `SSH_PRIVATE_KEY` | VMへのSSH秘密鍵 |
| `DISCORD_BOT_TOKEN` | `Mega Validation Report` でDiscord投稿済みファンダ本文をHTMLキャッシュへ追加取得するBotトークン。未設定でもHTML再生成は継続するが、新規ファンダ本文はHTML内に埋め込まれない |
| `DISCORD_REPORT_WEBHOOK_URL` | `Mega Validation Report` でHTML生成直後にDiscordへ完了通知を送るWebhook URL。未設定の場合、通知だけをスキップしHTML生成・コミット・デプロイは継続する |

`Mega Validation Report` のHTML生成完了通知は、旧GASのOHLCV完了通知と同じDiscord表示にする。タイトルは `✅ OHLCVデータ同期完了`、フィールド名は `🤖 スコアリングBot`、本文は `/scan` とブラウザリンクの案内だけにし、GitHub Actions実行ログ欄は出さない。
`Deploy Approved Logic` 承認後のレポート再生成ではこのDiscord完了通知を送らない。`deploy.yml` から `mega-validation-report.yml` を呼ぶ場合は `notify_discord: false` を明示し、承認適用したスコアロジックの内容通知は `--apply-pending` 中に一時JSONへ退避して、HTML再生成とreport-gate反映後に `mega-validation-report.yml` の最終段で送る。
`Mega Validation Report` workflow に平日21:00 JSTなどの定時 `schedule` は置かない。レポート再生成は `Daily Screener Optimization` からの共有workflow呼び出し、13:21先行OHLCV取得後の明示dispatch、または手動実行で行う。

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
- `vp_support` / `vp_no_overhead` / `vp_near_poc` は `ohlcv_4h` 由来のOHLCV足から価格帯出来高を近似する条件であり、約定別の真のVolume Profileではない。変更時は `optimize_screener.py`、`screener.js`、`generate_mega_validation_report.py` の条件名・計算式・表示ラベルを揃える。
- `aggregateToDailyBars()` はバーがソート済みであることを前提とする。未ソートだと20日ルックバックウィンドウが壊れる。
- `screenSymbol()` はシグナル日**以前**で最も近いバーを探す（完全一致不要）。シグナル日がバーの最終日より新しい場合は `null` を返す。

## Future Work

- **Moonshot mode is locked/deferred**: do not add `/scan moonshot`, enable `MOONSHOT_AUTO_OPTIMIZE_ENABLED`, create/apply `pending_logic_moonshot.json`, or populate `current_logic_moonshot.json` unless the user explicitly re-approves after fresh 20BD validation. The 2026-06-03 review found weak live/unconfirmed performance despite promising backtest averages, so the current sample is still too thin and likely to overfit.
