// sheets.js — Google Sheets API クライアント
const { google } = require('googleapis')
const config = require('./config')

let _auth = null
function getAuth() {
  if (!_auth) {
    _auth = new google.auth.GoogleAuth({
      keyFile: config.GOOGLE_CREDENTIALS_PATH,
      scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
    })
  }
  return _auth
}

async function getRawSheetData(sheetName) {
  const sheets = google.sheets({ version: 'v4', auth: getAuth() })
  const res = await sheets.spreadsheets.values.get({ spreadsheetId: config.SPREADSHEET_ID, range: sheetName })
  return res.data.values || []
}

// 「TYO:4074」などの文字列から「4074」だけを抽出する共通関数
function cleanSymbol(sym) {
  if (!sym) return ""
  const s = String(sym).trim()
  return s.includes(':') ? s.split(':')[1] : s
}

// alerts_raw 用 (4行目ヘッダー)
function parseAlerts(rows) {
  if (rows.length < 4) return []
  const header = rows[3].map(h => String(h).toLowerCase())
  
  const idx = {
    type: header.indexOf('signal_type'),
    symbol: header.indexOf('symbol_code'), 
    date: header.indexOf('signal_date'),
    name: header.indexOf('symbol_name'),
    entry: header.indexOf('entry_price'),
    eval5bd: header.indexOf('eval_close_5bd'), // M列を追加
    perf5bd: header.indexOf('perf_5bd')        // N列を追加
  }
  
  if (idx.symbol === -1 || idx.date === -1) return []

  return rows.slice(4).map(r => {
    // entry_priceを数値化
    const rawEntry = r[idx.entry];
    const entryPrice = rawEntry ? parseFloat(String(rawEntry).replace(/,/g, '')) : 0;
    
    // 5日後株価と騰落率を数値化（空欄やハイフンの場合は null）
    const rawEval5bd = r[idx.eval5bd];
    const eval5bd = rawEval5bd && String(rawEval5bd).trim() !== '' ? parseFloat(String(rawEval5bd).replace(/,/g, '')) : null;
    
    const rawPerf5bd = r[idx.perf5bd];
    const perf5bd = rawPerf5bd && String(rawPerf5bd).trim() !== '' ? parseFloat(String(rawPerf5bd).replace(/%/g, '')) : null;

    return {
      type: r[idx.type]?.toString().trim().toUpperCase(),
      symbol: cleanSymbol(r[idx.symbol]), 
      date: r[idx.date]?.toString().trim(),
      name: r[idx.name]?.toString().trim(),
      entry: entryPrice,
      eval5bd: eval5bd,
      perf5bd: perf5bd
    };
  }).filter(a => a.type === 'BOTTOM' && a.symbol);
}

// ohlcv_4h 用 (1行目ヘッダー)
function parseOHLCV(rows) {
  if (rows.length < 2) return new Map()
  const header = rows[0].map(h => String(h).toLowerCase())
  
  const idx = {
    symbol: header.indexOf('symbol'),
    dt:     header.indexOf('timestamp'),
    o:      header.indexOf('open'),
    h:      header.indexOf('high'),
    l:      header.indexOf('low'),
    c:      header.indexOf('close'),
    v:      header.indexOf('volume')
  }

  const map = new Map()
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i]
    const rawSym = r[idx.symbol]
    if (!rawSym) continue
    
    const sym = cleanSymbol(rawSym)
    if (!map.has(sym)) {
      map.set(sym, { name: sym, bars: [] })
    }
    
    const dateStr = String(r[idx.dt]).replace(/\//g, '-')
    const bar = {
      datetime: new Date(dateStr),
      open:   parseFloat(r[idx.o]),
      high:   parseFloat(r[idx.h]),
      low:    parseFloat(r[idx.l]),
      close:  parseFloat(r[idx.c]),
      volume: parseFloat(r[idx.v])
    }

    if (!isNaN(bar.close) && !isNaN(bar.datetime.getTime())) {
      map.get(sym).bars.push(bar)
    }
  }
  return map
}

async function fetchOHLCVData() {
  const rows = await getRawSheetData(config.OHLCV_SHEET_NAME)
  return parseOHLCV(rows)
}

async function fetchRecentBottomSymbols(specificDate = null, rangeDays = null) {
  const rows = await getRawSheetData(config.ALERTS_SHEET_NAME)
  const alerts = parseAlerts(rows)
  const symbolMap = new Map()

  // 1. 日付指定がある場合
  if (specificDate) {
    const target = specificDate.replace(/-/g, '/')
    alerts.forEach(a => {
      if (a.date && (a.date.includes(specificDate) || a.date.includes(target))) {
        // 【修正】eval5bd, perf5bd を追加
        symbolMap.set(a.symbol, { date: a.date, name: a.name, entry: a.entry, eval5bd: a.eval5bd, perf5bd: a.perf5bd })
      }
    })
    return symbolMap
  }

  // 2. 全期間 (0) の場合
  if (rangeDays === 0 || rangeDays === "0") {
    // 【修正】eval5bd, perf5bd を追加
    alerts.forEach(a => symbolMap.set(a.symbol, { date: a.date, name: a.name, entry: a.entry, eval5bd: a.eval5bd, perf5bd: a.perf5bd }))
    return symbolMap
  }

  // 3. 期間指定 (直近 n 日間)
  const days = rangeDays !== null ? Number(rangeDays) : config.RECENT_SIGNAL_DAYS
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - days)
  
  alerts.forEach(a => {
    const d = new Date(String(a.date).replace(/\//g, '-'))
    if (!isNaN(d.getTime()) && d >= cutoff) {
      // 【修正】eval5bd, perf5bd を追加
      symbolMap.set(a.symbol, { date: a.date, name: a.name, entry: a.entry, eval5bd: a.eval5bd, perf5bd: a.perf5bd })
    }
  })
  return symbolMap
}

// ============================================================
// fetchRecentBottomSignals — 配列返却（重複排除なし）
// 同一銘柄が期間内に複数回点灯している場合、全件返す
// ============================================================
async function fetchRecentBottomSignals(specificDate = null, rangeDays = null) {
  const rows = await getRawSheetData(config.ALERTS_SHEET_NAME)
  const alerts = parseAlerts(rows)

  // 1. 日付指定
  if (specificDate) {
    const target = specificDate.replace(/-/g, '/')
    return alerts.filter(a =>
      a.date && (a.date.includes(specificDate) || a.date.includes(target))
    )
  }

  // 2. 全期間
  if (rangeDays === 0 || rangeDays === '0') {
    return alerts
  }

  // 3. 直近 n 日
  const days = rangeDays !== null ? Number(rangeDays) : config.RECENT_SIGNAL_DAYS
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - days)
  return alerts.filter(a => {
    const d = new Date(String(a.date).replace(/\//g, '-'))
    return !isNaN(d.getTime()) && d >= cutoff
  })
}

// ============================================================
// fetchAllBottomSignals — 全期間または直近n日の全シグナル配列
// /stats コマンド等で使用
// ============================================================
async function fetchAllBottomSignals(days = 0) {
  const rows = await getRawSheetData(config.ALERTS_SHEET_NAME)
  const alerts = parseAlerts(rows)
  if (days === 0) return alerts
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - days)
  return alerts.filter(a => {
    const d = new Date(String(a.date).replace(/\//g, '-'))
    return !isNaN(d.getTime()) && d >= cutoff
  })
}

module.exports = { fetchOHLCVData, fetchRecentBottomSymbols, fetchRecentBottomSignals, fetchAllBottomSignals }