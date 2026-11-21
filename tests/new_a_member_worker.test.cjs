const assert = require('node:assert/strict');
const { createHash, createHmac } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { runInNewContext } = require('node:vm');
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
const otherFree = '555555555555555555';
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
const dashboard = '/api/cloud/new-a-view/dashboard.json';
const fundamental = '/api/cloud/new-a-view/fundamental.json';
const sessionPath = '/api/cloud/new-a-view/session';
const ended = { date: '2026-11-18', symbol: '0010', state: 'EXPIRED' };
const closed = { date: '2026-11-18', symbol: '0020', state: 'HOLD_ENDED' };
const reportFixture = {
  date: ended.date, symbol: ended.symbol, company_name: 'テスト会社', analysis_cutoff: '2026-11-18T07:00:00Z',
  fields: ['材料インパクト', '事業概要', '足元材料', 'ファンダ要点', '注意点', '開示リンク', 'Sources']
    .map(label => ({ label, text: 'AUDITED_REPORT_FIXTURE\nhttps://example.com/source' })),
};
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
          return { first, bind: (...params) => ({ first: () => first(...params),
            all: async () => { count++; return { results: statement.all(...params) }; },
            run: async () => statement.run(...params) }) };
        } };
      },
    },
  };
}

function setup(t, { report } = {}) {
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
    { kind: 'history', index: 0, rows: [{ date: day, symbol: '123A', state: 'WATCHING' }, ended] },
    { kind: 'history', index: 1, rows: [
      { ...ended, completed_on: ended.date }, { ...closed, completed_on: day },
    ] },
    { kind: 'history', index: 2, rows: [
      { date: day, symbol: '123A', state: 'WATCH_STARTED', lane: 'today' },
      { date: day, symbol: '123A', state: 'WATCHING', lane: 'watching' },
    ] },
    { kind: 'analytics', index: 0, rows: presets.map(preset => ({ preset, from: day, through: day, resolved: false, metrics: null })) },
    ...presets.map((_, index) => ({ kind: 'chart', index, rows: [{ date: day, equity_yen: null, holding_count: null }] })),
  ];
  const reportText = report && JSON.stringify(report);
  if (report) parts[0].rows[1] = { ...ended, fundamental_sha256: digest(reportText) };
  const shared = JSON.stringify({
    schema: report ? 'NEW_A_SHARED_READONLY_VIEW_V3' : 'NEW_A_SHARED_READONLY_VIEW_V2',
    ...(report ? { fundamental_reports: 1 } : {}),
    audience: 'AUTHENTICATED_TIERED_DISCORD_VIEW',
    history_layout: { premium_pages: 1, completed_pages: 1 },
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
  if (report) {
    memberDb.db.exec(loadSql('member-migrations/0005_new_a_member_fundamental_reports.sql'));
    memberDb.db.prepare('INSERT INTO private_projection_fundamental VALUES (?,?,?)')
      .run(identity, digest(reportText), reportText);
  }
  const paid = new Set([allowed, otherAllowed, owner]);
  const env = {
    ASSETS: { fetch: async url => /\/(member-loader|member-settings|reference-analytics)\.js$/.test(url)
      ? new Response('fixture code') : new Response(null, { status: 404 }) },
    CLOUD_DB: ownerDb.binding, CLOUD_MEMBER_DB: memberDb.binding, CLOUD_OWNER_DISCORD_ID: owner, CLOUD_OWNER_ONLY_ENABLED: 'true',
    CLOUD_MEMBER_VIEW_ENABLED: 'true', CLOUD_MEMBER_STAGE_ORIGIN: stage, PUBLIC_BASE_URL: stage,
    DISCORD_GUILD_ID: '1479418833352785944', DISCORD_ALLOWED_ROLE_IDS: '1487089073385373828',
    DISCORD_CLIENT_ID: 'fixture-client', SESSION_SECRET: 'isolated-worker-test-key',
    ACCESS_PURCHASE_URL: 'https://whop.com/scoring-bot/tenteikyokuchi/',
    CLOUD_ROLE_AUTHORITY: { idFromName: value => value, get: () => ({
      fetch: async (url, options) => {
        assert.equal(url, 'https://cloud-role-authority.invalid/check');
        const { accessToken } = JSON.parse(options.body);
        const now = Date.now();
        return Response.json({ status: [...paid].some(subject => accessToken === 'fixture-' + subject) ? 'paid' : 'free',
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
  return { env, request, ownerDb, memberDb, revoke: subject => paid.delete(subject) };
}

function productionFixture(t) {
  const fixture = setup(t);
  delete fixture.env.CLOUD_MEMBER_STAGE_ORIGIN;
  delete fixture.env.PUBLIC_BASE_URL;
  fixture.env.CLOUD_MEMBER_AUDIENCE = 'role_only';
  fixture.env.CLOUD_VERSION_METADATA = { id: workerVersion, tag: sourceCommit };
  return {
    ...fixture,
    call: async (route, user, env = fixture.env) => worker.fetch(await fixture.request(route, user, production), env),
    migrate: () => {
      for (const file of ['0002_new_a_member_release_policy.sql', '0004_new_a_member_access_tiers.sql']) {
        fixture.memberDb.db.exec(loadSql('member-migrations/' + file));
      }
    },
    setPolicy(mode, { source = sourceCommit, version = workerVersion, nonce = null, tag = null, freeTag = null } = {}) {
      fixture.memberDb.db.prepare('INSERT INTO new_a_member_release_policy VALUES (1,1,?,?,?,?,?,?)'
        + ' ON CONFLICT(singleton) DO UPDATE SET revision=revision+1, mode=excluded.mode, source_commit=excluded.source_commit,'
        + ' worker_version_id=excluded.worker_version_id, canary_nonce=excluded.canary_nonce,'
        + ' canary_subject_hmac=excluded.canary_subject_hmac, canary_free_subject_hmac=excluded.canary_free_subject_hmac')
        .run(mode, source, version, nonce, tag, freeTag);
    },
  };
}

test('the Worker serves assets and shared data to a verified member while keeping owner paths private', async t => {
  const f = setup(t);
  const call = async (route, user) => worker.fetch(await f.request(route, user), f.env);
  assert.equal((await call(documentPath)).status, 302);
  const freeFrame = await call(documentPath, denied);
  assert.equal(freeFrame.status, 200);
  assert.equal(freeFrame.headers.get('x-cloud-member-access'), 'free');
  const purchase = await call('/purchase', denied);
  assert.equal(purchase.status, 302);
  assert.equal(purchase.headers.get('location'), f.env.ACCESS_PURCHASE_URL);
  assert.equal((await call('/api/cloud/new-a-finite/input/manifest.json', allowed)).status, 403);
  assert.equal(f.ownerDb.reads(), 0);
  assert.equal(f.memberDb.reads(), 0);
  assert.match(await (await call(documentPath, allowed)).text(), /data-cloud-mode="member"/);
  assert.equal((await call('/new-a-assets/member-loader.js', allowed)).status, 200);
  assert.equal((await call(preferences, allowed)).status, 200);
  const result = await call(history, allowed);
  assert.equal(result.status, 200, await result.clone().text());
  const json = await result.json();
  assert.deepEqual(json.rows, [{ date: day, symbol: '123A', state: 'WATCHING' }, ended]);
  assert.doesNotMatch(JSON.stringify(json), /source_version|dataset_id|input_header/);
  const free = await call(history, denied);
  assert.equal(free.status, 200);
  assert.deepEqual((await free.json()).rows, [closed]);
  assert.equal((await call(dashboard, denied)).status, 403);
  const premiumDashboard = await call(dashboard, allowed);
  assert.equal(premiumDashboard.status, 200);
  assert.deepEqual((await premiumDashboard.json()).watching, [{ date: day, symbol: '123A', state: 'WATCHING' }]);
  f.ownerDb.db.exec('UPDATE new_a_active_pointer SET revision=2');
  assert.equal((await call(history, allowed)).status, 503);
});

test('an authenticated Free member can save only their display settings in the tiered Worker', async t => {
  const f = productionFixture(t);
  f.migrate();
  f.setPolicy('enabled');
  const page = '/weak_early_beta_settings.html';
  const asset = '/new-a-assets/member-settings.js';
  for (const path of [page, asset, preferences]) {
    assert.equal((await f.call(path, denied)).status, 403, path);
  }
  const tiered = { ...f.env, CLOUD_MEMBER_AUDIENCE: 'tiered' };
  for (const path of [page, asset]) {
    const response = await f.call(path, denied, tiered);
    assert.equal(response.status, 200, path);
    assert.equal(response.headers.get('x-cloud-member-access'), 'free');
    assert.equal(response.headers.get('cache-control'), 'private, no-store');
  }
  assert.equal((await f.call(preferences, undefined, tiered)).status, 401);
  assert.deepEqual(await (await f.call(preferences, denied, tiered)).json(), { error: 'member_session_required' });

  const sessionTag = async user => (await f.call(sessionPath, user, tiered)).headers.get('x-cloud-member-session');
  const [tag, otherTag, premiumTag] = await Promise.all([denied, otherFree, allowed].map(sessionTag));
  const settings = async (user, token, body) => {
    const request = await f.request(preferences, user, production);
    request.headers.set('x-cloud-member-session', token);
    if (body === undefined) return worker.fetch(request, tiered);
    request.headers.set('origin', production);
    request.headers.set('content-type', 'application/json');
    return worker.fetch(new Request(request, { method: 'PUT', body: JSON.stringify(body) }), tiered);
  };
  assert.equal((await settings(denied, premiumTag)).status, 403);
  assert.equal((await settings(denied, otherTag)).status, 403);
  const start = await (await settings(denied, tag)).json();
  const other = await (await settings(otherFree, otherTag)).json();
  const edit = {
    expected_revision: start.revision, save_binding: start.save_binding, preferences: start.preferences,
    view_preferences: { ...start.view_preferences, theme: 'light', font_size: 'large', page_size: 50 },
  };
  assert.equal((await settings(otherFree, otherTag, edit)).status, 409);
  assert.equal((await settings(denied, tag, { ...edit, preferences: { ...edit.preferences, base_shares: 200 } })).status, 400);
  const response = await settings(denied, tag, edit);
  assert.equal(response.status, 200);
  const saved = await response.json();
  assert.equal(saved.revision, start.revision + 1);
  assert.deepEqual(saved.view_preferences, edit.view_preferences);
  assert.deepEqual(saved.preferences, start.preferences);
  assert.deepEqual(await (await settings(denied, tag)).json(), saved);
  assert.deepEqual(await (await settings(otherFree, otherTag)).json(), other);
  assert.equal((await f.call(dashboard, denied, tiered)).status, 403);
  assert.equal((await f.call('/api/cloud/new-a-finite/input/manifest.json', denied, tiered)).status, 403);
});

test('Fundamentals requires the fresh Premium session and the exact visible history generation', async t => {
  const f = setup(t, { report: reportFixture });
  const call = async (route, user, headers = {}) => {
    const request = await f.request(route, user);
    for (const [key, value] of Object.entries(headers)) request.headers.set(key, value);
    return worker.fetch(request, f.env);
  };
  const route = fundamental + '?item=1.' + reportFixture.date + '.0010';
  const start = f.memberDb.reads();
  assert.equal((await call(route)).status, 401);
  assert.equal((await call(route, denied)).status, 403);
  assert.equal((await call(route, allowed)).status, 403);
  assert.equal(f.memberDb.reads(), start);
  const session = await call(sessionPath, allowed);
  assert.equal(session.status, 204);
  const memberSession = session.headers.get('x-cloud-member-session');
  assert.match(memberSession, /^[0-9a-f]{64}$/);
  const sameSession = { 'x-cloud-member-session': memberSession };
  const premium = await (await call(history, allowed, sameSession)).json();
  assert.deepEqual(premium.rows, [{ date: day, symbol: '123A', state: 'WATCHING' }, { ...ended, has_fundamental: true }]);
  assert.doesNotMatch(JSON.stringify(premium), /AUDITED_REPORT_FIXTURE|fundamental_sha256|company_name/);
  assert.deepEqual((await (await call(history, denied)).json()).rows, [closed]);
  assert.equal((await call(route, allowed, sameSession)).status, 403);
  const scoped = { ...sameSession, 'x-cloud-generation': premium.generation };
  assert.equal((await call(route, otherAllowed, scoped)).status, 403);
  assert.equal((await call(route, allowed, { ...scoped, 'x-cloud-generation': 'stale' })).status, 409);
  assert.equal((await call(route.replace('1.', '2.'), allowed, scoped)).status, 404);
  assert.equal((await call(route.replace(reportFixture.date, '2026-02-31'), allowed, scoped)).status, 400);
  const answer = await call(route, allowed, scoped);
  assert.equal(answer.status, 200);
  assert.match(answer.headers.get('cache-control'), /no-store/);
  assert.deepEqual(await answer.json(), { as_of: day, generation: premium.generation, ...reportFixture });
  f.revoke(allowed);
  assert.equal((await call(route, allowed, scoped)).status, 403);
});

test('Fundamentals rejects legacy, replaced and altered member projection bytes', async t => {
  const legacy = setup(t);
  const f = setup(t, { report: reportFixture });
  async function fetchAt(fixture, route, headers = {}) {
    const req = await fixture.request(route, allowed);
    for (const [name, value] of Object.entries(headers)) req.headers.set(name, value);
    return worker.fetch(req, fixture.env);
  }
  async function scope(fixture) {
    const session = await fetchAt(fixture, sessionPath);
    const list = await (await fetchAt(fixture, history)).json();
    return { 'x-cloud-member-session': session.headers.get('x-cloud-member-session'), 'x-cloud-generation': list.generation };
  }
  const route = fundamental + '?item=1.' + reportFixture.date + '.0010';
  const legacyReply = await fetchAt(legacy, route, await scope(legacy));
  assert.equal(legacyReply.status, 404);
  const scoped = await scope(f);
  f.memberDb.db.prepare('UPDATE private_projection_fundamental SET json=json || ?').run(' ');
  assert.equal((await fetchAt(f, route, scoped)).status, 503);
  f.ownerDb.db.exec('UPDATE new_a_active_pointer SET revision=2');
  assert.equal((await fetchAt(f, route, scoped)).status, 409);
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
  assert.equal((await f.call(dashboard, allowed)).status, 200);
  for (const route of [documentPath, history, dashboard, '/api/cloud/new-a-view/session',
    '/api/cloud/new-a-view/preferences', '/new-a-assets/member-loader.js']) {
    const deniedResponse = await f.call(route, denied);
    assert.equal(deniedResponse.status, 403);
    assert.equal(deniedResponse.headers.get('x-cloud-member-access'), null);
    assert.equal(deniedResponse.headers.get('x-cloud-member-session'), null);
    if (route === documentPath) {
      assert.match(deniedResponse.headers.get('content-type'), /text\/html/);
      assert.match(deniedResponse.headers.get('cache-control'), /no-store/);
      const html = await deniedResponse.text();
      assert.match(html, /href="\/purchase">Premiumアクセス権を購入する/);
      assert.doesNotMatch(html, /123A|0010|0020|data-cloud-mode|<script/);
    } else assert.deepEqual(await deniedResponse.json(), { error: 'role_required' });
  }
  for (const audience of [undefined, 'unknown']) {
    const invalid = { ...f.env, CLOUD_MEMBER_AUDIENCE: audience };
    assert.equal((await f.call(history, allowed, invalid)).status, 403);
    assert.deepEqual(await (await f.call('/api/cloud/new-a-finite/access', owner, invalid)).json(),
      { authorized: true, strategy: 'A_BASE' });
  }
  assert.equal((await f.call('/api/cloud/new-a-view/release', allowed)).status, 403);
  assert.equal((await f.call('/api/cloud/new-a-finite/input/manifest.json', allowed)).status, 403);
  assert.equal((await f.call(history)).status, 401);
});

test('the shared URLs use the Premium display for the owner and keep the raw-data boundary', async t => {
  const f = productionFixture(t);
  f.migrate();
  f.setPolicy('off');
  const ownerDoc = await f.call(documentPath, owner);
  assert.equal(ownerDoc.status, 200);
  assert.equal(ownerDoc.headers.get('cache-control'), 'private, no-store');
  const html = await ownerDoc.text();
  assert.match(html, /data-cloud-mode="member"/);
  assert.doesNotMatch(html, /owner-loader\.js|new-a-owner-access-check|new-a-history-jump/);
  assert.equal((await f.call('/new-a-assets/member-loader.js', owner)).status, 200);
  assert.equal((await f.call(sessionPath, owner)).status, 204);
  assert.equal((await f.call(history, owner)).status, 200);
  assert.equal((await f.call(history, allowed)).status, 403);
  assert.equal((await f.call(dashboard, denied)).status, 403);
  assert.deepEqual(await (await f.call('/api/cloud/new-a-finite/access', owner)).json(), { authorized: true, strategy: 'A_BASE' });
  assert.equal((await f.call('/api/cloud/new-a-finite/input/manifest.json', allowed)).status, 403);

  f.setPolicy('enabled');
  for (const route of ['/', '/report', '/index.html', documentPath,
    '/weak_early_beta_analytics.html', '/weak_early_beta_settings.html']) {
    const [ownerPage, memberPage] = await Promise.all([f.call(route, owner), f.call(route, allowed)]);
    assert.equal(ownerPage.status, 200, route);
    assert.equal(memberPage.status, 200, route);
    const memberHtml = await memberPage.text();
    assert.match(memberHtml, /member-loader\.js/);
    assert.doesNotMatch(memberHtml, /owner-loader\.js|new-a-owner-access-check|検出履歴へ/);
    assert.equal(await ownerPage.text(), memberHtml, route);
  }
  for (const route of [dashboard, history, '/api/cloud/new-a-view/analytics.json']) {
    const [ownerData, memberData] = await Promise.all([f.call(route, owner), f.call(route, allowed)]);
    assert.equal(ownerData.status, 200, route);
    assert.equal(memberData.status, 200, route);
    // Generation signatures are scoped to each logged-in account.
    const { generation: ownerGeneration, ...ownerProjection } = await ownerData.json();
    const { generation: memberGeneration, ...memberProjection } = await memberData.json();
    if (ownerGeneration !== undefined || memberGeneration !== undefined)
      assert.notEqual(ownerGeneration, memberGeneration, route);
    assert.deepEqual(ownerProjection, memberProjection, route);
  }
  for (const [route, destination] of [
    ['/research-a', documentPath],
    ['/weak_early_beta_latest_free.html', documentPath],
    ['/weak_early_beta_guide.html', documentPath],
    ['/weak_early_beta_analytics_free.html', '/weak_early_beta_analytics.html'],
  ]) {
    const redirected = await f.call(route, owner);
    assert.equal(redirected.status, 302, route);
    assert.equal(redirected.headers.get('location'), destination);
  }
  const disabled = await f.call(documentPath, owner, { ...f.env, CLOUD_MEMBER_VIEW_ENABLED: 'false' });
  assert.equal(disabled.status, 403);
  assert.doesNotMatch(await disabled.text(), /owner-loader\.js/);
  assert.equal((await f.call('/research-a', allowed)).status, 403);

  f.revoke(owner);
  for (const route of [documentPath, history, dashboard, sessionPath, '/api/cloud/new-a-finite/access']) {
    const result = await f.call(route, owner);
    assert.equal(result.status, 403);
    assert.equal(result.headers.get('x-cloud-member-session'), null);
  }
  assert.equal((await f.call(documentPath)).status, 302);
});

test('owner settings in the shared frame affect only the verified owner member account', async t => {
  const f = productionFixture(t);
  f.migrate();
  f.setPolicy('enabled');
  const rawPointer = f.ownerDb.db.prepare('SELECT * FROM new_a_active_pointer').get();
  const ownerReads = f.ownerDb.reads();
  const initial = await (await f.call(preferences, owner)).json();
  const other = await (await f.call(preferences, allowed)).json();
  assert.equal(initial.revision, 0);
  assert.notEqual(initial.save_binding, other.save_binding);
  const session = await f.call(sessionPath, owner);
  const request = await f.request(preferences, owner, production);
  const headers = new Headers(request.headers);
  headers.set('origin', production);
  headers.set('content-type', 'application/json');
  headers.set('x-cloud-member-session', session.headers.get('x-cloud-member-session'));
  const save = saveBinding => worker.fetch(new Request(request.url, {
    method: 'PUT', headers,
    body: JSON.stringify({
      expected_revision: initial.revision, save_binding: saveBinding,
      preferences: initial.preferences, view_preferences: { ...initial.view_preferences, theme: 'light' },
    }),
  }), f.env);
  assert.equal((await save(other.save_binding)).status, 409);
  const saved = await save(initial.save_binding);
  assert.equal(saved.status, 200, await saved.clone().text());
  assert.equal((await saved.json()).view_preferences.theme, 'light');
  assert.equal((await (await f.call(preferences, owner)).json()).revision, 1);
  assert.deepEqual(await (await f.call(preferences, allowed)).json(), other);
  assert.deepEqual(f.ownerDb.db.prepare('SELECT * FROM new_a_active_pointer').get(), rawPointer);
  assert.equal(f.ownerDb.reads(), ownerReads);
});

test('the exact canary proof narrows the normal role and is removed immediately for later requests', async t => {
  const f = productionFixture(t);
  f.migrate();
  const nonce = 'b7'.repeat(32);
  const sign = (subject, version = workerVersion) => createHmac('sha256', Buffer.from(nonce, 'hex'))
    .update(JSON.stringify(['new-a-member-rollout-subject-v1', sourceCommit, version, subject])).digest('hex');
  f.setPolicy('canary', { nonce, tag: sign(allowed), freeTag: sign(denied) });
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
  assert.equal((await f.call(history, denied)).status, 403);
  assert.equal((await f.call(dashboard, denied)).status, 403);
  assert.equal((await f.call(history, otherFree)).status, 403);
  assert.equal((await f.call(session, otherAllowed)).status, 403);
  f.setPolicy('canary', { nonce, tag: sign(denied) });
  assert.equal((await f.call(history, denied)).status, 403);
  f.setPolicy('canary', { nonce, tag: sign(allowed, '00000000-0000-4000-8000-000000000000'), freeTag: sign(denied) });
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

const ownerManifest = '/api/cloud/new-a-finite/input/manifest.json';
const observationBuild = workerModules.load('operational-build.generated').operationalBuild;

function observationFixture(t) {
  const f = setup(t);
  const tasks = [];
  const now = Date.now();
  const windowId = 'ab'.repeat(32);
  const key = '51'.repeat(32);
  const subjects = [allowed, denied];
  f.env.CLOUD_VERSION_METADATA = { id: workerVersion, tag: sourceCommit, timestamp: new Date(now - 120_000).toISOString() };
  for (const file of ['0002_new_a_member_release_policy.sql', '0003_new_a_member_response_observations.sql',
    '0004_new_a_member_access_tiers.sql', '0006_new_a_role_only_response_observations.sql']) {
    f.memberDb.db.exec(loadSql('member-migrations/' + file));
  }
  function tag(subject) {
    const target = ['new-a-member-observation-subject-v1', windowId, stage, sourceCommit,
      observationBuild.build_input_sha256, workerVersion, subject];
    return createHmac('sha256', Buffer.from(key, 'hex')).update(JSON.stringify(target)).digest('hex');
  }
  function open({ origin = stage, source = sourceCommit, build = observationBuild.build_input_sha256, id = workerVersion,
    opens = now - 1_000, closes = now + 60_000 } = {}) {
    f.memberDb.db.exec('DELETE FROM new_a_member_observation_window_v1');
    f.memberDb.db.prepare('INSERT INTO new_a_member_observation_window_v1 VALUES (1,?,?,?,?,?,?,?,?,?,?)')
      .run(windowId, origin, source, build, id, opens, closes, key, tag(allowed), tag(denied));
  }
  async function call(route, user, { env = f.env, headers = {} } = {}) {
    const request = await f.request(route, user);
    for (const [name, value] of Object.entries(headers)) request.headers.set(name, value);
    const response = await worker.fetch(request, env, { waitUntil: task => tasks.push(task) });
    await Promise.all(tasks.splice(0));
    return response;
  }
  const rows = (table = 'new_a_member_response_observation_v2') =>
    f.memberDb.db.prepare('SELECT * FROM ' + table + ' ORDER BY subject_hmac,route').all();
  return { ...f, key, subjects, tag, open, call, rows, windowId };
}

test('exact signed nonowner responses record both free and premium routes', async t => {
  const f = observationFixture(t);
  f.open();
  for (const user of f.subjects) {
    for (const route of [documentPath, history, dashboard, ownerManifest]) {
      const response = await f.call(route, user);
      const status = route === ownerManifest || (route === dashboard && user === denied) ? 403 : 200;
      assert.equal(response.status, status);
      for (const hidden of [f.key, user, f.tag(user)]) {
        assert.ok(!JSON.stringify([...response.headers]).includes(hidden));
        assert.ok(!(await response.clone().text()).includes(hidden));
      }
    }
  }
  const recorded = f.rows();
  assert.equal(recorded.length, 8);
  for (const row of recorded) {
    assert.equal(row.origin, stage);
    assert.equal(row.source_commit, sourceCommit);
    assert.equal(row.build_input_sha256, observationBuild.build_input_sha256);
    assert.equal(row.worker_version_id, workerVersion);
    assert.equal(row.window_id, f.windowId);
    assert.ok(Number.isSafeInteger(row.observed_at_ms));
    const actualRole = row.subject_hmac === f.tag(allowed) ? 'allowed' : row.subject_hmac === f.tag(denied) ? 'denied' : '';
    assert.ok(actualRole);
    assert.equal(row.role_result, row.route === ownerManifest ? 'not_checked' : actualRole);
    assert.equal(row.status, row.route === ownerManifest || (row.route === dashboard && actualRole === 'denied') ? 403 : 200);
    for (const hidden of [f.key, ...f.subjects]) assert.ok(!JSON.stringify(row).includes(hidden));
  }
  await f.call(documentPath, allowed);
  assert.deepEqual(f.rows(), recorded);
});

test('the role-only stage observes that roleless accounts receive no document or data', async t => {
  const f = observationFixture(t);
  f.env.CLOUD_MEMBER_AUDIENCE = 'role_only';
  f.open();

  for (const user of f.subjects) {
    for (const route of [documentPath, history, dashboard, ownerManifest]) {
      const result = await f.call(route, user);
      assert.equal(result.status, user === denied || route === ownerManifest ? 403 : 200);
      if (user === denied && route !== ownerManifest) {
        if (route === documentPath) assert.match(await result.text(), /href="\/purchase"/);
        else assert.deepEqual(await result.json(), { error: 'role_required' });
      }
    }
  }

  assert.deepEqual(f.rows(), []);
  const rows = f.rows('new_a_member_response_observation_v3');
  assert.equal(rows.length, 8);
  const denials = rows.filter(row => row.subject_hmac === f.tag(denied));
  assert.equal(denials.length, 4);
  assert.ok(denials.every(row => row.status === 403));
  assert.ok(denials.every(row => row.role_result === (row.route === ownerManifest ? 'not_checked' : 'denied')));
});

test('feeds no observation for unrelated actor, expired or mismatched window, or spoofed request', async t => {
  const f = observationFixture(t);
  assert.equal((await f.call(documentPath, allowed)).status, 200);
  assert.equal(f.rows().length, 0);
  for (const override of [{ origin: production }, { id: '11111111-1111-4111-8111-111111111111' },
    { build: 'c'.repeat(64) }, { source: 'd'.repeat(40) }, { opens: Date.now() - 10_000, closes: Date.now() - 1 }]) {
    f.open(override);
    assert.equal((await f.call(documentPath, allowed)).status, 200);
    assert.equal(f.rows().length, 0);
  }
  f.open();
  assert.equal((await f.call(documentPath, otherAllowed)).status, 200);
  assert.equal((await f.call(documentPath)).status, 302);
  assert.equal((await f.call(history + '?page=1', allowed)).status, 200);
  assert.equal((await f.call(documentPath, allowed, { headers: { 'x-forwarded-host': new URL(stage).host } })).status, 200);
  assert.equal((await f.call(history, allowed, { env: { ...f.env, CLOUD_VERSION_METADATA: {
    ...f.env.CLOUD_VERSION_METADATA, tag: 'e'.repeat(40),
  } } })).status, 200);
  assert.equal(f.rows().length, 0);
});

test('worker never counts Discord lookup failure or an observation revoked before storage', async t => {
  const f = observationFixture(t);
  f.open();
  const unavailable = { ...f.env, CLOUD_ROLE_AUTHORITY: { ...f.env.CLOUD_ROLE_AUTHORITY,
    get: () => ({ fetch: async () => Response.json({ status: 'unavailable', reason: 'discord_role_lookup_503' }) }),
  } };
  assert.equal((await f.call(documentPath, denied, { env: unavailable })).status, 503);
  const db = f.memberDb.binding;
  const revoked = { ...f.env, CLOUD_MEMBER_DB: { withSession(constraint) {
    const session = db.withSession(constraint);
    return { prepare(sql) {
      if (sql.startsWith('INSERT INTO new_a_member_response_observation_v2')) {
        f.memberDb.db.exec('DELETE FROM new_a_member_observation_window_v1');
      }
      return session.prepare(sql);
    } };
  } } };
  assert.equal((await f.call(documentPath, allowed, { env: revoked })).status, 200);
  assert.equal(f.rows().length, 0);
});

test('planned settlement uses Tokyo cash-market sessions with the entry session counted first', () => {
  const { plannedHoldingExit } = workerModules.load('new-a-market-calendar');
  for (const [entry, sessions, expected] of [
    ['2026-11-20', 5, '2026-11-27'], ['2026-11-20', 8, '2026-12-02'],
    ['2026-12-29', 5, '2027-01-06'], ['2026-12-29', 8, '2027-01-12'],
    ['2026-12-30', 8, '2027-01-13'],
  ]) assert.equal(plannedHoldingExit(entry, entry, sessions), expected, entry);
  for (const [entry, asOf, sessions] of [
    ['2026-02-30', '2026-03-02', 5],
    ['2026-11-21', '2026-11-24', 5],
    ['2026-11-23', '2026-11-24', 5],
    ['2026-11-20\n', '2026-11-20', 5],
    ['2026-11-20', '2026-11-23', 5],
    ['2026-11-20', '2026-11-19', 5],
    ['2026-11-20', '2026-11-27', 5],
    ['2027-12-30', '2027-12-30', 5],
    ['2026-11-20', '2026-11-20', 0],
  ]) assert.equal(plannedHoldingExit(entry, asOf, sessions), null);
});

test('reference views require tier-bound sessions and Free receives only aggregate analytics from verified chunks', async t => {
  const f = productionFixture(t);
  f.migrate();
  f.setPolicy('enabled');
  const storage = f.memberDb.db;
  const source = JSON.parse(storage.prepare('SELECT identity FROM private_projection_ready').get().identity);
  const schema = 'NEW_A_MEMBER_REFERENCE_V2';
  const identity = JSON.stringify(source) + '\n' + schema;
  const keys = ['dashboard', 'analytics'].flatMap(name =>
    ['defensive', 'medium', 'return_priority'].map(preset => name + '.' + preset));
  keys.push('history.1');
  const summary = ['defensive', 'medium', 'return_priority'].map(preset =>
    ({ preset, from: day, through: day, resolved: false, metrics: null }));
  const dashboardRows = [{ date: day, symbol: '5678', state: 'WATCHING', lane: 'watching' }];
  const chartRows = [{ date: day, equity_yen: 2000001, holding_count: 0 }];
  const data = new Map([
    ['data.dashboard', dashboardRows],
    ['data.analytics', summary],
    ...summary.map(({ preset }) => ['data.chart.' + preset, chartRows]),
  ]);
  keys.push(...data.keys());
  const dailyMarkup = '<template id="new-a-reference-daily-values">'
    + '{"daily":[["2026-11-19",90,10,100,1,false]],"summary":[["private probe","123A"]]}</template>';
  const chartMarkup = '<div class="cloud-chart" id="new-a-daily-chart"><svg><path d="M1 1"></path></svg></div>';
  const dailyTable = '<div id="new-a-daily-table"><div class="table-wrap"><table class="scenario-table" data-finite-table="daily">'
    + '<thead><tr><th>日付</th></tr></thead><tbody><tr><td>2026-11-19</td></tr></tbody></table></div></div>'
    + '<button id="new-a-daily-more" hidden>次の50営業日</button>';
  const analyticsMarkup = chartMarkup + '<details><summary>日次表</summary>' + dailyTable + '</details>' + dailyMarkup;
  const holdingRow = (entry, exit) => '<tr><td data-label="仮想買付日">' + entry
    + '</td><td data-label="仮想決済予定日">' + exit + '</td></tr>';
  const knownRow = holdingRow('2026-11-18', '2026-11-26');
  const invalidRow = holdingRow('2026-11-23', '未確認');
  const pendingRow = holdingRow('2026-11-18', '未確認');
  const holdingsMarker = '<table class="scenario-table" data-finite-table="holdings"><thead></thead><tbody>';
  const holdingsTail = knownRow + invalidRow + '</tbody></table>';
  const unrelatedTable = '<table class="scenario-table"><tbody>' + pendingRow + '</tbody></table>';
  const dashboardMarkup = unrelatedTable + holdingsMarker + pendingRow + holdingsTail;
  const finiteModule = { exports: {} };
  const finitePath = path.resolve(__dirname, '../weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-controller.js');
  runInNewContext(fs.readFileSync(finitePath, 'utf8'), { module: finiteModule });
  const finite = finiteModule.exports;
  const { analyticsReferenceMarkup } = require('../weak-early-beta-gate/scripts/new-a-ui-source/reference-analytics.cjs');
  const generated = analyticsReferenceMarkup({
    preferences: finite.BASE,
    result: {
      period: ['2026-11-18', day], counts: { WATCHING: 1, FILLED: 1 }, resolved: true, yearly: [],
      metrics: { initialCash: 100, endEquity: 103, netProfit: 3, realizedProfit: 2, unrealizedProfit: 1, closed: 1 },
      open_positions: { '5678': { symbol: '5678' } },
      watches: [{ symbol: '123A' }, { symbol: '5678' }],
      trades: [{ symbol: '0020', profit: 2 }],
      daily: [{ date: day, cash: 90, holdings_value: 13, equity_diagnostic: 103, positions: 1,
        unresolved: false, symbols: ['123A', '5678'] }],
    },
  }, finite);
  const chunks = [];
  const variants = keys.map((item, index) => {
    const markup = data.has(item) ? JSON.stringify(data.get(item))
      : item === 'history.1' ? '{"page":1,"rows":[{"symbol":"123A"}]}'
      : item.startsWith('dashboard.') ? dashboardMarkup
      : item === 'analytics.return_priority' ? analyticsMarkup
      : item === 'analytics.medium' ? generated : '<section>表示 ' + item + '</section>';
    const json = JSON.stringify({ markup });
    chunks.push(json);
    return { item, bytes: Buffer.byteLength(markup), sha256: digest(markup),
      parts: [{ index, bytes: Buffer.byteLength(json), sha256: digest(json) }] };
  });
  const manifest = JSON.stringify({ schema, source, variants });
  const hash = digest(manifest);
  storage.prepare('INSERT INTO private_projection_manifest VALUES (?,?,?)').run(identity, hash, manifest);
  const add = storage.prepare("INSERT INTO private_projection_part VALUES (?,'analytics',?,?)");
  for (const [index, json] of chunks.entries()) add.run(identity, index, json);
  const legacySchema = 'NEW_A_MEMBER_REFERENCE_V1';
  const legacyIdentity = JSON.stringify(source) + '\n' + legacySchema;
  const legacyManifest = JSON.stringify({ schema: legacySchema, source,
    variants: variants.filter(variant => !data.has(variant.item)) });
  const legacyDigest = digest(legacyManifest);
  storage.prepare('INSERT INTO private_projection_manifest VALUES (?,?,?)').run(legacyIdentity, legacyDigest, legacyManifest);
  for (const [index, json] of chunks.entries()) add.run(legacyIdentity, index, json);
  add.run(legacyIdentity, 10_000, JSON.stringify({ digest: legacyDigest }));
  const route = '/api/cloud/new-a-view/reference.json?item=dashboard.return_priority';
  const session = await f.call(sessionPath, allowed);
  const tag = session.headers.get('x-cloud-member-session');
  const historyResponse = await f.call(history, allowed);
  const { generation } = await historyResponse.json();
  const fetchReference = async (path, member = allowed, token = tag, generationPin = generation, env = f.env) => {
    const request = await f.request(path, member, production);
    request.headers.set('x-cloud-member-session', token);
    request.headers.set('x-cloud-generation', generationPin);
    return worker.fetch(request, env);
  };
  assert.equal((await f.call(route, denied)).status, 403);
  assert.equal((await f.call(route, allowed)).status, 403);
  assert.equal((await fetchReference(route)).status, 404);
  add.run(identity, 10_000, JSON.stringify({ digest: hash }));
  const ready = await fetchReference(route);
  assert.equal(ready.status, 200);
  assert.deepEqual(await ready.json(), {
    as_of: day, generation, markup: unrelatedTable + holdingsMarker + holdingRow('2026-11-18', '2026-11-30') + holdingsTail,
  });
  for (const preset of ['defensive', 'medium']) {
    const variant = await fetchReference(route.replace('return_priority', preset));
    assert.equal(variant.status, 200);
    assert.equal((await variant.json()).markup,
      unrelatedTable + holdingsMarker + holdingRow('2026-11-18', '2026-11-25') + holdingsTail);
  }
  assert.equal(storage.prepare("SELECT json FROM private_projection_part WHERE identity=? AND kind='analytics' AND idx=2")
    .get(identity).json, chunks[2]);
  assert.equal((await fetchReference('/api/cloud/new-a-view/reference.json?item=data.dashboard')).status, 400);
  assert.deepEqual(await (await fetchReference(dashboard)).json(), {
    as_of: day, generation, today: [], watching: [{ date: day, symbol: '5678', state: 'WATCHING' }],
  });
  assert.deepEqual(await (await fetchReference('/api/cloud/new-a-view/analytics.json')).json(), {
    as_of: day, generation, presets: summary,
  });
  assert.deepEqual(await (await fetchReference('/api/cloud/new-a-view/chart.json?preset=return_priority')).json(), {
    as_of: day, generation, preset: 'return_priority', rows: chartRows,
  });
  const oldGeneration = createHmac('sha256', f.env.SESSION_SECRET).update(JSON.stringify([
    'new-a-member-generation-v2', allowed, 'premium', source.dataset_id, source.revision, source.as_of, source.source_version,
  ])).digest('hex');
  assert.equal((await fetchReference(route, allowed, tag, oldGeneration)).status, 409);
  const overviewRoute = '/api/cloud/new-a-view/reference.json?item=analytics.overview.return_priority';
  const dailyRoute = '/api/cloud/new-a-view/reference.json?item=analytics.daily.return_priority';
  const compact = await fetchReference(overviewRoute);
  assert.equal(compact.status, 200);
  assert.deepEqual(await compact.json(), {
    as_of: day, generation, markup: analyticsMarkup.replace('<tr><td>2026-11-19</td></tr>', '').replace(dailyMarkup, ''),
  });
  const daily = await fetchReference(dailyRoute);
  assert.equal(daily.status, 200);
  assert.deepEqual(await daily.json(), { as_of: day, generation, markup: dailyMarkup });
  const full = await fetchReference('/api/cloud/new-a-view/reference.json?item=analytics.return_priority');
  assert.equal(full.status, 200);
  assert.deepEqual(await full.json(), { as_of: day, generation, markup: analyticsMarkup });
  assert.equal((await f.call(dailyRoute, denied)).status, 403);
  assert.equal((await fetchReference(dailyRoute, otherAllowed)).status, 403);
  assert.equal((await fetchReference(dailyRoute, allowed, tag, 'f'.repeat(64))).status, 409);
  const missingGeneration = await f.request(dailyRoute, allowed, production);
  missingGeneration.headers.set('x-cloud-member-session', tag);
  assert.deepEqual(await (await worker.fetch(missingGeneration, f.env)).json(), { error: 'generation_required' });
  assert.equal((await fetchReference('/api/cloud/new-a-view/reference.json?item=analytics.daily.invalid')).status, 400);
  const oldMarkup = await fetchReference('/api/cloud/new-a-view/reference.json?item=analytics.overview.defensive');
  assert.deepEqual(await oldMarkup.json(), { as_of: day, generation, markup: '<section>表示 analytics.defensive</section>' });
  assert.equal((await fetchReference('/api/cloud/new-a-view/reference.json?item=analytics.daily.defensive')).status, 404);
  const page = await fetchReference('/api/cloud/new-a-view/reference.json?item=history.1');
  assert.equal(page.status, 200);
  assert.equal(JSON.parse((await page.json()).markup).page, 1);
  assert.equal((await fetchReference(route, otherAllowed)).status, 403);
  assert.equal((await fetchReference(route, allowed, tag, 'f'.repeat(64))).status, 409);
  assert.equal((await fetchReference('/api/cloud/new-a-view/reference.json?item=history.999')).status, 400);

  const tiered = { ...f.env, CLOUD_MEMBER_AUDIENCE: 'tiered' };
  const freeSession = await f.call(sessionPath, denied, tiered);
  assert.equal(freeSession.status, 204);
  const freeTag = freeSession.headers.get('x-cloud-member-session');
  const freeHistory = await (await f.call(history, denied, tiered)).json();
  assert.deepEqual(freeHistory.rows, [closed]);
  assert.doesNotMatch(JSON.stringify(freeHistory), /123A|5678|0010|completed_on/);
  const freeGeneration = freeHistory.generation;
  const freeReference = (route, token = freeTag, pin = freeGeneration) => fetchReference(route, denied, token, pin, tiered);
  const analyticsPage = await f.call('/weak_early_beta_analytics.html', denied, tiered);
  assert.equal(analyticsPage.status, 200);
  assert.equal(analyticsPage.headers.get('x-cloud-member-access'), 'free');
  assert.doesNotMatch(await analyticsPage.text(), /123A|5678|0010/);
  assert.equal((await f.call('/new-a-assets/reference-analytics.js', denied, tiered)).status, 200);
  assert.equal((await f.call(overviewRoute, denied, tiered)).status, 403);
  assert.equal((await freeReference(dailyRoute, tag)).status, 403);
  assert.equal((await freeReference(dailyRoute, freeTag, generation)).status, 409);
  const freeDaily = await freeReference(dailyRoute);
  assert.equal(freeDaily.status, 200);
  assert.deepEqual(await freeDaily.json(), { as_of: day, generation: freeGeneration,
    markup: '<template id="new-a-reference-daily-values">{"daily":[["2026-11-19",90,10,100,1,false]]}</template>' });
  const freeOverview = await freeReference(overviewRoute.replace('return_priority', 'medium'));
  assert.equal(freeOverview.status, 200, await freeOverview.clone().text());
  const { markup: freeMarkup } = await freeOverview.json();
  assert.match(freeMarkup, /日次資金推移/);
  assert.match(freeMarkup, /class="equity-line"/);
  assert.doesNotMatch(freeMarkup, /123A|5678|0020|new-a-reference-daily-values|適用中の設定|weak_early_beta_settings|analytics-export/);
  assert.equal((await freeReference(overviewRoute.replace('return_priority', 'defensive'))).status, 404);
  for (const restricted of [route, dashboard, '/api/cloud/new-a-finite/input/manifest.json',
    '/api/cloud/new-a-view/chart.json?preset=medium', '/api/cloud/new-a-view/reference.json?item=analytics.medium',
    '/api/cloud/new-a-view/reference.json?item=history.index', '/api/cloud/new-a-view/reference.json?item=history.1',
    '/api/cloud/new-a-view/fundamental.json?item=1.2026-11-18.0020']) {
    assert.equal((await freeReference(restricted)).status, 403, restricted);
  }
  storage.prepare("UPDATE private_projection_part SET json='{}' WHERE identity=? AND kind='analytics' AND idx=2").run(identity);
  assert.equal((await fetchReference(route)).status, 503);
});
