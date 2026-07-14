// sheets.js — Google Sheets API クライアント
const { google } = require('googleapis')
const config = require('./config')
const { numericScore, parseJson, parseList, parseModes } = require('./signal_snapshot')

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

function normalizeHeader(value) {
  return String(value || '')
    .replace(/^\uFEFF/, '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
}

function firstHeaderIndex(header, aliases) {
  for (const alias of aliases) {
    const index = header.indexOf(alias)
    if (index >= 0) return index
  }
  return -1
}

function parseBoolean(value) {
  if (typeof value === 'boolean') return value
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return null
  if (['1', 'true', 'yes', 'y', 'on', 'selected'].includes(normalized)) return true
  if (['0', 'false', 'no', 'n', 'off', 'unselected'].includes(normalized)) return false
  return null
}

function parseSignalFeatureSnapshots(rows) {
  if (!Array.isArray(rows) || rows.length < 2) return new Map()

  let headerRow = -1
  let header = []
  for (let i = 0; i < Math.min(rows.length, 10); i++) {
    const candidate = (rows[i] || []).map(normalizeHeader)
    if (candidate.includes('alert_id') || candidate.includes('alertid')) {
      headerRow = i
      header = candidate
      break
    }
  }
  if (headerRow < 0) return new Map()

  const idx = {
    alertId: firstHeaderIndex(header, ['alert_id', 'alertid']),
    symbol: firstHeaderIndex(header, ['symbol_code', 'symbol', 'code']),
    signalDate: firstHeaderIndex(header, ['signal_date', 'date']),
    stableScore: firstHeaderIndex(header, [
      'stable_score', 'stable_star_score', 'stable_star', 'star_score', 'score',
    ]),
    sniperScore: firstHeaderIndex(header, ['sniper_score']),
    modes: firstHeaderIndex(header, [
      'modes_json', 'selected_modes_json', 'mode_flags_json', 'mode_json', 'modes',
    ]),
    sniperSelected: firstHeaderIndex(header, [
      'sniper_selected', 'is_sniper', 'sniper_enabled', 'sniper',
    ]),
    features: firstHeaderIndex(header, [
      'features_json', 'feature_json', 'indicators_json', 'features', 'indicators',
    ]),
    stableFilters: firstHeaderIndex(header, [
      'stable_filters_json', 'stable_conditions_json', 'stable_filters',
    ]),
    sniperFilters: firstHeaderIndex(header, [
      'sniper_filters_json', 'sniper_conditions_json', 'sniper_filters',
    ]),
    status: firstHeaderIndex(header, ['status', 'snapshot_status', 'state']),
    finalized: firstHeaderIndex(header, ['finalized', 'is_final', 'final']),
    cutoff: firstHeaderIndex(header, ['feature_cutoff', 'signal_feature_cutoff', 'cutoff']),
    logicHash: firstHeaderIndex(header, ['logic_hash', 'logic_version', 'stable_logic_hash']),
    inputHash: firstHeaderIndex(header, ['input_hash', 'data_hash']),
  }

  if (idx.alertId < 0 || idx.stableScore < 0) return new Map()

  const snapshots = new Map()
  for (let i = headerRow + 1; i < rows.length; i++) {
    const row = rows[i] || []
    const alertId = String(row[idx.alertId] || '').trim()
    const stableScore = numericScore(row[idx.stableScore], 6)
    if (!alertId || stableScore === null || snapshots.has(alertId)) continue

    const status = idx.status >= 0 ? String(row[idx.status] || '').trim() : ''
    const statusKey = status.toLowerCase().replace(/[\s-]+/g, '_')
    if (idx.status >= 0 && statusKey !== 'final') continue
    if (idx.finalized >= 0 && parseBoolean(row[idx.finalized]) === false) continue

    let modes = idx.modes >= 0 ? parseModes(row[idx.modes]) : new Set()
    let hasModes = idx.modes >= 0
    if (idx.sniperSelected >= 0) {
      const selected = parseBoolean(row[idx.sniperSelected])
      if (selected !== null) {
        hasModes = true
        if (selected) modes.add('sniper')
        else modes = new Set(Array.from(modes).filter(mode => !String(mode).startsWith('sniper')))
      }
    }

    const features = idx.features >= 0 ? parseJson(row[idx.features]) : null
    snapshots.set(alertId, {
      alertId,
      symbol: idx.symbol >= 0 ? cleanSymbol(row[idx.symbol]) : null,
      signalDate: idx.signalDate >= 0 ? String(row[idx.signalDate] || '').trim() : null,
      stableScore,
      sniperScore: idx.sniperScore >= 0 ? numericScore(row[idx.sniperScore], 99) : null,
      modes,
      hasModes,
      features: features && typeof features === 'object' && !Array.isArray(features) ? features : null,
      stableFilters: idx.stableFilters >= 0 ? parseList(row[idx.stableFilters]) : [],
      sniperFilters: idx.sniperFilters >= 0 ? parseList(row[idx.sniperFilters]) : [],
      hasStableFilters: idx.stableFilters >= 0,
      hasSniperFilters: idx.sniperFilters >= 0,
      status,
      cutoff: idx.cutoff >= 0 ? String(row[idx.cutoff] || '').trim() : null,
      logicHash: idx.logicHash >= 0 ? String(row[idx.logicHash] || '').trim() : null,
      inputHash: idx.inputHash >= 0 ? String(row[idx.inputHash] || '').trim() : null,
    })
  }
  return snapshots
}

let snapshotCache = new Map()

async function fetchSignalFeatureSnapshots() {
  try {
    const rows = await getRawSheetData(config.SIGNAL_FEATURE_SNAPSHOT_SHEET_NAME)
    snapshotCache = parseSignalFeatureSnapshots(rows)
    return snapshotCache
  } catch (err) {
    console.warn('[sheets] signal_feature_snapshots 取得スキップ:', err.message)
    return snapshotCache
  }
}

// 「TYO:4074」などの文字列から「4074」だけを抽出する共通関数
function cleanSymbol(sym) {
  if (!sym) return ""
  const s = String(sym).trim()
  return s.includes(':') ? s.split(':')[1] : s
}

function parseSignalDate(value) {
  const date = new Date(String(value || '').replace(/\//g, '-'))
  return isNaN(date.getTime()) ? null : date
}

function startOfToday() {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return today
}

function cutoffByCalendarDays(days) {
  const cutoff = startOfToday()
  cutoff.setDate(cutoff.getDate() - Math.max(Number(days) || 0, 1) + 1)
  return cutoff
}

function cutoffByBusinessDays(days) {
  const cutoff = startOfToday()
  let remaining = Math.max(Number(days) || 0, 1) - 1
  while (remaining > 0) {
    cutoff.setDate(cutoff.getDate() - 1)
    const day = cutoff.getDay()
    if (day !== 0 && day !== 6) remaining -= 1
  }
  return cutoff
}

function filterByCutoff(alerts, cutoff) {
  return alerts.filter(a => {
    const d = parseSignalDate(a.date)
    return d && d >= cutoff
  })
}

function matchesSpecificDate(alert, specificDate) {
  const target = specificDate.replace(/-/g, '/')
  return alert.date && (alert.date.includes(specificDate) || alert.date.includes(target))
}

function filterRecentAlerts(alerts, specificDate = null, rangeDays = null) {
  if (specificDate) return alerts.filter(a => matchesSpecificDate(a, specificDate))
  if (rangeDays === 0 || rangeDays === '0') return alerts
  if (rangeDays === null || rangeDays === undefined || rangeDays === '' || rangeDays === 'default') {
    return filterByCutoff(alerts, cutoffByBusinessDays(config.RECENT_SIGNAL_BUSINESS_DAYS))
  }
  return filterByCutoff(alerts, cutoffByCalendarDays(rangeDays))
}

function dedupeSignalsByAlertId(signals) {
  const seen = new Set()
  const result = []
  for (const signal of signals) {
    const id = signal.alertId ? String(signal.alertId) : ''
    if (id) {
      if (seen.has(id)) continue
      seen.add(id)
    }
    result.push(signal)
  }
  return result
}

// alerts_raw 用 (4行目ヘッダー)
function parseAlerts(rows) {
  if (rows.length < 4) return []
  const header = rows[3].map(h => String(h).toLowerCase())

  const idx = {
    alertId: header.indexOf('alert_id'),       // A列
    receivedAt: header.indexOf('received_at'),
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
      alertId: idx.alertId >= 0 ? (r[idx.alertId]?.toString().trim() || null) : null,
      receivedAt: idx.receivedAt >= 0 ? (r[idx.receivedAt]?.toString().trim() || null) : null,
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
    
    const rawTimestamp = String(r[idx.dt] || '').trim()
    const dateStr = rawTimestamp.replace(/\//g, '-')
    const dateKey = dateStr.slice(0, 10)
    const hourMatch = dateStr.match(/[ T](\d{1,2})(?::\d{1,2})?/)
    const sessionHour = hourMatch ? Number(hourMatch[1]) : null
    const bar = {
      datetime: new Date(dateStr),
      timestampText: rawTimestamp,
      dateKey,
      sessionHour,
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
  for (const item of map.values()) {
    item.bars.sort((a, b) => {
      const ad = a.dateKey || ''
      const bd = b.dateKey || ''
      if (ad !== bd) return ad < bd ? -1 : 1
      const ah = Number.isFinite(a.sessionHour) ? a.sessionHour : -1
      const bh = Number.isFinite(b.sessionHour) ? b.sessionHour : -1
      return ah - bh
    })
  }
  return map
}

async function fetchOHLCVData() {
  const rows = await getRawSheetData(config.OHLCV_SHEET_NAME)
  return parseOHLCV(rows)
}

async function fetchRecentBottomSymbols(specificDate = null, rangeDays = null) {
  const rows = await getRawSheetData(config.ALERTS_SHEET_NAME)
  const alerts = filterRecentAlerts(parseAlerts(rows), specificDate, rangeDays)
  const symbolMap = new Map()
  alerts.forEach(a => symbolMap.set(a.symbol, { date: a.date, name: a.name, entry: a.entry, eval5bd: a.eval5bd, perf5bd: a.perf5bd, receivedAt: a.receivedAt }))
  return symbolMap
}

// ============================================================
// fetchRecentBottomSignals — 配列返却（重複排除なし）
// 同一銘柄が期間内に複数回点灯している場合、全件返す
// ============================================================
async function fetchRecentBottomSignals(specificDate = null, rangeDays = null) {
  const rows = await getRawSheetData(config.ALERTS_SHEET_NAME)
  const alerts = parseAlerts(rows)
  return filterRecentAlerts(alerts, specificDate, rangeDays)
}

// ============================================================
// fetchAllBottomSignals — 全期間または直近n日の全シグナル配列
// /stats コマンド等で使用
// ============================================================
async function fetchAllBottomSignals(days = 0) {
  const rows = await getRawSheetData(config.ALERTS_SHEET_NAME)
  const alerts = parseAlerts(rows)
  if (days === 0) return alerts
  return filterByCutoff(alerts, cutoffByCalendarDays(days))
}

async function fetchBacktestBottomSignals(days = config.HELP_BACKTEST_DAYS) {
  const [rawRows, archiveRows] = await Promise.all([
    getRawSheetData(config.ALERTS_SHEET_NAME),
    getRawSheetData('signals_archive').catch(err => {
      console.warn('[sheets] signals_archive 取得スキップ:', err.message)
      return []
    }),
  ])
  const alerts = dedupeSignalsByAlertId([
    ...parseAlerts(rawRows),
    ...parseAlerts(archiveRows),
  ])
  return filterByCutoff(alerts, cutoffByCalendarDays(days))
}

// ============================================================
// fetchPremiumReasonsByAlertIds — premium_alert_log から理由を取得
// シグナル配列の alertId を使って K列 reason を引き、Map で返す
// ============================================================
async function fetchPremiumReasonsByAlertIds(signals) {
  if (!config.PREMIUM_SPREADSHEET_ID || !signals || signals.length === 0) return new Map()

  const idToSymbol = new Map()
  for (const sig of signals) {
    if (sig.alertId) idToSymbol.set(sig.alertId, sig.symbol)
  }
  if (idToSymbol.size === 0) return new Map()

  const sheets = google.sheets({ version: 'v4', auth: getAuth() })
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: config.PREMIUM_SPREADSHEET_ID,
    range: `${config.PREMIUM_SHEET_NAME}!A:K`,
  })
  const rows = res.data.values || []
  if (rows.length < 2) return new Map()

  const header = rows[0].map(h => String(h).toLowerCase().trim())
  const col = {
    eventType:  header.indexOf('event_type'),
    alertId:    header.indexOf('alert_id'),
    symbolCode: header.indexOf('symbol_code'),
    signalType: header.indexOf('signal_type'),
    // reason が header にない場合は K列（index 10）にフォールバック
    reason: header.indexOf('reason') !== -1 ? header.indexOf('reason') : 10,
  }

  const reasonMap = new Map()
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i]
    if (!r || r.length === 0) continue

    if (col.eventType >= 0 && String(r[col.eventType] || '').trim().toUpperCase() !== 'POSTED') continue
    if (col.signalType >= 0 && String(r[col.signalType] || '').trim().toUpperCase() !== 'BOTTOM') continue

    const alertId = col.alertId >= 0 ? String(r[col.alertId] || '').trim() : null
    if (!alertId || !idToSymbol.has(alertId)) continue

    // symbol_code の突合（銘柄ずれ防止）
    if (col.symbolCode >= 0) {
      const rowSymbol = cleanSymbol(String(r[col.symbolCode] || '').trim())
      if (rowSymbol !== idToSymbol.get(alertId)) continue
    }

    const reason = r[col.reason] ? String(r[col.reason]).trim() : null
    if (reason) reasonMap.set(alertId, reason) // 後勝ち
  }

  return reasonMap
}

module.exports = {
  fetchOHLCVData,
  fetchRecentBottomSymbols,
  fetchRecentBottomSignals,
  fetchAllBottomSignals,
  fetchBacktestBottomSignals,
  fetchSignalFeatureSnapshots,
  fetchPremiumReasonsByAlertIds,
  parseSignalFeatureSnapshots,
}
