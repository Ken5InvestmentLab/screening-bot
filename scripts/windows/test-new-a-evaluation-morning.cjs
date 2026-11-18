'use strict';

const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const test = require('node:test');
const { MORNING_CRON, planEvaluationMorning, planHoldingTransitions } = require('./new-a-evaluation-morning.cjs');
const hash = raw => createHash('sha256').update(raw).digest('hex');
const fullCalendar = ['2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19',
  '2026-11-20', '2026-11-24', '2026-11-25', '2026-11-26'];
const quote = [90, 101, 89, 100, 2000, 100, 2000, 1, true];

function fixture({ asOf = '2026-11-24', held = false, lowVolume = false, saved = true, live = true } = {}) {
  const symbol = '123A';
  const dates = fullCalendar.filter(date => date <= asOf);
  const scope = { symbol, candidate_date: dates[0], episode_id: 1, priority_score: 1 };
  const parts = {
    'episodes-000.json': [scope],
    'watches-000.json': [{ ...scope, watch_status: 'TRIGGERED', trigger_date: dates[1] }],
    'intents-000.json': [{ ...scope, trigger_date: dates[1] }],
    'quotes-000.json': dates.map((date, i) =>
      [symbol, date, lowVolume && i === 2 ? [90, 101, 89, 100, 0, 100, 0, 1, true] : quote]),
  };
  const part = name => {
    const raw = JSON.stringify(parts[name]);
    return { name, sha256: hash(raw), bytes: Buffer.byteLength(raw), rows: parts[name].length };
  };
  const key = 'a'.repeat(64);
  const manifest = {
    schema: 'A_BROWSER_PRIVATE_INPUT_V1', strategy: 'A_BASE', audience: 'EXISTING_CLOUD_OWNER_ONLY',
    source_version: key, live, as_of: dates.at(-1), daily_snapshot_sha256: 'b'.repeat(64),
    collections: {
      episodes: [part('episodes-000.json')], intents: [part('intents-000.json')],
      watches: [part('watches-000.json')], presentation: [], current_daily: [],
    },
    quotes: [part('quotes-000.json')], expected_quote_keys: dates.length,
    quote_fields: ['open', 'high', 'low', 'close', 'volume', 'actual_close', 'actual_volume',
      'split_factor', 'source_usable'],
    input_header: {
      source_version: key, calendar: dates,
      limits: { completeThrough: asOf, identityUnverifiedBefore: {},
        heldSymbols: held ? { [symbol]: { reason: 'SOURCE_QUARANTINED' } } : {} },
    },
  };
  const manifestText = JSON.stringify(manifest);
  const pointer = {
    status: 'READY', dataset_id: 'a-' + 'd'.repeat(24), revision: 1, source_version: key,
    manifest_sha256: hash(manifestText),
  };
  const publication = {
    schema: 'NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1',
    published: true, active_readback_verified: true, existing_owner_gate_verified: true,
    dataset_id: pointer.dataset_id, revision: pointer.revision, manifest_sha256: pointer.manifest_sha256,
    source_version: key, snapshot_sha256: manifest.daily_snapshot_sha256, as_of: asOf,
  };
  const active = { pointer, manifestText, publication };
  const settings = {
    schema_version: 1, has_saved_finite_preferences: saved, preference_source: 'new-a-saved',
    revision: 4, owner_binding_sha256: 'c'.repeat(64),
    preferences: {
      initial_cash_yen: 10_000_000, max_positions: 20, per_order_cap_yen: 500_000, base_shares: 100,
      cost_percent: 0, price_cap_yen: null, exit_endpoint: 'd6_open', year_scope: 'all', allocation: 'all',
    },
    exit_policy: { version: 'A_OPEN_EXIT_V2', first_d5_entry_session: '2026-11-17',
      legacy_endpoint: 'd6_open', new_endpoint: 'd5_open' },
    // Analytics presets do not determine holdings in the normal dashboard.
    view_preferences: { trial_preset: 'profit' },
  };
  const raw = JSON.stringify(fullCalendar);
  return {
    active, settings, args: {
      cron: MORNING_CRON, scheduledAt: Date.parse('2026-11-24T23:00:00Z'),
      now: Date.parse('2026-11-24T23:01:00Z'),
      bankBusinessDate: async day => (assert.equal(day, '2026-11-25'), true),
      readActive: async () => structuredClone(active),
      readOwnerPreferences: async () => structuredClone(settings),
      readCalendar: async () => ({ raw, sha256: hash(raw) }),
      readPart: async (dataset, name) => (assert.equal(dataset, pointer.dataset_id), JSON.stringify(parts[name])),
    },
  };
}

test('08 JST selects the saved virtual holding with the existing D5-open policy, no result price', async () => {
  const { args, settings } = fixture();
  const one = await planEvaluationMorning(args);
  assert.equal(one.status, 'planned');
  assert.equal(one.target_date, '2026-11-25');
  assert.equal(one.basis.preferences_revision, 4);
  assert.equal(one.notices.length, 1);
  const row = one.notices[0];
  assert.equal(row.symbol, '123A');
  assert.equal(row.simulated_entry_date, '2026-11-18');
  assert.equal(row.evaluation_endpoint, 'd5_open');
  assert.equal(row.evaluation_timing, 'OPEN');
  assert.equal(row.evaluation_price_status, 'NOT_YET_OBSERVED');
  assert.equal(row.execution_status, 'SIMULATED_NOT_ACTUAL_TRADES');
  assert.equal(row.title, '確定日の朝8時（日本時間）');
  assert.match(row.description, /価格はまだ確定していません/);
  assert.match(row.event_id, /^[0-9a-f]{64}$/);
  assert.equal(JSON.stringify(one).includes(settings.owner_binding_sha256), false);
  assert.deepEqual(await planEvaluationMorning(args), one);
});

test('endpoint changes preserve one reminder identity per holding and evaluation date', async () => {
  const { args, settings } = fixture();
  const open = (await planEvaluationMorning(args)).notices[0];
  settings.preferences.exit_endpoint = 'd5_close';
  const close = (await planEvaluationMorning(args)).notices[0];
  assert.equal(close.scheduled_evaluation_date, open.scheduled_evaluation_date);
  assert.equal(close.evaluation_endpoint, 'd5_close');
  assert.equal(close.evaluation_timing, 'CLOSE');
  assert.equal(close.event_id, open.event_id);
  settings.preferences.exit_endpoint = 'a20_close';
  assert.deepEqual((await planEvaluationMorning(args)).notices, []);
});

test('newer preset does not promote a non-filled or held source to a reminder', async () => {
  for (const options of [{ lowVolume: true }, { held: true }]) {
    const result = await planEvaluationMorning(fixture(options).args);
    assert.deepEqual(result.notices, []);
  }
});

test('out-of-window, unknown bank calendar and stale prior session do not read or plan sendable data', async () => {
  const { args } = fixture();
  const noRead = async () => { throw Error('must not read'); };
  for (const [override, status] of [
    [{ now: Date.parse('2026-11-25T00:00:00Z') }, 'outside_reminder_window'],
    [{ scheduledAt: Date.parse('2026-11-24T22:30:00Z') }, 'outside_reminder_window'],
    [{ bankBusinessDate: async () => undefined }, 'bank_calendar_unavailable'],
    [{ bankBusinessDate: async () => false }, 'bank_non_business_day'],
  ]) {
    const result = await planEvaluationMorning({ ...args, ...override, readActive: noRead });
    assert.equal(result.status, status);
    assert.deepEqual(result.notices, []);
  }
  const old = fixture({ asOf: '2026-11-20' }).args;
  assert.equal((await planEvaluationMorning({ ...old, readPart: noRead })).status,
    'previous_market_session_not_published');
});

test('unverified publication, unsaved defaults and part hash mismatch are fail-closed', async () => {
  const original = fixture();
  original.active.publication.existing_owner_gate_verified = false;
  await assert.rejects(planEvaluationMorning(original.args), /publication is not verified/);
  await assert.rejects(planEvaluationMorning(fixture({ saved: false }).args), /saved owner settings/);
  const corrupt = fixture().args;
  await assert.rejects(planEvaluationMorning({ ...corrupt, readPart: async () => '[]' }),
    /private part bytes differ/);
});

test('a saved preference change while reading does not return a stale notice', async () => {
  const { args, settings } = fixture();
  let version = 0;
  const switched = {
    ...args,
    readOwnerPreferences: async () => ({ ...settings, revision: settings.revision + version++ }),
  };
  await assert.rejects(planEvaluationMorning(switched), /settings changed during planning/);
});

function holdingFixture(options = {}) {
  const {args} = fixture({asOf: '2026-11-18', ...options});
  return {
    ...args, targetDate: '2026-11-18', now: Date.parse('2026-11-18T08:00:00Z'),
    bankBusinessDate: async day => (assert.equal(day, '2026-11-18'), true),
  };
}

test('watch to holding requires same-day normal-site simulated fill and a prior watch', async () => {
  const args = holdingFixture();
  const result = await planHoldingTransitions(args);
  assert.equal(result.status, 'planned');
  assert.equal(result.notices.length, 1);
  assert.equal(result.notices[0].kind, 'WATCH_TO_SIMULATED_HOLDING');
  assert.equal(result.notices[0].execution_status, 'SIMULATED_NOT_ACTUAL_TRADES');
  assert.equal(result.notices[0].simulated_entry_date, '2026-11-18');
  assert.match(result.notices[0].title, /仮想保有/);
  assert.deepEqual(await planHoldingTransitions(args), result);
});

test('unfilled, held, delayed or previous-day data cannot create a holding notice', async () => {
  for (const options of [{ lowVolume: true }, { held: true }, { live: false },
    { asOf: '2026-11-17' }]) {
    const result = await planHoldingTransitions(holdingFixture(options));
    assert.deepEqual(result.notices, []);
  }
  const result = await planHoldingTransitions({
    ...holdingFixture(), now: Date.parse('2026-11-18T15:00:00Z'),
    readActive: async () => { throw Error('never read'); },
  });
  assert.equal(result.status, 'not_current_jst_day');
});

test('legacy D6-open evaluates one market session later than the current D5-open policy', async () => {
  const { args, settings } = fixture({ asOf: '2026-11-25' });
  settings.exit_policy.first_d5_entry_session = '2026-11-19';
  const result = await planEvaluationMorning({
    ...args, scheduledAt: Date.parse('2026-11-25T23:00:00Z'),
    now: Date.parse('2026-11-25T23:00:00Z'), bankBusinessDate: async () => true,
  });
  assert.equal(result.target_date, '2026-11-26');
  assert.equal(result.notices.length, 1);
  assert.equal(result.notices[0].evaluation_endpoint, 'd6_open');
});

test('active pointer revision race prevents stale morning notices', async () => {
  const { active, args } = fixture();
  let version = 0;
  await assert.rejects(planEvaluationMorning({
    ...args,
    readActive: async () => {
      const current = structuredClone(active);
      current.pointer.revision += version;
      current.publication.revision += version++;
      return current;
    },
  }), /publication or saved owner settings changed/);
});
