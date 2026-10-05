const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const { Miniflare, convertV4MiniflareOptions } = require('../weak-early-beta-gate/node_modules/miniflare');
const { buildSync } = require('../weak-early-beta-gate/node_modules/esbuild');

// Exercise workerd's Request implementation, which a Node fetch mock cannot
// reproduce. All credentials, owners, roles and upstream responses are synthetic.
test('Cloud role lookup works in the isolated workerd runtime', { timeout: 30000 }, async t => {
  const requests = [];
  const upstream = http.createServer((request, response) => {
    requests.push({ method: request.method, path: request.url });
    if (request.headers.authorization === 'Bearer synthetic-redirect') {
      response.writeHead(302, { location: '/followed' });
      response.end(JSON.stringify({ roles: ['synthetic-allowed'] }));
      return;
    }
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({ roles: ['synthetic-allowed'] }));
  });
  await new Promise(resolve => upstream.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => upstream.close(resolve)));

  const authoritySource = path.resolve(__dirname, '../weak-early-beta-gate/src/cloud-role-authority.ts').replace(/\\/g, '/');
  const script = buildSync({
    stdin: {
      contents: `
        import { cloudReportRole } from ${JSON.stringify(authoritySource)};
        export { CloudRoleAuthority } from ${JSON.stringify(authoritySource)};
        export default {
          async fetch(request, env) {
            const mode = new URL(request.url).searchParams.get('mode');
            if (mode === 'unsupported') {
              try {
                await fetch(env.DISCORD_API_BASE + '/probe', {
                  cache: 'no-store', redirect: 'error',
                  signal: AbortSignal.timeout(10000),
                });
                return Response.json({ unexpectedSuccess: true });
              } catch (error) {
                return Response.json({ errorName: error.name });
              }
            }
            return Response.json(await cloudReportRole(
              env, 'synthetic-owner-' + mode, 'synthetic-' + mode, '/auth/check',
            ));
          }
        };
      `,
      sourcefile: 'synthetic-cloud-role-runtime.ts',
      loader: 'ts',
      resolveDir: __dirname,
    },
    bundle: true,
    format: 'esm',
    platform: 'neutral',
    external: ['cloudflare:workers'],
    write: false,
  }).outputFiles[0].text;

  const runtime = new Miniflare(convertV4MiniflareOptions({
    modules: true,
    script,
    compatibilityDate: '2026-06-07',
    bindings: {
      DISCORD_API_BASE: `http://127.0.0.1:${upstream.address().port}`,
      DISCORD_CLIENT_ID: 'synthetic-client',
      DISCORD_GUILD_ID: 'synthetic-guild',
      DISCORD_ALLOWED_ROLE_IDS: 'synthetic-allowed',
      SESSION_SECRET: 'synthetic-session-encryption-secret',
    },
    durableObjects: { CLOUD_ROLE_AUTHORITY: { className: 'CloudRoleAuthority', useSQLite: true } },
    durableObjectsPersist: false,
  }));
  t.after(() => runtime.dispose());
  const check = async mode => {
    const response = await runtime.dispatchFetch(`https://synthetic-worker.invalid/?mode=${mode}`);
    assert.equal(response.status, 200);
    return response.json();
  };

  await t.test('unsupported redirect:error fails before any upstream request', async () => {
    assert.deepEqual(await check('unsupported'), { errorName: 'TypeError' });
    assert.equal(requests.length, 0);
  });

  await t.test('the real authority accepts a permitted role from a manual GET', async () => {
    const result = await check('paid');
    assert.equal(result.status, 'paid');
    assert.equal(result.source, 'upstream');
    assert.equal(result.validUntil, result.checkedAt + 90000);
    assert.deepEqual(requests, [{ method: 'GET', path: '/users/@me/guilds/synthetic-guild/member' }]);
  });

  await t.test('the real authority rejects a redirect without following or trusting its roles', async () => {
    const before = requests.length;
    const result = await check('redirect');
    assert.equal(result.status, 'unavailable');
    assert.equal(result.reason, 'discord_role_lookup_302');
    assert.equal(result.retryAfterSeconds, 5);
    assert.equal(requests.length, before + 1);
    assert.equal(requests.some(request => request.path === '/followed'), false);
    assert.equal((await check('redirect')).status, 'unavailable');
    assert.equal(requests.length, before + 1);
  });
});
