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
assert.ok(tsPath, 'Install one gate package before running the membership tests.');
const ts = require(tsPath);

// Load the actual Worker modules with synthetic credentials and no network.
// Only relative imports under the Cloud source directory are permitted.
function createModules({ fetchMock, clock } = {}) {
  const sourceRoot = path.join(repoRoot, 'weak-early-beta-gate', 'src');
  const cache = new Map();
  function load(name, parent = sourceRoot) {
    const filename = path.resolve(parent, `${name.replace(/\.ts$/, '')}.ts`);
    assert.ok(filename.startsWith(`${sourceRoot}${path.sep}`), 'Test imports must remain inside the Cloud gate.');
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    let source = fs.readFileSync(filename, 'utf8');
    if (path.basename(filename) === 'shared-report-gate.ts') source += '\nexport const __test = { createSession };';
    const compiled = ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    }).outputText;
    const sandbox = {
      exports: module.exports, module,
      require: (specifier) => {
        if (specifier === 'cloudflare:workers') return require('./helpers/cloud-role-authority.cjs').runtime;
        assert.ok(specifier.startsWith('.'), `Unexpected dependency: ${specifier}`);
        return load(specifier, path.dirname(filename));
      },
      Request, Response, Headers, URL, URLSearchParams, AbortSignal,
      TextEncoder, TextDecoder, Uint8Array, crypto: webcrypto, atob, btoa,
      fetch: fetchMock || (() => { throw new Error('Network access is forbidden in membership tests.'); }),
      Date: class extends Date {
        constructor(...args) { super(...(args.length ? args : [clock ? clock.now : Date.now()])); }
        static now() { return clock ? clock.now : Date.now(); }
      },
      console: { error() {}, log() {}, warn() {} },
      setTimeout, clearTimeout,
    };
    vm.runInNewContext(compiled, sandbox, { filename });
    return module.exports;
  }
  return { load };
}

const OWNER = '111111111111111111';
const OTHER = '222222222222222222';
const routes = ['/', '/report', '/weak_early_beta_latest.html', '/weak_early_beta_guide.html', '/weak_early_beta_latest_free.html', '/weak_early_beta_data_free_latest_aaaaaaaaaaaaaaaa_0000.json', '/weak_early_beta_data_full_latest_aaaaaaaaaaaaaaaa_0000.json', '/api/cloud/preferences', '/api/cloud/push/config', '/report-assets/cloud-logo-light.png', '/weak-early-beta-scenarios.js', '/purchase', '/unexpected.csv'];
function fixture() {
  let assetReads = 0;
  const modules = createModules();
  const worker = modules.load('./index').default;
  const gate = modules.load('./cloud-owner-only').ownerOnlyGate;
  const session = modules.load('./shared-report-gate').__test.createSession;
  const env = { CLOUD_OWNER_ONLY_ENABLED: 'true', CLOUD_OWNER_DISCORD_ID: OWNER,
    SESSION_SECRET: 'synthetic-only-encryption-secret', DISCORD_CLIENT_ID: 'test-client', DISCORD_GUILD_ID:'test-guild', DISCORD_ALLOWED_ROLE_IDS:'allowed',
    ASSETS: { fetch: async () => { assetReads++; return new Response('PRIVATE ASSET'); } } };
  const request = async (route, sub, extra={}) => {
    const headers = {};
    if(sub) { const now=Math.floor(Date.now()/1000); const cookie=await session({sub,accessToken:'synthetic-access',refreshToken:'synthetic-refresh',exp:now+3600,tokenExp:now+3600,roles:['allowed'],roleCheckedAt:now,...extra},env.SESSION_SECRET); headers.cookie='__Host-report_gate_session='+encodeURIComponent(cookie); }
    return new Request('https://cloud.invalid'+route,{headers});
  };
  return {worker,gate,env,request,assetReads:()=>assetReads};
}
for (const route of routes) {
 test('owner-only rejects other signed account before downstream '+route,async()=>{const f=fixture();const r=await f.worker.fetch(await f.request(route,OTHER),f.env);assert.equal(r.status,403);assert.equal(f.assetReads(),0);assert.doesNotMatch(await r.text(),/PRIVATE ASSET/);assert.equal(r.headers.get('cache-control'),'private, no-store');});
 test('owner-only rejects anonymous '+route,async()=>{const f=fixture();const r=await f.worker.fetch(await f.request(route),f.env);assert.ok([302,401].includes(r.status));assert.equal(f.assetReads(),0);});
 test('owner identity passes entrance '+route,async()=>{const f=fixture();assert.equal(await f.gate(await f.request(route,OWNER),f.env),null);});
}
test('owner can refresh with expired OAuth token but valid signed session',async()=>{const f=fixture();assert.equal(await f.gate(await f.request('/auth/check',OWNER,{tokenExp:0}),f.env),null);});
test('expired signed owner session is rejected',async()=>{const f=fixture();assert.equal((await f.gate(await f.request('/api/cloud/preferences',OWNER,{exp:0}),f.env)).status,401);});
test('forged cookie cannot identify owner',async()=>{const f=fixture();const r=await f.gate(new Request('https://cloud.invalid/api/cloud/preferences',{headers:{cookie:'__Host-report_gate_session=v2.fake.fake','x-user-id':OWNER}}),f.env);assert.equal(r.status,401);});
test('nonowner auth/check 401 evicts old free-page guard without fetching roles',async()=>{const f=fixture();const r=await f.worker.fetch(await f.request('/auth/check',OTHER),f.env);assert.equal(r.status,401);assert.equal(r.headers.get('x-cloud-private'),'true');assert.equal((await r.json()).reason,'owner_only');});
test('missing or invalid owner and invalid enabled mode fail shut',async()=>{for(const change of [{CLOUD_OWNER_DISCORD_ID:undefined},{CLOUD_OWNER_DISCORD_ID:'bad'},{CLOUD_OWNER_ONLY_ENABLED:'tru'}]){const f=fixture();Object.assign(f.env,change);assert.equal((await f.worker.fetch(await f.request('/'),f.env)).status,503);assert.equal(f.assetReads(),0);}});
test('off restores original public free bundle; no account or role mutation',async()=>{const f=fixture();f.env.CLOUD_OWNER_ONLY_ENABLED='false';const r=await f.worker.fetch(await f.request('/weak_early_beta_data_free_latest_aaaaaaaaaaaaaaaa_0000.json'),f.env);assert.equal(r.status,200);assert.equal(await r.text(),'PRIVATE ASSET');});
test('only content-free public routes bypass entrance',async()=>{const f=fixture();for(const path of ['/auth/login','/auth/callback','/auth/logout','/auth/guard.js','/healthz','/robots.txt'])assert.equal(await f.gate(await f.request(path),f.env),null);assert.equal((await f.gate(await f.request('/private'),f.env)).status,403);});
test('owner free bundle reaches asset binding; other paths keep original inner authorization',async()=>{const f=fixture();const r=await f.worker.fetch(await f.request('/weak_early_beta_data_free_latest_aaaaaaaaaaaaaaaa_0000.json',OWNER),f.env);assert.equal(r.status,200);assert.equal(f.assetReads(),1);});
test('new guard recognizes private response before free-page fallback',()=>{const s=fs.readFileSync(path.join(repoRoot,'report-gate/src/index.ts'),'utf8');assert.ok(s.indexOf("response.headers.get('x-cloud-private')")<s.indexOf('if (freePage${'));assert.match(s,/window.location.replace\('\/private'\)/);});
