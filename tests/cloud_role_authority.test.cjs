const test=require('node:test'),assert=require('node:assert/strict');
const {modules}=require('./helpers/cloud-worker-modules.cjs');
const {namespace}=require('./helpers/cloud-role-authority.cjs');
const {createHash}=require('node:crypto');
const NOW=Date.parse('2026-10-05T00:00:00Z');
function harness() {
 const clock={now:NOW},requests=[],provider={roles:['allowed'],http:200,retry:86374,scope:'user'};
 const fetchMock=async(input,init)=>{requests.push({route:new URL(input).pathname});provider.started?.(); if(provider.wait)await provider.wait;
   if(provider.http===200)return Response.json({roles:provider.roles});
   return Response.json({retry_after:provider.retry,untrusted_secret:'must-not-be-stored-or-logged'},{status:provider.http,headers:{'x-ratelimit-scope':provider.scope}});
 };
 const mod=modules({clock,fetchMock}),authority=mod.load('./cloud-role-authority');
 const env={DISCORD_GUILD_ID:'synthetic-guild',DISCORD_ALLOWED_ROLE_IDS:'allowed',DISCORD_API_BASE:'https://discord.invalid/api',DISCORD_CLIENT_ID:'synthetic-client',SESSION_SECRET:'synthetic-encryption-secret'};
 env.CLOUD_ROLE_AUTHORITY=namespace(authority.CloudRoleAuthority,env);
 return {clock,requests,provider,mod,env,authority,check:(subject='owner',token='synthetic-access')=>authority.cloudReportRole(env,subject,token,'/auth/check')};
}
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
