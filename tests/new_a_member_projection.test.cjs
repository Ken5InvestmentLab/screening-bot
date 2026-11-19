const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { DatabaseSync } = require('node:sqlite');
const { test } = require('node:test');
const { createNewAMemberProjectionReader } = require('../weak-early-beta-gate/src/new-a-member-projection.ts');

const source = Object.freeze({
  status: 'READY',
  dataset_id: 'a-' + 'a'.repeat(20),
  revision: 4,
  as_of: '2026-11-19',
  source_version: 'b'.repeat(64),
});
const digest = json => createHash('sha256').update(json).digest('hex');
const history = [{ date: source.as_of, symbol: '123A', state: 'WATCHING' }];
const charts = [
  { date: '2026-11-18', equity_yen: null, holding_count: null },
  { date: source.as_of, equity_yen: 105, holding_count: 1 },
];
const analytics = ['defensive', 'medium', 'return_priority'].map(preset => ({
  preset, from: '2026-11-18', through: source.as_of, resolved: false, metrics: null,
}));

function fixture(t, { changePart = () => {}, changeManifest = () => {}, omitHistory = false, tiered = false } = {}) {
  const db = new DatabaseSync(':memory:');
  t.after(() => db.close());
  db.exec(`
    CREATE TABLE private_projection_ready (singleton INTEGER PRIMARY KEY, identity TEXT, digest TEXT);
    CREATE TABLE private_projection_manifest (identity TEXT PRIMARY KEY, digest TEXT, json TEXT);
    CREATE TABLE private_projection_part (
      identity TEXT, kind TEXT, idx INTEGER, json TEXT, PRIMARY KEY (identity, kind, idx)
    );
  `);
  const identity = JSON.stringify(source);
  const parts = [
    ...omitHistory ? [] : [{ kind: 'history', index: 0, rows: structuredClone(history) }],
    ...(tiered ? [
      { kind: 'history', index: 1, rows: [{ date: '2026-11-17', symbol: '123B', state: 'HOLD_ENDED', completed_on: '2026-11-18' }] },
      { kind: 'history', index: 2, rows: [{ date: source.as_of, symbol: '123A', state: 'WATCH_STARTED', lane: 'today' }] },
    ] : []),
    { kind: 'analytics', index: 0, rows: structuredClone(analytics) },
    ...[0, 1, 2].map(index => ({ kind: 'chart', index, rows: structuredClone(charts) })),
  ];
  const descriptors = parts.map(part => {
    changePart(part);
    const json = JSON.stringify(part);
    db.prepare('INSERT INTO private_projection_part VALUES (?, ?, ?, ?)')
      .run(identity, part.kind, part.index, json);
    return {
      kind: part.kind, index: part.index, rows: part.rows.length,
      bytes: Buffer.byteLength(json), sha256: digest(json),
    };
  });
  const manifest = {
    schema: tiered ? 'NEW_A_SHARED_READONLY_VIEW_V2' : 'NEW_A_SHARED_READONLY_VIEW_V1',
    audience: tiered ? 'AUTHENTICATED_TIERED_DISCORD_VIEW' : 'EXISTING_DESIGNATED_DISCORD_ROLE',
    ...(tiered ? { history_layout: { premium_pages: 1, completed_pages: 1 } } : {}),
    basis: 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS',
    source: { ...source },
    parts: descriptors,
  };
  changeManifest(manifest);
  const json = JSON.stringify(manifest);
  const manifestDigest = digest(json);
  db.prepare('INSERT INTO private_projection_ready VALUES (1, ?, ?)').run(identity, manifestDigest);
  db.prepare('INSERT INTO private_projection_manifest VALUES (?, ?, ?)').run(identity, manifestDigest, json);

  const sessions = [];
  const queries = [];
  let official = async () => source;
  let afterQuery = () => {};
  const binding = {
    withSession(constraint) {
      assert.equal(constraint, 'first-primary');
      const number = sessions.push(constraint);
      return {
        prepare(sql) {
          assert.match(sql, /^SELECT /);
          const statement = db.prepare(sql);
          let values = [];
          return {
            bind(...args) { values = args; return this; },
            async first() {
              queries.push({ number, sql });
              const result = statement.get(...values) ?? null;
              afterQuery(sql);
              return result;
            },
          };
        },
      };
    },
  };
  return {
    db, sessions, queries,
    read: createNewAMemberProjectionReader(binding, () => official()),
    setOfficial: fn => { official = fn; },
    afterQuery: fn => { afterQuery = fn; },
  };
}

test('reads the exact active generation, validates public rows and preserves chart gaps', async t => {
  const f = fixture(t);
  assert.deepEqual(await f.read(source, 'history', 0), { source, history_pages: 1, rows: history });
  assert.deepEqual(await f.read(source, 'analytics', 0), { source, history_pages: 1, rows: analytics });
  assert.deepEqual(await f.read(source, 'chart', 2), { source, history_pages: 1, rows: charts });
  assert.deepEqual(f.queries.map(query => query.number), [1, 1, 2, 3, 3, 4, 5, 5, 6]);
  assert.equal(await f.read(source, 'chart', 3), null);
});

test('an absent history page reports the verified page count and still rechecks activation', async t => {
  const f = fixture(t, { omitHistory: true });
  assert.deepEqual(await f.read(source, 'history', 1), { source, history_pages: 1, rows: [] });
  assert.equal(f.queries.length, 2);
  assert.equal(f.sessions.length, 2);
});

test('no binding or valid authoritative generation means no projection read', async t => {
  const unavailable = createNewAMemberProjectionReader(undefined, async () => {
    assert.fail('no official lookup without a projection binding');
  });
  assert.equal(await unavailable(source, 'history', 0), null);
  const f = fixture(t);
  assert.equal(await f.read({ ...source, as_of: '2026-02-30' }, 'history', 0), null);
  assert.equal(await f.read(source, 'history', -1), null);
  f.setOfficial(async () => ({ ...source, revision: source.revision + 1 }));
  assert.equal(await f.read(source, 'history', 0), null);
  assert.equal(f.queries.length, 0);
  f.setOfficial(async () => { throw Error('unavailable'); });
  assert.equal(await f.read(source, 'history', 0), null);
});

test('rejects official pointer or projection activation changes during a part read', async t => {
  const canonical = fixture(t);
  canonical.afterQuery(sql => {
    if (sql.includes('FROM private_projection_part')) {
      canonical.setOfficial(async () => ({ ...source, source_version: 'f'.repeat(64) }));
    }
  });
  assert.equal(await canonical.read(source, 'history', 0), null);
  assert.equal(canonical.sessions.length, 2);

  const activation = fixture(t);
  activation.afterQuery(sql => {
    if (sql.includes('FROM private_projection_part')) {
      activation.db.prepare('UPDATE private_projection_ready SET digest = ?').run('f'.repeat(64));
    }
  });
  assert.equal(await activation.read(source, 'history', 0), null);
  assert.equal(activation.sessions.length, 2);
});

test('rejects missing activation, wrong reviewed digest and altered bytes', async t => {
  const f = fixture(t);
  f.db.prepare('UPDATE private_projection_manifest SET json = json || ?').run(' ');
  assert.equal(await f.read(source, 'history', 0), null);
  const unapproved = fixture(t);
  unapproved.db.prepare('UPDATE private_projection_ready SET digest = ?').run('e'.repeat(64));
  assert.equal(await unapproved.read(source, 'history', 0), null);
  const altered = fixture(t);
  altered.db.prepare('UPDATE private_projection_part SET json = replace(json, ?, ?) WHERE kind = ?')
    .run('123A', '123B', 'history');
  assert.equal(await altered.read(source, 'history', 0), null);
  const missing = fixture(t);
  missing.db.exec('DELETE FROM private_projection_ready');
  assert.equal(await missing.read(source, 'history', 0), null);
});

test('rejects reviewed manifests with a different source or missing required parts', async t => {
  const changedSource = fixture(t, { changeManifest: value => { value.source.revision += 1; } });
  assert.equal(await changedSource.read(source, 'history', 0), null);
  const missingChart = fixture(t, { changeManifest: value => { value.parts.pop(); } });
  assert.equal(await missingChart.read(source, 'history', 0), null);
  const misindexed = fixture(t, { changeManifest: value => { value.parts[0].index = 1; } });
  assert.equal(await misindexed.read(source, 'history', 0), null);
});

test('rejects hash-matched projection rows outside the exact safe schema or date', async t => {
  const unsafe = fixture(t, {
    changePart: part => {
      if (part.kind === 'history') part.rows[0].owner_holding = 42;
      if (part.kind === 'analytics') part.rows[0].metrics = {};
      if (part.kind === 'chart') part.rows.pop();
    },
  });
  assert.equal(await unsafe.read(source, 'history', 0), null);
  assert.equal(await unsafe.read(source, 'analytics', 0), null);
  assert.equal(await unsafe.read(source, 'chart', 0), null);
});

test('V1 cannot serve roleless history or dashboard and V2 maps disjoint storage pages', async t => {
  const legacy = fixture(t);
  assert.equal(await legacy.read(source, 'completed-history', 0), null);
  assert.equal(await legacy.read(source, 'dashboard', 0), null);
  const f = fixture(t, { tiered: true });
  assert.deepEqual((await f.read(source, 'history', 0)).rows, history);
  assert.deepEqual((await f.read(source, 'history', 1)).rows, []);
  assert.deepEqual((await f.read(source, 'completed-history', 0)).rows,
    [{ date: '2026-11-17', symbol: '123B', state: 'HOLD_ENDED' }]);
  assert.deepEqual((await f.read(source, 'completed-history', 1)).rows, []);
  assert.deepEqual((await f.read(source, 'dashboard', 0)).rows,
    [{ date: source.as_of, symbol: '123A', state: 'WATCH_STARTED', lane: 'today' }]);
  assert.equal(await f.read(source, 'dashboard', 1), null);
});

test('even digest-matched completed pages reject current terminals, pending rows and hidden fields', async t => {
  for (const properties of [
    { completed_on: source.as_of },
    { state: 'WATCHING' },
    { owner_holdings: true },
  ]) {
    const f = fixture(t, { tiered: true, changePart(part) {
      if (part.kind === 'history' && part.index === 1) Object.assign(part.rows[0], properties);
    } });
    assert.equal(await f.read(source, 'completed-history', 0), null);
    assert.deepEqual((await f.read(source, 'history', 0)).rows, history);
  }
});
