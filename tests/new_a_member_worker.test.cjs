const assert = require('node:assert/strict');
const { createHash, createHmac } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const { test } = require('node:test');
const { modules } = require('./helpers/cloud-worker-modules.cjs');

const stage = 'https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev';
const production = 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
const day = '2026-11-19';
const owner = '111111111111111111';
const allowed = '222222222222222222';
const denied = '333333333333333333';
const otherAllowed = '444444444444444444';
const dateTime = day + 'T08:00:00Z';
const digest = text => createHash('sha256').update(text).digest('hex');
const loadSql = name => fs.readFileSync(path.resolve(__dirname, '../weak-early-beta-gate', name), 'utf8');
const workerModules = modules();
const worker = workerModules.load('index').default;
const sourceCommit = workerModules.load('operational-build.generated').operationalBuild.source_commit;
const workerVersion = '87654321-4321-4321-aaaa-123456789abc';
const makeSession = workerModules.load('shared-report-gate').__test.createSession;
const preferences = '/api/cloud/new-a-view/preferences';
const history = '/api/cloud/new-a-view/history.json';
const documentPath = '/weak_early_beta_latest.html';

function openDb(t, sql) {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(loadSql(sql));
  t.after(() => db.close());
  let count = 0;
  return {
    db,
    reads: () => count,
    binding: {
      withSession(constraint) {
        assert.equal(constraint, 'first-primary');
        return { prepare(sql) {
          const statement = db.prepare(sql);
          const first = async (...params) => { count++; return statement.get(...params) ?? null; };
          return { first, bind: (...params) => ({ first: () => first(...params) }) };
        } };
      },
    },
  };
}

function setup(t) {
  const ownerDb = openDb(t, 'schema/new-a-private.sql');
  const memberDb = openDb(t, 'member-migrations/0001_new_a_member_storage.sql');
  const version = 'e'.repeat(64);
  const manifest = JSON.stringify({
    schema: 'A_BROWSER_PRIVATE_INPUT_V1', audience: 'EXISTING_CLOUD_OWNER_ONLY', strategy: 'A_BASE', as_of: day,
    source_version: version, input_header: { source_version: version },
    collections: { episodes: [], intents: [], watches: [], presentation: [], current_daily: [] },
    quotes: [{ name: 'quotes-000.json', sha256: digest('[]'), bytes: 2, rows: 0 }],
  });
  const id = 'a-' + digest(manifest).slice(0, 24);
  ownerDb.db.prepare('INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?)')
    .run(id, version, manifest, digest(manifest), 'READY', dateTime);
  ownerDb.db.prepare("INSERT INTO new_a_active_pointer VALUES ('owner',?,?,?)").run(id, 1, dateTime);

  const source = { status: 'READY', dataset_id: id, revision: 1, as_of: day, source_version: version };
  const identity = JSON.stringify(source);
  const presets = ['defensive', 'medium', 'return_priority'];
  const parts = [
    { kind: 'history', index: 0, rows: [{ date: day, symbol: '123A', state: 'WATCHING' }] },
    { kind: 'analytics', index: 0, rows: presets.map(preset => ({ preset, from: day, through: day, resolved: false, metrics: null })) },
    ...presets.map((_, index) => ({ kind: 'chart', index, rows: [{ date: day, equity_yen: null, holding_count: null }] })),
  ];
  const shared = JSON.stringify({
    schema: 'NEW_A_SHARED_READONLY_VIEW_V1', audience: 'EXISTING_DESIGNATED_DISCORD_ROLE',
    basis: 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS', source, parts: parts.map(part => {
      const json = JSON.stringify(part);
      return { kind: part.kind, index: part.index, rows: part.rows.length, bytes: Buffer.byteLength(json), sha256: digest(json) };
    }),
  });
  const sharedDigest = digest(shared);
  memberDb.db.prepare('INSERT INTO private_projection_manifest VALUES (?,?,?)').run(identity, sharedDigest, shared);
  for (const part of parts) memberDb.db.prepare('INSERT INTO private_projection_part VALUES (?,?,?,?)')
    .run(identity, part.kind, part.index, JSON.stringify(part));
  memberDb.db.prepare('INSERT INTO private_projection_ready VALUES (1,?,?)').run(identity, sharedDigest);
  const env = {
    ASSETS: { fetch: async url => new Response(url.endsWith('/member-loader.js') ? 'fixture code' : null,
      { status: url.endsWith('/member-loader.js') ? 200 : 404 }) },
    CLOUD_DB: ownerDb.binding, CLOUD_MEMBER_DB: memberDb.binding, CLOUD_OWNER_DISCORD_ID: owner, CLOUD_OWNER_ONLY_ENABLED: 'true',
    CLOUD_MEMBER_VIEW_ENABLED: 'true', CLOUD_MEMBER_STAGE_ORIGIN: stage, PUBLIC_BASE_URL: stage,
    DISCORD_GUILD_ID: '1479418833352785944', DISCORD_ALLOWED_ROLE_IDS: '1487089073385373828',
    DISCORD_CLIENT_ID: 'fixture-client', SESSION_SECRET: 'isolated-worker-test-key',
    CLOUD_ROLE_AUTHORITY: { idFromName: value => value, get: () => ({
      fetch: async (url, options) => {
        assert.equal(url, 'https://cloud-role-authority.invalid/check');
        const { accessToken } = JSON.parse(options.body);
        const now = Date.now();
        return Response.json({ status: [allowed, otherAllowed, owner].some(subject => accessToken === 'fixture-' + subject) ? 'paid' : 'free',
          checkedAt: now, validUntil: now + 60000, source: 'discord' });
      },
    }) },
  };
  const request = async (route, user, origin = stage) => {
    const headers = {};
    if (user) {
      const now = Math.floor(Date.now() / 1000);
      const cookie = await makeSession({ sub: user, accessToken: 'fixture-' + user, exp: now + 1800,
        tokenExp: now + 1800, roleCheckedAt: now, roles: [] }, env.SESSION_SECRET);
      headers.cookie = '__Host-report_gate_session=' + encodeURIComponent(cookie);
    }
    return new Request(origin + route, { headers });
  };
  return { env, request, ownerDb, memberDb };
}

function productionFixture(t) {
  const fixture = setup(t);
  delete fixture.env.CLOUD_MEMBER_STAGE_ORIGIN;
  delete fixture.env.PUBLIC_BASE_URL;
  fixture.env.CLOUD_VERSION_METADATA = { id: workerVersion, tag: sourceCommit };
  return {
    ...fixture,
    call: async (route, user, env = fixture.env) => worker.fetch(await fixture.request(route, user, production), env),
    migrate: () => fixture.memberDb.db.exec(loadSql('member-migrations/0002_new_a_member_release_policy.sql')),
    setPolicy(mode, { source = sourceCommit, version = workerVersion, nonce = null, tag = null } = {}) {
      fixture.memberDb.db.prepare('INSERT INTO new_a_member_release_policy VALUES (1,1,?,?,?,?,?)'
        + ' ON CONFLICT(singleton) DO UPDATE SET revision=revision+1, mode=excluded.mode, source_commit=excluded.source_commit,'
        + ' worker_version_id=excluded.worker_version_id, canary_nonce=excluded.canary_nonce, canary_subject_hmac=excluded.canary_subject_hmac')
        .run(mode, source, version, nonce, tag);
    },
  };
}

test('the Worker serves assets and shared data to a verified member while keeping owner paths private', async t => {
  const f = setup(t);
  const call = async (route, user) => worker.fetch(await f.request(route, user), f.env);
  assert.equal((await call(documentPath)).status, 302);
  assert.equal((await call(documentPath, denied)).status, 403);
  assert.equal((await call('/api/cloud/new-a-finite/input/manifest.json', allowed)).status, 403);
  assert.equal(f.ownerDb.reads(), 0);
  assert.equal(f.memberDb.reads(), 0);
  assert.match(await (await call(documentPath, allowed)).text(), /data-cloud-mode="member"/);
  assert.equal((await call('/new-a-assets/member-loader.js', allowed)).status, 200);
  assert.equal((await call(preferences, allowed)).status, 200);
  const result = await call(history, allowed);
  assert.equal(result.status, 200, await result.clone().text());
  const json = await result.json();
  assert.deepEqual(json.rows, [{ date: day, symbol: '123A', state: 'WATCHING' }]);
  assert.doesNotMatch(JSON.stringify(json), /source_version|dataset_id|input_header/);
  f.ownerDb.db.exec('UPDATE new_a_active_pointer SET revision=2');
  assert.equal((await call(history, allowed)).status, 503);
});

test('disabled member view or missing or shared D1 bindings cannot open the protected member route', async t => {
  const f = setup(t);
  const request = () => f.request(documentPath, allowed);
  assert.equal((await worker.fetch(await request(), { ...f.env, CLOUD_MEMBER_VIEW_ENABLED: 'false' })).status, 403);
  assert.equal((await worker.fetch(await request(), { ...f.env, CLOUD_MEMBER_DB: undefined })).status, 503);
  assert.equal((await worker.fetch(await request(), { ...f.env, CLOUD_MEMBER_DB: f.env.CLOUD_DB })).status, 503);
  assert.equal(f.ownerDb.reads(), 0);
  assert.equal(f.memberDb.reads(), 0);
});

test('normal origin preserves the existing owner response and requires a matching release row', async t => {
  const f = productionFixture(t);
  assert.deepEqual(await (await f.call('/api/cloud/new-a-finite/access', owner)).json(), { authorized: true, strategy: 'A_BASE' });
  assert.equal(f.memberDb.reads(), 0);
  const noTable = await f.call(documentPath, allowed);
  assert.equal(noTable.status, 403);
  assert.equal(noTable.headers.get('x-cloud-private'), 'true');
  f.migrate();
  assert.equal((await f.call(history, allowed)).status, 403);
  f.setPolicy('off');
  assert.equal((await f.call(documentPath, allowed)).status, 403);
  f.setPolicy('enabled', { source: 'c'.repeat(40) });
  assert.equal((await f.call(history, allowed)).status, 403);
  f.setPolicy('enabled', { version: '00000000-0000-4000-8000-000000000000' });
  assert.equal((await f.call('/new-a-assets/member-loader.js', allowed)).status, 403);
  f.setPolicy('enabled');
  const badMetadata = { ...f.env, CLOUD_VERSION_METADATA: { id: workerVersion, tag: 'c'.repeat(40) } };
  assert.equal((await f.call(history, allowed, badMetadata)).status, 403);
  assert.equal((await f.call(history, allowed, { ...f.env, CLOUD_VERSION_METADATA: undefined })).status, 403);
  assert.equal((await f.call(documentPath, allowed)).status, 200);
  assert.equal((await f.call(history, allowed)).status, 200);
  assert.equal((await f.call(documentPath, denied)).status, 403);
  assert.equal((await f.call('/api/cloud/new-a-view/release', allowed)).status, 403);
  assert.equal((await f.call('/api/cloud/new-a-finite/input/manifest.json', allowed)).status, 403);
  assert.equal((await f.call(history)).status, 401);
});

test('the exact canary proof narrows the normal role and is removed immediately for later requests', async t => {
  const f = productionFixture(t);
  f.migrate();
  const nonce = 'b7'.repeat(32);
  const sign = (subject, version = workerVersion) => createHmac('sha256', Buffer.from(nonce, 'hex'))
    .update(JSON.stringify(['new-a-member-rollout-subject-v1', sourceCommit, version, subject])).digest('hex');
  f.setPolicy('canary', { nonce, tag: sign(allowed) });
  const response = await f.call(documentPath, allowed);
  assert.equal(response.status, 200);
  const body = await response.text();
  assert.match(body, /data-cloud-mode="member"/);
  for (const value of [nonce, sign(allowed), allowed]) {
    assert.ok(!body.includes(value));
    assert.ok(!JSON.stringify([...response.headers]).includes(value));
  }
  const session = '/api/cloud/new-a-view/session';
  assert.equal((await f.call(session, allowed)).status, 204);
  assert.equal((await f.call(session, otherAllowed)).status, 403);
  f.setPolicy('canary', { nonce, tag: sign(denied) });
  assert.equal((await f.call(history, denied)).status, 403);
  f.setPolicy('canary', { nonce, tag: sign(allowed, '00000000-0000-4000-8000-000000000000') });
  assert.equal((await f.call(history, allowed)).status, 403);
  f.setPolicy('enabled');
  assert.equal((await f.call(history, otherAllowed)).status, 200);
  f.setPolicy('off');
  assert.equal((await f.call(session, allowed)).status, 403);
  assert.equal((await f.call(history, otherAllowed)).status, 403);
});

test('production cannot select the isolated stage with request or environment origin hints', async t => {
  const f = productionFixture(t);
  const stageRequest = await f.request(documentPath, allowed, stage);
  assert.equal((await worker.fetch(stageRequest, f.env)).status, 403);
  const request = await f.request(documentPath, allowed, production);
  request.headers.set('x-forwarded-host', new URL(stage).host);
  assert.equal((await worker.fetch(request, f.env)).status, 403);
  const unsafeStageEnv = { ...f.env, CLOUD_MEMBER_STAGE_ORIGIN: production, PUBLIC_BASE_URL: production };
  assert.equal((await worker.fetch(request, unsafeStageEnv)).status, 403);
  const stageEnv = { ...f.env, CLOUD_MEMBER_STAGE_ORIGIN: stage, PUBLIC_BASE_URL: stage };
  assert.equal((await worker.fetch(request, stageEnv)).status, 403);
});

test('the private migration has no default grant and rejects malformed policy rows', t => {
  const f = productionFixture(t);
  f.migrate();
  assert.equal(f.memberDb.db.prepare('SELECT count(*) AS count FROM new_a_member_release_policy').get().count, 0);
  assert.throws(() => f.setPolicy('enabled', { nonce: 'b7'.repeat(32) }), /CHECK constraint/);
  assert.throws(() => f.setPolicy('canary', { nonce: 'b7'.repeat(32) }), /CHECK constraint/);
  assert.throws(() => f.setPolicy('canary', { nonce: 'b7'.repeat(32), tag: 'F'.repeat(64) }), /CHECK constraint/);
  assert.throws(() => f.setPolicy('enabled', { version: '87654321-b321-4321-áaaa-123456789abc' }), /CHECK constraint/);
});
