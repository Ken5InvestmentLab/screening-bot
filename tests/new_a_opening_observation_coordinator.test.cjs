'use strict';

const { createHash } = require('node:crypto');
const test = require('node:test');
const assert = require('node:assert/strict');
const { prepareOpeningObservation } = require('../scripts/windows/new-a-opening-observation.cjs');
const { OBSERVATION_SCHEMA } = require('../scripts/windows/new-a-opening-plan.cjs');

const priorDate = '2026-11-20';
const day = '2026-11-24';
const days = ['2026-11-19', priorDate, day, '2026-11-25'];
const now = Date.parse(day + 'T09:05:00+09:00');
const tradeAt = day + 'T09:00:05.123456789+09:00';
const observedAt = day + 'T09:02:00+09:00';
const source = 'a'.repeat(64);
const dataset = 'a-' + '9'.repeat(24);
const hash = raw => createHash('sha256').update(raw).digest('hex');
const proof = value => {
  const raw = JSON.stringify(value);
  return { raw, sha256: hash(raw) };
};
const firstPrint = (symbol, overrides = {}) => ({
  symbol, status: 'FIRST_REGULAR_TRADE_VERIFIED', exchange: 'XTKS', market: 'REGULAR', session: 'MORNING',
  first_trade_evidence: 'OFFICIAL_AM_OPEN', trade_at: tradeAt, observed_at: observedAt,
  actual_price_yen: 100, trade_size: 100, price_basis: 'ACTUAL_JPY', security_id: 'XTKS:' + symbol,
  source_id: 'TEST:AM-OPEN', source_sha256: 'b'.repeat(64), ...overrides,
});

function fixture(symbols = ['101A']) {
  const counts = { active: 0, prefs: 0, receipts: 0, identities: 0 };
  const intents = symbols.map((symbol, index) => ({ symbol, candidate_date: days[0], trigger_date: priorDate,
    episode_id: 1, priority_score: 100 - index }));
  const values = {
    episodes: intents,
    intents,
    watches: intents.map(row => ({ ...row, watch_status: 'TRIGGERED' })),
    quotes: symbols.flatMap(symbol => days.slice(0, 2).map(date => [symbol, date, [100, 102, 99, 100, 200, 100, 200, 1, true]])),
  };
  const parts = {};
  const descriptors = {};
  for (const [kind, rows] of Object.entries(values)) {
    const name = kind + '-000.json';
    const file = proof(rows);
    parts[name] = file.raw;
    descriptors[kind] = [{ name, bytes: Buffer.byteLength(file.raw), rows: rows.length, sha256: file.sha256 }];
  }
  const manifest = {
    schema: 'A_BROWSER_PRIVATE_INPUT_V1', strategy: 'A_BASE', audience: 'EXISTING_CLOUD_OWNER_ONLY',
    as_of: priorDate, live: true, source_version: source, daily_snapshot_sha256: 'b'.repeat(64),
    collections: { episodes: descriptors.episodes, intents: descriptors.intents, watches: descriptors.watches,
      presentation: [], current_daily: [] },
    quotes: descriptors.quotes,
    quote_fields: ['open', 'high', 'low', 'close', 'volume', 'actual_close', 'actual_volume', 'split_factor', 'source_usable'],
    expected_quote_keys: values.quotes.length,
    input_header: { calendar: days.slice(0, 2), source_version: source,
      limits: { completeThrough: priorDate, nextPlannedSession: day, identityUnverifiedBefore: {}, heldSymbols: {} } },
  };
  function active() {
    const { raw, sha256 } = proof(manifest);
    return {
      pointer: { status: 'READY', dataset_id: dataset, revision: 3, source_version: source, manifest_sha256: sha256 },
      manifestText: raw,
      publication: { schema: 'NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1', published: true, active_readback_verified: true,
        existing_owner_gate_verified: true, local_d1_emulation: false, dataset_id: dataset, revision: 3,
        manifest_sha256: sha256, source_version: source, snapshot_sha256: 'b'.repeat(64), as_of: priorDate },
    };
  }
  const preferences = {
    schema_version: 1, has_saved_finite_preferences: true, preference_source: 'new-a-saved', revision: 7,
    owner_binding_sha256: 'c'.repeat(64), view_preferences: null,
    preferences: { initial_cash_yen: 100_000, max_positions: 20, per_order_cap_yen: 50_000,
      base_shares: 100, cost_percent: 0, price_cap_yen: null, exit_endpoint: 'd6_open', year_scope: 'all', allocation: 'all' },
    exit_policy: { version: 'A_OPEN_EXIT_V2', first_d5_entry_session: '2026-11-17', legacy_endpoint: 'd6_open', new_endpoint: 'd5_open' },
  };
  let rows = symbols.map(symbol => firstPrint(symbol));
  const provider = () => proof({ schema: OBSERVATION_SCHEMA, target_date: day, rows });
  const options = {
    targetDate: day, now, bankBusinessDate: async d => (assert.equal(d, day), true),
    readActive: async () => (counts.active++, active()),
    readCalendar: async () => proof(days),
    readOwnerPreferences: async () => (counts.prefs++, structuredClone(preferences)),
    readPart: async (id, name) => (assert.equal(id, dataset), parts[name]),
    readSecurityIdentities: async ({ targetDate, symbols: selected, basis }) => {
      counts.identities++;
      assert.equal(targetDate, day);
      assert.equal(basis.preferences_revision, preferences.revision);
      return Object.fromEntries(selected.map(symbol => [symbol, 'XTKS:' + symbol]));
    },
    readVerifiedProviderReceipt: async ({ targetDate, symbols: selected, basis }) => {
      counts.receipts++;
      assert.equal(targetDate, day);
      assert.deepEqual(selected, symbols);
      assert.equal(basis.dataset_id, dataset);
      return provider();
    },
  };
  return { options, counts, active, manifest, preferences, provider, replace: value => { rows = value; } };
}

test('prepares the exact backend CAS shape from a verified prior live release and provider receipt', async () => {
  const f = fixture();
  const result = await prepareOpeningObservation(f.options);
  assert.equal(result.state, 'prepared');
  assert.equal(result.final, false);
  assert.deepEqual(result.payload, {
    target_date: day, dataset_id: dataset, pointer_revision: 3, manifest_sha256: f.active().pointer.manifest_sha256,
    preferences_revision: 7, expected_revision: 0, source_receipt_sha256: f.provider().sha256,
    rows: [{ symbol: '101A', candidate_date: days[0], episode_id: 1, status: 'PROVISIONAL_ELIGIBLE',
      trade_at: tradeAt, actual_price_yen: 100 }],
  });
  assert.deepEqual(f.counts, { active: 2, prefs: 2, identities: 1, receipts: 1 });
});

test('a missing first trade and uncertain preceding allocation stay pending while an observed hard ceiling is skipped', async () => {
  const f = fixture(['101A', '102A', '103A', '104A']);
  f.replace([{ symbol: '101A', status: 'AWAITING_FIRST_TRADE' }, firstPrint('102A'),
    firstPrint('103A', { actual_price_yen: 501 }), firstPrint('104A', { security_id: 'XTKS:OTHER' })]);
  const { payload } = await prepareOpeningObservation(f.options);
  assert.deepEqual(payload.rows.map(row => [row.status, Object.hasOwn(row, 'trade_at')]), [
    ['AWAITING_FIRST_TRADE', false], ['PENDING_PORTFOLIO', true], ['PROVISIONAL_SKIPPED', true], ['RECONCILE', false],
  ]);
});

test('malformed verified prints and prices unsupported by canonical storage are marked for reconciliation', async () => {
  const f = fixture(['101A', '102A', '103A', '104A']);
  f.replace([firstPrint('101A', { trade_at: day + 'T12:30:00+09:00' }),
    firstPrint('102A', { actual_price_yen: 100.123 }), { symbol: '103A', status: 'RECONCILE' }, firstPrint('104A')]);
  assert.deepEqual((await prepareOpeningObservation(f.options)).payload.rows.map(row => row.status),
    ['RECONCILE', 'RECONCILE', 'RECONCILE', 'PENDING_PORTFOLIO']);
});

test('cross-day, bank-holiday, stale publication, or empty candidate input do not call the provider reader', async () => {
  const f = fixture();
  const early = await prepareOpeningObservation({ ...f.options, now: Date.parse(day + 'T08:59:00+09:00') });
  assert.equal(early.state, 'outside_opening_session');
  assert.equal((await prepareOpeningObservation({ ...f.options, bankBusinessDate: async () => false })).state, 'bank_non_business_day');
  f.manifest.live = false;
  assert.equal((await prepareOpeningObservation(f.options)).state, 'prior_live_publication_required');
  assert.equal(f.counts.receipts, 0);
  const none = fixture([]);
  assert.equal((await prepareOpeningObservation(none.options)).state, 'no_opening_candidates');
  assert.equal(none.counts.receipts, 0);
});

test('calendar prefix, receipt bytes, duplicate observations and changed active/preferences fail closed', async () => {
  const f = fixture();
  await assert.rejects(prepareOpeningObservation({ ...f.options, readCalendar: async () => proof([priorDate, day]) }), /calendar prefix/);
  await assert.rejects(prepareOpeningObservation({ ...f.options,
    readVerifiedProviderReceipt: async () => ({ ...f.provider(), sha256: source }) }), /provider receipt differs/);
  f.replace([firstPrint('101A'), firstPrint('101A')]);
  await assert.rejects(prepareOpeningObservation(f.options), /ambiguous opening observation/);
  f.replace([firstPrint('101A')]);
  await assert.rejects(prepareOpeningObservation({ ...f.options, readVerifiedProviderReceipt: async () => {
    f.preferences.revision++;
    return f.provider();
  } }), /saved owner settings changed/);
  await assert.rejects(prepareOpeningObservation({ ...f.options, readVerifiedProviderReceipt: async () => {
    f.manifest.daily_snapshot_sha256 = source;
    return f.provider();
  } }), /publication is not verified/);
});

test('refresh cannot erase prior first price and checked corrections require reconciliation without mutating it', async () => {
  const f = fixture();
  const initial = (await prepareOpeningObservation(f.options)).payload;
  const { rows, ...basis } = initial;
  const existing = { ...basis, rows, revision: 1 };
  const options = { ...f.options, expectedRevision: 1, previousObservation: existing };
  const original = JSON.stringify(existing);
  const unchanged = await prepareOpeningObservation(options);
  assert.equal(unchanged.payload.expected_revision, 1);
  assert.deepEqual(unchanged.payload.rows, rows);
  f.replace([]);
  assert.equal((await prepareOpeningObservation(options)).state, 'opening_receipt_incomplete');
  f.replace([firstPrint('101A', { actual_price_yen: 101 })]);
  const correction = (await prepareOpeningObservation(options)).payload;
  assert.deepEqual(correction.rows, [{ symbol: '101A', candidate_date: days[0], episode_id: 1, status: 'RECONCILE' }]);
  assert.equal(JSON.stringify(existing), original);
  f.replace([firstPrint('101A', { trade_at: day + 'T00:00:05.123456789Z' })]);
  assert.equal((await prepareOpeningObservation(options)).payload.rows[0].status, 'PROVISIONAL_ELIGIBLE');
  f.replace([firstPrint('101A', { trade_at: day + 'T09:00:05.123456790+09:00' })]);
  assert.equal((await prepareOpeningObservation(options)).payload.rows[0].status, 'RECONCILE');
  await assert.rejects(prepareOpeningObservation({ ...options, expectedRevision: 2 }), /previous opening observation scope changed/);
});

test('the real storage writer accepts the prepared receipt and rejects reusing its old revision', async t => {
  const fs = require('node:fs');
  const path = require('node:path');
  const { DatabaseSync } = require('node:sqlite');
  const { modules } = require('./helpers/cloud-worker-modules.cjs');
  const f = fixture();
  const sqlite = new DatabaseSync(':memory:');
  t.after(() => sqlite.close());
  for (const name of ['new-a-private.sql', 'new-a-opening-observation.sql'])
    sqlite.exec(fs.readFileSync(path.join(__dirname, '../weak-early-beta-gate/schema', name), 'utf8'));
  const active = f.active();
  const member = 'cloud_' + f.preferences.owner_binding_sha256;
  sqlite.prepare('INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?)')
    .run(dataset, source, active.manifestText, active.pointer.manifest_sha256, 'READY', tradeAt);
  sqlite.prepare("INSERT INTO new_a_active_pointer VALUES ('owner',?,?,?)").run(dataset, active.pointer.revision, tradeAt);
  sqlite.prepare('INSERT INTO new_a_finite_trial_preferences VALUES (?,1,?,?,?)')
    .run(member, JSON.stringify(f.preferences.preferences), f.preferences.revision, tradeAt);
  const db = { prepare(sql) {
    const stmt = sqlite.prepare(sql);
    return { bind(...values) { return { first: async () => stmt.get(...values) ?? null }; } };
  } };
  const { load } = modules({ clock: { now } });
  const store = load('./new-a-opening-observation');
  const prepared = await prepareOpeningObservation(f.options);
  const saved = await store.saveOpeningObservation(db, member, prepared.payload, now);
  assert.equal(saved.revision, 1);
  assert.equal(await store.saveOpeningObservation(db, member, prepared.payload, now), null);
  const display = await store.readOpeningObservation(db, member, now);
  assert.equal(display.state, 'ready');
  assert.equal(display.rows[0].trade_at, tradeAt);
  assert.equal(Object.hasOwn(display.rows[0], 'episode_id'), false);
});
