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

  // 下ヒゲ優位（下ヒゲ長 ≥ 実体長）
  const lowerWick = Math.min(latestClose, latestOpen) - lows[last];
  const lowerWick50 = lowerWick >= Math.abs(latestClose - latestOpen) && lowerWick > 0;

  // 直近20日高値から15%以上の押し
  const preDecline15 = hi20v > 0 && (latestClose / hi20v - 1) <= -0.15;

  // RCI (Rank Correlation Index)
  function calcRCI(arr, period) {
    if (arr.length < period) return null;
    const p = arr.slice(-period);
    const n = period;
    const sorted = [...p].sort((a, b) => b - a);
    const priceRank = p.map(v => sorted.indexOf(v) + 1);
    const dSq = priceRank.reduce((sum, pr, i) => sum + Math.pow((i + 1) - pr, 2), 0);
    return (1 - 6 * dSq / (n * (n * n - 1))) * 100;
  }
  const rci9     = calcRCI(closes.slice(0, last + 1), 9);
  const rci9Prev = last >= 9 ? calcRCI(closes.slice(0, last), 9) : null;
  const rci26    = calcRCI(closes.slice(0, last + 1), 26);

  // 直近3日連続下落（押し目確認）
  const preDown3 = last >= 3
    && closes[last-1] < closes[last-2]
    && closes[last-2] < closes[last-3];

  // ギャップアップ（当日始値 > 前日終値）
  const gapUp = last > 0 && opens[last] > closes[last - 1];

  // 連続小陽線（シグナル前に body 0〜1% の陽線が連続）
  function isSmBull(i) {
    if (i < 0) return false;
    const bp = closes[i] > 0 ? (closes[i] - opens[i]) / closes[i] * 100 : 0;
    return bp > 0 && bp < 1.0;
  }
  const smbullSeq2 = last >= 2 && isSmBull(last-1) && isSmBull(last-2);
  const smbullSeq3 = last >= 3 && isSmBull(last-1) && isSmBull(last-2) && isSmBull(last-3);

  // CCI(14)
  const cciStart_ = Math.max(0, last - 13);
  const tp14_ = [];
  for (let i = cciStart_; i <= last; i++) tp14_.push((highs[i]+lows[i]+closes[i])/3);
  const tpMean_ = tp14_.reduce((a,b)=>a+b,0)/tp14_.length;
  const tpMd_   = tp14_.reduce((a,v)=>a+Math.abs(v-tpMean_),0)/tp14_.length;
  const cciVal  = tpMd_ > 0 ? (tp14_[tp14_.length-1]-tpMean_)/(0.015*tpMd_) : 0;

  // 一目均衡表
  function ichimokuMid(end, period) {
    if (end == null || end - period + 1 < 0) return null;
    const h = highs.slice(end - period + 1, end + 1);
    const l = lows.slice(end - period + 1, end + 1);
    return (Math.max(...h) + Math.min(...l)) / 2;
  }

  const ichTenkan = ichimokuMid(last, 9);
  const ichKijun  = ichimokuMid(last, 26);
  const ichSpanAFuture = (ichTenkan !== null && ichKijun !== null) ? (ichTenkan + ichKijun) / 2 : null;
  const ichSpanBFuture = ichimokuMid(last, 52);

  function visibleIchimokuCloud(end) {
    const base = end - 26;
    const t = ichimokuMid(base, 9);
    const k = ichimokuMid(base, 26);
    const b = ichimokuMid(base, 52);
    if (t === null || k === null || b === null) return { spanA: null, spanB: null, top: null };
    const a = (t + k) / 2;
    return { spanA: a, spanB: b, top: Math.max(a, b) };
  }

  const ichCloud = visibleIchimokuCloud(last);
  const ichCloudPrev = visibleIchimokuCloud(last - 1);
  const ichCloudGreen = ichSpanAFuture !== null && ichSpanBFuture !== null && ichSpanAFuture > ichSpanBFuture;
  const ichChikou = last >= 26 && latestClose > closes[last - 26];
  const ichKumoBreak = ichCloud.top !== null && ichCloudPrev.top !== null
    && closes[last - 1] <= ichCloudPrev.top && latestClose > ichCloud.top;

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
    lowerWick50,
    preDecline15,
    rci9:     rci9 !== null ? +rci9.toFixed(1) : null,
    rci9Prev: rci9Prev !== null ? +rci9Prev.toFixed(1) : null,
    rci26:    rci26 !== null ? +rci26.toFixed(1) : null,
    preDown3,
    gapUp,
    cciVal:   +cciVal.toFixed(1),
    ichTenkan:    ichTenkan !== null ? +ichTenkan.toFixed(2) : null,
    ichKijun:     ichKijun !== null ? +ichKijun.toFixed(2) : null,
    ichCloudTop:  ichCloud.top !== null ? +ichCloud.top.toFixed(2) : null,
    ichCloudGreen,
    ichChikou,
    ichKumoBreak,
    smbullSeq2,
    smbullSeq3,
  };
}

// ============================================================
// スコア計算（6点満点）
// ============================================================
// 自動最適化(方式A) 2026-05-14 20:32 / 1482件データ
// ★6: 20件 勝率65.0% 平均12.3% 上昇6件 下落0件
// 現行: 勝率54.1% 平均6.3%
// 【6条件（各1点）】
//   ① 当日出来高≥20日×1.5
//   ② 当日出来高≥20日×1.2
//   ③ ATR% < 5.0%
//   ④ ATR% < 7.0%
//   ⑤ ストキャス≥75
//   ⑥ 直近3日連続下落後

function calculateScore(ind) {
  if (!ind) return null;
  const filters = [];
  let score = 0;

  // ① 当日出来高≥20日×1.5
  if (ind.volSurge >= 1.5) {
    score++;
    filters.push(`①vol急増(${ind.volSurge}x)`);
  }

  // ② 当日出来高≥20日×1.2
  if (ind.volSurge >= 1.2) {
    score++;
    filters.push(`②vol急増(${ind.volSurge}x)`);
  }

  // ③ ATR% < 5.0%
  if (ind.atrPct < 5.0) {
    score++;
    filters.push(`③ATR(${ind.atrPct}%)`);
  }

  // ④ ATR% < 7.0%
  if (ind.atrPct < 7.0) {
    score++;
    filters.push(`④ATR(${ind.atrPct}%)`);
  }

  // ⑤ ストキャス≥75
  if (ind.stochK >= 75) {
    score++;
    filters.push(`⑤STOCH(${ind.stochK.toFixed(0)})`);
  }

  // ⑥ 直近3日連続下落後
  if (ind.preDown3) {
    score++;
    filters.push(`⑥3連陰後`);
  }

  return { score, filters };
}












// ============================================================
// Sniperモード採点（optimize_screener.py が最適化後に自動書き換え）
// ============================================================
// Sniperモード自動最適化 2026-05-12 07:51 / 1398件データ
// Sniper: 18件 勝率77.8% 平均1.8%
// 【Sniper条件（全6条件通過で採択）】
//   ① close > EMA25（中期トレンド）
//   ② 強い陽線（実体≥0.5%）
//   ③ ATR% < 5.0%
//   ④ ATR% < 7.0%
//   ⑤ 直近20日高値更新
//   ⑥ RSI 40〜60

function calculateScoreSniper(ind) {
  if (!ind) return null;
  const filters = [];
  let score = 0;

  // ① close > EMA25（中期トレンド）
  if (ind.ema25 !== null && ind.close > ind.ema25) {
    score++;
    filters.push(`①EMA25順張り`);
  }

  // ② 強い陽線（実体≥0.5%）
  if (ind.isStrongBull) {
    score++;
    filters.push(`②強陽線(${ind.bodyPct.toFixed(1)}%)`);
  }

  // ③ ATR% < 5.0%
  if (ind.atrPct < 5.0) {
    score++;
    filters.push(`③ATR(${ind.atrPct}%)`);
  }

  // ④ ATR% < 7.0%
  if (ind.atrPct < 7.0) {
    score++;
    filters.push(`④ATR(${ind.atrPct}%)`);
  }

  // ⑤ 直近20日高値更新
  if (ind.hiBrk20) {
    score++;
    filters.push(`⑤高値更新`);
  }

  // ⑥ RSI 40〜60
  if (!isNaN(ind.rsi14) && ind.rsi14 >= 40 && ind.rsi14 < 60) {
    score++;
    filters.push(`⑥RSI(${ind.rsi14.toFixed(0)})`);
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
