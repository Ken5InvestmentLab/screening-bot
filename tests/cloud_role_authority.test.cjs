const test=require('node:test'),assert=require('node:assert/strict');
const {modules}=require('./helpers/cloud-worker-modules.cjs');
const {namespace}=require('./helpers/cloud-role-authority.cjs');
const {createHash}=require('node:crypto');
const NOW=Date.parse('2026-10-05T00:00:00Z');
function harness() {
 const clock={now:NOW},requests=[],provider={roles:['allowed'],http:200,retry:86374,scope:'user'};
 const fetchMock=async(input,init)=>{requests.push({route:new URL(input).pathname,redirect:init.redirect});provider.started?.(); if(provider.wait)await provider.wait;
   clock.now+=provider.elapsed||0;
   if(provider.workerdRedirectGuard&&init.redirect==='error')throw new TypeError('Unsupported redirect mode: error');
   if(provider.error)throw provider.error;
   if(provider.response)return provider.response();
   if(provider.http===200)return Response.json({roles:provider.roles,...provider.successBody},{headers:provider.headers});
   return Response.json({retry_after:provider.retry,untrusted_secret:'must-not-be-stored-or-logged'},{status:provider.http,headers:{'x-ratelimit-scope':provider.scope,...(provider.retryHeader?{'retry-after':provider.retryHeader}:{})}});
 };
 const mod=modules({clock,fetchMock}),authority=mod.load('./cloud-role-authority');
 const env={DISCORD_GUILD_ID:'synthetic-guild',DISCORD_ALLOWED_ROLE_IDS:'allowed',DISCORD_API_BASE:'https://discord.invalid/api',DISCORD_CLIENT_ID:'synthetic-client',SESSION_SECRET:'synthetic-encryption-secret'};
 env.CLOUD_ROLE_AUTHORITY=namespace(authority.CloudRoleAuthority,env);
 return {clock,requests,provider,mod,env,authority,check:(subject='owner',token='synthetic-access')=>authority.cloudReportRole(env,subject,token,'/auth/check')};
}
test('role lookup uses a workerd-supported manual redirect mode',async()=>{
 const h=harness();h.provider.workerdRedirectGuard=true;
 const result=await h.check();assert.equal(result.status,'paid');assert.equal(h.requests.length,1);assert.equal(h.requests[0].redirect,'manual');
});
test('role redirect with a Location and permitted-role body remains unavailable without following it',async()=>{
 const h=harness();h.provider.response=()=>Response.json({roles:['allowed']},{status:302,headers:{location:'https://redirect.invalid/member'}});
 const result=await h.check();assert.equal(result.status,'unavailable');assert.equal(result.reason,'discord_role_lookup_302');assert.equal(result.retryAfterSeconds,5);
 assert.equal(h.requests.length,1);assert.equal(h.requests[0].redirect,'manual');
 const values=[...h.env.CLOUD_ROLE_AUTHORITY.records.values()][0];assert.equal(values.has('verified'),false);
 assert.equal((await h.check()).status,'unavailable');assert.equal(h.requests.length,1);
});
test('real authority shares one lookup across concurrent and serialized tabs, isolates, HTML and bundle requests',async()=>{
 const h=harness();let release;h.provider.wait=new Promise(r=>release=r);const started=new Promise(r=>h.provider.started=r);
 const calls=Array.from({length:4},()=>h.check());await started;assert.equal(h.requests.length,1);release();
 const results=await Promise.all(calls);assert.equal(results.every(r=>r.status==='paid'),true);assert.equal(h.requests.length,1);
 const separate=modules({clock:h.clock,fetchMock:()=>{throw Error('another isolate must use the same namespace');}}).load('./cloud-role-authority');
 for(const route of ['/auth/check','/weak_early_beta_latest.html','/full-data']) assert.equal((await separate.cloudReportRole(h.env,'owner','synthetic-access',route)).status,'paid');
 assert.equal(h.requests.length,1);
});
test('verified role is held at most 90 seconds; removed role closes access at its original deadline',async()=>{
 const h=harness();const initial=await h.check();assert.equal(initial.validUntil,NOW+90000);
 h.provider.roles=[];h.clock.now=NOW+89999;assert.equal((await h.check()).status,'paid');assert.equal(h.requests.length,1);
 h.clock.now=NOW+90000;const removed=await h.check();assert.equal(removed.status,'free');assert.equal(h.requests.length,2);
 assert.equal((await h.check()).status,'free');assert.equal(h.requests.length,2);
});

test('an exhausted successful quota preserves only the original 90 second decision, then waits through restart and token rotation',async()=>{
 const h=harness(),deadline=NOW+3600000;
 h.provider.headers={'x-ratelimit-remaining':'0','x-ratelimit-reset-after':'3600'};
 h.provider.successBody={untrusted_secret:'must-not-be-stored-or-logged',user:{id:'private-provider-user'},access_token:'private-provider-token'};
 const initial=await h.check();assert.equal(initial.status,'paid');assert.equal(initial.checkedAt,NOW);assert.equal(initial.validUntil,NOW+90000);
 const stored=h.env.CLOUD_ROLE_AUTHORITY.records,values=[...stored.values()][0];
 assert.equal(values.get('quotaRetryAt'),deadline);assert.equal(typeof values.get('quotaRetryAt'),'number');assert.equal(values.has('failure'),false);
 const persisted=JSON.stringify([...stored.values()].map(v=>[...v.entries()]));
 assert.doesNotMatch(persisted,/synthetic-access|rotated-access|must-not-be|allowed|owner|private-provider|access_token|user/);
 h.provider.roles=[];h.clock.now=NOW+89999;
 const withinLifetime=await h.check();assert.equal(withinLifetime.status,'paid');assert.equal(withinLifetime.validUntil,NOW+90000);assert.equal(h.requests.length,1);
 h.clock.now=NOW+90000;
 const waiting=await h.check();assert.equal(waiting.status,'unavailable');assert.equal(waiting.reason,'discord_role_rate_limit_wait');assert.equal(waiting.source,'quota_wait');
 assert.equal(waiting.retryAfterSeconds,3510);assert.equal(waiting.validUntil,undefined);assert.equal(h.requests.length,1);
 h.env.CLOUD_ROLE_AUTHORITY=namespace(h.authority.CloudRoleAuthority,h.env,stored);
 h.clock.now=NOW+120000;
 const restarted=await h.check('owner','synthetic-rotated-access');assert.equal(restarted.status,'unavailable');assert.equal(restarted.reason,'discord_role_rate_limit_wait');
 assert.equal(restarted.source,'quota_wait');assert.equal(restarted.retryAfterSeconds,3480);assert.equal(values.get('quotaRetryAt'),deadline);assert.equal(h.requests.length,1);
 h.clock.now=deadline-1;
 const almostReset=await h.check();assert.equal(almostReset.status,'unavailable');assert.equal(almostReset.retryAfterSeconds,1);assert.equal(h.requests.length,1);
 assert.equal(values.get('quotaRetryAt'),deadline);
 h.clock.now=deadline;h.provider.headers={'x-ratelimit-remaining':'3','x-ratelimit-reset-after':'60'};
 const revoked=await h.check('owner','synthetic-rotated-access');assert.equal(revoked.status,'free');assert.equal(revoked.source,'upstream');
 assert.equal(revoked.checkedAt,deadline);assert.equal(revoked.validUntil,deadline+90000);assert.equal(h.requests.length,2);assert.equal(values.has('quotaRetryAt'),false);
});

test('slow successful quota reset is measured from response completion without extending verified lifetime',async()=>{
 const h=harness();h.provider.elapsed=10000;h.provider.headers={'x-ratelimit-remaining':'0','x-ratelimit-reset-after':'3600'};
 const initial=await h.check();assert.equal(initial.checkedAt,NOW);assert.equal(initial.validUntil,NOW+90000);
 const values=[...h.env.CLOUD_ROLE_AUTHORITY.records.values()][0];assert.equal(values.get('quotaRetryAt'),NOW+10000+3600000);
 h.clock.now=NOW+90000;
 const waiting=await h.check();assert.equal(waiting.status,'unavailable');assert.equal(waiting.reason,'discord_role_rate_limit_wait');
 assert.equal(waiting.retryAfterSeconds,3520);assert.equal(h.requests.length,1);
});

for(const headers of [
 {},
 {'x-ratelimit-reset-after':'3600'},
 {'x-ratelimit-remaining':'','x-ratelimit-reset-after':'3600'},
 {'x-ratelimit-remaining':' ','x-ratelimit-reset-after':'3600'},
 {'x-ratelimit-remaining':'invalid','x-ratelimit-reset-after':'3600'},
 {'x-ratelimit-remaining':'-1','x-ratelimit-reset-after':'3600'},
 {'x-ratelimit-remaining':'1','x-ratelimit-reset-after':'3600'},
 {'x-ratelimit-remaining':'0'},
 {'x-ratelimit-remaining':'0','x-ratelimit-reset-after':''},
 {'x-ratelimit-remaining':'0','x-ratelimit-reset-after':' '},
 {'x-ratelimit-remaining':'0','x-ratelimit-reset-after':'0'},
 {'x-ratelimit-remaining':'0','x-ratelimit-reset-after':'-1'},
 {'x-ratelimit-remaining':'0','x-ratelimit-reset-after':'invalid'},
 {'x-ratelimit-remaining':'0','x-ratelimit-reset-after':'Infinity'},
 {'x-ratelimit-remaining':'0','x-ratelimit-reset-after':'1e308'},
])test(`missing, invalid or nonexhausted success quota headers do not create a wait: ${JSON.stringify(headers)}`,async()=>{
 const h=harness();h.provider.headers=headers;
 const initial=await h.check();assert.equal(initial.status,'paid');assert.equal(initial.validUntil,NOW+90000);
 const values=[...h.env.CLOUD_ROLE_AUTHORITY.records.values()][0];assert.equal(values.has('quotaRetryAt'),false);
 h.provider.roles=[];h.clock.now=NOW+90000;
 const removed=await h.check();assert.equal(removed.status,'free');assert.equal(removed.source,'upstream');assert.equal(h.requests.length,2);
 assert.equal(values.has('quotaRetryAt'),false);
});
test('provider 429 is unavailable, never free; deadline survives object restart and token rotation without paid grace',async()=>{
 const h=harness();await h.check();h.clock.now+=90000;h.provider.http=429;
 const failed=await h.check();assert.equal(failed.status,'unavailable');assert.equal(failed.reason,'discord_role_lookup_429');assert.equal(failed.retryAfterSeconds,86374);assert.equal(failed.scope,'user');assert.equal(failed.replyKind,'json');
 const count=h.requests.length;
 const stored=h.env.CLOUD_ROLE_AUTHORITY.records;
 h.env.CLOUD_ROLE_AUTHORITY=namespace(h.authority.CloudRoleAuthority,h.env,stored);
 h.clock.now+=30000;assert.equal((await h.check('owner','synthetic-rotated-access')).status,'unavailable');assert.equal(h.requests.length,count);
 assert.equal((await h.check()).validUntil,undefined);
 const persisted=JSON.stringify([...stored.values()].map(v=>[...v.entries()]));assert.doesNotMatch(persisted,/synthetic-access|rotated-access|must-not-be|allowed|owner/);
 h.clock.now=NOW+90000+86374000;h.provider.http=200;h.provider.roles=[];
 assert.equal((await h.check()).status,'free');assert.equal(h.requests.length,count+1);
});
test('qualification remains separated between owners and allowed-role policy versions',async()=>{
 const h=harness();assert.equal((await h.check('first')).status,'paid');h.provider.roles=[];
 assert.equal((await h.check('second')).status,'free');assert.equal((await h.check('first')).status,'paid');assert.equal(h.requests.length,2);
 h.env.DISCORD_ALLOWED_ROLE_IDS='other-policy';assert.equal((await h.check('first')).status,'free');assert.equal(h.requests.length,3);
});
for(const status of [401,403,404,503])test(`upstream HTTP ${status} never confirms a missing role`,async()=>{
 const h=harness();h.provider.http=status;const result=await h.check();assert.equal(result.status,'unavailable');assert.equal(result.reason,'discord_role_lookup_'+status);
 assert.equal((await h.check()).status,'unavailable');assert.equal(h.requests.length,1);
});

for(const failure of [
 {name:'10-second thrown timeout',provider:{elapsed:10000,error:new DOMException('synthetic timeout','TimeoutError')},reason:'discord_role_network_unavailable'},
 {name:'slow HTTP 503',provider:{elapsed:10000,http:503},reason:'discord_role_lookup_503'},
 {name:'slow invalid roles response',provider:{elapsed:10000,roles:null},reason:'discord_role_response_invalid'},
])test(`${failure.name} waits five seconds after completion, including restart and token rotation`,async()=>{
 const h=harness();Object.assign(h.provider,failure.provider);
 const result=await h.check();const completedAt=h.clock.now,deadline=completedAt+5000;
 assert.equal(completedAt,NOW+10000);assert.equal(result.status,'unavailable');assert.equal(result.reason,failure.reason);assert.equal(result.retryAfterSeconds,5);
 const stored=h.env.CLOUD_ROLE_AUTHORITY.records,values=[...stored.values()][0];
 assert.equal(values.get('failure').retryAt,deadline);
 assert.equal((await h.check()).source,'waiting');assert.equal(h.requests.length,1);
 // Persisted failure must also govern a new object with a newly rotated token.
 h.env.CLOUD_ROLE_AUTHORITY=namespace(h.authority.CloudRoleAuthority,h.env,stored);
 h.clock.now=completedAt+1000;const restarted=await h.check('owner','synthetic-rotated-access');
 assert.equal(restarted.status,'unavailable');assert.equal(restarted.source,'waiting');assert.equal(restarted.retryAfterSeconds,4);assert.equal(h.requests.length,1);
 h.clock.now=deadline-1;const waiting=await h.check();
 assert.equal(waiting.status,'unavailable');assert.equal(waiting.retryAfterSeconds,1);assert.equal(h.requests.length,1);assert.equal(values.get('failure').retryAt,deadline);
 Object.assign(h.provider,{elapsed:0,error:undefined,http:200,roles:['allowed']});h.clock.now=deadline;
 const recovered=await h.check('owner','synthetic-rotated-access');assert.equal(recovered.status,'paid');assert.equal(recovered.source,'upstream');assert.equal(h.requests.length,2);assert.equal(values.has('failure'),false);
});

for(const wait of [
 {name:'Retry-After header',provider:{retryHeader:'17',retry:13},seconds:17},
 {name:'JSON retry_after',provider:{retry:13},seconds:13},
 {name:'invalid Retry-After fallback',provider:{retryHeader:'invalid',retry:0},seconds:5},
])test(`slow 429 preserves its ${wait.name} deadline`,async()=>{
 const h=harness();Object.assign(h.provider,{elapsed:10000,http:429},wait.provider);
 const result=await h.check();const deadline=NOW+10000+wait.seconds*1000;
 assert.equal(result.status,'unavailable');assert.equal(result.reason,'discord_role_lookup_429');assert.equal(result.retryAfterSeconds,wait.seconds);
 const values=[...h.env.CLOUD_ROLE_AUTHORITY.records.values()][0];assert.equal(values.get('failure').retryAt,deadline);
 h.clock.now=deadline-1;assert.equal((await h.check()).source,'waiting');assert.equal(h.requests.length,1);assert.equal(values.get('failure').retryAt,deadline);
 h.clock.now=deadline;Object.assign(h.provider,{elapsed:0,http:200});assert.equal((await h.check()).status,'paid');assert.equal(h.requests.length,2);
});

test('a slow successful lookup keeps its original checkedAt plus 90-second absolute expiry',async()=>{
 const h=harness();h.provider.elapsed=10000;
 const result=await h.check();assert.equal(result.checkedAt,NOW);assert.equal(result.validUntil,NOW+90000);
 h.provider.elapsed=0;h.provider.roles=[];h.clock.now=NOW+89999;assert.equal((await h.check()).status,'paid');assert.equal(h.requests.length,1);
 h.clock.now=NOW+90000;assert.equal((await h.check()).status,'free');assert.equal(h.requests.length,2);
});
test('missing authority fails closed without independent per-isolate fallback',async()=>{
 const h=harness();delete h.env.CLOUD_ROLE_AUTHORITY;assert.equal((await h.check()).status,'unavailable');assert.equal(h.requests.length,0);
});
test('an inherited absolute provider wait suppresses requests without sliding on reload or applying to another owner',async()=>{
 const h=harness();const until=NOW+86374000;
 h.env.CLOUD_ROLE_INITIAL_WAIT=JSON.stringify({member_id:'cloud_'+createHash('sha256').update('cloud-member:owner').digest('hex'),until:new Date(until).toISOString()});
 const first=await h.check();assert.equal(first.status,'unavailable');assert.equal(first.source,'inherited_wait');assert.equal(first.retryAfterSeconds,86374);assert.equal(h.requests.length,0);
 h.clock.now+=60000;const second=await h.check();assert.equal(second.retryAfterSeconds,86314);assert.equal(h.requests.length,0);
 assert.equal((await h.check('another-owner')).status,'paid');assert.equal(h.requests.length,1);
 h.clock.now=until;assert.equal((await h.check()).status,'paid');assert.equal(h.requests.length,2);
});
