const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const { test } = require('node:test');
const { modules } = require('./helpers/cloud-worker-modules.cjs');

const { createNewAMemberCurrentReader } = modules().load('./new-a-member-current');
const schema = readFileSync(path.resolve(__dirname, '../weak-early-beta-gate/schema/new-a-private.sql'), 'utf8');
const date = '2026-11-19';
const sourceVersion = 'b'.repeat(64);
const digest = value => createHash('sha256').update(value).digest('hex');

function canonicalManifest() {
  return {
    schema: 'A_BROWSER_PRIVATE_INPUT_V1',
    audience: 'EXISTING_CLOUD_OWNER_ONLY',
    strategy: 'A_BASE',
    as_of: date,
    source_version: sourceVersion,
    input_header: { source_version: sourceVersion },
    collections: { episodes: [], intents: [], watches: [], presentation: [], current_daily: [] },
    quotes: [{ name: 'quotes-000.json', sha256: 'a'.repeat(64), bytes: 2, rows: 0 }],
    live: false,
  };
}

function primary(db, sessions = [], queries = []) {
  return { withSession(constraint) {
    assert.equal(constraint, 'first-primary');
    const id = sessions.push(constraint);
    return { prepare(sql) {
      assert.match(sql, /^SELECT /);
      const statement = db.prepare(sql);
      const result = values => ({ async first() { queries.push(id); return statement.get(...values) ?? null; } });
      return { ...result([]), bind: (...values) => result(values) };
    } };
  } };
}

function fixture(t) {
  const db = new DatabaseSync(':memory:');
  t.after(() => db.close());
  db.exec(schema);
  const sessions = [];
  const queries = [];
  const binding = primary(db, sessions, queries);
  function stage(manifest, { status = 'READY', version = sourceVersion, hash, id } = {}) {
    const json = typeof manifest === 'string' ? manifest : JSON.stringify(manifest);
    const manifestHash = hash ?? digest(json);
    const datasetId = id ?? 'a-' + digest(json).slice(0, 24);
    db.prepare('INSERT INTO new_a_private_datasets VALUES (?, ?, ?, ?, ?, ?)').run(
      datasetId, version, json, manifestHash, status, date + 'T08:15:00Z',
    );
    return datasetId;
  }
  function point(id, revision) {
    db.prepare("INSERT INTO new_a_active_pointer VALUES ('owner', ?, ?, ?)"
      + ' ON CONFLICT (pointer_key) DO UPDATE SET dataset_id=excluded.dataset_id, revision=excluded.revision')
      .run(id, revision, date + 'T08:15:00Z');
  }
  return { db, binding, read: createNewAMemberCurrentReader(binding), point, stage, sessions, queries };
}

function publishedFixture(t) {
  const owner = fixture(t);
  const member = new DatabaseSync(':memory:');
  t.after(() => member.close());
  member.exec(readFileSync(path.resolve(__dirname,
    '../weak-early-beta-gate/member-migrations/0001_new_a_member_storage.sql'), 'utf8'));
  const binding = primary(member);
  const source = (dataset_id, revision, as_of = date) => ({
    status: 'READY', dataset_id, revision, as_of, source_version: sourceVersion,
  });
  function stage(value, activate = true) {
    const identity = JSON.stringify(value);
    const json = JSON.stringify({ schema: 'NEW_A_SHARED_READONLY_VIEW_V2',
      audience: 'AUTHENTICATED_TIERED_DISCORD_VIEW', basis: 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS',
      source: value, history_layout: { premium_pages: 1, completed_pages: 0 }, parts: [] });
    member.prepare('INSERT INTO private_projection_manifest VALUES (?,?,?)').run(identity, digest(json), json);
    if (activate) member.prepare('INSERT INTO private_projection_ready VALUES (1,?,?)'
      + ' ON CONFLICT(singleton) DO UPDATE SET identity=excluded.identity,digest=excluded.digest').run(identity, digest(json));
  }
  return { owner, member, binding, source, stage, read: createNewAMemberCurrentReader(owner.binding, binding) };
}

test('keeps the published day during owner staging and switches only on member activation', async t => {
  const f = publishedFixture(t);
  const first = f.owner.stage(canonicalManifest());
  f.owner.point(first, 4);
  const old = f.source(first, 4);
  f.stage(old);
  assert.deepEqual({ ...await f.read() }, old);
  const next = f.owner.stage({ ...canonicalManifest(), as_of: '2026-11-20' });
  f.owner.point(next, 5);
  assert.deepEqual({ ...await f.read() }, old, 'advancing private owner input must not interrupt published members');
  const current = f.source(next, 5, '2026-11-20');
  f.stage(current, false);
  assert.deepEqual({ ...await f.read() }, old, 'staged projection is not a published generation');
  f.member.prepare('UPDATE private_projection_ready SET identity=?,digest=(SELECT digest FROM private_projection_manifest WHERE identity=?)')
    .run(JSON.stringify(current), JSON.stringify(current));
  assert.deepEqual({ ...await f.read() }, current);
});

test('fails closed when a member publication or its retained owner evidence is unavailable', async t => {
  const f = publishedFixture(t);
  const first = f.owner.stage(canonicalManifest());
  f.owner.point(first, 4);
  assert.equal(await f.read(), null, 'missing member activation must not fall back to private owner input');
  f.stage(f.source(first, 4));
  const next = f.owner.stage({ ...canonicalManifest(), as_of: '2026-11-20' });
  f.owner.point(next, 5);
  f.owner.db.prepare("UPDATE new_a_private_datasets SET status='STAGING' WHERE dataset_id=?").run(first);
  assert.equal(await f.read(), null);
  f.owner.db.prepare("UPDATE new_a_private_datasets SET status='READY',manifest_sha256=? WHERE dataset_id=?")
    .run('e'.repeat(64), first);
  assert.equal(await f.read(), null, 'a retained owner dataset needs its original manifest integrity');
  assert.equal(await createNewAMemberCurrentReader(f.owner.binding, { withSession() { throw Error('offline'); } })(), null);
});

test('rejects a corrupt projection, a future source and a mismatched source at the same revision', async t => {
  for (const kind of ['corrupt', 'future', 'same-revision', 'source-mismatch']) {
    await t.test(kind, async t => {
      const f = publishedFixture(t);
      const first = f.owner.stage(canonicalManifest());
      f.owner.point(first, 4);
      const next = f.owner.stage({ ...canonicalManifest(), daily_snapshot_sha256: 'd'.repeat(64) });
      if (kind === 'same-revision') f.owner.point(next, 4);
      f.stage(f.source(first, kind === 'future' ? 5 : 4));
      if (kind === 'corrupt') f.member.exec("UPDATE private_projection_manifest SET json=json_set(json,'$.basis','CORRUPT')");
      if (kind === 'source-mismatch') {
        const changed = f.member.prepare('SELECT identity,json FROM private_projection_manifest').get();
        const data = JSON.parse(changed.json); data.source.revision = 3;
        const text = JSON.stringify(data);
        f.member.prepare('UPDATE private_projection_manifest SET json=?,digest=?').run(text, digest(text));
        f.member.prepare('UPDATE private_projection_ready SET digest=?').run(digest(text));
      }
      assert.equal(await f.read(), null);
    });
  }
});

test('does not return a selection that changed during primary readback', async t => {
  const f = publishedFixture(t);
  const first = f.owner.stage(canonicalManifest());
  f.owner.point(first, 4); f.stage(f.source(first, 4));
  const moving = { withSession() {
    const session = f.binding.withSession('first-primary');
    return { prepare(sql) {
      if (sql === 'SELECT identity, digest FROM private_projection_ready WHERE singleton = 1')
        f.member.exec('DELETE FROM private_projection_ready');
      return session.prepare(sql);
    } };
  } };
  assert.equal(await createNewAMemberCurrentReader(f.owner.binding, moving)(), null);
});

test('returns only verified owner READY identity and observes same-day revisions on the primary', async t => {
  const { read, stage, point, sessions, queries } = fixture(t);
  const first = stage(canonicalManifest());
  const next = stage({ ...canonicalManifest(), daily_snapshot_sha256: 'd'.repeat(64) });
  assert.equal(await read(), null, 'inactive READY rows never count as the official current pointer');
  point(first, 4);
  assert.deepEqual({ ...await read() }, {
    status: 'READY', dataset_id: first, revision: 4, as_of: date, source_version: sourceVersion,
  });
  point(next, 5);
  assert.deepEqual({ ...await read() }, {
    status: 'READY', dataset_id: next, revision: 5, as_of: date, source_version: sourceVersion,
  });
  assert.deepEqual(sessions, ['first-primary', 'first-primary', 'first-primary']);
  assert.deepEqual(queries, [1, 2, 3]);
});

test('fails closed on absent or unavailable primary D1 and never falls back to an ad-hoc prepare', async () => {
  const noPrimary = { prepare() { assert.fail('must not query without an authoritative D1 session'); } };
  assert.equal(await createNewAMemberCurrentReader(undefined)(), null);
  assert.equal(await createNewAMemberCurrentReader(noPrimary)(), null);
  assert.equal(await createNewAMemberCurrentReader({
    withSession() { throw Error('offline primary'); },
  })(), null);
});

test('rejects unpublished, oversized, mismatched and malformed owner rows', async t => {
  const cases = [
    ['staging', {}, { status: 'STAGING' }],
    ['non-owner audience', { audience: 'EXISTING_DESIGNATED_DISCORD_ROLE' }, {}],
    ['incorrect strategy', { strategy: 'OTHER' }, {}],
    ['bad as-of date', { as_of: '2026-02-30' }, {}],
    ['noncanonical as-of date', { as_of: '2026-1-01' }, {}],
    ['invalid collection', { collections: {} }, {}],
    ['different source version', {}, { version: 'c'.repeat(64) }],
    ['tampered manifest', {}, { hash: 'e'.repeat(64) }],
    ['invalid dataset ID', {}, { id: 'wrong' }],
    ['malformed text', '{', {}],
    ['oversized Unicode manifest', { padding: '仮'.repeat(350_000) }, {}],
  ];
  for (const [description, overrides, options] of cases) {
    await t.test(description, async t => {
      const { read, stage, point } = fixture(t);
      point(stage(typeof overrides === 'string' ? overrides : { ...canonicalManifest(), ...overrides }, options), 4);
      assert.equal(await read(), null);
    });
  }
});

test('does not accept a revision above the JavaScript exact integer range', async t => {
  const { db, stage, point, read } = fixture(t);
  point(stage(canonicalManifest()), 4);
  db.exec('UPDATE new_a_active_pointer SET revision = 9007199254740992');
  assert.equal(await read(), null);
});
