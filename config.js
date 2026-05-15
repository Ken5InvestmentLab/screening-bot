// config.js — 全設定
// .env ファイルの値を読み込む
require('dotenv').config()

module.exports = {
  // ── Discord ──────────────────────────────────────────
  DISCORD_TOKEN: process.env.DISCORD_TOKEN,

  // 使用を許可するロール名（Discordサーバーで作成する）
  ALLOWED_ROLE_NAME: process.env.ALLOWED_ROLE_NAME || 'シグナル受信者',
  GUILD_ID:          process.env.GUILD_ID          || '1479418833352785944',
  ALLOWED_ROLE_ID:   process.env.ALLOWED_ROLE_ID   || '1487089073385373828',

  // ── Google Sheets ─────────────────────────────────────
  GOOGLE_CREDENTIALS_PATH: process.env.GOOGLE_CREDENTIALS_PATH || './credentials.json',
  SPREADSHEET_ID: process.env.SPREADSHEET_ID,

  // シート名（GASが書き込むシート名に合わせる）
  OHLCV_SHEET_NAME:   process.env.OHLCV_SHEET_NAME   || 'ohlcv_4h',
  ALERTS_SHEET_NAME:  process.env.ALERTS_SHEET_NAME  || 'alerts_raw',

  // ── Premium Report スプレッドシート ───────────────────────
  // ポジティブ材料（K列 reason）を参照するシート
  PREMIUM_SPREADSHEET_ID: process.env.PREMIUM_SPREADSHEET_ID || '1GeLT-DUEdsYzT6AR3n1MkhkCeivqgtsMEXMhYfnHm9s',
  PREMIUM_SHEET_NAME:     process.env.PREMIUM_SHEET_NAME     || 'premium_alert_log',

  // ── スクリーニング設定 ─────────────────────────────────
  // Stableモード: スコアがこの値以上を表示
  SCORE_STABLE:     parseInt(process.env.SCORE_STABLE     || '4', 10),
  // Aggressiveモード: スコアがこの値以上を表示
  SCORE_AGGRESSIVE: parseInt(process.env.SCORE_AGGRESSIVE || '4', 10),

  // 結果の最大表示件数
  MAX_RESULTS: parseInt(process.env.MAX_RESULTS || '20', 10),

  // 直近BOTTOMシグナルの対象日数（この日数以内のシグナルを持つ銘柄のみ対象）
  // 0 にすると全銘柄スキャン
  RECENT_SIGNAL_DAYS: parseInt(process.env.RECENT_SIGNAL_DAYS || '30', 10),

  // 指標の計算に必要な最低4h足本数
  MIN_4H_BARS: parseInt(process.env.MIN_4H_BARS || '30', 10),

  // ── フィルター数値（要件通り固定、変更禁止） ──────────────
  FILTER: {
    VOL_RATIO_MIN:    0.80,   // ② 出来高 >= 5日平均 × この値
    EMA_GAP_MIN:     -3.00,   // ③ EMA5-EMA25乖離(%) >= この値
    EMA25_SLOPE_MIN: -0.50,   // ④ EMA25傾き(5日,%) >= この値
    RANGE_POS_MAX:    0.95,   // ⑤ 5日レンジ位置 >= この値なら除外（強制除外）
    CUMUL3D_MAX:      4.00,   // ⑥ 直近3日上昇率(%) > この値なら除外（強制除外）
    EMA_SHORT_PERIOD: 5,      // EMA短期期間
    EMA_LONG_PERIOD:  25,     // EMA長期期間
    EMA_SLOPE_BARS:   5,      // EMA25傾き計算の参照本数
  },
}
