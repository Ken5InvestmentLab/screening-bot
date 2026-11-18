'use strict';

const { createHash } = require('node:crypto');
const { createDatasetRuntime } = require('../../weak-early-beta-gate/scripts/new-a-ui-source/engine/dataset-runtime.cjs');
const { verifiedActive, savedOwner, replayInputs, validateCalendar, sourceBasis,
  checkSourcesUnchanged } = require('./new-a-evaluation-morning.cjs');
const { OBSERVATION_SCHEMA, openingTimestamp, planOpeningEntries, evaluateOpeningEntries } = require('./new-a-opening-plan.cjs');

const SHA256 = /^[0-9a-f]{64}$/;
const CODE = /^[0-9A-Z]{4}$/;
const JST_MS = 9 * 60 * 60 * 1000;
const MAX_CALENDAR_BYTES = 256 * 1024;
const MAX_PROVIDER_BYTES = 512 * 1024;
const MAX_ROWS = 500;
const MAX_STORED_ROWS_BYTES = 96 * 1024;
const FIRST_TRADE = 'FIRST_REGULAR_TRADE_VERIFIED';
const POST_STATUSES = new Set(['AWAITING_FIRST_TRADE', 'FIRST_TRADE_VERIFIED', 'PROVISIONAL_ELIGIBLE',
  'PROVISIONAL_SKIPPED', 'PENDING_PORTFOLIO', 'RECONCILE']);
const HELD = new Set(['PORTFOLIO_UNVERIFIED', 'IDENTITY_UNVERIFIED', 'SIGNAL_PRICE_UNVERIFIED',
  'SOURCE_HELD', 'UPSTREAM_SOURCE_HELD', 'UPSTREAM_OPEN_UNCONFIRMED', 'PROVISIONAL_DAILY_FILL_CAP',
  'PROVISIONAL_CASH_INSUFFICIENT']);
const SKIPPED = new Set(['OUTSIDE_SCOPE', 'PRICE_CAP', 'DUPLICATE_HELD', 'CAPACITY',
  'OPEN_ABOVE_ALLOCATION_CEILING', 'OPEN_ABOVE_STARTING_CASH_CEILING']);

const episodeKey = row => [row.symbol, row.candidate_date, row.episode_id].join('|');
const hash = raw => createHash('sha256').update(raw).digest('hex');
const canStorePrice = price => typeof price === 'number' && price > 0 && price <= 1e9 && /^\d+(?:\.\d{1,2})?$/.test(String(price));

function requireValid(condition, message) {
  if (!condition) throw Error(message);
}

function verifiedBytes(receipt, limit, message) {
  if (typeof receipt?.raw !== 'string' && !Buffer.isBuffer(receipt?.raw)) throw Error(message);
  const raw = Buffer.isBuffer(receipt.raw) ? receipt.raw : Buffer.from(receipt.raw);
  requireValid(raw.length >= 2 && raw.length <= limit && typeof receipt.sha256 === 'string' &&
    SHA256.test(receipt.sha256) && hash(raw) === receipt.sha256, message);
  return new TextDecoder('utf-8', { fatal: true }).decode(raw);
}

function previousRows(previous, expectedRevision, target, basis, plan) {
  if (expectedRevision === 0) {
    requireValid(previous == null, 'unexpected previous opening observation');
    return new Map();
  }
  requireValid(previous?.revision === expectedRevision && previous.target_date === target &&
    previous.dataset_id === basis.dataset_id && previous.pointer_revision === basis.revision &&
    previous.manifest_sha256 === basis.manifest_sha256 && previous.preferences_revision === basis.preferences_revision &&
    typeof previous.source_receipt_sha256 === 'string' && SHA256.test(previous.source_receipt_sha256) &&
    Array.isArray(previous.rows), 'previous opening observation scope changed');
  const candidates = new Set(plan.orders.map(episodeKey));
  const rows = new Map();
  for (const row of previous.rows) {
    const key = episodeKey(row);
    const hasPrint = row.trade_at !== undefined || row.actual_price_yen !== undefined;
    requireValid(candidates.has(key) && !rows.has(key) && POST_STATUSES.has(row.status) &&
      (!hasPrint || openingTimestamp(row.trade_at) !== null &&
       canStorePrice(row.actual_price_yen)), 'previous opening observation row changed');
    rows.set(key, row);
  }
  requireValid(rows.size === candidates.size, 'previous opening observation missing candidates');
  return rows;
}

// A disputed price is unknown to the whole priority allocation, not just its row.
function evidenceForCalculation(row, prior) {
  if (prior?.status === 'RECONCILE' || row.status === 'RECONCILE') return { symbol: row.symbol, status: 'RECONCILE' };
  if (row.status !== FIRST_TRADE) return row;
  if (!canStorePrice(row.actual_price_yen) || prior?.trade_at !== undefined &&
      (openingTimestamp(prior.trade_at) !== openingTimestamp(row.trade_at) || prior.actual_price_yen !== row.actual_price_yen))
    return { symbol: row.symbol, status: 'RECONCILE' };
  return row;
}

function saveRow(output, evidence, prior) {
  const { symbol, candidate_date, episode_id } = output;
  const key = { symbol, candidate_date, episode_id };
  const trade = output.trade_at === undefined ? {} : {
    trade_at: output.trade_at, actual_price_yen: output.actual_price_yen,
  };

  if (prior?.status === 'RECONCILE' || evidence?.status === 'RECONCILE' ||
      evidence?.status === FIRST_TRADE && output.trade_at === undefined)
    return { ...key, status: 'RECONCILE' };

  if (output.status === 'OPEN_NOT_VERIFIED') return { ...key, status: 'AWAITING_FIRST_TRADE' };
  if (output.status === 'PROVISIONAL_PRICE_CONDITIONS_MET') return { ...key, status: 'PROVISIONAL_ELIGIBLE', ...trade };
  if (HELD.has(output.status)) return { ...key, status: 'PENDING_PORTFOLIO', ...trade };
  if (SKIPPED.has(output.status)) return { ...key, status: 'PROVISIONAL_SKIPPED', ...trade };
  throw Error('unexpected opening projection status');
}

// Only verified/injected readers are used. Caller must separately authorize
// the provider, keep its raw source receipts, and write through existing CAS.
async function prepareOpeningObservation({ now, targetDate, expectedRevision = 0, previousObservation = null,
  bankBusinessDate, readActive, readOwnerPreferences, readCalendar, readPart, readSecurityIdentities,
  readVerifiedProviderReceipt }) {
  requireValid(Number.isSafeInteger(now) && Number.isSafeInteger(expectedRevision) && expectedRevision >= 0 &&
    expectedRevision < Number.MAX_SAFE_INTEGER &&
    [bankBusinessDate, readActive, readOwnerPreferences, readCalendar, readPart, readSecurityIdentities,
      readVerifiedProviderReceipt].every(reader => typeof reader === 'function'), 'opening observation readers are incomplete');
  validateCalendar([targetDate]);
  const local = new Date(now + JST_MS).toISOString();
  const held = state => ({ state, final: false, target_date: targetDate, payload: null });
  if (local.slice(0, 10) !== targetDate || local.slice(11, 16) < '09:00') return held('outside_opening_session');
  const business = await bankBusinessDate(targetDate);
  if (business !== true) return held(business === false ? 'bank_non_business_day' : 'bank_calendar_unavailable');

  const priorPublication = await readActive();
  const active = verifiedActive(priorPublication);
  if (active.manifest.live !== true || priorPublication.publication.local_d1_emulation !== false ||
      active.manifest.as_of >= targetDate) return held('prior_live_publication_required');
  const calendarReceipt = await readCalendar();
  const calendar = validateCalendar(JSON.parse(verifiedBytes(calendarReceipt, MAX_CALENDAR_BYTES, 'opening calendar proof differs')));
  const cutoff = calendar.indexOf(active.manifest.as_of);
  const prefix = cutoff < 0 ? [] : calendar.slice(0, cutoff + 1);
  const published = validateCalendar(active.manifest.input_header.calendar);
  requireValid(prefix.length === published.length && prefix.every((date, i) => date === published[i]) &&
    active.manifest.input_header.limits?.nextPlannedSession === calendar[cutoff + 1],
  'published prior session or calendar prefix differs');
  if (calendar[cutoff + 1] !== targetDate) return held('not_next_market_session');

  const owner = savedOwner(await readOwnerPreferences());
  const { input, quotes } = await replayInputs(active, readPart);
  const basis = sourceBasis(active, owner);
  const symbols = input.intents.filter(row => row.trigger_date === active.manifest.as_of).map(row => row.symbol);
  requireValid(symbols.every(symbol => typeof symbol === 'string' && CODE.test(symbol)), 'invalid opening symbol projection');
  const securityIdentities = symbols.length ? await readSecurityIdentities({ targetDate, symbols: [...new Set(symbols)], basis }) : {};
  const portfolio = createDatasetRuntime(input, quotes).currentPortfolio(owner.preferences, active.manifest.as_of,
    { exitPolicy: owner.exitPolicy, trialPreset: owner.dashboardTrialPreset });
  const plan = planOpeningEntries({ input, quotes, portfolio, preferences: owner.preferences,
    trialPreset: owner.dashboardTrialPreset, asOf: active.manifest.as_of, nextSession: targetDate, securityIdentities });
  const previous = previousRows(previousObservation, expectedRevision, targetDate, basis, plan);
  const readback = () => checkSourcesUnchanged({ readActive, readOwnerPreferences }, active, owner);
  if (!plan.orders.length) {
    await readback();
    return held('no_opening_candidates');
  }
  if (plan.orders.length > MAX_ROWS) {
    await readback();
    return held('opening_candidate_limit_exceeded');
  }

  const receipt = await readVerifiedProviderReceipt({ targetDate, symbols: plan.orders.map(row => row.symbol), basis });
  if (!receipt) {
    await readback();
    return held('opening_receipt_unavailable');
  }
  const observation = JSON.parse(verifiedBytes(receipt, MAX_PROVIDER_BYTES, 'opening provider receipt differs'));
  requireValid(observation?.schema === OBSERVATION_SCHEMA && observation.target_date === targetDate &&
    Array.isArray(observation.rows) && observation.rows.every(row => row &&
      [FIRST_TRADE, 'AWAITING_FIRST_TRADE', 'RECONCILE'].includes(row.status)), 'invalid verified provider receipt');

  const previousBySymbol = new Map([...previous.values()].map(row => [row.symbol, row]));
  const checked = observation.rows.map(row => evidenceForCalculation(row, previousBySymbol.get(row.symbol)));
  const outcome = evaluateOpeningEntries(plan, { observation: { ...observation, rows: checked }, observedAt: now });
  const evidenceBySymbol = new Map(checked.map(row => [row.symbol, row]));
  const rows = outcome.orders.map(row => saveRow(row, evidenceBySymbol.get(row.symbol), previous.get(episodeKey(row))));
  await readback();

  // An incomplete refresh must not erase a prior verified opening price.
  // Provider corrections are represented as RECONCILE without an invented price.
  if (rows.some(row => previous.get(episodeKey(row))?.trade_at !== undefined &&
      row.trade_at === undefined && row.status !== 'RECONCILE')) return held('opening_receipt_incomplete');

  if (Buffer.byteLength(JSON.stringify(rows)) > MAX_STORED_ROWS_BYTES) return held('opening_rows_size_exceeded');

  return {
    state: 'prepared', final: false, target_date: targetDate,
    payload: { target_date: targetDate, dataset_id: basis.dataset_id, pointer_revision: basis.revision,
      manifest_sha256: basis.manifest_sha256, preferences_revision: basis.preferences_revision,
      expected_revision: expectedRevision, source_receipt_sha256: receipt.sha256, rows },
  };
}

module.exports = { prepareOpeningObservation };
