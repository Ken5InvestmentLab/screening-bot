'use strict';

const { createHash } = require('node:crypto');
const { createDatasetRuntime } = require('../../weak-early-beta-gate/scripts/new-a-ui-source/engine/dataset-runtime.cjs');
const { exitTerms, validateExitPolicy, validatePreferences } = require('../../weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs');

const MORNING_CRON = '0 23 * * *';
const JST_MS = 9 * 60 * 60 * 1000;
const SHA256 = /^[0-9a-f]{64}$/;
const DATASET_ID = /^a-[0-9a-f]{24}$/;
const KINDS = ['episodes', 'intents', 'watches', 'presentation', 'current_daily'];
const REPLAY_KINDS = ['episodes', 'intents', 'watches'];
const hash = value => createHash('sha256').update(value).digest('hex');
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function requireValid(condition, message) {
  if (!condition) throw Error(message);
}

function isDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = Date.parse(value + 'T00:00:00Z');
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 10) === value;
}

function validateCalendar(dates) {
  requireValid(Array.isArray(dates) && dates.length > 0 &&
    dates.every((date, index) => isDate(date) && (index === 0 || dates[index - 1] < date)),
  'unverified market calendar');
  return dates;
}

function verifiedActive(value) {
  const { pointer, manifestText, publication } = value;
  requireValid(pointer?.status === 'READY' && DATASET_ID.test(pointer.dataset_id) &&
    Number.isSafeInteger(pointer.revision) && pointer.revision > 0 &&
    SHA256.test(pointer.manifest_sha256) && typeof manifestText === 'string' &&
    Buffer.byteLength(manifestText) <= 256 * 1024 &&
    hash(manifestText) === pointer.manifest_sha256, 'active published manifest differs');

  const manifest = JSON.parse(manifestText);
  requireValid(manifest.schema === 'A_BROWSER_PRIVATE_INPUT_V1' && manifest.strategy === 'A_BASE' &&
    manifest.audience === 'EXISTING_CLOUD_OWNER_ONLY' && isDate(manifest.as_of) &&
    SHA256.test(manifest.source_version) && SHA256.test(manifest.daily_snapshot_sha256) &&
    pointer.source_version === manifest.source_version &&
    manifest.input_header?.source_version === manifest.source_version, 'active New A source differs');
  requireValid(publication?.schema === 'NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1' &&
    publication.published === true && publication.active_readback_verified === true &&
    publication.existing_owner_gate_verified === true &&
    publication.dataset_id === pointer.dataset_id && publication.revision === pointer.revision &&
    publication.manifest_sha256 === pointer.manifest_sha256 &&
    publication.snapshot_sha256 === manifest.daily_snapshot_sha256 &&
    publication.source_version === manifest.source_version && publication.as_of === manifest.as_of,
  'owner publication is not verified for the active source');

  requireValid(manifest.collections && Object.keys(manifest.collections).length === KINDS.length &&
    KINDS.every(kind => Array.isArray(manifest.collections[kind])) && Array.isArray(manifest.quotes),
  'private manifest collections differ');
  const entries = [...KINDS.map(kind => [kind, manifest.collections[kind]]), ['quotes', manifest.quotes]];
  const names = new Set();
  for (const [kind, parts] of entries) {
    for (const part of parts) {
      requireValid(new RegExp('^' + kind + '-[0-9]{3}\\.json$').test(part.name) &&
        !names.has(part.name) && names.size < 512 && SHA256.test(part.sha256) &&
        (part.dataset_id === undefined || DATASET_ID.test(part.dataset_id)) &&
        Number.isSafeInteger(part.bytes) && part.bytes >= 2 && part.bytes <= 65536 &&
        Number.isSafeInteger(part.rows) && part.rows >= 0, 'private part descriptor differs');
      names.add(part.name);
    }
  }
  return { pointer, manifest };
}

function savedOwner(value) {
  requireValid(value?.schema_version === 1 && value.has_saved_finite_preferences === true &&
    value.preference_source === 'new-a-saved' && Number.isSafeInteger(value.revision) &&
    value.revision > 0 && SHA256.test(value.owner_binding_sha256),
  'verified saved owner settings required');
  const preferences = validatePreferences(value.preferences);
  const exitPolicy = validateExitPolicy(value.exit_policy);
  requireValid(exitPolicy !== null, 'verified service exit policy required');
  return { binding: value.owner_binding_sha256, revision: value.revision, preferences, exitPolicy };
}

async function partRows(readPart, descriptor, datasetId) {
  const raw = await readPart(descriptor.dataset_id || datasetId, descriptor.name);
  requireValid(typeof raw === 'string' && Buffer.byteLength(raw) === descriptor.bytes &&
    hash(raw) === descriptor.sha256, 'published private part bytes differ');
  const value = JSON.parse(raw);
  requireValid(Array.isArray(value) && value.length === descriptor.rows, 'published private part rows differ');
  return value;
}

async function replayPublished(active, owner, readPart) {
  const { pointer, manifest } = active;
  const input = { ...manifest.input_header };
  const dates = validateCalendar(input.calendar);
  requireValid(dates.at(-1) === manifest.as_of && input.limits?.completeThrough === manifest.as_of,
    'published source did not complete through its cutoff');

  for (const kind of REPLAY_KINDS) {
    input[kind] = [];
    for (const part of manifest.collections[kind]) {
      input[kind].push(...await partRows(readPart, part, pointer.dataset_id));
    }
  }
  const expectedFields = ['open', 'high', 'low', 'close', 'volume', 'actual_close', 'actual_volume',
    'split_factor', 'source_usable'];
  requireValid(same(manifest.quote_fields, expectedFields) &&
    Number.isSafeInteger(manifest.expected_quote_keys) && manifest.expected_quote_keys >= 0,
  'published quote schema differs');

  const quotes = new Map();
  for (const part of manifest.quotes) {
    for (const row of await partRows(readPart, part, pointer.dataset_id)) {
      requireValid(Array.isArray(row) && row.length === 3 && /^[0-9A-Z]{4}$/.test(row[0]) &&
        isDate(row[1]) && (row[2] === null ||
          (Array.isArray(row[2]) && row[2].length === expectedFields.length)),
      'published quote record differs');
      const key = row[0] + '|' + row[1];
      requireValid(!quotes.has(key), 'duplicate published quote record');
      quotes.set(key, row[2] === null ? null :
        Object.fromEntries(expectedFields.map((field, index) => [field, row[2][index]])));
    }
  }
  requireValid(quotes.size === manifest.expected_quote_keys, 'published quote count differs');
  const reader = {
    get(symbol, date) {
      const key = symbol + '|' + date;
      requireValid(quotes.has(key), 'missing published quote key');
      return quotes.get(key);
    },
  };

  // The site displays the model result for holdings, separately from analytics
  // trial presets. Reuse that same model rather than recreating virtual fills.
  return createDatasetRuntime(input, reader).currentPortfolio(owner.preferences, manifest.as_of,
    { exitPolicy: owner.exitPolicy });
}

function jst(ms) {
  requireValid(Number.isSafeInteger(ms), 'invalid schedule timestamp');
  return new Date(ms + JST_MS).toISOString();
}

async function checkSourcesUnchanged({ readActive, readOwnerPreferences }, active, owner) {
  const latest = verifiedActive(await readActive());
  const latestOwner = savedOwner(await readOwnerPreferences());
  requireValid(same(latest.pointer, active.pointer) && same(latestOwner, owner),
    'publication or saved owner settings changed during planning');
}

function sourceBasis(active, owner) {
  return {
    dataset_id: active.pointer.dataset_id,
    revision: active.pointer.revision,
    manifest_sha256: active.pointer.manifest_sha256,
    source_version: active.manifest.source_version,
    snapshot_sha256: active.manifest.daily_snapshot_sha256,
    preferences_revision: owner.revision,
  };
}

function heldSymbols(active) {
  const held = active.manifest.input_header.limits.heldSymbols ?? {};
  requireValid(held && typeof held === 'object' && !Array.isArray(held), 'invalid held symbols');
  return held;
}

/**
 * Plan only. The host must supply established read-only, owner-scoped adapters
 * for the live D1 active pointer/bundle and saved settings, and independently
 * pin the existing bootstrap calendar. No transport, credentials or storage
 * writes are available in this module.
 */
async function planEvaluationMorning({ cron, scheduledAt, now, bankBusinessDate, readActive,
                                       readOwnerPreferences, readCalendar, readPart }) {
  const scheduledJst = jst(scheduledAt);
  const actualJst = jst(now);
  const target = scheduledJst.slice(0, 10);
  const empty = status => ({ status, target_date: target, notices: [] });

  if (cron !== MORNING_CRON || scheduledAt > now || scheduledJst.slice(11, 16) !== '08:00' ||
      actualJst.slice(0, 10) !== target || actualJst.slice(11, 13) !== '08') {
    return empty('outside_reminder_window');
  }
  const business = await bankBusinessDate(target);
  if (business !== true) return empty(business === false ? 'bank_non_business_day' : 'bank_calendar_unavailable');

  const active = verifiedActive(await readActive());
  const owner = savedOwner(await readOwnerPreferences());
  const calendarReceipt = await readCalendar();
  requireValid(calendarReceipt && typeof calendarReceipt.raw === 'string' &&
    Buffer.byteLength(calendarReceipt.raw) <= 256 * 1024 &&
    SHA256.test(calendarReceipt.sha256) && hash(calendarReceipt.raw) === calendarReceipt.sha256,
  'bootstrap calendar proof differs');
  const calendar = validateCalendar(JSON.parse(calendarReceipt.raw));
  const publishedDays = validateCalendar(active.manifest.input_header.calendar);
  const cutoff = calendar.indexOf(active.manifest.as_of);
  requireValid(cutoff >= 0 && same(calendar.slice(0, cutoff + 1), publishedDays),
    'published calendar is inconsistent with the bootstrap calendar');
  const next = calendar[cutoff + 1];
  if (!next || next < target) return empty('previous_market_session_not_published');
  if (next > target) return empty('market_non_business_day');

  const portfolio = await replayPublished(active, owner, readPart);
  if (!portfolio) return empty('virtual_model_not_current');

  const held = heldSymbols(active);
  const notices = [];
  for (const [symbol, position] of Object.entries(portfolio.result.open_positions)) {
    if (Object.hasOwn(held, symbol)) continue;
    const entry = calendar.indexOf(position.entry_date);
    requireValid(entry >= 0 && entry <= cutoff && isDate(position.candidate_date) &&
      Number.isSafeInteger(position.episode_id), 'invalid virtual holding identity');
    const terms = exitTerms(owner.preferences.exit_endpoint, position.entry_date, owner.exitPolicy);
    if (calendar[entry + terms.sessions - 1] !== target) continue;
    // One morning reminder for this position and day, even if the owner
    // changes between an open and close evaluation on the same market date.
    const id = ['NEW_A_EVALUATION_MORNING_V1', owner.binding, symbol,
      position.candidate_date, position.episode_id, position.entry_date, target];
    notices.push({
      event_id: hash(JSON.stringify(id)),
      kind: 'EVALUATION_DAY_MORNING',
      symbol,
      candidate_date: position.candidate_date,
      simulated_entry_date: position.entry_date,
      scheduled_evaluation_date: target,
      evaluation_endpoint: terms.endpoint,
      evaluation_timing: terms.timing,
      title: '確定日の朝8時（日本時間）',
      description: '今日は、設定した確定日です。その日の価格はまだ確定していません。',
      evaluation_price_status: 'NOT_YET_OBSERVED',
      execution_status: 'SIMULATED_NOT_ACTUAL_TRADES',
    });
  }
  await checkSourcesUnchanged({ readActive, readOwnerPreferences }, active, owner);
  return {
    status: 'planned', target_date: target,
    model_basis: portfolio.basis,
    basis: { ...sourceBasis(active, owner), calendar_sha256: calendarReceipt.sha256 },
    notices: notices.sort((a, b) => a.symbol.localeCompare(b.symbol)),
  };
}

/**
 * A WATCH_STARTED, ENTRY_CANDIDATE or REFERENCE_OPEN event by itself is not
 * a virtual purchase. Plan only from the same position engine as the dashboard.
 */
async function planHoldingTransitions({ now, targetDate, bankBusinessDate, readActive,
                                        readOwnerPreferences, readPart }) {
  requireValid(isDate(targetDate), 'invalid target date');
  const empty = status => ({ status, target_date: targetDate, notices: [] });
  if (jst(now).slice(0, 10) !== targetDate) return empty('not_current_jst_day');
  const business = await bankBusinessDate(targetDate);
  if (business !== true) return empty(business === false ? 'bank_non_business_day' : 'bank_calendar_unavailable');

  const active = verifiedActive(await readActive());
  if (active.manifest.as_of !== targetDate || active.manifest.live !== true)
    return empty('current_live_publication_required');
  const owner = savedOwner(await readOwnerPreferences());
  const portfolio = await replayPublished(active, owner, readPart);
  if (!portfolio) return empty('virtual_model_not_current');
  const { result } = portfolio;

  const held = heldSymbols(active);
  const days = active.manifest.input_header.calendar;
  const priorMarketDate = days.at(-2);
  const watched = new Set(result.watches.filter(watch => watch.watch_status === 'TRIGGERED' &&
    watch.trigger_date === priorMarketDate && watch.candidate_date <= priorMarketDate)
    .map(watch => [watch.symbol, watch.candidate_date, watch.episode_id].join('|')));
  const filled = new Set(result.orders.filter(order => order.order_date === targetDate && order.status === 'FILLED')
    .map(order => [order.symbol, order.candidate_date, order.episode_id].join('|')));

  const notices = [];
  for (const [symbol, position] of Object.entries(result.open_positions)) {
    if (position.entry_date !== targetDate || Object.hasOwn(held, symbol)) continue;
    const key = [symbol, position.candidate_date, position.episode_id].join('|');
    requireValid(filled.has(key) && watched.has(key), 'new holding lacks a matching fill and prior watch');
    notices.push({
      event_id: hash(JSON.stringify(['NEW_A_HOLDING_TRANSITION_V1', owner.binding, key, targetDate])),
      kind: 'WATCH_TO_SIMULATED_HOLDING',
      symbol,
      candidate_date: position.candidate_date,
      simulated_entry_date: targetDate,
      title: '監視から仮想保有に移行',
      description: '保存した条件による仮想保有です。実際の取引は行われていません。',
      execution_status: 'SIMULATED_NOT_ACTUAL_TRADES',
    });
  }
  await checkSourcesUnchanged({ readActive, readOwnerPreferences }, active, owner);
  return {
    status: 'planned', target_date: targetDate,
    model_basis: portfolio.basis,
    basis: sourceBasis(active, owner),
    notices: notices.sort((a, b) => a.symbol.localeCompare(b.symbol)),
  };
}

module.exports = { MORNING_CRON, planEvaluationMorning, planHoldingTransitions };
