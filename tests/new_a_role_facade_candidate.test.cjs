const {test}=require('node:test'),a=require('node:assert/strict');
const {modules}=require('./helpers/cloud-worker-modules.cjs');
const {roleFacade:routeWithRelease}=modules().load('new-a-role-facade');
const roleFacade=(request,env,denial,services)=>routeWithRelease(request,env,denial,services,async()=>true);
const origin='https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
const env={CLOUD_OWNER_ONLY_ENABLED:'true',CLOUD_MEMBER_VIEW_ENABLED:'true',CLOUD_MEMBER_AUDIENCE:'role_only',DISCORD_GUILD_ID:'1479418833352785944',DISCORD_ALLOWED_ROLE_IDS:'1487089073385373828',SESSION_SECRET:'synthetic-test-key'};
const tieredStageOrigin = 'https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev';
const tieredStage = { ...env, CLOUD_MEMBER_AUDIENCE: 'tiered', CLOUD_MEMBER_STAGE_ORIGIN: tieredStageOrigin,
  PUBLIC_BASE_URL: tieredStageOrigin };
const stageRequest = (path, init) => new Request(tieredStageOrigin + path, init);
function setup(identity={subject:'123456789012345678',discord_authorized:true}){const calls=[];const f=k=>async(r,s,tier)=>{calls.push([k,s,tier]);return new Response(k)};return {calls,s:{identity:async()=>identity,document:f('document'),aggregate:f('aggregate'),preferences:f('preferences'),asset:f('asset')}}}
const req=(p,init)=>new Request(origin+p,init),deny=()=>new Response('owner only',{status:403});
test('owner and other original denials unchanged; default off',async()=>{const {s,calls}=setup();a.equal(await roleFacade(req('/weak_early_beta_latest.html'),env,null,s),null);for(const status of [302,401,503]){const d=new Response(null,{status});a.equal(await roleFacade(req('/weak_early_beta_latest.html'),env,d,s),d)}const d=deny();a.equal(await roleFacade(req('/weak_early_beta_latest.html'),{...env,CLOUD_MEMBER_VIEW_ENABLED:'false'},d,s),d);a.equal(calls.length,0)});
test('invalid or unavailable role verification refuses before data',async()=>{for(const id of [{subject:'123456789012345678'},{subject:'invalid',discord_authorized:false},{subject:123456789012345680,discord_authorized:false},{subject:'123456789012345678',reason:'discord_role_lookup_404',discord_authorized:false},{reason:'refresh_required'},{reason:'unavailable'}]){const {s,calls}=setup(id);a.ok([401,503].includes((await roleFacade(req('/weak_early_beta_latest.html'),env,deny(),s)).status));a.equal(calls.length,0)}});
test('raw/owner admin/notification/compute endpoints remain denied for both tiers',async()=>{for(const discord_authorized of [false,true]){const {s,calls}=setup({subject:'123456789012345678',discord_authorized});for(const p of ['/api/cloud/new-a-finite/input/manifest.json','/api/cloud/new-a-finite/preferences','/api/cloud/new-a-finite/notification-preferences','/api/cloud/new-a-view/compute','/api/cloud/push-config','/new-a-assets/owner-loader.js']){const d=deny();a.equal(await roleFacade(req(p),env,d,s),d)}a.equal(calls.length,0)}});
test('members receive their signed subject only; input subject and cross origin rejected',async()=>{for(const subject of ['123456789012345678','223456789012345678']){const {s,calls}=setup({subject,discord_authorized:true});const res=await roleFacade(req('/api/cloud/new-a-view/analytics.json'),env,deny(),s);a.equal(res.status,200);a.equal(res.headers.get('cache-control'),'private, no-store');a.deepEqual(calls,[['aggregate',subject,'premium']]);a.equal((await roleFacade(req('/api/cloud/new-a-view/analytics.json?subject=999'),env,deny(),s)).status,400);a.equal((await roleFacade(req('/api/cloud/new-a-view/preferences',{method:'PUT',headers:{origin:'https://evil.test'}}),env,deny(),s)).status,403)}});
test('missing production adapters fails closed; HEAD never returns body; exact policy',async()=>{a.equal((await roleFacade(req('/weak_early_beta_latest.html'),env,deny(),undefined)).status,503);const {s}=setup();a.equal(await (await roleFacade(req('/weak_early_beta_latest.html',{method:'HEAD'}),env,deny(),s)).text(),'');a.equal((await roleFacade(req('/weak_early_beta_latest.html'),{...env,DISCORD_ALLOWED_ROLE_IDS:'other'},deny(),s)).status,503)});

test('the normal entry shows the member front page and access checks return no private data', async () => {
  const { s, calls } = setup();
  a.equal((await roleFacade(req('/'), env, deny(), s)).status, 200);
  a.deepEqual(calls, [['document', '123456789012345678', 'premium']]);

  const session = '/api/cloud/new-a-view/session';
  const response = await roleFacade(req(session), env, deny(), s);
  a.equal(response.status, 204);
  a.equal(await response.text(), '');
  a.equal(response.headers.get('cache-control'), 'private, no-store');
  a.equal(response.headers.get('x-cloud-member-access'), 'premium');
  const tag = response.headers.get('x-cloud-member-session');
  a.match(tag, /^[0-9a-f]{64}$/);
  const sameAccount = await roleFacade(req(session), env, deny(), s);
  a.equal(sameAccount.headers.get('x-cloud-member-session'), tag);
  const otherAccount = setup({ subject: '223456789012345678', discord_authorized: true });
  const other = await roleFacade(req(session), env, deny(), otherAccount.s);
  a.notEqual(other.headers.get('x-cloud-member-session'), tag);
  a.equal((await roleFacade(req(session), { ...env, SESSION_SECRET: '' }, deny(), s)).status, 503);
  const settings = '/api/cloud/new-a-view/preferences';
  const oldTab = req(settings, { method: 'PUT', headers: { 'x-cloud-member-session': tag } });
  a.equal((await roleFacade(oldTab, env, deny(), otherAccount.s)).status, 403);
  a.deepEqual(otherAccount.calls, []);
  a.equal(calls.length, 1);

  const revoked = setup({ subject: '123456789012345678', discord_authorized: false });
  const free = await roleFacade(stageRequest(session), tieredStage, deny(), revoked.s);
  a.equal(free.status, 204);
  a.equal(free.headers.get('x-cloud-member-access'), 'free');
  a.notEqual(free.headers.get('x-cloud-member-session'), tag);
  const history = '/api/cloud/new-a-view/history.json';
  const stale = await roleFacade(stageRequest(history, { headers: { 'x-cloud-member-session': tag } }), tieredStage, deny(), revoked.s);
  a.equal(stale.status, 403);
  a.deepEqual(await stale.json(), { error: 'member_session_changed' });
  const current = await roleFacade(stageRequest(history, { headers: { 'x-cloud-member-session': free.headers.get('x-cloud-member-session') } }), tieredStage, deny(), revoked.s);
  a.equal(current.status, 200);
  a.deepEqual(revoked.calls, [['aggregate', '123456789012345678', 'free']]);
  a.equal((await roleFacade(req(session + '?subject=123'), env, deny(), s)).status, 404);
  const anonymousDenial = new Response(null, { status: 401 });
  a.equal(await roleFacade(req(session), env, anonymousDenial, s), anonymousDenial);
});

test('isolated stage only accepts the configured HTTPS OAuth origin', async () => {
  const { s, calls } = setup();
  const stageOrigin = 'https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev';
  const path = '/api/cloud/new-a-view/session';
  const stage = { ...env, CLOUD_MEMBER_STAGE_ORIGIN: stageOrigin, PUBLIC_BASE_URL: stageOrigin };
  a.equal((await roleFacade(new Request(stageOrigin + path), env, deny(), s)).status, 403);
  a.equal((await roleFacade(new Request(stageOrigin + path), stage, deny(), s)).status, 204);
  a.equal((await roleFacade(req(path), stage, deny(), s)).status, 403);
  a.equal((await roleFacade(new Request(stageOrigin + path), { ...stage, PUBLIC_BASE_URL: origin }, deny(), s)).status, 403);
  a.equal((await roleFacade(new Request(stageOrigin + path, { headers: { host: new URL(origin).host } }), stage, deny(), s)).status, 403);
  const arbitrary = 'https://cloud-stage.example';
  a.equal((await roleFacade(new Request(arbitrary + path), { ...stage, CLOUD_MEMBER_STAGE_ORIGIN: arbitrary, PUBLIC_BASE_URL: arbitrary }, deny(), s)).status, 403);
  a.equal(calls.length, 0);
});

test('the release check can restrict both independently verified access tiers', async () => {
  const { s, calls } = setup();
  const path = '/weak_early_beta_latest.html';
  const denial = deny();
  const seen = [];
  const allows = async (subject, tier) => { seen.push([subject, tier]); return false; };
  a.equal(await routeWithRelease(req(path), env, denial, s), denial);
  a.equal(await routeWithRelease(req(path), env, denial, s, allows), denial);
  a.equal(await routeWithRelease(req(path), env, null, s, allows), null);
  await routeWithRelease(req(path), env, denial, setup({ subject: '987654321012345678', discord_authorized: false }).s, allows);
  a.deepEqual(seen, [['123456789012345678', 'premium'], ['987654321012345678', 'free']]);
  a.deepEqual(calls, []);
});

test('Free reaches shared history and aggregate analytics after explicit production opt-in', async () => {
  const subject = '123456789012345678';
  const { s, calls } = setup({ subject, discord_authorized: false });
  const observations = [];
  const observe = (res, actor, role) => observations.push([res.status, actor, role]);
  const tiered = { ...env, CLOUD_MEMBER_AUDIENCE: 'tiered' };
  const call = (path, init) => routeWithRelease(req(path, init), tiered, deny(), s, async () => true, observe);
  for (const path of ['/', '/weak_early_beta_latest.html', '/weak_early_beta_analytics.html']) {
    a.equal((await call(path)).status, 200);
  }
  a.equal((await call('/weak_early_beta_settings.html')).status, 403);
  a.equal((await call('/new-a-assets/member-loader.js')).status, 200);
  a.equal((await call('/new-a-assets/reference-analytics.js')).status, 200);
  a.equal((await call('/new-a-assets/member-settings.js')).status, 403);
  a.equal((await call('/api/cloud/new-a-view/history.json?page=2')).status, 200);
  const ref = '/api/cloud/new-a-view/reference.json?item=';
  const session = await call('/api/cloud/new-a-view/session');
  const token = session.headers.get('x-cloud-member-session');
  const signed = { headers: { 'x-cloud-member-session': token } };
  for (const item of ['analytics.overview.return_priority', 'analytics.daily.defensive']) {
    a.equal((await call(ref + item)).status, 403);
    a.equal((await call(ref + item, signed)).status, 200);
  }
  for (const item of ['history.index', 'history.1', 'data.analytics', 'dashboard.return_priority',
    'analytics.return_priority', 'analytics.daily.invalid', 'analytics.overview.medium%0a']) {
    a.deepEqual(await (await call(ref + item, signed)).json(), { error: 'role_required' });
  }
  for (const endpoint of ['dashboard.json', 'analytics.json', 'chart.json', 'personal.json', 'preferences']) {
    const res = await call('/api/cloud/new-a-view/' + endpoint, { headers: { 'x-cloud-member-access': 'premium' } });
    a.equal(res.status, 403);
    a.deepEqual(await res.json(), { error: 'role_required' });
  }
  a.equal((await call('/api/cloud/new-a-view/preferences', { method: 'PUT' })).status, 403);
  a.deepEqual(calls, [
    ...Array.from({ length: 3 }, () => ['document', subject, 'free']),
    ...Array.from({ length: 2 }, () => ['asset', subject, 'free']),
    ...Array.from({ length: 3 }, () => ['aggregate', subject, 'free']),
  ]);
  a.ok(observations.every(([, actor, role]) => actor === subject && role === 'denied'));
  a.ok(observations.some(([status]) => status === 200));
  a.ok(observations.some(([status]) => status === 403));
  const paid = setup();
  a.equal((await roleFacade(req('/api/cloud/new-a-view/dashboard.json'), env, deny(), paid.s)).status, 200);
  a.deepEqual(paid.calls, [['aggregate', subject, 'premium']]);
});

test('private aggregate routes reject unsupported and repeated query parameters', async () => {
  const { s, calls } = setup();
  for (const path of ['/history.json?page=1&page=2', '/analytics.json?page=1', '/personal.json?page=1']) {
    a.equal((await roleFacade(req('/api/cloud/new-a-view' + path), env, deny(), s)).status, 400);
  }
  a.equal(calls.length, 0);
});

test('an expired member document can use ordinary Discord login without opening the API', async () => {
  const { s, calls } = setup({ reason: 'refresh_required' });
  const navigation = { headers: { 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document' } };
  const document = await roleFacade(req('/weak_early_beta_analytics.html', navigation), env, deny(), s);
  a.equal(document.status, 302);
  a.equal(document.headers.get('location'), '/auth/login?return_to=%2Fweak_early_beta_analytics.html');
  const api = await roleFacade(req('/api/cloud/new-a-view/analytics.json', navigation), env, deny(), s);
  a.equal(api.status, 401);
  a.equal(calls.length, 0);
});
