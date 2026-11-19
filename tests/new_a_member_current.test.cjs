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

function fixture(t) {
  const db = new DatabaseSync(':memory:');
  t.after(() => db.close());
  db.exec(schema);
  const sessions = [];
  const queries = [];
  const binding = {
    withSession(constraint) {
      assert.equal(constraint, 'first-primary');
      const id = sessions.push(constraint);
      return {
        prepare(sql) {
          assert.match(sql, /^SELECT /);
          const statement = db.prepare(sql);
          return {
            bind(limit) {
              assert.equal(limit, 1024 * 1024);
              return {
                async first() {
                  queries.push(id);
                  return statement.get(limit) ?? null;
                },
              };
            },
          };
        },
      };
    },
  };
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
  return { db, read: createNewAMemberCurrentReader(binding), point, stage, sessions, queries };
}

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
