// Synthetic credentials/data only. No listener, provider connection or private input.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{webcrypto,createHash}=require('node:crypto'),{DatabaseSync}=require('node:sqlite');
const repo=path.resolve(__dirname,'..'),gate=path.join(repo,'weak-early-beta-gate'),source=path.join(gate,'src');
const tsFile=[path.join(gate,'node_modules/typescript/lib/typescript.js'),process.env.NEW_A_TEST_TYPESCRIPT].find(p=>p&&fs.existsSync(p));assert(tsFile,'Install gate dependencies, or explicitly provide the local review TypeScript');const ts=require(tsFile);
const sha=s=>createHash('sha256').update(s).digest('hex'),OWNER='100000000000000001',OTHER='100000000000000002';
function modules(log=()=>{}, entry='./index'){const cache=new Map(),mock={
 './shared-report-gate':{reportVerifiedSessionSubject:async r=>r.headers.get('x-synthetic-subject')||undefined,reportIdentity:async(r,e,fresh)=>{assert.equal(fresh,true);const refresh=r.headers.get('x-synthetic-refresh')==='yes';return{subject:r.headers.get('x-synthetic-subject')||undefined,discord_authorized:!refresh&&r.headers.get('x-synthetic-role')==='yes',...(refresh?{reason:'refresh_required'}:{})};},default:{fetch:async()=>new Response('legacy-auth')}},
 './operational-build.generated':{operationalBuild:{source_commit:'1'.repeat(40),build_input_sha256:'2'.repeat(64),target:{worker:'tentei-kyokuchi-cloud',database:'tentei-cloud-settings'}}},
 './cloud-api':{cloudMemberId:async s=>'cloud_'+sha('cloud-member:'+s),cloudApi:async()=>Response.json({legacy:true})},'./cloud-role-authority':{cloudReportRole:async()=>({status:'paid'}),CloudRoleAuthority:class{}},'./cloud-push-scheduler':{runScheduledPersonalNotifications:async()=>({status:'disabled'})}};
 function load(name,parent=source){if(mock[name])return mock[name];let file=path.resolve(parent,name.replace(/\.ts$/,'')+'.ts');assert(file.startsWith(source+path.sep));if(!fs.existsSync(file)&&process.env.NEW_A_TEST_BASELINE_ROOT)file=path.resolve(process.env.NEW_A_TEST_BASELINE_ROOT,'weak-early-beta-gate/src',path.relative(source,file));if(cache.has(file))return cache.get(file).exports;const module={exports:{}};cache.set(file,module);const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;vm.runInNewContext(code,{module,exports:module.exports,require:n=>load(n,path.dirname(file)),crypto:webcrypto,Request,Response,Headers,URL,TextEncoder,TextDecoder,setTimeout,clearTimeout,console:{log}},{filename:file});return module.exports;}const loaded=load(entry);return loaded.default??loaded;}
function fixture(){const sql=new DatabaseSync(':memory:');sql.exec(fs.readFileSync(path.join(gate,'schema/new-a-private.sql'),'utf8'));sql.exec('CREATE TABLE cloud_member_preferences(member_id TEXT PRIMARY KEY,preferences_json TEXT,updated_at TEXT)');let reads=0;const db={prepare(query){reads++;return{bind(...args){return{first:async()=>sql.prepare(query).get(...args)||null,run:async()=>({success:true,meta:{changes:Number(sql.prepare(query).run(...args).changes)}})};}};}};const env={CLOUD_OWNER_ONLY_ENABLED:'true',CLOUD_OWNER_DISCORD_ID:OWNER,SESSION_SECRET:'synthetic-session-secret',CLOUD_DB:db,ASSETS:{fetch:async()=>new Response('// synthetic asset')}};const logs=[],app=modules(event=>logs.push(event));return{sql,env,app,logs,get reads(){return reads;},close:()=>sql.close()};}
function request(url,subject=OWNER,role=true,init={}){return new Request('https://synthetic.invalid'+url,{...init,headers:{...(subject?{'x-synthetic-subject':subject}:{}),'x-synthetic-role':role?'yes':'no',...init.headers}});}
const ownerDocument = '/weak_early_beta_latest.html';
const ownerAccess = '/api/cloud/new-a-finite/access';

test('owner notification settings patch only the two consent fields in the approved profile',async t=>{
 const f=fixture();t.after(f.close);const member='cloud_'+sha('cloud-member:'+OWNER);
 const prior={max_price:1234.5,exit_endpoint:'d5_close',base_shares:300,cost_percent:1.25,
  notifications:{new_detection:false,reminder:false,result:true}};
 const select=f.sql.prepare('SELECT preferences_json FROM cloud_member_preferences WHERE member_id=?');
 f.sql.prepare('INSERT INTO cloud_member_preferences(member_id,preferences_json) VALUES (?,?)').run(member,JSON.stringify(prior));
 const route='/api/cloud/new-a-finite/notification-preferences';
 const config={...f.env,CLOUD_PUSH_MODE:'new_a_owner_registration',CLOUD_PUSH_REGISTRATION_ENABLED:'true',
  CLOUD_PUSH_TEST_MEMBER_ID:member,CLOUD_PUSH_AUDIENCE:'paid',CLOUD_PUSH_MEMBERSHIP_POLICY:'whop_managed_discord_role'};
 const desired={new_detection:true,reminder:false};
 const put=(subject=OWNER,role=true,body={notifications:desired},origin='https://synthetic.invalid')=>request(route,subject,role,
  {method:'PUT',headers:{origin,'content-type':'application/json'},body:JSON.stringify(body)});
 const closed=await f.app.fetch(request(route),f.env);
 assert.deepEqual(await closed.json(),{ok:true,notifications:{new_detection:false,reminder:false},available:false});
 assert.equal((await f.app.fetch(put(),f.env)).status,503);
 const beforeRefusal=f.reads;
 assert.equal((await f.app.fetch(put(null),config)).status,401);
 const nonowner=await f.app.fetch(put(OTHER),config);
 assert.equal(nonowner.status,403);
 assert.equal(nonowner.headers.get('x-cloud-private'),'true');
 assert.equal((await f.app.fetch(put(OWNER,false),config)).status,403);
 assert.equal(f.reads,beforeRefusal);
 assert.equal((await f.app.fetch(put(OWNER,true,{notifications:desired,max_price:1}),config)).status,400);
 assert.equal((await f.app.fetch(put(OWNER,true,{notifications:desired},'https://other.invalid'),config)).status,403);
 assert.equal(select.get(member).preferences_json,JSON.stringify(prior));
 const update=await f.app.fetch(put(),config);
 assert.equal(update.status,200);
 assert.deepEqual(await update.json(),{ok:true,notifications:desired,available:true});
 assert.deepEqual(JSON.parse(select.get(member).preferences_json),{...prior,notifications:{...desired,result:true}});
 assert.equal(f.sql.prepare('SELECT count(*) AS n FROM new_a_finite_trial_preferences').get().n,0);
});
const observedVersion = {
 id: '12345678-1234-1234-1234-123456789abc',
 tag: '1'.repeat(40),
 timestamp: '2026-01-01T00:00:00Z',
};
function normalOwnerRequest(route, ...args) {
 return new Request('https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev'+route, request(route,...args));
}
const ownerLogs = f => f.logs.filter(event=>event.operation==='cloud_owner_response_observed');
test('normal final owner responses produce minimal provider audit events without changing the response', async t=>{
 const f=fixture();t.after(f.close);
 const env={...f.env,CLOUD_VERSION_METADATA:observedVersion};
 const auth={headers:{cookie:'synthetic-cookie-value'}};
 const doc=await f.app.fetch(normalOwnerRequest(ownerDocument,OWNER,true,auth),env);
 assert.equal(f.reads,1);
 const api=await f.app.fetch(normalOwnerRequest(ownerAccess,OWNER,true,auth),env);
 assert.equal(doc.status,200);assert.doesNotMatch(await doc.text(),/data-auth-recovery/);
 assert.equal(api.status,200);assert.deepEqual(await api.json(),{authorized:true,strategy:'A_BASE'});
 assert.equal(api.headers.get('cache-control'),'private, no-store, max-age=0');
 assert.equal(f.reads,1);
 assert.deepEqual(JSON.parse(JSON.stringify(ownerLogs(f))),[ownerDocument,ownerAccess].map(route=>({
  operation:'cloud_owner_response_observed',
  schema:'NEW_A_PROTECTED_OWNER_RESPONSE_V1',
  source_commit:observedVersion.tag,
  build_input_sha256:'2'.repeat(64),
  worker:'tentei-kyokuchi-cloud',
  version_id:observedVersion.id,
  version_timestamp:observedVersion.timestamp,
  route,status:200,strategy:'A_BASE',
  ...(route===ownerAccess?{verified_access_contract:{authorized:true,strategy:'A_BASE'}}:{}),
 })));
});
test('denial, synthetic preview, recovery shell and routing overrides cannot produce owner evidence', async t=>{
 const f=fixture();t.after(f.close);
 const env={...f.env,CLOUD_VERSION_METADATA:observedVersion};
 const recovery=await f.app.fetch(normalOwnerRequest(ownerDocument,OWNER,true,{headers:{'x-synthetic-refresh':'yes'}}),env);
 assert.equal(recovery.status,200);assert.match(await recovery.text(),/data-auth-recovery/);
 for(const [req,targetEnv] of [
  [normalOwnerRequest(ownerAccess,null),env],
  [normalOwnerRequest(ownerAccess,OTHER),env],
  [normalOwnerRequest(ownerAccess,OWNER,false),env],
  [normalOwnerRequest(ownerAccess,OWNER,true,{method:'HEAD'}),env],
  [normalOwnerRequest(ownerDocument+'?ignored=1'),env],
  [normalOwnerRequest(ownerAccess,OWNER,true,{headers:{'cloudflare-workers-version-key':'synthetic'}}),env],
  [normalOwnerRequest(ownerAccess,OWNER,true,{headers:{authorization:'synthetic'}}),env],
  [request(ownerAccess),env],
  [normalOwnerRequest(ownerAccess),f.env],
  [normalOwnerRequest(ownerAccess),{...env,CLOUD_VERSION_METADATA:{...observedVersion,tag:'3'.repeat(40)}}],
 ]) await f.app.fetch(req,targetEnv);
 assert.deepEqual(ownerLogs(f),[]);
});
test('access observation skips wrong, extra or oversized JSON without consuming the original response', async ()=>{
 const logs=[];
 const {observeOwnerResponse}=modules(event=>logs.push(event),'./owner-response-observation');
 const context={ownerAuthorized:true,roleAuthorized:true,current:true,subject:OWNER};
 const build={source_commit:observedVersion.tag,build_input_sha256:'2'.repeat(64),target:{worker:'tentei-kyokuchi-cloud',database:'tentei-cloud-settings'}};
 for(const body of [
  {authorized:false,strategy:'A_BASE'},
  {authorized:true,strategy:'OTHER'},
  {authorized:true,strategy:'A_BASE',extra:'synthetic-not-for-logs'},
 ]) {
  const response=Response.json(body);
  await observeOwnerResponse(normalOwnerRequest(ownerAccess),response,context,build,observedVersion);
  assert.deepEqual(await response.json(),body);
 }
 const longBody=' '.repeat(300)+'{"authorized":true,"strategy":"A_BASE"}';
 const oversized=new Response(longBody,{headers:{'content-type':'application/json'}});
 await observeOwnerResponse(normalOwnerRequest(ownerAccess),oversized,context,build,observedVersion);
 assert.equal(await oversized.text(),longBody);
 assert.deepEqual(logs,[]);
});
test('refresh documents activate the existing recovery guard while private APIs remain closed until refreshed',async()=>{
 const f=fixture();try{
  const initialReads=f.reads,refresh={headers:{'x-synthetic-refresh':'yes'}};
  for(const route of ['/weak_early_beta_latest.html','/weak_early_beta_analytics.html','/weak_early_beta_settings.html']){
   const response=await f.app.fetch(request(route,OWNER,true,refresh),f.env),html=await response.text();
   assert.equal(response.status,200);assert.match(html,/<html[^>]*\bdata-auth-recovery\b/);assert.match(html,/src="\/auth\/guard\.js"/);
   assert.match(response.headers.get('cache-control'),/no-store/);assert.equal(f.reads,initialReads);
  }
  for(const route of ['/api/cloud/new-a-finite/access','/api/cloud/new-a-finite/input/manifest.json']){
   const response=await f.app.fetch(request(route,OWNER,true,refresh),f.env);
   assert.equal(response.status,401);assert.equal((await response.json()).error,'refresh_required');assert.equal(f.reads,initialReads);
  }
  const refreshed=await f.app.fetch(request('/api/cloud/new-a-finite/access'),f.env);
  assert.equal(refreshed.status,200);assert.deepEqual(await refreshed.json(),{authorized:true,strategy:'A_BASE'});assert.equal(f.reads,initialReads);
 }finally{f.close();}
});
test('unsaved server and existing modal reset retain D6; a saved D5 remains authoritative and reset is draft-only',async()=>{
 const f=fixture();try{
  const get=async()=>await(await f.app.fetch(request('/api/cloud/new-a-finite/preferences'),f.env)).json();
  const initial=await get();assert.equal(initial.has_saved_preferences,false);assert.equal(initial.preferences.exit_endpoint,'d6_open');assert.equal(initial.default_proposal_verified,false);
  const member='cloud_'+sha('cloud-member:'+OWNER),saved=JSON.stringify({max_price:1000,exit_endpoint:'d5_close',base_shares:100,cost_percent:0});f.sql.prepare('INSERT INTO cloud_member_preferences(member_id,preferences_json) VALUES (?,?)').run(member,saved);
  const legacy=await get();assert.equal(legacy.has_saved_preferences,true);assert.equal(legacy.preferences.exit_endpoint,'d5_close');
  const c={module:{exports:{}}};vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(gate,'scripts/new-a-ui-source/assets/finite-controller.js'),'utf8'),c);assert.equal(c.module.exports.BASE.exit_endpoint,'d6_open');let writes=0;
  const controller=c.module.exports.createController({calculateOnLoad:false,transport:async(url,init)=>{if(init.method!=='GET')writes++;return f.app.fetch(request(url,OWNER,true,init),f.env);}});
  assert.equal(await controller.load(),true);assert.equal(controller.state().applied.exit_endpoint,'d5_close');controller.reset();assert.equal(controller.state().draft.exit_endpoint,'d6_open');assert.equal(controller.state().applied.exit_endpoint,'d5_close');assert.equal(controller.state().dirty,true);assert.equal(writes,0);
  controller.cancel();assert.equal(controller.state().draft.exit_endpoint,'d5_close');assert.equal(controller.state().dirty,false);assert.equal(writes,0);assert.equal(f.sql.prepare('SELECT preferences_json FROM cloud_member_preferences WHERE member_id=?').get(member).preferences_json,saved);assert.equal(f.sql.prepare('SELECT count(*) AS n FROM new_a_finite_trial_preferences').get().n,0);
 }finally{f.close();}
});
test('existing owner/fresh-role boundary precedes every private D1 read; code-only access needs no D1',async()=>{const f=fixture();try{for(const target of ['/','/weak_early_beta_settings.html','/api/cloud/new-a-finite/access','/api/cloud/new-a-finite/input/manifest.json','/new-a-assets/owner-loader.js'])for(const[id,role]of[[null,true],[OTHER,true],[OWNER,false]]){const before=f.reads,r=await f.app.fetch(request(target,id,role),f.env);assert([302,401,403].includes(r.status));assert.equal(f.reads,before);}const before=f.reads,r=await f.app.fetch(request('/api/cloud/new-a-finite/access'),{...f.env,CLOUD_DB:undefined});assert.equal(r.status,200);assert.deepEqual(await r.json(),{authorized:true,strategy:'A_BASE'});assert.equal(f.reads,before);}finally{f.close();}});
test('manifest pins immutable READY parts; old pending data routes and foreign-site reads stay closed',async()=>{const f=fixture();try{const id='a-'+'1'.repeat(24),version=sha('synthetic-source'),collections={},quotes=[],body='[]';for(const kind of['episodes','intents','watches','presentation','current_daily','quotes']){const d={name:kind+'-000.json',sha256:sha(body),bytes:2,rows:0};if(kind==='quotes')quotes.push(d);else collections[kind]=[d];}const manifest=JSON.stringify({schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',source_version:version,input_header:{source_version:version},collections,quotes});f.sql.prepare('INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?)').run(id,version,manifest,sha(manifest),'READY','synthetic');for(const d of[...quotes,...Object.values(collections).flat()])f.sql.prepare('INSERT INTO new_a_private_parts VALUES (?,?,?,?,?)').run(id,d.name,body,d.sha256,2);f.sql.prepare('INSERT INTO new_a_active_pointer VALUES (?,?,?,?)').run('owner',id,1,'synthetic');const m=await(await f.app.fetch(request('/api/cloud/new-a-finite/input/manifest.json'),f.env)).json();assert.equal(m.dataset_id,id);const r=await f.app.fetch(request(`/api/cloud/new-a-finite/input/${id}/quotes-000.json`),f.env);assert.equal(await r.text(),body);assert.equal(r.headers.get('cache-control'),'private, no-store, max-age=0');assert.equal((await f.app.fetch(request('/api/cloud/new-a-finite/input/manifest.json',OWNER,true,{headers:{'sec-fetch-site':'cross-site'}}),f.env)).status,403);assert.equal((await f.app.fetch(request('/research-a/details.json'),f.env)).status,410);assert.equal((await f.app.fetch(request('/api/cloud/new-a-finite/simulate',OWNER,true,{method:'POST'}),f.env)).status,409);}finally{f.close();}});
test('finite preferences save/reload and conflict preserve existing preference/notification bytes',async()=>{const f=fixture();try{const member='cloud_'+sha('cloud-member:'+OWNER),legacy=JSON.stringify({max_price:1000,exit_endpoint:'d5_close',base_shares:100,cost_percent:0,notifications:{new_detection:true}});f.sql.prepare('INSERT INTO cloud_member_preferences(member_id,preferences_json) VALUES (?,?)').run(member,legacy);const before=await(await f.app.fetch(request('/api/cloud/new-a-finite/preferences'),f.env)).json();assert.equal(before.has_saved_preferences,true);assert.equal(before.has_saved_finite_preferences,false);const preferences={...before.preferences,initial_cash_yen:20000000,max_positions:7},put=()=>f.app.fetch(request('/api/cloud/new-a-finite/preferences',OWNER,true,{method:'PUT',headers:{origin:'https://synthetic.invalid','content-type':'application/json'},body:JSON.stringify({preferences,expected_revision:0,request_id:'synthetic-save'})}),f.env);assert.equal((await put()).status,200);assert.equal((await put()).status,409);const after=await(await f.app.fetch(request('/api/cloud/new-a-finite/preferences'),f.env)).json();assert.deepEqual(after.preferences,preferences);assert.equal(f.sql.prepare('SELECT preferences_json FROM cloud_member_preferences WHERE member_id=?').get(member).preferences_json,legacy);}finally{f.close();}});
const preferencesPath = '/api/cloud/new-a-finite/preferences';
const firstView = {trial_preset: 'profit', theme: 'light', font_size: 'large', page_size: 50};
const secondView = {trial_preset: null, theme: 'system', font_size: 'small', page_size: 100};
const putSettings = (f, preferences, expected_revision, extra = {}, id = OWNER, env = f.env) =>
 f.app.fetch(request(preferencesPath, id, true, {
  method: 'PUT',
  headers: {origin: 'https://synthetic.invalid', 'content-type': 'application/json'},
  body: JSON.stringify({preferences, expected_revision, request_id: 'fixture-save', ...extra}),
 }), env);
const readSettings = async (f, id = OWNER, env = f.env) => {
 const response = await f.app.fetch(request(preferencesPath, id), env);
 assert.equal(response.status, 200);
 assert.equal(response.headers.get('cache-control'), 'private, no-store, max-age=0');
 assert.equal(response.headers.get('vary'), 'Cookie');
 return response.json();
};

test('owner documents use the saved theme before loading application scripts', async t => {
 const f = fixture();
 t.after(f.close);
 const member = 'cloud_'+sha('cloud-member:'+OWNER);
 const routes = [ownerDocument, '/weak_early_beta_analytics.html', '/weak_early_beta_settings.html'];
 const systemScript = '<script src="/new-a-assets/initial-display.js"></script>';
 for (const theme of ['light','system','dark']) {
  const current = await readSettings(f);
  const saved = await putSettings(f,current.preferences,current.revision,{
   view_preferences:{...firstView,theme},save_binding:current.save_binding,
  });
  assert.equal(saved.status,200);
  for (const route of routes) {
   const before = f.reads;
   const response = await f.app.fetch(request(route),f.env);
   const html = await response.text();
   assert.equal(response.status,200);
   assert.equal(response.headers.get('cache-control'),'private, no-store, max-age=0');
   assert.equal(response.headers.get('vary'),'Cookie');
   assert.match(response.headers.get('content-security-policy'),/script-src 'self';/);
   assert(html.startsWith(`<!doctype html><html lang="ja" data-theme="${theme}" data-initial-theme="${theme}"`));
   assert(!html.includes(member));
   assert.equal(f.reads,before+1);
   if (theme==='system') assert(html.indexOf(systemScript)>=0&&html.indexOf(systemScript)<html.indexOf('<style>'));
   else assert(!html.includes(systemScript));
  }
 }
 const before = f.reads;
 const head = await f.app.fetch(request(ownerDocument,OWNER,true,{method:'HEAD'}),f.env);
 assert.equal(head.status,200);
 assert.equal(await head.text(),'');
 assert.equal(f.reads,before);
 f.sql.prepare('UPDATE new_a_finite_trial_preferences SET preferences_json=? WHERE member_id=?')
  .run(JSON.stringify({...firstView,theme:'invalid'}),'new-a-view:v1:'+member);
 const fallback = await f.app.fetch(request(ownerDocument),f.env);
 assert.equal(fallback.status,200);
 assert.match(await fallback.text(),/^<!doctype html><html lang="ja" data-theme="dark" data-initial-theme="dark"/);
});

test('view and trial settings persist by account and trial-only clients keep the saved view', async t => {
 const f = fixture();
 t.after(f.close);
 const initial = await readSettings(f);
 assert.equal(initial.view_preferences, null);
 const trialA = {...initial.preferences, cost_percent: 0.25};
 const trialB = {...initial.preferences, allocation: 'unique'};
 assert.match(initial.save_binding, /^[a-f0-9]{64}$/);
 const accountA = await putSettings(f, trialA, 0, {view_preferences: firstView, save_binding: initial.save_binding});
 assert.equal(accountA.status, 200);
 const receiptA = await accountA.json();
 assert.deepEqual(receiptA.view_preferences, firstView);
 assert.notEqual(receiptA.save_binding, initial.save_binding);

 const otherEnv = {...f.env, CLOUD_OWNER_DISCORD_ID: OTHER};
 assert.equal((await f.app.fetch(request(preferencesPath, OTHER), f.env)).status, 403);
 const initialB = await readSettings(f, OTHER, otherEnv);
 assert.equal(initialB.view_preferences, null);
 assert.equal((await putSettings(f, trialB, 0, {view_preferences: secondView, save_binding: initialB.save_binding}, OTHER, otherEnv)).status, 200);
 assert.equal((await readSettings(f)).save_binding, receiptA.save_binding);
 const updatedTrialA = {...trialA, base_shares: 200};
 const legacy = await putSettings(f, updatedTrialA, 1);
 assert.equal(legacy.status, 200);
 assert.equal(Object.hasOwn(await legacy.json(), 'view_preferences'), false);
 const savedA = await readSettings(f);
 const savedB = await readSettings(f, OTHER, otherEnv);
 assert.deepEqual(savedA.preferences, updatedTrialA);
 assert.deepEqual(savedA.view_preferences, firstView);
 assert.equal(savedA.revision, 2);
 assert.deepEqual(savedB.preferences, trialB);
 assert.deepEqual(savedB.view_preferences, secondView);
 assert.equal(savedB.revision, 1);
});

test('trial and view CAS rejects a stale or failed settings save without changing either row', async t => {
 const f = fixture();
 t.after(f.close);
 const {preferences, save_binding} = await readSettings(f);
 const changes = [
  {preferences: {...preferences, cost_percent: 0.25}, view_preferences: firstView},
  {preferences: {...preferences, cost_percent: 0.5}, view_preferences: secondView},
 ];
 const tie = await Promise.all(changes.map(change => putSettings(f, change.preferences, 0, {view_preferences: change.view_preferences, save_binding})));
 assert.deepEqual(tie.map(r => r.status).sort(), [200, 409]);
 const winner = changes[tie.findIndex(r => r.ok)];
 const conflict = await tie.find(r => r.status === 409).json();
 assert.equal(conflict.error, 'revision_conflict');
 assert.equal(conflict.revision, 1);

 f.sql.exec(`CREATE TRIGGER synthetic_failed_view_update
  BEFORE UPDATE ON new_a_finite_trial_preferences
  WHEN NEW.member_id GLOB 'new-a-view:v1:*'
  BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END;`);
 const beforeFailure = await readSettings(f);
 const failed = await putSettings(f, preferences, 1, {view_preferences: secondView, save_binding: beforeFailure.save_binding});
 assert.equal(failed.status, 503);
 assert.deepEqual(await failed.json(), {error: 'new_a_service_unavailable'});
 const saved = await readSettings(f);
 assert.equal(saved.revision, 1);
 assert.deepEqual(saved.preferences, winner.preferences);
 assert.deepEqual(saved.view_preferences, winner.view_preferences);
});

test('an open account draft cannot save under a different authorized account at the same revision', async t => {
 const f = fixture();
 t.after(f.close);
 const a = await readSettings(f);
 const otherEnv = {...f.env, CLOUD_OWNER_DISCORD_ID: OTHER};
 const b = await readSettings(f, OTHER, otherEnv);
 assert.equal(a.revision, b.revision);
 assert.notEqual(a.save_binding, b.save_binding);
 const draft = {...a.preferences, max_positions: 7};
 const result = await putSettings(f, draft, a.revision, {view_preferences: firstView, save_binding: a.save_binding}, OTHER, otherEnv);
 assert.equal(result.status, 409);
 assert.deepEqual(await result.json(), {error: 'settings_session_changed', request_id: 'fixture-save'});
 assert.deepEqual(await readSettings(f), a);
 assert.deepEqual(await readSettings(f, OTHER, otherEnv), b);
 assert.equal(f.sql.prepare('SELECT count(*) AS n FROM new_a_finite_trial_preferences').get().n, 0);
});

test('settings rejects caller-supplied account selectors, invalid values and anonymous requests', async t => {
 const f = fixture();
 t.after(f.close);
 const {preferences} = await readSettings(f);
 assert.equal((await putSettings(f, preferences, 0, {member_id: OTHER})).status, 400);
 assert.equal((await putSettings(f, preferences, 0, {view_preferences: {...firstView, member_id: OTHER}})).status, 400);
 for(const binding of [{}, {save_binding:'invalid'}]){
  const rejected = await putSettings(f, preferences, 0, {view_preferences: firstView, ...binding});
  assert.equal(rejected.status, 400);
  assert.deepEqual(await rejected.json(), {error: 'save_binding_required'});
 }
 for(const invalid of [null, {...firstView, page_size: '50'}, {...firstView, trial_preset: 'custom'}, {...firstView, theme: 'other'}, {...firstView, font_size: 'normal'}]){
  const rejected = await putSettings(f, preferences, 0, {view_preferences: invalid});
  assert.equal(rejected.status, 400);
  assert.deepEqual(await rejected.json(), {error: 'invalid_view_preferences'});
 }
 assert.equal((await putSettings(f, preferences, Number.MAX_SAFE_INTEGER)).status, 400);
 assert.equal((await f.app.fetch(request(preferencesPath + '?member_id=' + OTHER), f.env)).status, 404);
 assert.equal((await f.app.fetch(request(preferencesPath, null), f.env)).status, 401);
 assert.equal((await putSettings(f, preferences, 0, {}, null)).status, 401);
 assert.equal((await f.app.fetch(request(preferencesPath, OWNER, false), f.env)).status, 403);
 assert.equal((await readSettings(f)).revision, 0);
});

test('normal large current display reassembles UTF-8 fragments; missing/order/tamper/size and snapshot mismatch are rejected',async()=>{
 const c={module:{exports:{}},TextEncoder,TextDecoder,Uint8Array,atob,crypto:webcrypto};vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(gate,'scripts/new-a-ui-source/assets/owner-loader.js'),'utf8'),c);const api=c.module.exports;
 const display={schema:'NEW_A_OWNER_DAILY_DISPLAY_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',source_snapshot_sha256:sha('synthetic snapshot'),monitor_state:{watches:Object.fromEntries(Array.from({length:250},(_,i)=>[String(i),{episode:{symbol:String(1000+i),candidate_date:'synthetic-date',note:'合成監視'.repeat(30)}}]))},events:[]},bytes=Buffer.from(JSON.stringify(display));assert(bytes.length>65536);const count=Math.ceil(bytes.length/32768),fragments=Array.from({length:count},(_,index)=>({schema:'NEW_A_CURRENT_JSON_FRAGMENT_V1',index,count,display_sha256:sha(bytes),bytes_total:bytes.length,payload_base64:bytes.subarray(index*32768,(index+1)*32768).toString('base64')}));
 const restored=await api.assembleCurrent(fragments,webcrypto);assert.equal(sha(JSON.stringify(restored[0])),sha(JSON.stringify(display)));assert.equal(Object.keys(restored[0].monitor_state.watches).length,250);
 for(const broken of [fragments.slice(1),[...fragments].reverse(),fragments.map((f,i)=>i?f:{...f,payload_base64:'~'+f.payload_base64.slice(1)}),fragments.map(f=>({...f,display_sha256:'0'.repeat(64)})),fragments.map(f=>({...f,bytes_total:8*1024*1024+1}))])await assert.rejects(()=>api.assembleCurrent(broken,webcrypto));
 const parts=new Map(),ds=fragments.map((f,i)=>{const name='current_daily-'+String(i).padStart(3,'0')+'.json',text=JSON.stringify([f]);parts.set(name,text);return{name,bytes:Buffer.byteLength(text),sha256:sha(text),rows:1};}),version=sha('synthetic input'),manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',source_version:version,dataset_id:'a-'+'1'.repeat(24),input_header:{source_version:version},collections:{episodes:[],intents:[],watches:[],presentation:[],current_daily:ds},quotes:[],daily_snapshot_sha256:'0'.repeat(64)};
 await assert.rejects(()=>api.readPresentation(async url=>url.endsWith('/manifest.json')?Response.json(manifest):new Response(parts.get(url.split('/').pop())),webcrypto),/daily_snapshot_mismatch/);
});
test('verified current snapshot is available while history is pending',async()=>{
 const context={module:{exports:{}},TextDecoder};
 vm.createContext(context);
 vm.runInContext(fs.readFileSync(path.join(gate,'scripts/new-a-ui-source/assets/owner-loader.js'),'utf8'),context);
 const api=context.module.exports;
 const source_version=sha('ordered read'),snapshotHash=sha('current snapshot');
 const display={schema:'NEW_A_OWNER_DAILY_DISPLAY_V1',source_snapshot_sha256:snapshotHash};
 const datePart=JSON.stringify([display]),historyPart=JSON.stringify([{identity:'current'}]);
 const descriptor=(name,text)=>({name,bytes:Buffer.byteLength(text),sha256:sha(text),rows:1});
 const date=descriptor('current_daily-000.json',datePart),history=descriptor('presentation-000.json',historyPart);
 const manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',source_version,
  dataset_id:'a-'+'1'.repeat(24),input_header:{source_version},daily_snapshot_sha256:snapshotHash,
  collections:{episodes:[],intents:[],watches:[],presentation:[history],current_daily:[date]},quotes:[]};
 const requests=[],observed=[];
 const historyResponse=Promise.withResolvers(),historyRequested=Promise.withResolvers();
 const network=async path=>{
  const name=path.split('/').pop();requests.push(name);
  if(name==='manifest.json')return Response.json(manifest);
  if(name===date.name)return new Response(datePart);
  assert.equal(name,history.name);historyRequested.resolve();return historyResponse.promise;
 };
 const pending=api.readPresentation(network,webcrypto,current=>observed.push(JSON.stringify(current)));
 await historyRequested.promise;
 assert.deepEqual(requests,['manifest.json',date.name,history.name]);
 assert.deepEqual(observed,[datePart]);
 historyResponse.resolve(new Response(historyPart));
 assert.equal(JSON.stringify((await pending).rows),historyPart);
 const denied=[];
 await assert.rejects(api.readPresentation(async url=>url.endsWith('manifest.json')?Response.json(manifest):new Response(null,{status:403}),webcrypto,current=>denied.push(current)),/authorization_required/);
 assert.deepEqual(denied,[]);
});
test('dashboard identifies the snapshot day, a delayed observation and independent held stocks',()=>{
 const c={module:{exports:{}}};
 vm.createContext(c);
 vm.runInContext(fs.readFileSync(path.join(gate,'scripts/new-a-ui-source/assets/owner-loader.js'),'utf8'),c);
 const snapshot={
  schema:'NEW_A_OWNER_DAILY_DISPLAY_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',as_of:'2026-11-16',
  observed_at:'2026-11-16T16:00:00Z',observation_kind:'DELAYED_SCHEDULED_OBSERVATION',
  held_symbols:{'1111':{day:'2026-11-16',reason:'MISSING_SOURCE'},'2222':{day:'2026-11-16',reason:'SOURCE_QUARANTINED'},'4444':{day:'2026-11-16',reason:'VERIFIED_RESTRICTED'}},
  monitor_state:{watches:{'1111|1':{episode:{symbol:'1111',candidate_date:'2026-11-14',episode_id:1}},'3333|1':{episode:{symbol:'3333',candidate_date:'2026-11-15',episode_id:1}}}},
  events:[{session:'2026-11-16',symbol:'3333',candidate_date:'2026-11-16',episode_id:1,kind:'WATCH_STARTED',is_delayed_scheduled_signal:true},{session:'2026-11-16',symbol:'3333',candidate_date:'2026-11-16',episode_id:1,kind:'WATCH_STARTED',is_delayed_scheduled_signal:true}],
 };
 const {currentMarkup}=c.module.exports;
 const watchSelection=Object.values(snapshot.monitor_state.watches).map(({episode})=>({...episode,watch_status:'WATCHING',selection_reason:null}));
 const html=currentMarkup([snapshot],[],{watchSelection});
 assert.match(html,/対象 2026-11-16/);
 assert.match(html,/観測 11\/17 01:00 JST/);
 assert.match(html,/遅延実行/);
 assert.match(html,/新規検出 1銘柄/);
 assert.match(html,/監視開始 <b>1件/);
 assert.match(html,/データ保留 3銘柄/);
 for(const label of ['取得未確認','価格照合','取引制限','監視中'])assert(html.includes(label));
 assert.doesNotMatch(html,/今日の新規検出|最終観測/);
 assert.doesNotMatch(currentMarkup([{...snapshot,observation_kind:'CATCHUP_NOT_NEW'}]),/新規検出 /);
 assert.match(currentMarkup([]),/監視状況を確認できません/);
});

// Exit-transition fixtures are synthetic; no actual price input or production session.
const transitionEngine=require(path.join(gate,'scripts/new-a-ui-source/engine/finite-engine.cjs'));
const transitionPolicy={version:'A_OPEN_EXIT_V2',first_d5_entry_session:'2026-11-17',legacy_endpoint:'d6_open',new_endpoint:'d5_open'};
const transitionCalendar=['09','10','11','12','13','16','17','18','19','20','24','25','26','27','30'].map(d=>'2026-11-'+d);
const transitionPreferences={price_cap_yen:null,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,year_scope:'all',allocation:'all',initial_cash_yen:10000000,max_positions:20,per_order_cap_yen:500000};
const transitionIntent=(symbol,day)=>({symbol,candidate_date:day,trigger_date:day,episode_id:1,priority_score:1});
const transitionQuote=()=>({open:100,high:101,low:99,close:100,actual_close:100,volume:100,actual_volume:100,split_factor:1,source_usable:true});
function transitionReplay(intents,patch={},options={}){return transitionEngine.replay({calendar:transitionCalendar,intents,quotes:{get:transitionQuote},...options},{...transitionPreferences,...patch},{exitPolicy:transitionPolicy});}

test('open-exit transition starts with Nov17 entries, counts purchase day one and skips Nov23',()=>{
 assert.equal(transitionPolicy.first_d5_entry_session,'2026-11-17');
 const result=transitionReplay([transitionIntent('1111','2026-11-13'),transitionIntent('2222','2026-11-16')]);
 assert.equal(result.trades.length,2);
 const old=result.trades.find(t=>t.symbol==='1111'),fresh=result.trades.find(t=>t.symbol==='2222');
 assert.equal(old.entry_date,'2026-11-16');assert.equal(old.exit_date,'2026-11-24');assert.equal(old.actual_exit_timing,'OPEN');assert.equal(old.exit_endpoint,undefined);
 assert.equal(fresh.entry_date,'2026-11-17');assert.equal(fresh.exit_date,'2026-11-24');assert.equal(fresh.actual_exit_timing,'OPEN');assert.equal(fresh.exit_endpoint,'d5_open');
 assert.equal(old.exit_i-old.entry_i,5);assert.equal(fresh.exit_i-fresh.entry_i,4);assert.equal(fresh.exit_policy_version,transitionEngine.OPEN_EXIT_POLICY_VERSION);
 assert.equal(result.open_positions['1111'],undefined);assert.equal(result.open_positions['2222'],undefined);
});
test('positions bought before transition retain D6 even when their exit is after transition',()=>{
 const result=transitionReplay([transitionIntent('1111','2026-11-09')]);
 assert.equal(result.trades[0].entry_date,'2026-11-10');assert.equal(result.trades[0].exit_date,'2026-11-17');assert.equal(result.trades[0].exit_endpoint,undefined);
 const first=transitionReplay([transitionIntent('1111','2026-11-09')],{}, {calendar:transitionCalendar.slice(0,6)});
 assert.equal(first.trades.length,0);assert.equal(first.open_positions['1111'].exit_i,6);assert.equal(first.open_positions['1111'].exit_endpoint,undefined);
});
test('D5 close and A20 close preserve their old timing and calendar offsets',()=>{
 const close=transitionReplay([transitionIntent('1111','2026-11-16')],{exit_endpoint:'d5_close'});
 assert.equal(close.trades[0].exit_date,'2026-11-24');assert.equal(close.trades[0].actual_exit_timing,'CLOSE');assert.equal(close.exit_policy,undefined);
 assert.deepEqual(transitionEngine.exitTerms('a20_close','2026-11-17'),{sessions:20,timing:'CLOSE',endpoint:'a20_close'});
});
test('missing or one-price D5 quote stays unresolved and never silently delays to D6',()=>{
 for(const kind of ['missing','flat']){
  const quotes={get:(s,d)=>d==='2026-11-24'?(kind==='missing'?null:{...transitionQuote(),open:100,high:100,low:100,close:100}):transitionQuote()};
  const result=transitionReplay([transitionIntent('1111','2026-11-16')],{}, {quotes});
  assert.equal(result.trades.length,0);assert.equal(result.resolved,false);assert.equal(result.metrics.netProfit,null);assert.equal(result.metrics.winRate,null);assert(result.unresolved.some(x=>x.reason==='UNRESOLVED_SCHEDULED_EXIT'));
 }
});
test('fixed lots, per-order cap, portfolio cap and absence of an extra daily cap are retained',()=>{
 const intents=Array.from({length:21},(_,i)=>transitionIntent(String(1100+i),'2026-11-16'));
 const result=transitionReplay(intents);assert.equal(result.counts.FILLED,20);assert.equal(result.counts.CAPACITY,1);assert.equal(result.trades.length,20);assert(result.trades.every(t=>t.shares===100));assert(result.daily.every(d=>d.positions<=20));
 const capped=transitionReplay([transitionIntent('1111','2026-11-16')],{}, {quotes:{get:()=>({...transitionQuote(),open:6000,high:6100,low:5900,close:6000,actual_close:6000})}});
 assert.equal(capped.counts.LOT_EXCEEDS_ALLOCATION,1);assert.equal(capped.metrics.fills,0);
});
test('repeated simulation of the same mixed holdings cannot create double settlements',()=>{
 const intents=[transitionIntent('1111','2026-11-13'),transitionIntent('2222','2026-11-16')];
 const first=transitionReplay(intents),second=transitionReplay(intents);assert.deepEqual(first,second);assert.equal(new Set(first.trades.map(t=>t.symbol+'|'+t.entry_date)).size,2);
});
test('settings reload keeps saved d6_open bytes while labels and exports describe each cohort',()=>{
 const c={module:{exports:{}}};vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(gate,'scripts/new-a-ui-source/assets/finite-controller.js'),'utf8'),c);const api=c.module.exports;
 const result=transitionReplay([transitionIntent('1111','2026-11-13'),transitionIntent('2222','2026-11-16')]),policy=result.exit_policy;
 assert.equal(api.validate(transitionPreferences).exit_endpoint,'d6_open');
 assert.equal(api.exitLabel('d6_open',{entry_date:'2026-11-16'},policy),'6営業日目 寄付');assert.equal(api.exitLabel('d6_open',{entry_date:'2026-11-17'},policy),'5営業日目 寄付');
 const d={request_id:'synthetic-transition',source_version:'synthetic-version',view_kind:'synthetic',preferences:transitionPreferences,result:{...result,watches:[]}};
 const html=api.render(d);assert(html.includes('2026-11-17買付から5営業日目'));assert(html.includes('以前は6営業日目'));
 assert(api.exportsFor(d,'daily').includes('exit_policy'));assert(api.exportsFor(d,'daily').includes(transitionEngine.OPEN_EXIT_POLICY_VERSION));
});

test('private owner policy passes through the real browser broker and worker; missing policy fails closed',async()=>{
 const f=fixture();try{
  const state=await(await f.app.fetch(request('/api/cloud/new-a-finite/preferences'),f.env)).json();assert.deepEqual(state.exit_policy,transitionPolicy);
  const runtime=require(path.join(gate,'scripts/new-a-ui-source/engine/dataset-runtime.cjs'));
  const manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',dataset_id:'a-'+'1'.repeat(24),source_version:'synthetic',input_header:{source_version:'synthetic',calendar:transitionCalendar,limits:{identityUnverifiedBefore:{}}},collections:{episodes:[],intents:[],watches:[]},quotes:[],quote_fields:[],expected_quote_keys:0};
  let workers=0,policy=state.exit_policy,authorized=true;
  const brokerContext={module:{exports:{}},Response,TextDecoder,Uint8Array,AbortController,crypto:webcrypto};vm.createContext(brokerContext);vm.runInContext(fs.readFileSync(path.join(gate,'scripts/new-a-ui-source/assets/browser-transport.js'),'utf8'),brokerContext);
  const broker=brokerContext.module.exports.create({fetch:async()=>authorized?Response.json({exit_policy:policy}):new Response(null,{status:403}),pinnedManifest:manifest,createWorker(){workers++;const worker={terminate(){},postMessage(message){context.onmessage({data:message});}},context={AFiniteDataset:runtime,TextDecoder,postMessage:message=>worker.onmessage({data:message})};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(gate,'scripts/new-a-ui-source/engine/worker-entry.js'),'utf8'),context);return worker;}});
  const simulate=()=>broker.transport('/api/cloud/new-a-finite/simulate',{method:'POST',body:JSON.stringify({preferences:transitionPreferences,request_id:'synthetic'})});
  const ok=await simulate();assert.equal(ok.status,200);assert.deepEqual((await ok.json()).result.exit_policy,transitionPolicy);assert.equal(workers,1);
  policy=undefined;assert.equal((await simulate()).status,503);assert.equal(workers,1);
  authorized=false;assert.equal((await simulate()).status,403);assert.equal(workers,1);
 }finally{f.close();}
});

test('runtime caches policy generations separately and preserves original semantics without transition',()=>{
 const {createDatasetRuntime}=require(path.join(gate,'scripts/new-a-ui-source/engine/dataset-runtime.cjs'));
 const intents=[transitionIntent('1111','2026-11-16')],input={calendar:transitionCalendar,intents,episodes:[],watches:[],limits:{identityUnverifiedBefore:{}},source_version:'synthetic'},runtime=createDatasetRuntime(input,{get:transitionQuote});
 assert.equal(runtime.simulate(transitionPreferences).trades[0].exit_date,'2026-11-25');
 assert.equal(runtime.simulate(transitionPreferences,{exitPolicy:transitionPolicy}).trades[0].exit_date,'2026-11-24');
 assert.equal(runtime.simulate(transitionPreferences).trades[0].exit_date,'2026-11-25');
 for(const invalid of [{},{...transitionPolicy,version:'unknown'},{...transitionPolicy,first_d5_entry_session:'invalid'}])assert.throws(()=>runtime.simulate(transitionPreferences,{exitPolicy:invalid}),/exit_policy_invalid/);
});
