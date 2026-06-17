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
// 自動最適化(方式A) 2026-05-28 18:34 / 1798件データ
// ★6: 25件 勝率60.0% 平均12.6% 上昇8件 下落3件
// 現行: 勝率58.8% 平均11.0%
// 【6条件（各1点）】
//   ① close > EMA25（中期トレンド）
//   ② MACD hist > 0
//   ③ ストキャス≥75
//   ④ BB位置≥80%
//   ⑤ 直近3日連続下落後
//   ⑥ ギャップアップ（始値>前終値）

function calculateScore(ind) {
  if (!ind) return null;
  const filters = [];
  let score = 0;

  // ① close > EMA25（中期トレンド）
  if (ind.ema25 !== null && ind.close > ind.ema25) {
    score++;
    filters.push(`①EMA25順張り`);
  }

  // ② MACD hist > 0
  if (ind.macdPos) {
    score++;
    filters.push(`②MACD上昇`);
  }

  // ③ ストキャス≥75
  if (ind.stochK >= 75) {
    score++;
    filters.push(`③STOCH(${ind.stochK.toFixed(0)})`);
  }

  // ④ BB位置≥80%
  if (ind.bbPct >= 0.80) {
    score++;
    filters.push(`④BB上部(${(ind.bbPct*100).toFixed(0)}%)`);
  }

  // ⑤ 直近3日連続下落後
  if (ind.preDown3) {
    score++;
    filters.push(`⑤3連陰後`);
  }

  // ⑥ ギャップアップ（始値>前終値）
  if (ind.gapUp) {
    score++;
    filters.push(`⑥GAP-UP`);
  }

  return { score, filters };
}






// ============================================================
// マーケットフェーズ検出: シグナル後の価格軌跡を分類
// ============================================================
function detectMarketPhase(dailyBars, signalIdx, ind) {
  const postBars = dailyBars.slice(signalIdx); // index 0 = signal day
  const n = postBars.length;
  const daysSince = n - 1;

  // ATRスケール補正（ATR5%基準。高ATR銘柄の過剰判定を抑制）
  const atrMul = ind ? Math.max(0.8, Math.min(1.5, (ind.atrPct || 5) / 5.0)) : 1.0;

  // ── 点灯前コンテキスト計算（最大20日分）─────────────────
  const preStartIdx = Math.max(0, signalIdx - 20);
  const preBars     = dailyBars.slice(preStartIdx, signalIdx);
  const preCloses   = preBars.map(b => b.close);
  const hasPreData  = preCloses.length >= 10; // 最低10日分必要

  let pre20Low = null, pre20High = null, pre20Trend = 0, signalZone = 'mid';
  if (hasPreData) {
    pre20Low   = Math.min(...preCloses);
    pre20High  = Math.max(...preCloses);
    pre20Trend = (preCloses[preCloses.length - 1] - preCloses[0]) / preCloses[0] * 100;
    const signalClose = postBars[0]?.close;
    if (pre20High > pre20Low && signalClose !== undefined) {
      const pos = (signalClose - pre20Low) / (pre20High - pre20Low);
      if (pos <= 0.25)      signalZone = 'low';
      else if (pos >= 0.75) signalZone = 'high';
      else                  signalZone = 'mid';
    }
  }

  // 点灯日が点灯前20日安値を下回ったか（安値ブレイク判定）
  const isBreakdown = hasPreData && pre20Low !== null && postBars[0]?.close < pre20Low;

  // daysSince = 0: 点灯当日 — 指標と点灯前ゾーンで状態描写
  if (daysSince === 0) {
    if (!ind && !hasPreData) return '🔔 シグナル点灯';

    // 安値ブレイク（最優先）
    if (isBreakdown) return '🔻 20日安値ブレイクで点灯';

    // 指標ベース判定
    if (ind) {
      const isStrong = ind.volSurge >= 2.0 && ind.bodyPct >= 0.8 && (ind.macdPos || ind.macdGC3d);
      const isHot    = ind.rsi14 >= 65 || ind.stochK >= 80;
      const isWeak   = ind.volSurge < 1.2 && ind.bodyPct < 0.3;

      if (isStrong) {
        if (signalZone === 'low')  return '🔥 安値圏で出来高急増';
        if (signalZone === 'high') return '⚠️ 高値圏で出来高急増';
        return '🔥 出来高急増・勢い強い';
      }
      if (isHot)  return '⚠️ 短期過熱域';
      if (isWeak) return '🔍 出来高・モメンタム弱め';
    }

    // ゾーンベースのフォールバック
    if (signalZone === 'low') {
      if (pre20Trend <= -5) return '🪨 急落後・安値圏で点灯';
      return '🪨 安値圏で点灯';
    }
    if (signalZone === 'high') return '⚠️ 高値圏で点灯';
    // 中段
    if (pre20Trend <= -3) return '📍 下落後・中段で点灯';
    return '📍 中段で点灯';
  }

  // daysSince = 1: 初動の方向で状態描写
  if (daysSince === 1) {
    const d = (postBars[1].close - postBars[0].close) / postBars[0].close * 100;
    if (d >= 2)  return '⚡ 初日から上昇発進｜+1日';
    if (d >= 0)  return '↗️ 初日小幅上昇｜+1日';
    if (d >= -3) return '↘️ 初日小幅下落｜+1日';
    return '⚠️ 初日大幅下落｜+1日';
  }

  // daysSince >= 2: 軌跡ベースのフェーズ分類
  const baseClose   = postBars[0].close;
  const latestClose = postBars[n - 1].close;

  let maxClose = baseClose, peakIdx = 0;
  for (let i = 0; i < n; i++) {
    if (postBars[i].close > maxClose) { maxClose = postBars[i].close; peakIdx = i; }
  }
  let troughClose = maxClose;
  for (let i = peakIdx; i < n; i++) {
    if (postBars[i].close < troughClose) troughClose = postBars[i].close;
  }
  let maxHigh = baseClose;
  for (const b of postBars) maxHigh = Math.max(maxHigh, b.high ?? b.close);

  const totalChange = (latestClose - baseClose) / baseClose * 100;
  const maxGain     = (maxClose   - baseClose) / baseClose * 100;
  const maxHighGain = (maxHigh    - baseClose) / baseClose * 100;
  const dipFromPeak = maxClose > 0 ? (troughClose - maxClose) / maxClose * 100 : 0;

  const recentN = Math.min(3, daysSince);
  let recentMomentum = 0;
  for (let i = n - recentN; i < n; i++) {
    recentMomentum += (postBars[i].close - postBars[i - 1].close) / postBars[i - 1].close * 100;
  }
  recentMomentum /= recentN;

  const tSurge = 10 * atrMul;
  const tHold  = 7  * atrMul;
  const tPeak  = 5  * atrMul;
  const tCrash = -5 * atrMul;
  const tTrend = 4  * atrMul;
  const tRise  = 2  * atrMul;
  const tFade  = 3  * atrMul;
  const tSoft  = -3 * atrMul;
  const tBase  = -2.5 * atrMul;
  const tNear  = 1.5 * atrMul; // シグナル価格±tNear% を「付近」と判定

  const dayStr = '+' + daysSince + '日';

  if (maxHighGain >= tSurge && totalChange >= tHold)
    return '🚀 急騰継続中｜' + dayStr;

  if (maxGain >= tPeak && totalChange <= tCrash)
    return '🔻 高値から急反落｜' + dayStr;

  if (maxGain >= tPeak && dipFromPeak <= -3 && totalChange >= 1 && recentMomentum > 0 && peakIdx < n - 1)
    return '🔄 押し目から反発｜' + dayStr;

  if ((totalChange >= tTrend && recentMomentum >= -0.5) || (totalChange >= tRise && recentMomentum > 0.3))
    return '📈 上昇トレンド中｜' + dayStr;

  if (maxGain >= tFade && totalChange >= 0 && recentMomentum < -0.3)
    return '🧱 上値の重い展開｜' + dayStr;

  if (maxGain >= 2 && totalChange < 0 && recentMomentum < -0.2)
    return '⚠️ 戻り売り優勢｜' + dayStr;

  if (totalChange <= tSoft)
    return '📉 軟調推移｜' + dayStr;

  if (daysSince >= 5 && totalChange >= tBase && recentMomentum > -0.3) {
    const signalVolBars = dailyBars.slice(Math.max(0, signalIdx - 5), signalIdx + 1);
    const signalVolAvg  = signalVolBars.reduce((a, b) => a + (b.volume || 0), 0) / (signalVolBars.length || 1);
    const recentVolBars = postBars.slice(-3);
    const recentVolAvg  = recentVolBars.reduce((a, b) => a + (b.volume || 0), 0) / (recentVolBars.length || 1);
    const volNote = (signalVolAvg > 0 && recentVolAvg / signalVolAvg < 0.7) ? '（出来高収縮）' : '';
    return '🛡️ 底値固め中' + volNote + '｜' + dayStr;
  }

  // 無分類フォールバック — 点灯前ゾーンとシグナル価格との関係性で描写
  const zoneSuffix = hasPreData
    ? (signalZone === 'low' ? '安値圏' : signalZone === 'high' ? '高値圏' : '中段')
    : null;
  const zoneTag = zoneSuffix ? '｜' + zoneSuffix : '';

  if (daysSince < 5) {
    if (totalChange > tNear)
      return '↗️ シグナル価格を上回り推移' + zoneTag + '｜' + dayStr;
    if (totalChange < -tNear)
      return '↘️ シグナル価格を下回り推移' + zoneTag + '｜' + dayStr;
    return '↔️ シグナル価格付近で推移' + zoneTag + '｜' + dayStr;
  }

  if (daysSince < 15) {
    if (signalZone === 'low' && totalChange >= -tNear)
      return '🪨 安値圏で揉み合い継続｜' + dayStr;
    if (totalChange < -tNear)
      return '🔻 シグナル価格を割込み停滞｜' + dayStr;
    return '⏸ シグナル価格付近で推移｜' + dayStr;
  }

  // daysSince >= 15
  if (signalZone === 'low' && totalChange >= -tNear)
    return '🪨 長期ベース形成（安値圏）｜' + dayStr;
  return '⏹ 長期レンジ推移｜' + dayStr;
}











// ============================================================
// Sniperモード採点（optimize_screener.py が最適化後に自動書き換え）
// ============================================================
// Sniper scoring mode - approved 2026-06-17
// Adopted logic: 18 confirmed signals, win 88.2%, avg +6.7%.
// Conditions are all-pass: vol12 + atr3 + hb20 + rsi5070 + ich_chikou + rci9_os.
// Stable and Mega modes remain on their current approved logic.
// ============================================================
function calculateScoreSniper(ind) {
  if (!ind) return null;
  const filters = [];
  let score = 0;

  // 1. Volume surge >= 20-day average x 1.2
  if (ind.volSurge >= 1.2) {
    score++;
    filters.push(`1 vol>=1.2x(${ind.volSurge}x)`);
  }

  // 2. ATR% < 3.0%
  if (ind.atrPct < 3.0) {
    score++;
    filters.push(`2 ATR<3%(${ind.atrPct}%)`);
  }

  // 3. Break above recent 20-day high
  if (ind.hiBrk20) {
    score++;
    filters.push(`3 20d-high-break`);
  }

  // 4. RSI 50-70
  if (!isNaN(ind.rsi14) && ind.rsi14 >= 50 && ind.rsi14 < 70) {
    score++;
    filters.push(`4 RSI50-70(${ind.rsi14.toFixed(0)})`);
  }

  // 5. Ichimoku chikou condition: close > close 26 days ago
  if (ind.ichChikou) {
    score++;
    filters.push(`5 ichimoku-chikou`);
  }

  // 6. RCI(9) <= -50
  if (ind.rci9 !== null && ind.rci9 <= -50) {
    score++;
    filters.push(`6 RCI9<=-50(${ind.rci9 !== null ? ind.rci9.toFixed(0) : 'N/A'})`);
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

  const marketPhase = detectMarketPhase(dailyBars, signalIdx, ind);

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
    marketPhase,
  };
}

module.exports = { screenSymbol };
