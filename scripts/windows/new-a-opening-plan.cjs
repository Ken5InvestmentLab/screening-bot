'use strict';

const {
  compare, valid, validatePreferences, trialTerms,
} = require('../../weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs');

const PLAN_SCHEMA = 'NEW_A_OPENING_PLAN_V1';
const OBSERVATION_SCHEMA = 'NEW_A_FIRST_REGULAR_TRADE_OBSERVATION_V1';
const OUTCOME_SCHEMA = 'NEW_A_OPENING_PROVISIONAL_V1';
const FIRST_TRADE = 'FIRST_REGULAR_TRADE_VERIFIED';
const ORDER_STATES = new Set([
  'AWAITING_OPEN', 'PORTFOLIO_UNVERIFIED', 'OUTSIDE_SCOPE', 'IDENTITY_UNVERIFIED', 'SIGNAL_PRICE_UNVERIFIED',
  'PRICE_CAP', 'DUPLICATE_HELD', 'CAPACITY', 'SOURCE_HELD', 'UPSTREAM_SOURCE_HELD',
]);
const EPS = 1e-7;
const JST_MS = 9 * 60 * 60 * 1000;
const SYMBOL = /^[0-9A-Z]{4}$/;
const SECURITY_ID = /^[a-zA-Z0-9:_-]{1,120}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const INSTANT = /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.(\d{1,9}))?(?:Z|\+09:00)$/;
const OPEN_EVIDENCE = new Set(['VENUE_OPEN_MARKER', 'OFFICIAL_AM_OPEN', 'GAP_FREE_REGULAR_STREAM']);

function requireValid(condition, message) {
  if (!condition) throw Error(message);
}

function isDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const ms = Date.parse(value + 'T00:00:00Z');
  return Number.isFinite(ms) && new Date(ms).toISOString().slice(0, 10) === value;
}

function instant(value) {
  return typeof value === 'string' && INSTANT.test(value) && isDate(value.slice(0, 10)) ? Date.parse(value) : NaN;
}

function openingTimestamp(value) {
  const ms = instant(value);
  if (!Number.isFinite(ms)) return null;
  const fraction = INSTANT.exec(value)[1] ?? '';
  return BigInt(ms) * 1_000_000n + BigInt(fraction.padEnd(9, '0').slice(3));
}

const jst = ms => new Date(ms + JST_MS).toISOString();
const key = row => [row.symbol, row.candidate_date, row.episode_id].join('|');
const openingCeiling = (cash, shares, fee) => Math.max(0, cash) / (shares * fee);

// Caller supplies the receipt-verified bundle and exact dashboard-equivalent
// portfolio replay. This step never asks for a quote from the next session.
function planOpeningEntries({ input, quotes, portfolio, preferences, trialPreset = null,
                              asOf, nextSession, securityIdentities = {} }) {
  const prefs = validatePreferences(preferences);
  const trial = trialTerms(trialPreset);
  requireValid(isDate(asOf) && isDate(nextSession) && nextSession > asOf &&
    input?.calendar?.at(-1) === asOf && input.limits?.completeThrough === asOf &&
    input.limits.nextPlannedSession === nextSession && SHA256.test(input.source_version) &&
    Array.isArray(input.intents) && Array.isArray(input.watches) && typeof quotes?.get === 'function',
  'unverified prior-close or next market session');
  requireValid(securityIdentities && typeof securityIdentities === 'object' && !Array.isArray(securityIdentities),
    'invalid security identity projection');

  const candidates = input.intents.filter(intent => intent.trigger_date === asOf);
  const sessions = new Set(input.calendar);
  const triggered = new Set(input.watches.filter(watch => watch.watch_status === 'TRIGGERED' &&
    watch.trigger_date === asOf).map(key));
  const seen = new Set();
  for (const entry of candidates) {
    requireValid(typeof entry.symbol === 'string' && SYMBOL.test(entry.symbol) && sessions.has(entry.candidate_date) &&
      entry.candidate_date <= asOf && Number.isSafeInteger(entry.episode_id) && entry.episode_id > 0 &&
      Number.isFinite(entry.priority_score) && triggered.has(key(entry)) && !seen.has(entry.symbol),
    'opening candidate identity differs');
    seen.add(entry.symbol);
  }
  candidates.sort(compare);

  const result = portfolio?.result;
  const closing = result?.daily?.at(-1);
  const knownModel = ['SAVED_SCOPE', 'LATEST_YEAR_STANDALONE'].includes(portfolio?.basis) &&
    result?.resolved === true && result.period?.[1] === asOf && sessions.has(result.period?.[0]) &&
    (result.trial_policy?.id ?? null) === trialPreset && closing?.date === asOf &&
    Number.isFinite(closing.cash) && closing.cash >= -1e-6 &&
    result.open_positions && typeof result.open_positions === 'object' && !Array.isArray(result.open_positions);
  const free = knownModel ? prefs.max_positions - Object.keys(result.open_positions).length : null;
  requireValid(free === null || free >= 0, 'opening capacity differs from saved model');

  const fee = 1 + prefs.cost_percent / 100;
  const allocationCeiling = prefs.per_order_cap_yen / prefs.base_shares;
  const cashCeiling = knownModel ? openingCeiling(closing.cash, prefs.base_shares, fee) : null;
  let admitted = 0, heldAdmission = false;
  const orders = candidates.map(entry => {
    const { symbol, candidate_date, episode_id, priority_score } = entry;
    const identity = Object.hasOwn(securityIdentities, symbol) ? securityIdentities[symbol] : null;
    requireValid(identity === null || typeof identity === 'string' && SECURITY_ID.test(identity),
      'invalid expected security identity');
    const row = { symbol, candidate_date, episode_id, priority_score, security_id: identity };

    if (!knownModel) return { ...row, status: 'PORTFOLIO_UNVERIFIED' };
    if (candidate_date < result.period[0] || prefs.year_scope !== 'all' && !candidate_date.startsWith(prefs.year_scope))
      return { ...row, status: 'OUTSIDE_SCOPE' };
    const identityFloor = input.limits.identityUnverifiedBefore?.[symbol];
    if (identityFloor && candidate_date < identityFloor) return { ...row, status: 'IDENTITY_UNVERIFIED' };
    if (prefs.price_cap_yen !== null) {
      const signal = quotes.get(symbol, candidate_date);
      if (!valid(signal)) return { ...row, status: 'SIGNAL_PRICE_UNVERIFIED' };
      if (signal.actual_close > prefs.price_cap_yen) return { ...row, status: 'PRICE_CAP' };
    }
    if (Object.hasOwn(result.open_positions, symbol)) return { ...row, status: 'DUPLICATE_HELD' };
    if (admitted >= free) return { ...row, status: 'CAPACITY' };

    // A quarantined source must not silently free its place for a lower rank.
    if (Object.hasOwn(input.limits.heldSymbols ?? {}, symbol)) {
      heldAdmission = true;
      return { ...row, status: 'SOURCE_HELD' };
    }
    if (heldAdmission) return { ...row, status: 'UPSTREAM_SOURCE_HELD' };
    const admissionRank = ++admitted;
    return { ...row, status: 'AWAITING_OPEN', admission_rank: admissionRank,
      allocation_ceiling_yen: allocationCeiling, cash_ceiling_yen: cashCeiling,
      conditional_ceiling_yen: Math.min(allocationCeiling, cashCeiling),
      prior_orders_can_reduce_cash: admissionRank > 1 };
  });

  return {
    schema: PLAN_SCHEMA, source_version: input.source_version, as_of: asOf, target_date: nextSession,
    state: candidates.length && !knownModel ? 'held' : 'planned',
    model_basis: knownModel ? portfolio.basis : null, trial_preset: trialPreset,
    opening_cash_yen: knownModel ? closing.cash : null, opening_free_positions: free,
    base_shares: prefs.base_shares, per_order_cap_yen: prefs.per_order_cap_yen, cost_percent: prefs.cost_percent,
    daily_fill_cap: trial?.daily_fill_cap ?? null, orders,
  };
}

function verifiedPrint(row, order, target, now) {
  if (row?.status !== FIRST_TRADE || row.exchange !== 'XTKS' || row.market !== 'REGULAR' ||
      row.session !== 'MORNING' || !OPEN_EVIDENCE.has(row.first_trade_evidence) ||
      row.price_basis !== 'ACTUAL_JPY' || !order.security_id || row.security_id !== order.security_id ||
      typeof row.source_id !== 'string' || !SECURITY_ID.test(row.source_id) ||
      typeof row.source_sha256 !== 'string' || !SHA256.test(row.source_sha256) ||
      !Number.isFinite(row.actual_price_yen) || row.actual_price_yen <= 0 ||
      !Number.isSafeInteger(row.trade_size) || row.trade_size <= 0) return null;
  const tradedAt = openingTimestamp(row.trade_at), receivedAt = openingTimestamp(row.observed_at);
  if (tradedAt === null || receivedAt === null || tradedAt > receivedAt || receivedAt > BigInt(now) * 1_000_000n) return null;
  if (tradedAt < openingTimestamp(target + 'T09:00:00+09:00') ||
      tradedAt > openingTimestamp(target + 'T11:30:00+09:00')) return null;
  return { actual_price_yen: row.actual_price_yen, trade_at: row.trade_at, observed_at: row.observed_at,
    source_id: row.source_id, source_sha256: row.source_sha256 };
}

// Earliest prices are projections of conditions only. The existing engine
// still requires completed session OHLCV and owns all simulated fill decisions.
function evaluateOpeningEntries(plan, { observation, observedAt }) {
  const now = typeof observedAt === 'number' ? observedAt : instant(observedAt);
  requireValid(plan?.schema === PLAN_SCHEMA && ['held', 'planned'].includes(plan.state) &&
    isDate(plan.as_of) && isDate(plan.target_date) && plan.as_of < plan.target_date &&
    typeof plan.source_version === 'string' && SHA256.test(plan.source_version) &&
    Number.isSafeInteger(plan.base_shares) && plan.base_shares > 0 && plan.base_shares % 100 === 0 &&
    Number.isSafeInteger(plan.per_order_cap_yen) && plan.per_order_cap_yen > 0 &&
    Number.isFinite(plan.cost_percent) && plan.cost_percent >= 0 && plan.cost_percent <= 10 &&
    (plan.daily_fill_cap === null || Number.isSafeInteger(plan.daily_fill_cap) && plan.daily_fill_cap > 0) &&
    Array.isArray(plan.orders) &&
    observation?.schema === OBSERVATION_SCHEMA && observation.target_date === plan.target_date &&
    Array.isArray(observation.rows) && Number.isSafeInteger(now) && jst(now).slice(0, 10) === plan.target_date,
  'invalid opening observation scope');
  const candidates = new Set();
  for (const order of plan.orders) {
    requireValid(typeof order.symbol === 'string' && SYMBOL.test(order.symbol) &&
      isDate(order.candidate_date) && order.candidate_date <= plan.as_of &&
      Number.isSafeInteger(order.episode_id) && order.episode_id > 0 && ORDER_STATES.has(order.status) &&
      !candidates.has(order.symbol), 'opening plan row differs');
    if (order.status === 'AWAITING_OPEN') {
      requireValid(plan.state === 'planned' && Number.isFinite(plan.opening_cash_yen) &&
        plan.opening_cash_yen >= -1e-6, 'opening cash is unverified');
    }
    candidates.add(order.symbol);
  }
  const observed = new Map();
  for (const row of observation.rows) {
    requireValid(candidates.has(row?.symbol) && !observed.has(row.symbol), 'ambiguous opening observation');
    observed.set(row.symbol, row);
  }

  let budget = plan.opening_cash_yen, conditionalFills = 0, upstreamUnknown = false;
  const fee = 1 + plan.cost_percent / 100;
  const orders = plan.orders.map(order => {
    const base = { symbol: order.symbol, candidate_date: order.candidate_date, episode_id: order.episode_id };
    const print = order.status === 'IDENTITY_UNVERIFIED' ? null :
      verifiedPrint(observed.get(order.symbol), order, plan.target_date, now);
    if (order.status !== 'AWAITING_OPEN') return { ...base, ...print, status: order.status };
    if (!print) {
      upstreamUnknown = true;
      return { ...base, status: 'OPEN_NOT_VERIFIED' };
    }
    const row = { ...base, ...print };
    const allocation = plan.base_shares * print.actual_price_yen;
    const cost = allocation * fee;
    if (allocation > plan.per_order_cap_yen + EPS)
      return { ...row, status: 'OPEN_ABOVE_ALLOCATION_CEILING' };
    if (cost > plan.opening_cash_yen + EPS)
      return { ...row, status: 'OPEN_ABOVE_STARTING_CASH_CEILING' };
    if (upstreamUnknown) return { ...row, status: 'UPSTREAM_OPEN_UNCONFIRMED' };
    if (plan.daily_fill_cap !== null && conditionalFills >= plan.daily_fill_cap)
      return { ...row, status: 'PROVISIONAL_DAILY_FILL_CAP' };
    if (cost > budget + EPS) return { ...row, status: 'PROVISIONAL_CASH_INSUFFICIENT' };

    // This is a conditional reservation, exactly in engine order. Actual
    // daily-bar admissibility (including one-price handling) remains unknown.
    budget -= cost;
    conditionalFills++;
    return { ...row, status: 'PROVISIONAL_PRICE_CONDITIONS_MET', estimated_cost_yen: cost };
  });
  return { schema: OUTCOME_SCHEMA, state: 'provisional', final: false, target_date: plan.target_date,
    source_version: plan.source_version, execution_status: 'SIMULATED_NOT_ACTUAL_TRADES', orders };
}

module.exports = { PLAN_SCHEMA, OBSERVATION_SCHEMA, OUTCOME_SCHEMA, openingTimestamp, planOpeningEntries, evaluateOpeningEntries };
