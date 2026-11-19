const {test}=require('node:test'),a=require('node:assert/strict');
const {roleFacade:routeWithRelease}=require('../weak-early-beta-gate/src/new-a-role-facade.ts');
const roleFacade=(request,env,denial,services)=>routeWithRelease(request,env,denial,services,async()=>true);
const origin='https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
const env={CLOUD_OWNER_ONLY_ENABLED:'true',CLOUD_MEMBER_VIEW_ENABLED:'true',DISCORD_GUILD_ID:'1479418833352785944',DISCORD_ALLOWED_ROLE_IDS:'1487089073385373828',SESSION_SECRET:'synthetic-test-key'};
function setup(identity={subject:'123456789012345678',discord_authorized:true}){const calls=[];const f=k=>async(r,s)=>{calls.push([k,s]);return new Response(k)};return {calls,s:{identity:async()=>identity,document:f('document'),aggregate:f('aggregate'),preferences:f('preferences'),asset:f('asset')}}}
const req=(p,init)=>new Request(origin+p,init),deny=()=>new Response('owner only',{status:403});
test('owner and other original denials unchanged; default off',async()=>{const {s,calls}=setup();a.equal(await roleFacade(req('/weak_early_beta_latest.html'),env,null,s),null);for(const status of [302,401,503]){const d=new Response(null,{status});a.equal(await roleFacade(req('/weak_early_beta_latest.html'),env,d,s),d)}const d=deny();a.equal(await roleFacade(req('/weak_early_beta_latest.html'),{...env,CLOUD_MEMBER_VIEW_ENABLED:'false'},d,s),d);a.equal(calls.length,0)});
test('role session invalid/revoked/unavailable refuses before data',async()=>{for(const id of [{subject:'123456789012345678',discord_authorized:false},{reason:'refresh_required'},{reason:'unavailable'}]){const {s,calls}=setup(id);a.ok([401,403,503].includes((await roleFacade(req('/weak_early_beta_latest.html'),env,deny(),s)).status));a.equal(calls.length,0)}});
test('raw/owner admin/notification/compute endpoints remain denied',async()=>{const {s,calls}=setup();for(const p of ['/api/cloud/new-a-finite/input/manifest.json','/api/cloud/new-a-finite/preferences','/api/cloud/new-a-finite/notification-preferences','/api/cloud/new-a-view/compute','/api/cloud/push-config','/new-a-assets/owner-loader.js']){const d=deny();a.equal(await roleFacade(req(p),env,d,s),d)}a.equal(calls.length,0)});
test('members receive their signed subject only; input subject and cross origin rejected',async()=>{for(const subject of ['123456789012345678','223456789012345678']){const {s,calls}=setup({subject,discord_authorized:true});const res=await roleFacade(req('/api/cloud/new-a-view/analytics.json'),env,deny(),s);a.equal(res.status,200);a.equal(res.headers.get('cache-control'),'private, no-store');a.deepEqual(calls,[['aggregate',subject]]);a.equal((await roleFacade(req('/api/cloud/new-a-view/analytics.json?subject=999'),env,deny(),s)).status,400);a.equal((await roleFacade(req('/api/cloud/new-a-view/preferences',{method:'PUT',headers:{origin:'https://evil.test'}}),env,deny(),s)).status,403)}});
test('missing production adapters fails closed; HEAD never returns body; exact policy',async()=>{a.equal((await roleFacade(req('/weak_early_beta_latest.html'),env,deny(),undefined)).status,503);const {s}=setup();a.equal(await (await roleFacade(req('/weak_early_beta_latest.html',{method:'HEAD'}),env,deny(),s)).text(),'');a.equal((await roleFacade(req('/weak_early_beta_latest.html'),{...env,DISCORD_ALLOWED_ROLE_IDS:'other'},deny(),s)).status,503)});

test('the normal entry shows the member front page and access checks return no private data', async () => {
  const { s, calls } = setup();
  a.equal((await roleFacade(req('/'), env, deny(), s)).status, 200);
  a.deepEqual(calls, [['document', '123456789012345678']]);

  const session = '/api/cloud/new-a-view/session';
  const response = await roleFacade(req(session), env, deny(), s);
  a.equal(response.status, 204);
  a.equal(await response.text(), '');
  a.equal(response.headers.get('cache-control'), 'private, no-store');
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
  a.equal((await roleFacade(req(session), env, deny(), revoked.s)).status, 403);
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

test('the release check can restrict only an already verified member', async () => {
  const { s, calls } = setup();
  const path = '/weak_early_beta_latest.html';
  const denial = deny();
  const seen = [];
  const allows = async subject => { seen.push(subject); return false; };
  a.equal(await routeWithRelease(req(path), env, denial, s), denial);
  a.equal(await routeWithRelease(req(path), env, denial, s, allows), denial);
  a.equal(await routeWithRelease(req(path), env, null, s, allows), null);
  await routeWithRelease(req(path), env, denial, setup({ subject: '987654321012345678', discord_authorized: false }).s, allows);
  a.deepEqual(seen, ['123456789012345678']);
  a.deepEqual(calls, []);
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
