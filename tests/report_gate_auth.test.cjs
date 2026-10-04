const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

const repoRoot = path.resolve(__dirname, '..');
const tsPath = [
  'weak-early-beta-gate/node_modules/typescript/lib/typescript.js',
  'report-gate/node_modules/typescript/lib/typescript.js',
].map((relative) => path.join(repoRoot, relative)).find((candidate) => fs.existsSync(candidate));
assert.ok(tsPath, 'Install one gate package before running the authentication tests.');
const ts = require(tsPath);

// Execute the real shared Worker in isolation. All credentials, tokens, requests,
// and cookies are synthetic; neither Discord nor deployed Workers are contacted.
function createGate(fetchMock, { clock } = {}) {
  const source = fs.readFileSync(path.join(repoRoot, 'report-gate/src/index.ts'), 'utf8');
  const compiled = ts.transpileModule(`${source}\n` +
    'globalThis.__gateTest = { createSession, createOAuthState, readSession, accessGuardScript };', {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const sandbox = {
    exports: {}, Request, Response, Headers, URL, URLSearchParams, AbortSignal,
    TextEncoder, TextDecoder, Uint8Array, crypto: webcrypto, atob, btoa,
    fetch: fetchMock,
    Date: class extends Date { static now() { return clock ? clock.now : Date.now(); } },
    console: { error() {}, log() {} },
    setTimeout, clearTimeout,
  };
  vm.runInNewContext(compiled, sandbox, { filename: 'shared-report-gate.js' });
  const env = {
    DISCORD_CLIENT_ID: 'test-client',
    DISCORD_CLIENT_SECRET: 'test-client-secret',
    DISCORD_GUILD_ID: 'test-guild',
    DISCORD_ALLOWED_ROLE_IDS: 'test-allowed-role',
    SESSION_SECRET: 'test-only-session-encryption-secret',
    DISCORD_API_BASE: 'https://discord.invalid/api',
    ASSETS: { fetch: async () => new Response('<html><body>Test report</body></html>') },
  };
  return { worker: sandbox.exports.default, api: sandbox.__gateTest, env };
}

function sessionPayload(overrides = {}) {
  const now = Math.floor(Date.now() / 1000);
  return {
    sub: 'test-user', accessToken: 'test-old-access', refreshToken: 'test-old-refresh',
    exp: now + 86400, tokenExp: now - 60, roleCheckedAt: now - 1000,
    roles: ['test-allowed-role'], ...overrides,
  };
}

async function requestFor(gate, pathname = '/auth/check', payload = sessionPayload()) {
  const encrypted = await gate.api.createSession(payload, gate.env.SESSION_SECRET);
  return new Request(`https://gate.invalid${pathname}`, {
    headers: { cookie: `__Host-report_gate_session=${encodeURIComponent(encrypted)}` },
  });
}

async function savedSession(gate, response) {
  const setCookie = response.headers.get('set-cookie');
  assert.ok(setCookie, 'The response must save the updated session.');
  assert.doesNotMatch(setCookie, /Max-Age=0(?:\D|$)/, 'The updated session must not be cleared.');
  const cookiePair = setCookie.split(';', 1)[0];
  return gate.api.readSession(new Request('https://gate.invalid/auth/check', {
    headers: { cookie: cookiePair },
  }), gate.env);
}

function tokenResponse() {
  return Response.json({
    access_token: 'test-new-access', refresh_token: 'test-new-refresh', expires_in: 3600,
  });
}

function discordMock({ refresh = tokenResponse, member, accessToken = 'test-new-access' } = {}) {
  const calls = { refresh: 0, member: 0 };
  const fetchMock = async (input, init) => {
    const url = String(input);
    if (url === 'https://discord.invalid/api/oauth2/token') {
      assert.equal(init.headers['user-agent'], 'DiscordBot (https://github.com/Ken5InvestmentLab/screening-bot, 1.0)');
      calls.refresh += 1;
      assert.equal(init.body.get('grant_type'), 'refresh_token');
      assert.equal(init.body.get('refresh_token'), 'test-old-refresh');
      return refresh(calls.refresh);
    }
    if (url === 'https://discord.invalid/api/users/@me/guilds/test-guild/member') {
      assert.equal(init.headers['user-agent'], 'DiscordBot (https://github.com/Ken5InvestmentLab/screening-bot, 1.0)');
      calls.member += 1;
      assert.equal(init.headers.authorization, `Bearer ${accessToken}`);
      return member ? member(calls.member) : Response.json({ roles: ['test-allowed-role'] });
    }
    throw new Error(`Unexpected synthetic request: ${url}`);
  };
  return { fetchMock, calls };
}

test('refresh then temporary role lookup failure saves the rotated token on /auth/check', async () => {
    const mock = discordMock({ member: () => new Response('Temporary outage', { status: 503 }) });
    const gate = createGate(mock.fetchMock);
    const response = await gate.worker.fetch(await requestFor(gate), gate.env);
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('location'), null);
    const persisted = await savedSession(gate, response);
    assert.equal(persisted.accessToken, 'test-new-access');
    assert.equal(persisted.refreshToken, 'test-new-refresh');
    assert.ok(persisted.tokenExp > Math.floor(Date.now() / 1000));
});

test('document navigation with an expiring token waits for the serialized browser refresh', async () => {
  const mock = discordMock();
  const gate = createGate(mock.fetchMock);
  const response = await gate.worker.fetch(await requestFor(gate, '/'), gate.env);
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /data-auth-recovery/);
  assert.match(html, /\/auth\/guard\.js/);
  assert.doesNotMatch(html, /Test report/);
  assert.equal(mock.calls.refresh, 0);
  assert.equal(mock.calls.member, 0);
});

for (const [description, member] of [
  ['Discord rejects guild access', () => new Response('Forbidden', { status: 403 })],
  ['Discord returns no permitted role', () => Response.json({ roles: ['test-other-role'] })],
]) {
  test(`role denial saves the rotated token when ${description}`, async () => {
    const gate = createGate(discordMock({ member }).fetchMock);
    const response = await gate.worker.fetch(await requestFor(gate), gate.env);
    assert.equal(response.status, 403);
    assert.equal((await response.json()).reason, 'role_required');
    const persisted = await savedSession(gate, response);
    assert.equal(persisted.refreshToken, 'test-new-refresh');
  });
}

for (const [status, body] of [
  [400, { error: 'invalid_client' }],
  [401, { error: 'invalid_client' }],
  [403, { error: 'access_denied' }],
]) {
  test(`refresh ${status} without invalid_grant keeps the existing login`, async () => {
    const mock = discordMock({ refresh: () => Response.json(body, { status }) });
    const gate = createGate(mock.fetchMock);
    const response = await gate.worker.fetch(await requestFor(gate), gate.env);
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('location'), null);
    assert.doesNotMatch(response.headers.get('set-cookie') || '', /Max-Age=0(?:\D|$)/);
    assert.notEqual((await response.json()).reason, 'login_required');
    assert.equal(mock.calls.member, 0);
  });
}

test('an explicitly invalid refresh grant requires a new login', async () => {
  const mock = discordMock({ refresh: () => Response.json({ error: 'invalid_grant' }, { status: 400 }) });
  const gate = createGate(mock.fetchMock);
  const response = await gate.worker.fetch(await requestFor(gate), gate.env);
  assert.equal(response.status, 401);
  const result = await response.json();
  assert.equal(result.reason, 'login_required');
  assert.equal(result.confirmation_required, true);
  assert.doesNotMatch(response.headers.get('set-cookie') || '', /Max-Age=0(?:\D|$)/);
  assert.equal(mock.calls.member, 0);
});

test('concurrent and delayed requests sharing a refresh token reuse one rotation', async () => {
  let signalStarted;
  const started = new Promise((resolve) => { signalStarted = resolve; });
  let releaseRefresh;
  const heldRefresh = new Promise((resolve) => { releaseRefresh = resolve; });
  const mock = discordMock({ refresh: () => { signalStarted(); return heldRefresh; } });
  const gate = createGate(mock.fetchMock);
  const request = await requestFor(gate);
  const pending = [gate.worker.fetch(request.clone(), gate.env), gate.worker.fetch(request.clone(), gate.env)];
  await started;
  await new Promise(setImmediate);
  await new Promise(setImmediate);
  assert.equal(mock.calls.refresh, 1, 'Concurrent requests must not rotate one token twice.');
  releaseRefresh(tokenResponse());
  const responses = await Promise.all(pending);
  for (const response of responses) {
    assert.equal(response.status, 200);
    assert.equal((await savedSession(gate, response)).refreshToken, 'test-new-refresh');
  }
  const delayed = await gate.worker.fetch(request.clone(), gate.env);
  assert.equal(delayed.status, 200);
  assert.equal((await savedSession(gate, delayed)).refreshToken, 'test-new-refresh');
  assert.equal(mock.calls.refresh, 1, 'A late request carrying the old cookie must recover from the cached rotation.');
});

test('a temporary refresh failure does not poison later retries', async () => {
  const mock = discordMock({
    refresh: (attempt) => attempt === 1 ? new Response('Temporary outage', { status: 503 }) : tokenResponse(),
  });
  const gate = createGate(mock.fetchMock);
  const request = await requestFor(gate);
  const failed = await gate.worker.fetch(request.clone(), gate.env);
  assert.equal(failed.status, 503);
  const retried = await gate.worker.fetch(request.clone(), gate.env);
  assert.equal(retried.status, 200);
  assert.equal((await savedSession(gate, retried)).refreshToken, 'test-new-refresh');
  assert.equal(mock.calls.refresh, 2);
});

test('a delayed role-only result does not overwrite a cookie at the refresh boundary', async () => {
  const clock = { now: Math.floor(Date.now() / 1000) * 1000 };
  const mock = discordMock({
    accessToken: 'test-old-access',
    member: () => {
      clock.now += 2000;
      return Response.json({ roles: ['test-allowed-role'] });
    },
  });
  const gate = createGate(mock.fetchMock, { clock });
  const payload = sessionPayload({ tokenExp: clock.now / 1000 + 301 });
  const response = await gate.worker.fetch(await requestFor(gate, '/auth/check', payload), gate.env);
  assert.equal(response.status, 200);
  assert.equal(mock.calls.refresh, 0);
  assert.equal(mock.calls.member, 1);
  assert.equal(response.headers.get('set-cookie'), null,
    'A role response that crossed the refresh boundary must not restore the older token.');
});

test('a slow report document never overwrites a concurrent authentication rotation', async () => {
  const clock = { now: Math.floor(Date.now() / 1000) * 1000 };
  let notifyDocumentLookup;
  const documentLookup = new Promise((resolve) => { notifyDocumentLookup = resolve; });
  let finishDocumentLookup;
  const heldDocumentLookup = new Promise((resolve) => { finishDocumentLookup = resolve; });
  let refreshes = 0;
  let memberLookups = 0;
  const gate = createGate(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/oauth2/token')) {
      refreshes += 1;
      assert.equal(init.body.get('refresh_token'), 'test-old-refresh');
      return tokenResponse();
    }
    if (url.endsWith('/users/@me/guilds/test-guild/member')) {
      memberLookups += 1;
      if (init.headers.authorization === 'Bearer test-old-access') {
        notifyDocumentLookup();
        return heldDocumentLookup;
      }
      assert.equal(init.headers.authorization, 'Bearer test-new-access');
      return Response.json({ roles: ['test-allowed-role'] });
    }
    throw new Error(`Unexpected synthetic request: ${url}`);
  }, { clock });
  const payload = sessionPayload({ tokenExp: clock.now / 1000 + 301 });
  const oldCookieDocument = await requestFor(gate, '/', payload);
  const oldCookieCheck = await requestFor(gate, '/auth/check', payload);
  const documentResponse = gate.worker.fetch(oldCookieDocument, gate.env);
  await documentLookup;
  clock.now += 2000;
  const authenticationResponse = await gate.worker.fetch(oldCookieCheck, gate.env);
  assert.equal(authenticationResponse.status, 200);
  assert.equal((await savedSession(gate, authenticationResponse)).refreshToken, 'test-new-refresh');
  finishDocumentLookup(Response.json({ roles: ['test-allowed-role'] }));
  const response = await documentResponse;
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /Test report/);
  assert.match(html, /\/auth\/guard\.js/);
  assert.equal(response.headers.get('set-cookie'), null,
    'Late document responses must not replace the cookie written by /auth/check.');
  assert.equal(refreshes, 1);
  assert.equal(memberLookups, 2);
});

for (const state of ['missing', 'expired']) {
  test(`${state} authentication cookie requires login without erasing a concurrent session`, async () => {
    const gate = createGate(() => { throw new Error('Unauthenticated checks must not call Discord.'); });
    const request = state === 'missing'
      ? new Request('https://gate.invalid/auth/check')
      : await requestFor(gate, '/auth/check', sessionPayload({ exp: Math.floor(Date.now() / 1000) - 1 }));
    const response = await gate.worker.fetch(request, gate.env);
    assert.equal(response.status, 401);
    assert.equal((await response.json()).reason, 'login_required');
    assert.equal(response.headers.get('set-cookie'), null);
  });
}

function guardHarness(script, fetchMock, { recovering = false, freePage = false, locks = { request: async (_name, callback) => callback() } } = {}) {
  const windowEvents = new Map();
  const documentEvents = new Map();
  const intervals = [];
  const timeouts = [];
  const navigations = [];
  let reloads = 0;
  const document = {
    hidden: false,
    documentElement: { innerHTML: 'original report', hasAttribute: (name) => (name === 'data-auth-recovery' && recovering) || (name === 'data-auth-free' && freePage) },
    addEventListener: (name, callback) => documentEvents.set(name, callback),
  };
  const window = {
    location: {
      pathname: '/report', search: '?test=1', replace: (url) => navigations.push(url),
      reload: () => { reloads += 1; },
    },
    addEventListener: (name, callback) => windowEvents.set(name, callback),
    setInterval: (callback) => { intervals.push(callback); return intervals.length; },
    setTimeout: (callback) => { timeouts.push(callback); return timeouts.length; },
  };
  vm.runInNewContext(script, {
    window, document, fetch: fetchMock, encodeURIComponent, AbortSignal,
    navigator: { locks },
    setTimeout: window.setTimeout, clearTimeout() {},
  }, { filename: 'access-guard.js' });
  return { windowEvents, documentEvents, intervals, timeouts, navigations, document, reloads: () => reloads };
}

async function flushGuardTimers(guard) {
  for (let step = 0; step < 10; step += 1) {
    await new Promise(setImmediate);
    while (guard.timeouts.length) guard.timeouts.shift()();
  }
}

for (const status of [401, 403, 503]) test(`public free guard stays masked without reload/login loop after ${status}`, async () => {
  const gate = createGate(() => { throw new Error('No provider request in guard fixture.'); });
  let requests = 0;
  const guard = guardHarness(gate.api.accessGuardScript({ ...gate.env, REPORT_PUBLIC_FREE: 'true' }), async () => {
    requests += 1; return new Response(null, { status });
  }, { freePage: true });
  await guard.windowEvents.get('pageshow')();
  assert.equal(requests, 1); assert.equal(guard.reloads(), 0); assert.deepEqual(guard.navigations, []);
  await guard.intervals[0](); assert.equal(requests, 2); assert.equal(guard.reloads(), 0);
});

test('public free guard promotes only after a successful serialized role check', async () => {
  const gate = createGate(() => { throw new Error('No provider request in guard fixture.'); });
  let status = 503;
  const guard = guardHarness(gate.api.accessGuardScript({ ...gate.env, REPORT_PUBLIC_FREE: 'true' }), async () => new Response(null, { status }), { freePage: true });
  await guard.windowEvents.get('pageshow')(); assert.equal(guard.reloads(), 0);
  status = 200;
  guard.documentEvents.get('visibilitychange')(); await flushGuardTimers(guard); assert.equal(guard.reloads(), 1);
  await guard.intervals[0](); assert.equal(guard.reloads(), 1); assert.deepEqual(guard.navigations, []);
});

test('fresh Cloud full document skips duplicate initial lookup but checks restored pages and intervals', async () => {
  const gate = createGate(() => { throw new Error('No provider request in guard fixture.'); });
  let requests = 0;
  const guard = guardHarness(gate.api.accessGuardScript({ ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true' }), async () => { requests += 1; return new Response(null, { status: 200 }); });
  await guard.windowEvents.get('pageshow')({ persisted: false }); assert.equal(requests, 0);
  await guard.windowEvents.get('pageshow')({ persisted: true }); assert.equal(requests, 1);
  await guard.intervals[0](); assert.equal(requests, 2);
});

test('Cloud free document with expired token recovers paid access via auth/check without leaking full assets', async () => {
  const mock = discordMock(); const gate = createGate(mock.fetchMock);
  const env = { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true', ASSETS: { fetch: async input => new Response(`<html><body>${String(input).includes('_free.html') ? 'MASKED-FREE' : 'PRIVATE-PAID'}</body></html>`) } };
  const before = await gate.worker.fetch(await requestFor(gate, '/'), env);
  const html = await before.text(); assert.match(html, /MASKED-FREE/); assert.match(html, /data-auth-free/); assert.match(html, /auth\/guard/); assert.doesNotMatch(html, /PRIVATE-PAID/);
  assert.equal(mock.calls.refresh, 0); assert.equal(mock.calls.member, 0);
  const check = await gate.worker.fetch(await requestFor(gate), env); assert.equal(check.status, 200);
  const after = await gate.worker.fetch(new Request('https://gate.invalid/', { headers: { cookie: check.headers.get('set-cookie').split(';', 1)[0] } }), env);
  assert.match(await after.text(), /PRIVATE-PAID/); assert.equal(mock.calls.refresh, 1); assert.equal(mock.calls.member, 2);
});

test('newly assigned role unlocks Cloud documents even when the signed session previously had no roles', async () => {
  const mock = discordMock({ accessToken: 'test-old-access' }); const gate = createGate(mock.fetchMock);
  const env = { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true' };
  const now = Math.floor(Date.now() / 1000);
  const response = await gate.worker.fetch(await requestFor(gate, '/', sessionPayload({ tokenExp: now + 3600, roleCheckedAt: now, roles: [] })), env);
  assert.equal(response.status, 200); assert.doesNotMatch(await response.text(), /data-auth-free/); assert.equal(mock.calls.member, 1);
});

test('first Cloud visit goes directly to Discord OAuth and a valid free member returns to the free report', async () => {
  const gate = createGate(async input => String(input).endsWith('/oauth2/token') ? tokenResponse() : Response.json({ roles: [], user: { id: 'test-free-user' } }));
  const env = { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_LOGIN_REQUIRED: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true' };
  const start = await gate.worker.fetch(new Request('https://gate.invalid/'), env);
  assert.equal(start.status, 302); assert.match(start.headers.get('location'), /^\/auth\/login/); assert.doesNotMatch(await start.text(), /purchase|whop/);
  const login = await gate.worker.fetch(new Request(new URL(start.headers.get('location'), 'https://gate.invalid')), env);
  const destination = new URL(login.headers.get('location'));
  assert.equal(destination.origin, 'https://discord.com'); assert.equal(destination.pathname, '/oauth2/authorize'); assert.equal(destination.searchParams.get('scope'), 'identify guilds.members.read');
  const state = await gate.api.createOAuthState('/mega_validation_report_latest.html', env.SESSION_SECRET);
  const callback = await gate.worker.fetch(new Request(`https://gate.invalid/auth/callback?code=synthetic-code&state=${encodeURIComponent(state)}`), env);
  assert.equal(callback.status, 302); assert.equal(callback.headers.get('location'), '/mega_validation_report_latest.html');
  const report = await gate.worker.fetch(new Request('https://gate.invalid/mega_validation_report_latest.html', { headers: { cookie: callback.headers.get('set-cookie').split(';', 1)[0] } }), env);
  assert.equal(report.status, 200); assert.match(await report.text(), /data-auth-free/);
});

test('Cloud free page requires reauthentication only after confirming a failed session, never a missing paid role', async () => {
  const gate = createGate(() => { throw new Error('No provider request in guard fixture.'); });
  const env = { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_LOGIN_REQUIRED: 'true' };
  const free = guardHarness(gate.api.accessGuardScript(env), async () => new Response(null, { status: 403 }), { freePage: true });
  await free.windowEvents.get('pageshow')(); assert.deepEqual(free.navigations, []); assert.equal(free.reloads(), 0);
  let calls = 0;
  const invalid = guardHarness(gate.api.accessGuardScript(env), async () => { calls += 1; return new Response(null, { status: 401 }); }, { freePage: true });
  const check = invalid.windowEvents.get('pageshow')(); await flushGuardTimers(invalid); await check;
  assert.equal(calls, 3); assert.deepEqual(invalid.navigations, ['/auth/login?return_to=%2Freport%3Ftest%3D1']); assert.equal(invalid.reloads(), 0);
});

test('concurrent fresh role checks share only the active request and recheck a later role revocation', async () => {
  let release; let lookups = 0; let roles = ['test-allowed-role'];
  const gate = createGate(async () => { lookups += 1; if (lookups === 1) await new Promise(resolve => { release = resolve; }); return Response.json({ roles }); });
  const now = Math.floor(Date.now() / 1000);
  const request = await requestFor(gate, '/', sessionPayload({ tokenExp: now + 3600, roleCheckedAt: now }));
  const env = { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true' };
  const pending = [gate.worker.fetch(request.clone(), env), gate.worker.fetch(request.clone(), env)];
  while (!release) await new Promise(setImmediate);
  await new Promise(setImmediate); assert.equal(lookups, 1); release();
  for (const response of await Promise.all(pending)) assert.doesNotMatch(await response.text(), /data-auth-free/);
  roles = [];
  const revoked = await gate.worker.fetch(request.clone(), env); assert.match(await revoked.text(), /data-auth-free/); assert.equal(lookups, 2);
});

for (const recovered of [true, false]) test(`short fresh-role rate limit retry ${recovered ? 'recovers' : 'fails closed'}`, async () => {
  let calls = 0;
  const gate = createGate(async () => {
    calls += 1;
    return recovered && calls === 2 ? Response.json({ roles: ['test-allowed-role'] }) : new Response(null, { status: 429, headers: { 'retry-after': '0.001' } });
  });
  const now = Math.floor(Date.now() / 1000);
  const response = await gate.worker.fetch(await requestFor(gate, '/', sessionPayload({ tokenExp: now + 3600, roleCheckedAt: now })), { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true' });
  const html = await response.text(); assert.equal(/data-auth-free/.test(html), !recovered); assert.equal(calls, 2);
});

test('fresh role lookup respects a numeric JSON retry interval without response headers', async () => {
  let calls = 0;
  const gate = createGate(async () => ++calls === 1 ? Response.json({ retry_after: 0.001 }, { status: 429 }) : Response.json({ roles: ['test-allowed-role'] }));
  const now = Math.floor(Date.now() / 1000);
  const response = await gate.worker.fetch(await requestFor(gate, '/', sessionPayload({ tokenExp: now + 3600 })), { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true' });
  assert.doesNotMatch(await response.text(), /data-auth-free/); assert.equal(calls, 2);
});

for (const retry_after of [60, '0.001', -1, null]) test(`invalid or long retry interval ${retry_after} cannot bypass fresh authorization`, async () => {
  let calls = 0;
  const gate = createGate(async () => { calls += 1; return Response.json({ retry_after }, { status: 429 }); });
  const now = Math.floor(Date.now() / 1000);
  const response = await gate.worker.fetch(await requestFor(gate, '/', sessionPayload({ tokenExp: now + 3600 })), { ...gate.env, REPORT_PUBLIC_FREE: 'true', REPORT_REQUIRE_FRESH_ROLE: 'true' });
  assert.match(await response.text(), /data-auth-free/); assert.equal(calls, 1);
});

test('open-page guard serializes page, visibility, and interval checks', async () => {
  const gate = createGate(() => { throw new Error('Worker fetch is not used by this test.'); });
  let resolveFetch;
  let requests = 0;
  const guard = guardHarness(gate.api.accessGuardScript(gate.env), () => {
    requests += 1;
    return new Promise((resolve) => { resolveFetch = resolve; });
  });
  const check = guard.windowEvents.get('pageshow')();
  guard.documentEvents.get('visibilitychange')();
  guard.intervals[0]();
  assert.equal(requests, 1, 'All guard event sources must share one running check.');
  resolveFetch(new Response(null, { status: 200 }));
  await check;
  assert.deepEqual(guard.navigations, []);
});

test('open-page guard confirms 401 and keeps the report when the retry succeeds', async () => {
  const gate = createGate(() => { throw new Error('Worker fetch is not used by this test.'); });
  let requests = 0;
  const guard = guardHarness(gate.api.accessGuardScript(gate.env), async () => {
    requests += 1;
    return new Response(null, { status: requests === 1 ? 401 : 200 });
  });
  const check = guard.windowEvents.get('pageshow')();
  // A short confirmation delay is simulated, so this test never sleeps or redirects a browser.
  await flushGuardTimers(guard);
  await check;
  assert.equal(requests, 2);
  assert.deepEqual(guard.navigations, []);
  assert.equal(guard.document.documentElement.innerHTML, 'original report');
});

test('open-page guard redirects only after repeated login-required responses', async () => {
  const gate = createGate(() => { throw new Error('Worker fetch is not used by this test.'); });
  let requests = 0;
  const guard = guardHarness(gate.api.accessGuardScript(gate.env), async () => {
    requests += 1;
    return new Response(null, { status: 401 });
  });
  const check = guard.windowEvents.get('pageshow')();
  await flushGuardTimers(guard);
  await check;
  assert.equal(requests, 3);
  assert.deepEqual(guard.navigations, ['/auth/login?return_to=%2Freport%3Ftest%3D1']);
});

test('open-page guard removes premium content when a real role denial is returned', async () => {
  const gate = createGate(() => { throw new Error('Worker fetch is not used by this test.'); });
  const guard = guardHarness(gate.api.accessGuardScript(gate.env), async () => new Response(null, { status: 403 }));
  await guard.windowEvents.get('pageshow')();
  assert.doesNotMatch(guard.document.documentElement.innerHTML, /original report/);
  assert.match(guard.document.documentElement.innerHTML, /アクセス権限がありません/);
  assert.deepEqual(guard.navigations, []);
  assert.equal(guard.reloads(), 0);
});

for (const status of [403, 503]) test(`Cloud guard reloads into public free page after ${status}`, async () => {
  const gate = createGate(() => { throw new Error('No Worker request in guard fixture.'); });
  const guard = guardHarness(gate.api.accessGuardScript({ ...gate.env, REPORT_PUBLIC_FREE: 'true' }), async () => new Response(null, { status }));
  await guard.windowEvents.get('pageshow')();
  assert.equal(guard.reloads(), 1);
  assert.deepEqual(guard.navigations, []);
  assert.equal(guard.document.documentElement.innerHTML, 'original report');
});

test('Cloud guard reloads into public free page when role check transport fails', async () => {
  const gate = createGate(() => { throw new Error('No Worker request in guard fixture.'); });
  const guard = guardHarness(gate.api.accessGuardScript({ ...gate.env, REPORT_PUBLIC_FREE: 'true' }), async () => { throw new Error('fixture-network-failure'); });
  await guard.windowEvents.get('pageshow')();
  assert.equal(guard.reloads(), 1);
  assert.deepEqual(guard.navigations, []);
});

for (const status of [200, 403]) {
  test(`authentication wait page reloads once after ${status} and does not continue checking`, async () => {
    const gate = createGate(() => { throw new Error('Worker fetch is not used by this test.'); });
    let requests = 0;
    const guard = guardHarness(gate.api.accessGuardScript(gate.env), async () => {
      requests += 1;
      return new Response(null, { status });
    }, { recovering: true });
    await guard.windowEvents.get('pageshow')();
    await guard.intervals[0]();
    assert.equal(guard.reloads(), 1);
    assert.equal(requests, 1);
    assert.deepEqual(guard.navigations, []);
  });
}

test('guard serializes authentication across two tabs through a shared Web Lock', async () => {
  const gate = createGate(() => { throw new Error('Worker fetch is not used by this test.'); });
  let lockTail = Promise.resolve();
  const locks = {
    request: (name, callback) => {
      assert.equal(name, 'report-gate-auth');
      const running = lockTail.then(callback);
      lockTail = running.catch(() => {});
      return running;
    },
  };
  let firstRelease;
  let requests = 0;
  const fetchMock = () => {
    requests += 1;
    return requests === 1 ? new Promise((resolve) => { firstRelease = resolve; }) : Promise.resolve(new Response(null, { status: 200 }));
  };
  const first = guardHarness(gate.api.accessGuardScript(gate.env), fetchMock, { locks });
  const second = guardHarness(gate.api.accessGuardScript(gate.env), fetchMock, { locks });
  const checks = [first.windowEvents.get('pageshow')(), second.windowEvents.get('pageshow')()];
  await new Promise(setImmediate);
  assert.equal(requests, 1);
  firstRelease(new Response(null, { status: 200 }));
  await Promise.all(checks);
  assert.equal(requests, 2);
  assert.deepEqual(first.navigations, []);
  assert.deepEqual(second.navigations, []);
});
