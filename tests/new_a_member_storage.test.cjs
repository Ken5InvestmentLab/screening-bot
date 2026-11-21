const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const { test } = require('node:test');
const { modules } = require('./helpers/cloud-worker-modules.cjs');

const { createMemberSettings, createMemberPersonalReader } = modules().load('new-a-member-storage');
const migration = fs.readFileSync(path.join(__dirname, '../weak-early-beta-gate/member-migrations/0001_new_a_member_storage.sql'), 'utf8');
const origin = 'https://member-test.example.invalid';
const url = origin + '/api/cloud/new-a-view/preferences';
const first = '111111111111111111';
const second = '222222222222222222';
const source = {
  status: 'READY', dataset_id: 'a-' + '4'.repeat(20), revision: 8,
  as_of: '2026-11-19', source_version: '3'.repeat(64),
};

function makeDb(t) {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec('PRAGMA foreign_keys = ON');
  sqlite.exec(migration);
  t.after(() => sqlite.close());
  const db = {
    prepare(sql) {
      const statement = sqlite.prepare(sql);
      return { bind: (...params) => ({ first: async () => statement.get(...params) ?? null }) };
    },
  };
  return { sqlite, settings: createMemberSettings(db, 'test-secret-member-settings'), personal: createMemberPersonalReader(db) };
}

function payload(state, theme = 'light') {
  return {
    expected_revision: state.revision, save_binding: state.save_binding,
    preferences: state.preferences, view_preferences: { ...state.view_preferences, theme },
  };
}

function save(body, headers = { origin, 'content-type': 'application/json' }) {
  return new Request(url, { method: 'PUT', headers, body: typeof body === 'string' ? body : JSON.stringify(body) });
}

test('default and saved settings isolate two authorized accounts, including across account changes', async t => {
  const { sqlite, settings } = makeDb(t);
  const initial = await (await settings(new Request(url), first)).json();
  const other = await (await settings(new Request(url), second)).json();
  assert.equal(initial.revision, 0);
  assert.equal(initial.view_preferences.theme, 'dark');
  assert.notEqual(initial.save_binding, other.save_binding);
  assert.equal((await settings(save(payload(initial)), second)).status, 409);
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM new_a_member_settings').get().n, 0);

  const response = await settings(save(payload(initial)), first);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  const saved = await response.json();
  assert.equal(saved.revision, 1);
  assert.equal(saved.view_preferences.theme, 'light');
  assert.notEqual(saved.save_binding, initial.save_binding);
  assert.deepEqual(await (await settings(new Request(url), first)).json(), saved);
  assert.deepEqual(await (await settings(new Request(url), second)).json(), other);
  const stored = sqlite.prepare('SELECT * FROM new_a_member_settings').get();
  assert.match(stored.scope, /^[0-9a-f]{64}$/);
  assert.doesNotMatch(JSON.stringify(stored), new RegExp(first));
  assert.equal(await (await settings(new Request(url, { method: 'HEAD' }), first)).text(), '');
});

test('saved and requested legacy trial fees are fixed at zero', async t => {
  const { sqlite, settings } = makeDb(t);
  const initial = await (await settings(new Request(url), first)).json();
  const stored = await (await settings(save(payload(initial)), first)).json();
  const prior = { ...stored.preferences, cost_percent: 0.35 };
  sqlite.prepare('UPDATE new_a_member_settings SET trial_json=?').run(JSON.stringify(prior));
  const current = await (await settings(new Request(url), first)).json();
  assert.deepEqual(current, stored);
  assert.deepEqual(JSON.parse(sqlite.prepare('SELECT trial_json FROM new_a_member_settings').get().trial_json), prior);

  const previousClient = await settings(save({ ...payload(current), preferences: prior }), first);
  assert.equal(previousClient.status, 200);
  const accepted = await previousClient.json();
  assert.equal(accepted.preferences.cost_percent, 0);
  assert.equal(JSON.parse(sqlite.prepare('SELECT trial_json FROM new_a_member_settings').get().trial_json).cost_percent, 0);

  const { cost_percent, ...noFeeInput } = accepted.preferences;
  const next = await settings(save({ ...payload(accepted), preferences: noFeeInput }), first);
  assert.equal(next.status, 200);
  assert.deepEqual((await next.json()).preferences, accepted.preferences);
});

test('one CAS wins, the written revision keeps its durable trial request and an old save cannot overwrite it', async t => {
  const { sqlite, settings } = makeDb(t);
  const initial = await (await settings(new Request(url), first)).json();
  const replies = await Promise.all([
    settings(save(payload(initial, 'light')), first),
    settings(save(payload(initial, 'system')), first),
  ]);
  assert.deepEqual(replies.map(reply => reply.status).sort(), [200, 409]);
  const stored = sqlite.prepare('SELECT revision, requested_at FROM new_a_member_settings').get();
  assert.equal(stored.revision, 1);
  assert.ok(Number.isFinite(Date.parse(stored.requested_at)));
  assert.equal((await settings(save(payload(initial)), first)).status, 409);
});

test('only JSON, current origin, the verified session and allowed settings may write', async t => {
  const { sqlite, settings } = makeDb(t);
  const initial = await (await settings(new Request(url), first)).json();
  assert.equal((await settings(save(payload(initial), {}), first)).status, 403);
  assert.equal((await settings(save(payload(initial), { origin }), first)).status, 415);
  assert.equal((await settings(save(' '.repeat(8200)), first)).status, 413);
  assert.equal((await settings(save({ ...payload(initial), subject: second }), first)).status, 400);
  assert.equal((await settings(save({ ...payload(initial), view_preferences: { ...initial.view_preferences, theme: 'arbitrary' } }), first)).status, 400);
  assert.equal((await settings(save(payload(initial)), 'invalid')).status, 401);
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM new_a_member_settings').get().n, 0);
});

test('personal metrics must match account, accepted settings revision, and exact dataset generation', async t => {
  const { sqlite, personal, settings } = makeDb(t);
  const initial = await (await settings(new Request(url), first)).json();
  const saved = await (await settings(save(payload(initial)), first)).json();
  const scope = sqlite.prepare('SELECT scope FROM new_a_member_settings').get().scope;
  const metrics = { net_profit: 3500, max_drawdown_pct: -3, trade_count: 2, win_rate_pct: 50 };
  sqlite.prepare('INSERT INTO new_a_member_results VALUES (?,?,?,?,?,?,?)').run(scope, saved.revision,
    source.dataset_id, source.revision, source.as_of, source.source_version, JSON.stringify(metrics));
  assert.deepEqual(JSON.parse(JSON.stringify(await personal(first, source))), metrics);
  assert.equal(await personal(second, source), null);
  assert.equal(await personal(first, { ...source, revision: 9 }), null);
  sqlite.prepare('UPDATE new_a_member_results SET metrics_json=?').run(JSON.stringify({ ...metrics, owner_notes: 'private' }));
  assert.equal(await personal(first, source), null);
  sqlite.prepare('UPDATE new_a_member_results SET metrics_json=?').run(JSON.stringify(metrics));
  sqlite.prepare('UPDATE new_a_member_settings SET trial_json=?')
    .run(JSON.stringify({ ...saved.preferences, cost_percent: 0.25 }));
  assert.equal(await personal(first, source), null);
  assert.equal((await settings(save(payload(saved, 'system')), first)).status, 200);
  assert.equal(await personal(first, source), null);
});
