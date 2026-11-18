'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { createDatasetRuntime } = require('../weak-early-beta-gate/scripts/new-a-ui-source/engine/dataset-runtime.cjs');
const { savedOwner } = require('../scripts/windows/new-a-evaluation-morning.cjs');
const { planOpeningEntries, evaluateOpeningEntries, OBSERVATION_SCHEMA } = require('../scripts/windows/new-a-opening-plan.cjs');

const asOf = '2026-11-20';
const next = '2026-11-24';
const calendar = ['2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19', asOf];
const source = 'a'.repeat(64);
const openAt = next + 'T09:00:05+09:00';
const readAt = next + 'T09:01:00+09:00';
const now = next + 'T09:02:00+09:00';

function quote(open) {
  return { open, high: open + 1, low: open - 1, close: open, actual_close: open,
    volume: 1_000, actual_volume: 1_000, source_usable: true };
}

const candidate = (symbol, priority_score, candidate_date = calendar[0], trigger_date = asOf) =>
  ({ symbol, priority_score, candidate_date, trigger_date, episode_id: 1 });

function fixture(intents, { preferences = {}, trialPreset = null, bars = {}, limits = {}, identities = true } = {}) {
  const prefs = { initial_cash_yen: 100_000, max_positions: 10, per_order_cap_yen: 80_000,
    base_shares: 100, cost_percent: 1, price_cap_yen: null, exit_endpoint: 'd5_close',
    year_scope: 'all', allocation: 'all', ...preferences };
  const input = { calendar, source_version: source, episodes: intents,
    watches: intents.map(row => ({ ...row, watch_status: 'TRIGGERED' })), intents,
    limits: { identityUnverifiedBefore: {}, heldSymbols: {}, completeThrough: asOf, nextPlannedSession: next, ...limits } };
  const quotes = { get(symbol, day) {
    assert(day <= asOf, 'no tomorrow quote before open');
    return Object.hasOwn(bars, symbol + '|' + day) ? bars[symbol + '|' + day] : quote(100);
  } };
  const portfolio = createDatasetRuntime(input, quotes).currentPortfolio(prefs, asOf, { trialPreset });
  const securityIdentities = identities ? Object.fromEntries(intents.map(row => [row.symbol, 'XTKS:' + row.symbol])) : {};
  const options = { input, quotes, portfolio, preferences: prefs, trialPreset, asOf, nextSession: next, securityIdentities };
  const plan = () => planOpeningEntries(options);
  function final(barsAtOpen) {
    const completed = { ...input, calendar: [...calendar, next] };
    const quotesWithResult = { get(symbol, day) {
      return day === next ? barsAtOpen[symbol] ?? null : quotes.get(symbol, day);
    } };
    return createDatasetRuntime(completed, quotesWithResult).simulate(prefs, { trialPreset });
  }
  return { plan, options, final };
}

function print(symbol, actual_price_yen, override = {}) {
  return { symbol, actual_price_yen, status: 'FIRST_REGULAR_TRADE_VERIFIED', exchange: 'XTKS', market: 'REGULAR',
    session: 'MORNING', price_basis: 'ACTUAL_JPY', first_trade_evidence: 'OFFICIAL_AM_OPEN',
    trade_at: openAt, observed_at: readAt, trade_size: 100, security_id: 'XTKS:' + symbol,
    source_id: 'TEST:official-am-open', source_sha256: 'b'.repeat(64), ...override };
}

function opening(plan, rows, extra = {}) {
  return evaluateOpeningEntries(plan, { observedAt: now, observation: { schema: OBSERVATION_SCHEMA, target_date: next, rows }, ...extra });
}

test('evening orders follow exact model priority and fee-inclusive limits without reading a future quote', () => {
  const { plan } = fixture([candidate('103A', 900, calendar[1]), candidate('102A', 300),
    candidate('101A', 300)], { preferences: { initial_cash_yen: 70_000, max_positions: 2, cost_percent: 5 } });
  const snapshot = plan();
  assert.equal(snapshot.target_date, next);
  assert.equal(snapshot.opening_cash_yen, 70_000);
  assert.deepEqual(snapshot.orders.map(({ symbol, status }) => [symbol, status]),
    [['101A', 'AWAITING_OPEN'], ['102A', 'AWAITING_OPEN'], ['103A', 'CAPACITY']]);
  const [first, second] = snapshot.orders;
  assert.equal(first.allocation_ceiling_yen, 800);
  assert.equal(first.cash_ceiling_yen, 70_000 / 105);
  assert.equal(first.conditional_ceiling_yen, 70_000 / 105);
  assert.equal(first.prior_orders_can_reduce_cash, false);
  assert.equal(second.prior_orders_can_reduce_cash, true);
});

test('watch-start close cap and identity floor are distinct from a next-session open ceiling', () => {
  const { plan } = fixture([candidate('101A', 3), candidate('102A', 2), candidate('103A', 1)], {
    preferences: { price_cap_yen: 110 },
    bars: { ['101A|' + calendar[0]]: quote(120), ['102A|' + calendar[0]]: null },
    limits: { identityUnverifiedBefore: { '103A': calendar[1] } },
  });
  assert.deepEqual(plan().orders.map(o => o.status), ['PRICE_CAP', 'SIGNAL_PRICE_UNVERIFIED', 'IDENTITY_UNVERIFIED']);
});

test('positions scheduled to sell on the same session still use capacity and their cash is unavailable', () => {
  const existing = candidate('100A', 4, calendar[0], calendar[0]);
  const candidates = [existing, candidate('101A', 2), candidate('102A', 1)];
  const oneSlot = fixture(candidates, { preferences: { max_positions: 1 } });
  const snapshot = oneSlot.plan();
  assert.equal(snapshot.opening_cash_yen, 89_900);
  assert.equal(snapshot.opening_free_positions, 0);
  assert(snapshot.orders.every(o => o.status === 'CAPACITY'));
  const seen = opening(snapshot, [print('101A', 200)]).orders[0];
  assert.equal(seen.status, 'CAPACITY');
  assert.equal(seen.actual_price_yen, 200);
  assert.equal(seen.trade_at, openAt);
  const result = oneSlot.final({ '100A': quote(1_000), '101A': quote(200), '102A': quote(300) });
  assert.equal(result.trades[0].exit_date, next);
  assert.deepEqual(result.orders.filter(o => o.order_date === next).map(o => o.status), ['CAPACITY', 'CAPACITY']);

  const unusedCash = fixture([existing, candidate('101A', 2)], { preferences: { max_positions: 2,
    initial_cash_yen: 40_000 } });
  assert.equal(unusedCash.plan().opening_cash_yen, 29_900);
  assert.equal(opening(unusedCash.plan(), [print('101A', 300)]).orders[0].status, 'OPEN_ABOVE_STARTING_CASH_CEILING');
  const nextResult = unusedCash.final({ '100A': quote(1_000), '101A': quote(300) });
  assert.equal(nextResult.orders.find(o => o.order_date === next).status, 'CASH_INSUFFICIENT');
});

test('same verified first prices produce only provisional allocation/fee conclusions in replay priority order', () => {
  const entries = [candidate('101A', 4), candidate('102A', 3), candidate('103A', 2), candidate('104A', 1)];
  const { plan, final } = fixture(entries);
  const current = opening(plan(), [print('104A', 200), print('101A', 250), print('103A', 600), print('102A', 850)]);
  assert.equal(current.final, false);
  assert.deepEqual(current.orders.map(o => o.status), ['PROVISIONAL_PRICE_CONDITIONS_MET', 'OPEN_ABOVE_ALLOCATION_CEILING',
    'PROVISIONAL_PRICE_CONDITIONS_MET', 'PROVISIONAL_CASH_INSUFFICIENT']);
  assert.equal(current.orders[0].estimated_cost_yen, 25_250);
  assert.deepEqual(final({ '101A': quote(250), '102A': quote(850), '103A': quote(600), '104A': quote(200) })
    .orders.filter(o => o.order_date === next).map(o => o.status), ['FILLED', 'LOT_EXCEEDS_ALLOCATION', 'FILLED', 'CASH_INSUFFICIENT']);
  const row = quote(250);
  const onePrice = final({ '101A': { ...row, high: row.open, low: row.open }, '102A': quote(850), '103A': quote(600), '104A': quote(200) });
  assert.equal(onePrice.orders[0].status, 'UNFILLED_UNCERTAIN_ONE_PRICE');
  assert.equal(current.orders[0].status, 'PROVISIONAL_PRICE_CONDITIONS_MET');
  assert.equal(onePrice.orders.at(-1).status, 'CASH_INSUFFICIENT'); // The engine reserved cash for earlier unfilled orders.
});

test('a missing higher-ranked print cannot silently free its reservation; observation gating remains per symbol', () => {
  const { plan } = fixture([candidate('101A', 3), candidate('102A', 2), candidate('103A', 1)]);
  const current = opening(plan(), [print('102A', 200), print('103A', 850)]);
  assert.deepEqual(current.orders.map(o => o.status),
    ['OPEN_NOT_VERIFIED', 'UPSTREAM_OPEN_UNCONFIRMED', 'OPEN_ABOVE_ALLOCATION_CEILING']);

  for (const bad of [{ session: 'AFTERNOON' }, { exchange: 'PTS' }, { market: 'TOSNET' },
    { trade_at: next + 'T08:59:59+09:00' }, { trade_at: next + 'T12:30:00+09:00' },
    { trade_at: asOf + 'T09:00:00+09:00' }, { observed_at: next + 'T09:20:00+09:00' },
    { observed_at: next + 'T09:00:00+09:00' }, { trade_size: 0 }, { first_trade_evidence: 'FIRST_SEEN' },
    { price_basis: 'ADJUSTED_JPY' }, { security_id: 'XTKS:DIFFERENT' }, { source_sha256: 'unknown' }]) {
    const { orders } = opening(plan(), [print('101A', 100, bad)]);
    assert.equal(orders[0].status, 'OPEN_NOT_VERIFIED');
  }
  assert.throws(() => opening(plan(), [print('101A', 100), print('101A', 100)]), /ambiguous opening observation/);
  const noIdentity = fixture([candidate('101A', 1)], { identities: false });
  assert.equal(opening(noIdentity.plan(), [print('101A', 100)]).orders[0].status, 'OPEN_NOT_VERIFIED');
});

test('lot and fee boundaries, source holds and unavailable current model do not produce fills', () => {
  const exact = fixture([candidate('101A', 2)], { preferences: { per_order_cap_yen: 20_000, initial_cash_yen: 21_000, cost_percent: 5 } });
  const snapshot = exact.plan();
  assert.equal(snapshot.orders[0].conditional_ceiling_yen, 200);
  assert.equal(opening(snapshot, [print('101A', 200)]).orders[0].status, 'PROVISIONAL_PRICE_CONDITIONS_MET');
  assert.equal(opening(snapshot, [print('101A', 200.01)]).orders[0].status, 'OPEN_ABOVE_ALLOCATION_CEILING');
  const held = fixture([candidate('101A', 2), candidate('102A', 1)], { limits: { heldSymbols: { '101A': {} } } });
  assert.deepEqual(held.plan().orders.map(o => o.status), ['SOURCE_HELD', 'UPSTREAM_SOURCE_HELD']);
  const { options } = exact;
  const unavailable = planOpeningEntries({ ...options, portfolio: null });
  assert.equal(unavailable.state, 'held');
  assert.equal(opening(unavailable, [print('101A', 100)]).orders[0].status, 'PORTFOLIO_UNVERIFIED');
  const forged = { ...snapshot, orders: [{ ...snapshot.orders[0], status: 'FILLED' }] };
  assert.throws(() => opening(forged, [print('101A', 100)]), /opening plan row differs/);
  assert.throws(() => planOpeningEntries({ ...options, nextSession: '2026-11-23' }), /unverified prior-close/);
});

test('dashboard presets preserve daily caps without changing custom or legacy reminder semantics', () => {
  const entries = [candidate('101A', 4), candidate('102A', 3), candidate('103A', 2), candidate('104A', 1)];
  const samePrices = Object.fromEntries(entries.map(({ symbol }) => [symbol, quote(100)]));
  for (const [preset, cap] of [[null, null], ['balanced', null], ['defensive', 3], ['profit', 3]]) {
    const { plan, final } = fixture(entries, { trialPreset: preset });
    assert.equal(plan().daily_fill_cap, cap);
    const output = opening(plan(), entries.map(({ symbol }) => print(symbol, 100)));
    const expected = cap ? 'PROVISIONAL_DAILY_FILL_CAP' : 'PROVISIONAL_PRICE_CONDITIONS_MET';
    assert.equal(output.orders.at(-1).status, expected);
    assert.equal(final(samePrices).orders.at(-1).status, cap ? 'DAILY_FILLED_CAP' : 'FILLED');
  }
  const { options } = fixture([]);
  const owner = { schema_version: 1, has_saved_finite_preferences: true, preference_source: 'new-a-saved',
    revision: 4, owner_binding_sha256: source, preferences: options.preferences,
    exit_policy: { version: 'A_OPEN_EXIT_V2', first_d5_entry_session: '2026-11-17', legacy_endpoint: 'd6_open', new_endpoint: 'd5_open' } };
  assert.equal(savedOwner(owner).dashboardTrialPreset, 'balanced');
  assert.equal(savedOwner({ ...owner, view_preferences: null }).dashboardTrialPreset, 'balanced');
  assert.equal(savedOwner({ ...owner, view_preferences: { trial_preset: null } }).dashboardTrialPreset, null);
  assert.equal(savedOwner({ ...owner, view_preferences: { trial_preset: 'profit' } }).dashboardTrialPreset, 'profit');
});
