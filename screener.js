// screener.js — v14.1（日付バグ修正版）
//
// 【v14.0からの修正】
//   aggregateToDailyBars: String(b.datetime).slice(0,10) のバグを修正。
//   Date オブジェクトを String() すると "Wed Mar 18 2026..." になり
//   slice(0,10) が "Wed Mar 18" を返す。→ toISOString().slice(0,10) で "2026-03-18" に修正。
//   これにより signalIdx が正しく計算され、シグナル日時点のテクニカルで採点される。
//
// 【6条件 6点満点 — 原理ベース設計】
//   ① close > EMA75     長期上昇トレンド（落ちるナイフを避ける）
//   ② vol当日≥20日×2.0  強い出来高急増（大口資金流入の証明）
//   ③ 強い陽線(体≥0.5%)  反発の意志（買い主体が積極的）
//   ④ MACD GC(3日以内)   トレンド転換の初動シグナル
//   ⑤ ATR% < 5.0%       低ボラ銘柄限定（大幅下落リスク軽減）
//   ⑥ close > EMA25     中期トレンド確認（二重確認）
//
// 【684件バックテスト結果（v14.0と同値）】
//   Stable(5+):     58件 勝率43.1% +10%率13.8% 平均+2.18%
//   Aggressive(4+): 190件 勝率33.7% +10%率 6.8% 平均-0.61%
//   ベースライン:    684件 勝率30.1% +10%率 5.1% 平均-0.82%

const config = require('./config');

// ============================================================
// 安全な日付→ISO文字列変換（"2026-03-18" 形式を保証）
// ============================================================
function toDateKey(datetimeVal) {
  if (datetimeVal instanceof Date) {
    // Date オブジェクト → toISOString() で UTC基準のISO文字列
    return datetimeVal.toISOString().slice(0, 10);
  }
  // 文字列の場合：スラッシュをハイフンに統一してから先頭10文字
  return String(datetimeVal).replace(/\//g, '-').slice(0, 10);
}

// ============================================================
// 4hバー → 日次バーへ集約
// ============================================================
function aggregateToDailyBars(bars) {
  const dayMap = new Map();
  for (const b of bars) {
    const dateKey = toDateKey(b.datetime); // ← 修正: 必ず "YYYY-MM-DD" 形式
    if (!dayMap.has(dateKey)) {
      dayMap.set(dateKey, {
        datetime: dateKey,   // 文字列 "YYYY-MM-DD" として保持
        open:   b.open,
        high:   b.high,
        low:    b.low,
        close:  b.close,
        volume: b.volume,
      });
    } else {
      const d = dayMap.get(dateKey);
      if (b.high > d.high) d.high = b.high;
      if (b.low  < d.low)  d.low  = b.low;
      d.close   = b.close;
      d.volume += b.volume;
    }
  }
  // 日付文字列の辞書順ソートで時系列順になる（YYYY-MM-DD 形式なので正確）
  return Array.from(dayMap.values()).sort((a, b) =>
    a.datetime < b.datetime ? -1 : a.datetime > b.datetime ? 1 : 0
  );
}

// ============================================================
// EMA配列計算
// ============================================================
function calcEMAArray(values, period) {
  if (values.length < period) return new Array(values.length).fill(null);
  const k = 2 / (period + 1);
  const result = new Array(period - 1).fill(null);
  let ema = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result.push(ema);
  for (let i = period; i < values.length; i++) {
    ema = values[i] * k + ema * (1 - k);
    result.push(ema);
  }
  return result;
}

// ============================================================
// 全指標を計算（日次バー配列、signalIdxまで）
// ============================================================
function computeIndicators(dailyBars, signalIdx) {
  const bars = dailyBars.slice(0, signalIdx + 1);
  if (bars.length < 30) return null;

  const last = bars.length - 1;
  const closes  = bars.map(b => b.close);
  const highs   = bars.map(b => b.high);
  const lows    = bars.map(b => b.low);
  const opens   = bars.map(b => b.open);
  const volumes = bars.map(b => b.volume);
  const latestClose = closes[last];
  const latestOpen  = opens[last];

  // ── EMA25 / EMA75 ───────────────────────────────────────
  const ema25Arr = calcEMAArray(closes, 25);
  const ema75Arr = calcEMAArray(closes, 75);
  const ema25 = ema25Arr[last];
  const ema75 = ema75Arr[last]; // 75本未満なら null
  if (ema25 === null) return null;

  // ── ATR%(14) ────────────────────────────────────────────
  const trArr = [];
  for (let i = Math.max(1, last - 27); i <= last; i++) {
    trArr.push(Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i]  - closes[i - 1])
    ));
  }
  const atr14  = trArr.slice(-14).reduce((a, b) => a + b, 0) / Math.min(14, trArr.length);
  const atrPct = latestClose > 0 ? (atr14 / latestClose) * 100 : 999;

  // ── 出来高急増（当日 vs 直近20日平均・当日除く）────────────
  const vol20Avg = last >= 20
    ? volumes.slice(last - 20, last).reduce((a, b) => a + b, 0) / 20
    : volumes.slice(0, last).reduce((a, b) => a + b, 0) / Math.max(1, last);
  const volSurge = vol20Avg > 0 ? volumes[last] / vol20Avg : 0;

  // ── 陽線強度（実体 / 終値 × 100%）──────────────────────
  const bodyPct  = latestClose > 0 ? (latestClose - latestOpen) / latestClose * 100 : 0;
  const isStrongBull = bodyPct >= 0.5;

  // ── MACD(12,26,9) GC（3日以内）──────────────────────────
  const ema12Arr = calcEMAArray(closes, 12);
  const ema26Arr = calcEMAArray(closes, 26);
  const macdLine = ema12Arr.map((v, i) =>
    (v !== null && ema26Arr[i] !== null) ? v - ema26Arr[i] : null
  );
  const validMacd     = macdLine.filter(v => v !== null);
  const macdSignalArr = calcEMAArray(validMacd, 9);

  let macdGC3d = false;
  if (validMacd.length >= 12 && macdSignalArr.length >= 4) {
    for (let i = 0; i < 3 && i < macdSignalArr.length - 1; i++) {
      const idx     = macdSignalArr.length - 1 - i;
      const prevIdx = idx - 1;
      if (prevIdx < 0) break;
      const histNow  = validMacd[validMacd.length - 1 - i] - macdSignalArr[idx];
      const histPrev = validMacd[validMacd.length - 2 - i] - macdSignalArr[prevIdx];
      if (histNow > 0 && histPrev <= 0) { macdGC3d = true; break; }
    }
  }


  // ── 追加指標（optimize_screener.pyが使用する可能性のある条件）───────
  // MACD hist > 0
  const macdHistVal = (validMacd.length > 0 && macdSignalArr.length > 0)
    ? validMacd[validMacd.length-1] - macdSignalArr[macdSignalArr.length-1] : 0;
  const macdPos = macdHistVal > 0;

  // RSI(14)
  let rsiSumG = 0, rsiSumL = 0;
  for (let i = Math.max(1, last-13); i <= last; i++) {
    const d = closes[i] - closes[i-1];
    if (d > 0) rsiSumG += d; else rsiSumL -= d;
  }
  const rsiLen14 = Math.min(14, last);
  const rsi14 = (rsiSumL/rsiLen14) > 0
    ? 100 - 100 / (1 + (rsiSumG/rsiLen14) / (rsiSumL/rsiLen14)) : 100;

  // Stochastic K(14)
  const stochLo = Math.min(...lows.slice(Math.max(0, last-13), last+1));
  const stochHi = Math.max(...highs.slice(Math.max(0, last-13), last+1));
  const stochK  = (stochHi - stochLo) > 0
    ? (latestClose - stochLo) / (stochHi - stochLo) * 100 : 50;

  // BB位置（20日）
  const bbSlc   = closes.slice(Math.max(0, last-19), last+1);
  const bbMean_ = bbSlc.reduce((a, b) => a + b, 0) / bbSlc.length;
  const bbStd_  = Math.sqrt(bbSlc.reduce((a, b) => a + (b - bbMean_) ** 2, 0) / bbSlc.length);
  const bbPct   = bbStd_ > 0
    ? Math.min(1, Math.max(0, (latestClose - (bbMean_ - 2 * bbStd_)) / (4 * bbStd_))) : 0.5;

  // 直近20日高値更新
  const hi20Arr = highs.slice(Math.max(0, last-20), last);
  const hi20v   = hi20Arr.length > 0 ? Math.max(...hi20Arr) : latestClose;
  const hiBrk20 = latestClose > hi20v;

  return {
    close:       latestClose,
    ema25:       ema25 !== null ? +ema25.toFixed(2) : null,
    ema75:       ema75 !== null ? +ema75.toFixed(2) : null,
    atrPct:      +atrPct.toFixed(2),
    volSurge:    +volSurge.toFixed(2),
    bodyPct:     +bodyPct.toFixed(2),
    isStrongBull,
    macdGC3d,
    macdPos,
    rsi14:    +rsi14.toFixed(2),
    stochK:   +stochK.toFixed(2),
    bbPct:    +bbPct.toFixed(4),
    hiBrk20,
  };
}

// ============================================================
// スコア計算（6点満点）
// ============================================================
// 自動最適化(方式A +閾値最適化) 2026-04-23 21:02 / 1174件データ
// ★6: 31件 勝率61.3% 平均9.8% 上昇9件 下落1件
// 現行: 勝率56.1% 平均8.5%
// 【6条件（各1点）】
//   ① close > EMA75（長期上昇トレンド）
//   ② 当日出来高≥20日×2.00
//   ③ 強い陽線（実体≥2.00%）
//   ④ ATR% < 5.0%
//   ⑤ ストキャス≥65
//   ⑥ RSI 50〜70

function calculateScore(ind) {
  if (!ind) return null;
  const filters = [];
  let score = 0;

  // ① close > EMA75（長期上昇トレンド）
  if (ind.ema75 !== null && ind.close > ind.ema75) {
    score++;
    filters.push(`①EMA75順張り`);
  }

  // ② 当日出来高≥20日×2.00
  if (ind.volSurge >= 2.00) {
    score++;
    filters.push(`②vol急増(${ind.volSurge}x)`);
  }

  // ③ 強い陽線（実体≥2.00%）
  if (ind.bodyPct >= 2.00) {
    score++;
    filters.push(`③強陽線(${ind.bodyPct.toFixed(2)}%)`);
  }

  // ④ ATR% < 5.0%
  if (ind.atrPct < 5.0) {
    score++;
    filters.push(`④ATR(${ind.atrPct}%)`);
  }

  // ⑤ ストキャス≥65
  if (ind.stochK >= 65) {
    score++;
    filters.push(`⑤STOCH(${ind.stochK.toFixed(0)})`);
  }

  // ⑥ RSI 50〜70
  if (!isNaN(ind.rsi14) && ind.rsi14 >= 50 && ind.rsi14 < 70) {
    score++;
    filters.push(`⑥RSI(${ind.rsi14.toFixed(0)})`);
  }

  return { score, filters };
}









// ============================================================
// Sniperモード採点（optimize_screener.py が最適化後に自動書き換え）
// ============================================================
// Sniperモード自動最適化 2026-04-25 / 1199件データ（C(18,5) Walk-forward 70/30検証済み）
// Sniper: 24件 勝率70.8% 平均+4.1%（検証勝率72.7% — 過学習なし）
// 【Sniper条件（全5条件通過で採択）】
//   ① 出来高急増（20日平均×1.5以上）
//   ② ATR% < 5.0%（低ボラ）
//   ③ ストキャス≥75（モメンタム）
//   ④ RSI 40〜60（中立ゾーン）
//   ⑤ BB位置≥80%（上方ブレイクアウト）

function calculateScoreSniper(ind) {
  if (!ind) return null;
  const filters = [];
  let score = 0;

  // ① 出来高急増（20日平均×1.5以上）
  if (ind.volSurge >= 1.5) {
    score++;
    filters.push(`①vol急増(${ind.volSurge}x)`);
  }

  // ② ATR% < 5.0%（低ボラ）
  if (ind.atrPct < 5.0) {
    score++;
    filters.push(`②ATR(${ind.atrPct}%)`);
  }

  // ③ ストキャス≥75（モメンタム）
  if (ind.stochK >= 75) {
    score++;
    filters.push(`③STOCH(${ind.stochK.toFixed(0)})`);
  }

  // ④ RSI 40〜60（中立ゾーン）
  if (!isNaN(ind.rsi14) && ind.rsi14 >= 40 && ind.rsi14 < 60) {
    score++;
    filters.push(`④RSI(${ind.rsi14.toFixed(0)})`);
  }

  // ⑤ BB位置≥80%（上方ブレイクアウト）
  if (ind.bbPct >= 0.80) {
    score++;
    filters.push(`⑤BB(${(ind.bbPct * 100).toFixed(0)}%)`);
  }

  return { score, filters };
}




// ============================================================
// メインAPI: 銘柄スクリーニング
// ============================================================
function screenSymbol(symbol, ohlcvData, signalDateStr, entryPrice, eval5bd, perf5bd) {
  const { bars } = ohlcvData;
  if (!bars || bars.length === 0) return null;

  const dailyBars = aggregateToDailyBars(bars);

  // シグナル日をISO文字列 "YYYY-MM-DD" に正規化
  const signalDateISO = signalDateStr.replace(/\//g, '-').slice(0, 10);

  // ← 修正: ISO文字列の辞書順比較（Date変換なし・timezone依存なし）
  let signalIdx = -1;
  for (let i = 0; i < dailyBars.length; i++) {
    if (dailyBars[i].datetime <= signalDateISO) {
      signalIdx = i;
    } else {
      break;
    }
  }
  if (signalIdx === -1) return null;

  const signalPrice = (entryPrice && entryPrice > 0) ? entryPrice : dailyBars[signalIdx].close;
  if (!signalPrice) return null;

  const ind = computeIndicators(dailyBars, signalIdx);
  if (!ind) return null;

  const sr = calculateScore(ind);
  if (!sr) return null;

  const srSniper = calculateScoreSniper(ind);

  const futurePrice = (eval5bd !== null && !isNaN(eval5bd)) ? eval5bd : null;
  const futureDiff  = (perf5bd !== null && !isNaN(perf5bd)) ? Number(perf5bd).toFixed(2) : null;
  const latestBar   = bars[bars.length - 1];
  const latestClose = latestBar ? latestBar.close : null;
  let currentChange = '0.00';
  if (latestClose && signalPrice) {
    currentChange = ((latestClose / signalPrice - 1) * 100).toFixed(2);
  }

  return {
    symbol,
    score:    sr.score,
    maxScore: 6,
    filters:  sr.filters,
    sniperScore:   srSniper !== null ? srSniper.score : -1,
    sniperFilters: srSniper !== null ? srSniper.filters : [],
    sniperEnabled: srSniper !== null,
    indicators: ind,
    atrPct:   ind.atrPct,
    signalDate: signalDateStr,
    signalPrice,
    futurePrice, futureDiff,
    latestClose, change: currentChange,
  };
}

module.exports = { screenSymbol };
