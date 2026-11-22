'use strict';

const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { DATASET_ID, validateManifest } = require('../src/new-a-private.ts');
const { DEFAULTS, OPEN_EXIT_POLICY } = require('../src/new-a-preferences.ts');
const { createDatasetRuntime, createQuoteDecoder, validDay } = require('./new-a-ui-source/engine/dataset-runtime.cjs');

const digest = raw => createHash('sha256').update(raw).digest('hex');
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const manifestLimit = 1024 * 1024;
const partLimit = 196608;
const historyPageSize = 100;
const fundamentalLimit = 16_384;
const fundamentalFields = ['材料インパクト', '事業概要', '足元材料', 'ファンダ要点', '注意点', '開示リンク', 'Sources'];
const analysisTimestamp = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)$/;
const chartLimit = 3000;
const sharedPreferences = Object.freeze({ ...DEFAULTS, price_cap_yen: null });
const presets = [['defensive', 'defensive'], ['medium', 'balanced'], ['return_priority', 'profit']];
const completedWatchStates = new Set(['EXPIRED', 'UP_ESCAPED', 'DOWN_INVALIDATED']);
const states = new Set(['WATCHING', 'TRIGGERED', 'REFERENCE_ONLY', ...completedWatchStates,
  'DATA_GAP', 'BASIS_CHANGED', 'IDENTITY_CHANGED']);
const dashboardRowLimit = 1000;
const symbolPattern = /^[0-9A-Z]{4}$/;

function episodeKey(row) {
  assert(row && typeof row.symbol === 'string' && symbolPattern.test(row.symbol)
    && validDay(row.candidate_date) && Number.isSafeInteger(row.episode_id), 'Invalid history episode identity');
  return [row.symbol, row.candidate_date, row.episode_id].join('|');
}

async function readBounded(file, limit) {
  const info = await fs.lstat(file);
  assert(info.isFile() && info.size <= limit, 'Invalid input file or byte limit exceeded');
  const raw = await fs.readFile(file);
  assert(raw.length <= limit, 'Input exceeded its byte limit');
  return raw;
}

function readActiveEvidence(proofRaw, proofSha256, bundleManifestSha256, manifest) {
  assert(hash(proofSha256) && digest(proofRaw) === proofSha256, 'Owner readback proof pin mismatch');
  const proof = JSON.parse(proofRaw);
  assert.equal(proof.schema, 'NEW_A_OPERATIONAL_OBSERVATION_V1', 'Unsupported owner readback proof');
  assert(hash(proof.raw_response_sha256) && hash(proof.active_manifest_sha256)
    && hash(proof.active_logical_manifest_sha256) && typeof proof.observed_at === 'string'
    && Number.isFinite(Date.parse(proof.observed_at)), 'Incomplete verified owner readback');
  assert(bundleManifestSha256 === proof.active_manifest_sha256
    || bundleManifestSha256 === proof.active_logical_manifest_sha256, 'Bundle differs from the verified owner READY manifest');
  assert(typeof proof.active_dataset_id === 'string' && DATASET_ID.test(proof.active_dataset_id)
    && Number.isSafeInteger(proof.active_revision) && proof.active_revision > 0
    && hash(proof.active_source_version) && validDay(proof.active_as_of), 'Invalid owner READY identity');
  const active = ['NEW_A_ACTIVE_METADATA_V1', proof.active_dataset_id, proof.active_revision, 'READY',
    proof.active_source_version, proof.active_manifest_sha256, proof.active_as_of];
  assert.equal(digest(JSON.stringify(active)), proof.d1_active_sha256, 'Owner READY metadata digest mismatch');
  assert(manifest.strategy === 'A_BASE' && manifest.as_of === proof.active_as_of
    && manifest.source_version === proof.active_source_version, 'Bundle generation mismatch');
  return {
    status: 'READY',
    dataset_id: proof.active_dataset_id,
    revision: proof.active_revision,
    as_of: proof.active_as_of,
    source_version: proof.active_source_version,
  };
}

function assembleCurrent(records) {
  if (!records.length) return null;
  const first = records[0];
  assert(first?.schema === 'NEW_A_CURRENT_JSON_FRAGMENT_V1' && first.count === records.length
    && records.length <= 256 && Number.isSafeInteger(first.bytes_total) && first.bytes_total > 0
    && first.bytes_total <= 8 * 1024 * 1024 && hash(first.display_sha256), 'Invalid current dashboard fragments');
  let size = 0;
  const fragments = records.map((row, index) => {
    assert(row.schema === first.schema && row.index === index && row.count === first.count
      && row.bytes_total === first.bytes_total && row.display_sha256 === first.display_sha256
      && typeof row.payload_base64 === 'string' && row.payload_base64.length <= 43692,
    'Invalid current dashboard fragment order');
    const raw = Buffer.from(row.payload_base64, 'base64');
    assert(raw.length > 0 && raw.length <= 32768 && raw.toString('base64') === row.payload_base64,
      'Invalid current dashboard fragment bytes');
    size += raw.length;
    assert(size <= first.bytes_total, 'Invalid current dashboard size');
    return raw;
  });
  const bytes = Buffer.concat(fragments);
  assert(size === first.bytes_total && digest(bytes) === first.display_sha256, 'Current dashboard fragment hash mismatch');
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}

async function openVerifiedBundle(bundle, manifest, { includeDisplay = false } = {}) {
  async function readPart(descriptor) {
    const raw = await readBounded(path.join(bundle, descriptor.name), partLimit);
    assert(raw.length === descriptor.bytes && digest(raw) === descriptor.sha256, 'Canonical source part hash or size mismatch');
    const values = JSON.parse(raw);
    assert(Array.isArray(values) && values.length === descriptor.rows, 'Canonical source part row count mismatch');
    return values;
  }
  async function collectParts(descriptors) {
    const rows = [];
    for (const descriptor of descriptors) {
      for (const row of await readPart(descriptor)) rows.push(row);
    }
    return rows;
  }

  const input = { ...manifest.input_header };
  for (const key of ['episodes', 'intents', 'watches']) input[key] = await collectParts(manifest.collections[key]);
  const presentations = [];
  for (const descriptor of manifest.collections.presentation) {
    for (const row of await readPart(descriptor)) {
      if (includeDisplay || row?.fundamental?.auditStatus === 'pass') presentations.push(row);
    }
  }
  const current = assembleCurrent(await collectParts(manifest.collections.current_daily));
  if (current) {
    assert(current.schema === 'NEW_A_OWNER_DAILY_DISPLAY_V1' && current.as_of === manifest.as_of
      && current.strategy === 'A_BASE' && current.audience === 'EXISTING_CLOUD_OWNER_ONLY'
      && hash(manifest.daily_snapshot_sha256) && current.source_snapshot_sha256 === manifest.daily_snapshot_sha256
      && Array.isArray(current.events) && current.monitor_state?.schema === 'NEW_A_CURRENT_MONITOR_STATE_V1'
      && current.monitor_state.strategy === 'A_BASE' && current.monitor_state.actual_fills === false
      && current.monitor_state.watches && typeof current.monitor_state.watches === 'object'
      && !Array.isArray(current.monitor_state.watches)
      && Array.isArray(current.monitor_state.pending_references), 'Current dashboard evidence differs');
  } else {
    assert(manifest.live !== true, 'Live source has no current dashboard evidence');
  }
  assert(Array.isArray(input.calendar) && input.calendar.length > 0 && input.calendar.length <= chartLimit
    && input.calendar.at(-1) === manifest.as_of
    && input.calendar.every((day, i) => validDay(day) && (i === 0 || input.calendar[i - 1] < day)), 'Invalid canonical calendar');

  assert(Array.isArray(manifest.quote_fields) && manifest.quote_fields.length > 0, 'Invalid canonical quote fields');
  const quoteDecoder = createQuoteDecoder(manifest.quote_fields, input.calendar, manifest.as_of);
  const quotes = new Map();
  for (const descriptor of manifest.quotes) {
    for (const row of await readPart(descriptor)) {
      assert(Array.isArray(row) && row.length === 3, 'Invalid canonical quote row');
      const [symbol, date, values] = row;
      const key = symbol + '|' + date;
      assert(typeof symbol === 'string' && symbolPattern.test(symbol) && validDay(date) && !quotes.has(key), 'Invalid canonical quote key');
      quotes.set(key, quoteDecoder.normal(symbol, date, values));
    }
  }
  assert.equal(quotes.size, manifest.expected_quote_keys, 'Canonical quote key count mismatch');
  let dashboardCloses;
  if (includeDisplay) {
    const { valid } = require('./new-a-ui-source/engine/finite-engine.cjs');
    const date = manifest.as_of;
    const prices = Object.create(null);
    if (date === input.limits?.completeThrough) {
      for (const [key, quote] of quotes) {
        const [symbol, day] = key.split('|');
        if (day === date && /^[0-9][0-9A-Z]{3}$/.test(symbol) && valid(quote, true)) {
          prices[symbol] = { date, price: quote.actual_close };
        }
      }
    }
    dashboardCloses = { date, prices };
  }
  return {
    watches: input.watches,
    presentations,
    ...(includeDisplay ? { dashboardCloses } : {}),
    calendar: input.calendar,
    current,
    runtime: createDatasetRuntime(input, {
      get(symbol, date) {
        const key = symbol + '|' + date;
        assert(quotes.has(key), 'Canonical simulation requires an unavailable quote key');
        return quotes.get(key);
      },
      scheduledExit: quoteDecoder.scheduledExit,
      decisionSkipped: quoteDecoder.decisionSkipped,
    }),
  };
}

function safeHistory(watches, asOf) {
  const episodes = new Map();
  const paid = new Map();
  for (const watch of watches) {
    const key = episodeKey(watch);
    const { symbol, candidate_date: date, watch_status: state } = watch;
    assert(date <= asOf && states.has(state) && !episodes.has(key), 'Invalid shared history row');
    episodes.set(key, watch);
    const summaryKey = date + '|' + symbol;
    assert(!paid.has(summaryKey) || paid.get(summaryKey).state === state, 'Ambiguous shared history state');
    paid.set(summaryKey, { date, symbol, state });
  }
  return { episodes, history: sortedRows(paid.values()) };
}

function sortedRows(rows) {
  return [...rows].sort((a, b) => b.date.localeCompare(a.date) || a.symbol.localeCompare(b.symbol, 'en'));
}

function settlementEvidence(models, sharedScenarios, marketDays, asOf) {
  const open = new Set();
  for (const model of [...models, ...sharedScenarios]) {
    for (const [symbol, position] of Object.entries(model.open_positions)) {
      open.add(episodeKey({ ...position, symbol }));
    }
  }
  const closed = new Map();
  for (const model of models) {
    const fills = new Map(model.orders.filter(order => order.status === 'FILLED')
      .map(order => [episodeKey(order), order.order_date]));
    for (const trade of model.trades) {
      const key = episodeKey(trade);
      if (open.has(key) || fills.get(key) !== trade.entry_date || !marketDays.has(trade.entry_date)
        || !marketDays.has(trade.exit_date) || trade.entry_date > trade.exit_date || trade.exit_date > asOf
        || model.unresolved.some(item => item.symbol === trade.symbol && item.date >= trade.entry_date
          && item.date <= trade.exit_date)) continue;
      const previous = closed.get(key);
      if (!previous || trade.exit_date > previous) closed.set(key, trade.exit_date);
    }
  }
  return closed;
}

function attachFundamentals(history, episodes, presentations) {
  const byDetection = new Map();
  for (const [key, watch] of episodes) {
    const detection = watch.candidate_date + '|' + watch.symbol;
    byDetection.set(detection, byDetection.has(detection) ? null : key);
  }
  const reports = new Map();
  for (const row of presentations) {
    const report = row.fundamental;
    const detection = row.signalDate + '|' + row.symbol;
    const episode = byDetection.get(detection);
    if (typeof episode !== 'string' || row.identity !== episode || row.signalDate !== row.candidateDate
      || row.identityStatus === 'PRELISTING_HISTORY_MAPPING_UNVERIFIED' || row.chartAllowed === false
      || report.identity !== detection || report.symbol !== row.symbol || report.signalDate !== row.signalDate
      || report.analysisCutoff !== row.analysisCutoff) continue;
    assert(!reports.has(detection) && typeof report.analysisCutoff === 'string'
      && analysisTimestamp.test(report.analysisCutoff) && Number.isFinite(Date.parse(report.analysisCutoff))
      && Array.isArray(report.fields) && report.fields.length === fundamentalFields.length,
      'Invalid verified member fundamental report');
    const fields = report.fields.map((field, index) => {
      assert(field?.label === fundamentalFields[index] && typeof field.text === 'string' && field.text.trim()
        && Buffer.byteLength(field.text) <= 8192, 'Invalid verified member fundamental field');
      return { label: field.label, text: field.text };
    });
    const company_name = row.nameStatus !== 'NAME_UNVERIFIED' && typeof row.companyName === 'string'
      && row.companyName.trim() && Buffer.byteLength(row.companyName) <= 256 ? row.companyName : null;
    const json = JSON.stringify({
      date: row.signalDate, symbol: row.symbol, company_name, analysis_cutoff: report.analysisCutoff, fields,
    });
    assert(Buffer.byteLength(json) <= fundamentalLimit, 'Verified member fundamental report exceeds the storage limit');
    reports.set(detection, { sha256: digest(json), json });
  }
  const fundamentals = [];
  for (const row of history) {
    const report = reports.get(row.date + '|' + row.symbol);
    if (!report) continue;
    row.fundamental_sha256 = report.sha256;
    fundamentals.push(report);
  }
  assert(fundamentals.length === reports.size, 'Verified member fundamental report is outside Premium history');
  return fundamentals;
}

function completedHistory(episodes, settlements, current, marketDays, asOf) {
  const active = new Set(Object.values(current?.monitor_state.watches ?? {}).map(watch => episodeKey(watch.episode)));
  // Entry references can be retained after a simulated position closes.
  // Neither an old reference price nor its separate reference exit date is settlement evidence.
  const pending = new Set((current?.monitor_state.pending_references ?? [])
    .filter(item => item.price_status !== 'HISTORICAL_REFERENCE_ONLY'
      || !marketDays.has(item.reference_entry_date) || item.reference_entry_date >= asOf)
    .map(episodeKey));
  const rows = new Map();
  const blocked = new Set();
  for (const [key, watch] of episodes) {
    const { candidate_date: date, symbol, watch_status: state, terminal_date: terminal, trigger_date: trigger } = watch;
    const summaryKey = date + '|' + symbol;
    let row;
    if (!active.has(key) && !pending.has(key) && marketDays.has(terminal) && date <= terminal && terminal <= asOf) {
      if (completedWatchStates.has(state) && trigger == null) {
        row = { date, symbol, state, completed_on: terminal };
      } else if (state === 'TRIGGERED' && trigger === terminal) {
        const closed = settlements.get(key);
        if (closed && terminal < closed && closed <= asOf) {
          row = { date, symbol, state: 'HOLD_ENDED', completed_on: closed };
        }
      }
    }
    // A collapsed date/symbol key must never certify another ambiguous episode.
    if (!row || rows.has(summaryKey)) blocked.add(summaryKey);
    if (row) rows.set(summaryKey, row);
  }
  return sortedRows([...rows].filter(([key]) => !blocked.has(key)).map(([, row]) => row));
}

function dashboardRows(current, currentModel, episodes, marketDays, asOf) {
  if (!current) return [];
  const rows = new Map();
  function add(date, symbol, state, lane) {
    rows.set([lane, date, symbol, state].join('|'), { date, symbol, state, lane });
  }
  const actions = new Set(['WATCH_STARTED', 'ENTRY_CANDIDATE', 'WATCH_TERMINAL']);
  for (const event of current.events) {
    if (!actions.has(event.kind)) continue;
    assert(event.session === asOf && episodes.has(episodeKey(event)), 'Invalid current dashboard event');
    add(asOf, event.symbol, event.kind, 'today');
  }
  if (currentModel?.resolved === true && currentModel.period[1] === asOf) {
    for (const trade of currentModel.trades) {
      if (trade.entry_date === asOf) add(asOf, trade.symbol, 'HOLD_STARTED', 'today');
      if (trade.exit_date === asOf) add(asOf, trade.symbol, 'HOLD_ENDED', 'today');
    }
    for (const [symbol, position] of Object.entries(currentModel.open_positions)) {
      if (position.entry_date === asOf) add(asOf, symbol, 'HOLD_STARTED', 'today');
    }
  }
  for (const { episode } of Object.values(current.monitor_state.watches)) {
    const watch = episodes.get(episodeKey(episode));
    assert(watch?.watch_status === 'WATCHING' && marketDays.has(episode.candidate_date), 'Invalid current monitoring row');
    add(episode.candidate_date, episode.symbol, 'WATCHING', 'watching');
  }
  const result = sortedRows(rows.values());
  assert(result.length <= dashboardRowLimit, 'Dashboard row limit exceeded');
  return result;
}

function amount(value) {
  assert(Number.isFinite(value) && Math.abs(value) < 1e12, 'Invalid shared simulation amount');
  return Math.round(value * 100) / 100;
}

function sharedAnalytics(preset, result, asOf) {
  assert(Array.isArray(result.period) && validDay(result.period[0]) && result.period.at(-1) === asOf
    && typeof result.resolved === 'boolean', 'Simulation does not match the canonical period');
  const row = { preset, from: result.period[0], through: asOf, resolved: result.resolved, metrics: null };
  if (!result.resolved) return row;
  const { netProfit, maxDrawdown, winRate, closed } = result.metrics;
  assert(Number.isSafeInteger(closed) && closed >= 0 && Number.isFinite(maxDrawdown) && maxDrawdown >= -1
    && maxDrawdown <= 0 && (closed === 0 ? winRate === null : Number.isFinite(winRate) && winRate >= 0 && winRate <= 1),
  'Invalid shared simulation metrics');
  return {
    ...row,
    metrics: {
      net_profit: amount(netProfit),
      max_drawdown_pct: amount(maxDrawdown * 100),
      win_rate_pct: winRate === null ? null : amount(winRate * 100),
      trade_count: closed,
    },
  };
}

function sharedChart(result, asOf) {
  const rows = result.daily.map((day, index) => {
    assert(validDay(day.date) && (index === 0 || result.daily[index - 1].date < day.date)
      && typeof day.unresolved === 'boolean', 'Invalid shared simulation day');
    if (day.unresolved) return { date: day.date, equity_yen: null, holding_count: null };
    assert(Number.isSafeInteger(day.positions) && day.positions >= 0, 'Invalid shared holding count');
    return { date: day.date, equity_yen: amount(day.equity_diagnostic), holding_count: day.positions };
  });
  assert(rows.length <= chartLimit && rows.at(-1)?.date === asOf, 'Invalid shared simulation chart range');
  return rows;
}

async function prepareNewAMemberProjection({ bundle, readyProof, readyProofSha256 }) {
  const [manifestRaw, proofRaw] = await Promise.all([
    readBounded(path.join(bundle, 'manifest.json'), manifestLimit),
    readBounded(readyProof, manifestLimit),
  ]);
  const sourceManifestSha256 = digest(manifestRaw);
  const manifest = validateManifest(JSON.parse(manifestRaw));
  const source = readActiveEvidence(proofRaw, readyProofSha256, sourceManifestSha256, manifest);
  const { runtime, watches, presentations, calendar, current } = await openVerifiedBundle(bundle, manifest);
  const { episodes, history } = safeHistory(watches, source.as_of);
  const fundamentals = attachFundamentals(history, episodes, presentations);
  const marketDays = new Set(calendar);
  const options = { exitPolicy: OPEN_EXIT_POLICY };
  const fullModel = runtime.simulate(sharedPreferences, options);
  const currentModel = runtime.currentPortfolio(sharedPreferences, source.as_of,
    { ...options, fullResult: fullModel })?.result;
  const scenarios = presets.map(([, trialPreset]) => runtime.simulate(sharedPreferences, { ...options, trialPreset }));
  const settlements = settlementEvidence(currentModel && currentModel !== fullModel ? [fullModel, currentModel] : [fullModel],
    scenarios, marketDays, source.as_of);
  const completed = completedHistory(episodes, settlements, current, marketDays, source.as_of);
  const dashboard = dashboardRows(current, currentModel, episodes, marketDays, source.as_of);
  const parts = [];
  function add(kind, index, rows) {
    const json = JSON.stringify({ kind, index, rows });
    const bytes = Buffer.byteLength(json);
    assert(bytes <= partLimit, 'Shared projection part exceeds the storage limit');
    parts.push({ kind, index, rows: rows.length, bytes, sha256: digest(json), json });
  }
  let historyIndex = 0;
  for (const view of [history, completed]) {
    for (let offset = 0; offset < view.length; offset += historyPageSize) {
      add('history', historyIndex++, view.slice(offset, offset + historyPageSize));
    }
  }
  add('history', historyIndex, dashboard);
  const premium_pages = Math.ceil(history.length / historyPageSize);
  const completed_pages = Math.ceil(completed.length / historyPageSize);
  assert(premium_pages <= 200 && completed_pages <= premium_pages, 'Shared history exceeds its page limit');
  const analytics = [];
  for (const [index, [preset]] of presets.entries()) {
    const result = scenarios[index];
    analytics.push(sharedAnalytics(preset, result, source.as_of));
    add('chart', index, sharedChart(result, source.as_of));
  }
  add('analytics', 0, analytics);
  const projection = {
    schema: fundamentals.length ? 'NEW_A_SHARED_READONLY_VIEW_V3' : 'NEW_A_SHARED_READONLY_VIEW_V2',
    audience: 'AUTHENTICATED_TIERED_DISCORD_VIEW',
    basis: 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS',
    source,
    history_layout: { premium_pages, completed_pages },
    parts: parts.map(({ json, ...descriptor }) => descriptor),
    ...(fundamentals.length ? { fundamental_reports: fundamentals.length } : {}),
  };
  const manifestJson = JSON.stringify(projection);
  assert(Buffer.byteLength(manifestJson) <= 65_536, 'Shared projection manifest exceeds the storage limit');
  return {
    manifestJson,
    parts,
    fundamentals,
    receipt: {
      schema: fundamentals.length ? 'NEW_A_MEMBER_PROJECTION_OFFLINE_V3' : 'NEW_A_MEMBER_PROJECTION_OFFLINE_V2',
      ...(fundamentals.length ? { fundamental_reports: fundamentals.length } : {}),
      source,
      source_manifest_sha256: sourceManifestSha256,
      owner_readback_sha256: readyProofSha256,
      projection_manifest_sha256: digest(manifestJson),
      history_rows: history.length,
      parts: parts.length,
      activated: false,
    },
  };
}

async function main(args) {
  const { values } = parseArgs({ args, options: {
    bundle: { type: 'string' },
    'ready-proof': { type: 'string' },
    'ready-proof-sha256': { type: 'string' },
    out: { type: 'string' },
  } });
  assert(Object.values(values).length === 4 && Object.values(values).every(Boolean),
    'Required arguments: --bundle --ready-proof --ready-proof-sha256 --out');
  const { manifestJson, parts, fundamentals, receipt } = await prepareNewAMemberProjection({
    bundle: values.bundle, readyProof: values['ready-proof'], readyProofSha256: values['ready-proof-sha256'],
  });
  await fs.mkdir(values.out);
  await fs.writeFile(path.join(values.out, 'manifest.json'), manifestJson, { flag: 'wx' });
  for (const part of parts) {
    await fs.writeFile(path.join(values.out, part.kind + '-' + part.index + '.json'), part.json, { flag: 'wx' });
  }
  for (const report of fundamentals) {
    await fs.writeFile(path.join(values.out, 'fundamental-' + report.sha256 + '.json'), report.json, { flag: 'wx' });
  }
  await fs.writeFile(path.join(values.out, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
}

module.exports = {
  prepareNewAMemberProjection, attachFundamentals, digest, historyPageSize, openVerifiedBundle, presets,
  readActiveEvidence, readBounded, safeHistory, dashboardRows, sharedAnalytics, sharedChart,
};
if (require.main === module) {
  main(process.argv.slice(2)).catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
