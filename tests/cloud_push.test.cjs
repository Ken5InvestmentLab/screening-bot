const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const { modules } = require('./helpers/cloud-worker-modules.cjs');
// RFC 8291 section 5 published example. No newly generated signing/identity keys.
const AS = 'BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8';
const D = 'yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw';
const UA = 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4';
const AUTH = 'BTBZMqHH6r4Tts7J_aSIgg', SALT = 'DGv6ra1nlYgDCS1FRnbzlw';
const noGenerate = { subtle: new Proxy(webcrypto.subtle, { get(target, name) {
  if (name === 'generateKey') return () => { throw new Error('key_generation_forbidden'); };
  const value = Reflect.get(target, name); return typeof value === 'function' ? value.bind(target) : value;
} }), getRandomValues: values => webcrypto.getRandomValues(values), randomUUID: () => '11111111-1111-4111-8111-111111111111' };
const cryptoModule = modules({ cryptoMock: noGenerate }).load('./cloud-web-push');
const subscription = { endpoint: 'https://push.example.invalid/device', p256dh: UA, auth: AUTH };
const config = { CLOUD_PUSH_REGISTRATION_ENABLED: 'true', CLOUD_PUSH_ALLOWED_ORIGINS: 'https://push.example.invalid',
  CLOUD_VAPID_PUBLIC_KEY: AS, CLOUD_VAPID_PRIVATE_KEY: D, CLOUD_VAPID_SUBJECT: 'https://cloud.example.invalid/',
  CLOUD_PUSH_MODE: 'personal_test', CLOUD_PUSH_TEST_MEMBER_ID: 'mine', CLOUD_PUSH_TEST_SUBSCRIPTION_ID: 'my-device' };
async function fixture() {
  const point = cryptoModule.decode(AS,65);
  const privateKey = await webcrypto.subtle.importKey('jwk', { kty:'EC', crv:'P-256', x:cryptoModule.encode(point.slice(1,33)), y:cryptoModule.encode(point.slice(33)), d:D }, { name:'ECDH', namedCurve:'P-256' },false,['deriveBits']);
  return { privateKey, publicKey:point, salt:cryptoModule.decode(SALT,16) };
}
test('RFC8291 encryption matches the published section5 binary fixture without generating keys',async()=>{
  const body=await cryptoModule.encryptPushPayload(subscription,'When I grow up, I want to be a watermelon',await fixture());
  const expected='DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN';
  assert.equal(cryptoModule.encode(body),expected);
});
test('VAPID audience, lifetime, HTTPS subject and signature are verified with published fixture keys',async()=>{
 const header=await cryptoModule.vapidAuthorization(new URL(subscription.endpoint),config,1720000000000);
 const token=/^vapid t=(.+), k=/.exec(header)[1],parts=token.split('.');
 const claims=JSON.parse(Buffer.from(parts[1],'base64url'));
 assert.equal(claims.aud,'https://push.example.invalid');assert.equal(claims.exp,1720000000+3600);assert.equal(claims.sub,config.CLOUD_VAPID_SUBJECT);
 const publicKey=await webcrypto.subtle.importKey('raw',cryptoModule.decode(AS),{name:'ECDSA',namedCurve:'P-256'},false,['verify']);
 assert.equal(await webcrypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},publicKey,cryptoModule.decode(parts[2]),new TextEncoder().encode(parts.slice(0,2).join('.'))),true);
 await assert.rejects(cryptoModule.vapidAuthorization(new URL(subscription.endpoint),{...config,CLOUD_VAPID_SUBJECT:'mailto:unused@example.invalid'}));
});
for(const endpoint of ['http://push.example.invalid/a','https://127.0.0.1/a','https://push.example.invalid.evil.invalid/a','https://user@push.example.invalid/a','https://push.example.invalid:444/a','https://push.example.invalid/a#fragment'])test('sender rejects unapproved endpoint '+endpoint,()=>assert.throws(()=>cryptoModule.allowedEndpoint(endpoint,config)));
test('default-off, wrong member and wrong device never encrypt or call transport',async()=>{
 let calls=0;const transport=()=>{calls++;throw new Error('forbidden');};
 for(const [env,member,device] of [[{},'mine','my-device'],[config,'other','my-device'],[config,'mine','other'],[{...config,CLOUD_PUSH_MODE:'members'},'mine','my-device']])assert.equal((await cryptoModule.sendPersonalPush(env,member,device,subscription,'test',transport)).status,'disabled');
 assert.equal(calls,0);
});
test('owner registration-only mode cannot send, and scheduled owner mode cannot use the legacy manual sender',async()=>{
 let calls=0;
 const transport=async()=>{calls++;return new Response('',{status:201});};
 const member='cloud_'+'a'.repeat(64);
 const base={...config,CLOUD_PUSH_TEST_MEMBER_ID:member,CLOUD_OWNER_ONLY_ENABLED:'true',CLOUD_NEW_A_OWNER_PUSH_ENABLED:'true'};
 const register={...base,CLOUD_PUSH_MODE:'new_a_owner_registration'};
 const scheduled={...base,CLOUD_PUSH_MODE:'new_a_owner_scheduled'};
 for(const env of [register,scheduled])assert.equal((await cryptoModule.sendPersonalPush(env,member,'my-device',subscription,'fixture',transport)).status,'disabled');
 assert.equal((await cryptoModule.sendNewAOwnerPush(register,member,'my-device',subscription,'fixture',transport)).status,'disabled');
 assert.equal((await cryptoModule.sendNewAOwnerPush({...scheduled,CLOUD_NEW_A_OWNER_PUSH_ENABLED:'false'},member,'my-device',subscription,'fixture',transport)).status,'disabled');
 assert.equal(calls,0);
 assert.equal((await cryptoModule.sendNewAOwnerPush(scheduled,member,'my-device',subscription,'fixture',transport,await fixture())).status,'accepted');
 assert.equal(calls,1);
});
for(const [http,status] of [[201,'accepted'],[404,'expired'],[410,'expired'],[429,'rejected'],[503,'rejected']])test('personal sender records HTTP '+http+' as '+status+' without claiming arrival',async()=>{
 let calls=0;const result=await cryptoModule.sendPersonalPush(config,'mine','my-device',subscription,'本人端末テスト',async(url,init)=>{
 calls++;assert.equal(url,subscription.endpoint);assert.equal(init.redirect,'error');assert.equal(init.headers['Content-Encoding'],'aes128gcm');assert.equal(init.headers.TTL,'300');assert.ok(init.body.length>86);return new Response('',{status:http});},await fixture());
 assert.equal(calls,1);assert.equal(result.status,status);assert.doesNotMatch(JSON.stringify(result),/vapid|device|endpoint|yfWP/);
});
test('lost response is unknown and caller receives no automatic retry instruction',async()=>{
 let calls=0;const result=await cryptoModule.sendPersonalPush(config,'mine','my-device',subscription,'test',async()=>{calls++;throw new Error('connection_lost');},await fixture());
 assert.equal(calls,1);assert.equal(result.status,'unknown');assert.match(result.reason,/no_auto_retry/);
});
test('subscription validates actual curve point, canonical encoding and auth length',async()=>{
 const good={endpoint:subscription.endpoint,expirationTime:null,keys:{p256dh:UA,auth:AUTH}};
 assert.equal((await cryptoModule.validateSubscription(good,config)).p256dh,UA);
 for(const bad of [{...good,email:'unused'}, {...good,keys:{p256dh:UA,auth:'AA'}}, {...good,keys:{p256dh:'A'.repeat(87),auth:AUTH}}, {...good,expirationTime:1}]) await assert.rejects(cryptoModule.validateSubscription(bad,config));
});
function database(owner='mine') {
 const statements=[];let batchCalls=0;
 return {statements,get batchCalls(){return batchCalls;},prepare(sql){const query={sql,values:[],bind(...values){this.values=values;return this;},async first(){return sql.includes('SELECT revoked_at')?(this.values[0]===owner?{revoked_at:null}:null):sql.includes('WHERE endpoint')?{subscription_id:'11111111-1111-4111-8111-111111111111',member_id:owner}:null;},async all(){return {success:true,results:[]};},async run(){statements.push(this);return {success:true,meta:{changes:1}};}};return query;},async batch(rows){batchCalls++;return Promise.all(rows.map(row=>row.run()));}};
}
function request(path,method='GET',body){return new Request('https://cloud.example.invalid'+path,{method,headers:body?{'content-type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{})});}
const push=modules({cryptoMock:noGenerate}).load('./cloud-push');
test('config exposes only own opaque device list; disabled mode excludes even public key',async()=>{
 const db=database(), response=await push.pushApi(request('/api/cloud/push-config'),{CLOUD_DB:db},{memberId:'mine',roleAuthorized:true,membership:async()=>({status:'paid'})});
 const value=await response.json();assert.equal(value.registration_available,false);assert.equal(value.delivery_available,false);assert.equal(value.public_key,undefined);assert.equal(response.headers.get('cache-control'),'private, no-store');
});
test('only the fixed verified owner can prepare a registration-only device before its origin is known',async()=>{
 const memberId='cloud_'+'a'.repeat(64), db=database(memberId);
 const owner={memberId,ownerVerified:true,roleAuthorized:true,membership:async()=>({status:'paid'})};
 const env={...config,CLOUD_DB:db,CLOUD_PUSH_MODE:'new_a_owner_registration',CLOUD_OWNER_ONLY_ENABLED:'true',
  CLOUD_PUSH_TEST_MEMBER_ID:memberId,CLOUD_PUSH_AUDIENCE:'paid',CLOUD_PUSH_ALLOWED_ORIGINS:'',CLOUD_PUSH_TEST_RUN_ID:'legacy_retained_fixture'};
 const endpointPath='/api/cloud/push-config';
 const allowed=await(await push.pushApi(request(endpointPath),env,owner)).json();
 assert.equal(allowed.owner_enrollment_available,true);assert.equal(allowed.preparation_available,true);
 assert.equal(allowed.registration_available,false);assert.equal(allowed.personal_test_available,false);
 for(const rejected of [{...owner,ownerVerified:false},{...owner,memberId:'cloud_'+'b'.repeat(64)}]){
  assert.equal((await push.pushApi(request(endpointPath),env,rejected)).status,403);
 }
 const unauthenticated=await(await push.pushApi(request(endpointPath),env,{...owner,roleAuthorized:false})).json();
 assert.equal(unauthenticated.owner_enrollment_available,false);
 assert.equal(db.batchCalls,0);
});
for(const status of ['paid','free','unavailable','unverified'])test('notification config contains no paid-plan offer: '+status,async()=>{
 const configured=JSON.parse(fs.readFileSync(require('node:path').resolve(__dirname,'../weak-early-beta-gate/wrangler.jsonc'),'utf8')).vars.ACCESS_PURCHASE_URL;
 const db=database(),response=await push.pushApi(request('/api/cloud/push-config'),{CLOUD_DB:db,ACCESS_PURCHASE_URL:configured},{memberId:'mine',roleAuthorized:status==='paid',membership:async()=>({status,reason:'fixture'})});
 const value=await response.json();assert.equal(value.purchase_url,undefined);assert.equal(db.batchCalls,0);
});
for(const status of ['free','expired','unverified','unavailable'])test('registration refuses '+status+' without any write',async()=>{
 const db=database();const response=await push.pushApi(request('/api/cloud/push-subscriptions','POST',{opt_in:true,subscription:{endpoint:subscription.endpoint,keys:{p256dh:UA,auth:AUTH}}}),{...config,CLOUD_DB:db},{memberId:'mine',roleAuthorized:true,membership:async()=>({status})});assert.equal(response.status,403);assert.equal(db.batchCalls,0);
});
test('registration cannot take over another account subscription',async()=>{
 const db=database('another');const response=await push.pushApi(request('/api/cloud/push-subscriptions','POST',{opt_in:true,subscription:{endpoint:subscription.endpoint,keys:{p256dh:UA,auth:AUTH}}}),{...config,CLOUD_DB:db},{memberId:'mine',roleAuthorized:true,membership:async()=>({status:'paid'})});assert.equal(response.status,409);assert.equal(db.batchCalls,0);
});
test('explicit opt-in atomically saves session-owned device and metadata without enabling preferences',async()=>{
 const db=database();const response=await push.pushApi(request('/api/cloud/push-subscriptions','POST',{opt_in:true,subscription:{endpoint:subscription.endpoint,keys:{p256dh:UA,auth:AUTH}}}),{...config,CLOUD_DB:db},{memberId:'mine',roleAuthorized:true,membership:async()=>({status:'paid'})});assert.equal(response.status,200);assert.equal(db.batchCalls,1);assert.equal(db.statements.length,2);assert.doesNotMatch(db.statements.map(row=>row.sql).join(''),/preferences/);assert.equal(db.statements[0].values[1],'mine');assert.equal((await response.json()).delivery_available,false);
});
test('expired member can revoke only their own device',async()=>{
 const db=database();const response=await push.pushApi(request('/api/cloud/push-subscriptions/device','DELETE',{subscription_id:'11111111-1111-4111-8111-111111111111'}),{CLOUD_DB:db},{memberId:'mine',roleAuthorized:false,membership:async()=>{throw Error('must_not_require_payment');}});assert.equal(response.status,200);assert.match(db.statements[0].sql,/member_id = \? AND subscription_id = \?/);assert.equal(db.statements[0].values[1],'mine');
});

test('device revoke changes exactly one owned row, is idempotent, and rejects other owners',async()=>{
 const otherId='22222222-2222-4222-8222-222222222222',mine='11111111-1111-4111-8111-111111111111';
 const rows=[{member_id:'mine',subscription_id:mine,revoked_at:null},{member_id:'mine',subscription_id:otherId,revoked_at:null},{member_id:'other',subscription_id:'33333333-3333-4333-8333-333333333333',revoked_at:null}];
 let writes=0;
 const db={prepare(sql){return {bind(...values){this.values=values;return this;},async first(){assert.match(sql,/SELECT revoked_at/);return rows.find(r=>r.member_id===this.values[0]&&r.subscription_id===this.values[1])||null;},async run(){assert.match(sql,/WHERE member_id = \? AND subscription_id = \? AND revoked_at IS NULL/);writes++;let changes=0;for(const row of rows)if(row.member_id===this.values[1]&&row.subscription_id===this.values[2]&&!row.revoked_at){row.revoked_at=this.values[0];changes++;}return {success:true,meta:{changes}};}};}};
 const context={memberId:'mine',roleAuthorized:false,membership:async()=>{throw Error('must-not-change-membership');}};
 const revoke=id=>push.pushApi(request('/api/cloud/push-subscriptions/device','DELETE',{subscription_id:id}),{CLOUD_DB:db},context);
 assert.equal((await revoke(mine)).status,200);assert.ok(rows[0].revoked_at);assert.equal(rows[1].revoked_at,null);assert.equal(rows[2].revoked_at,null);
 assert.equal((await revoke(mine)).status,200);assert.equal(writes,1);
 const denied=await revoke(rows[2].subscription_id);assert.equal(denied.status,404);assert.notEqual((await denied.json()).device_revoked,true);assert.equal(writes,1);
});
test('fresh-role option bypasses cached authorization and refuses 429 grace',async()=>{
 for(const code of [200,429,503,403]){
 let reads=0;const m=modules({fetchMock:async()=>{reads++;return new Response(JSON.stringify({roles:[]}),{status:code});}});const gate=m.load('./shared-report-gate');const now=Math.floor(Date.now()/1000);const env={SESSION_SECRET:'test-secret-long-enough-only-fixture',DISCORD_ALLOWED_ROLE_IDS:'role',DISCORD_GUILD_ID:'guild'};
 const session=await gate.__test.createSession({sub:'mine',accessToken:'fixture',exp:now+86400,tokenExp:now+3600,roleCheckedAt:now,roles:['role']},env.SESSION_SECRET);
 const req=new Request('https://cloud.example.invalid/',{headers:{cookie:'__Host-report_gate_session='+encodeURIComponent(session)}});
 assert.equal((await gate.reportIdentity(req,env)).discord_authorized,true);assert.equal(reads,0);
 assert.equal((await gate.reportIdentity(req,env,true)).discord_authorized,false);assert.equal(reads,1);
 }
});
test('service worker has no fetch cache and clicks only fixed same-origin report',async()=>{
 const handlers={},opened=[],shown=[];const self={location:{href:'https://cloud.example.invalid/weak-early-beta-service-worker.js'},addEventListener:(name,fn)=>handlers[name]=fn,registration:{showNotification:async(...args)=>shown.push(args)},clients:{matchAll:async()=>[],openWindow:async url=>opened.push(url)}};
 vm.runInNewContext(fs.readFileSync(require('node:path').resolve(__dirname,'../reports/weak-early-beta-service-worker.js'),'utf8'),{self,URL,crypto:webcrypto,TextEncoder,Uint8Array});
 assert.deepEqual(Object.keys(handlers).sort(),['notificationclick','push']);let wait;
 handlers.push({data:{json:()=>({version:1,kind:'reminder',body:'今日は、設定した確定日です',tag:'private-signal'})},waitUntil:p=>wait=p});await wait;assert.equal(shown.length,1);assert.equal(shown[0][0],'確定日の朝8時（日本時間）');assert.equal(shown[0][1].body,'今日は、設定した確定日です');assert.match(shown[0][1].tag,/^[0-9a-f]{64}$/);assert.doesNotMatch(JSON.stringify(shown),/private-signal/);
 handlers.push({data:{json:()=>({version:1,kind:'result',body:'fake',tag:'fake'})},waitUntil:()=>assert.fail('removed result')});assert.equal(shown.length,1);
 handlers.notificationclick({notification:{close(){},data:{url:'https://evil.invalid/'}},waitUntil:p=>wait=p});await wait;assert.deepEqual(opened,['https://cloud.example.invalid/weak_early_beta_latest.html']);
});

async function dispatchHarness({ optIn=true, optOutBeforeFinal=false, roleNetworkFailure=false, providerStatus=200, revokeBeforeSend=false, roleStatus=200, transportFailure=false, eventOverride={}, background=false, removeRoleBeforeSend=false, wrongReturnedSubject=false, wrongConfiguredSubject=false, deviceMissing=false, deviceTest=false, testRunId='personal_test_20261004', wrongMember=false, audience }={}) {
 let memberId, roleReads=0, paymentReads=0, delivered=0;const receipts=new Map();
 const subject=background?'123456789012345678':'discord-user',role=background?'234567890123456789':'role';
 const now=Date.now(), start=new Date(now-86400000).toISOString(), end=new Date(now+86400000*30).toISOString();
 const membership={id:'mem_1',user_id:'user_1',account:{id:'biz_1'},product_id:'prod_1',plan_id:'plan_1',status:'active',current_period_start:start,current_period_end:end,cancel_at_period_end:false};
 const payment={id:'pay_1',membership_id:'mem_1',account_id:'biz_1',user:{id:'user_1'},status:'paid',total:{amount:'1000',currency:'jpy'},refunded_amount:{amount:'0',currency:'jpy'},paid_at:start};
 const event={signal_id:'private-signal',kind:'new_detection',detection_date:new Date(now+9*3600000).toISOString().slice(0,10),adapter_version:'cloud-ledger-v1',source_ledger_revision:'a'.repeat(64),signal_actual_close:1000,signal_price_status:'verified',endpoints:{d5_close:{date:'2026-10-09'},d6_open:{date:'2026-10-13'}},...eventOverride};
 const m=modules({cryptoMock:noGenerate,fetchMock:async(input)=>{
 const url=String(input);
 if(url.includes('discord.com')){roleReads++;if(roleNetworkFailure)throw Error('fixture-network-failure');if(optOutBeforeFinal)optIn=false;if(background)assert.equal(url,`https://discord.com/api/v10/guilds/345678901234567890/members/${subject}`);return new Response(JSON.stringify({user:{id:wrongReturnedSubject?'456789012345678901':subject},roles:roleStatus===200&&!(removeRoleBeforeSend&&(deviceTest||roleReads>1))?[role]:[]}),{status:roleStatus});}
 assert.match(url,/^https:\/\/api\.whop\.com\//);paymentReads++;
 if(providerStatus!==200)return new Response('',{status:providerStatus});
 if(url.includes('/memberships/'))return Response.json({...membership,status:revokeBeforeSend&&paymentReads>3?'revoked':'active'});
 if(url.includes('/payments?'))return Response.json({data:[payment]});return Response.json(payment);
 }});
 const db={prepare(sql){return {values:[],bind(...values){this.values=values;return this;},async first(){
 if(sql.includes('cloud_member_links')){assert.equal(background||deviceTest,false,'managed role must not query a Whop identity link');return {member_id:memberId,discord_user_id:subject,whop_user_id:'user_1',membership_id:'mem_1',payment_id:'pay_1',environment:'live',verification_method:'verified_operator',evidence_reference:'operator-proof',verified_at:start,revoked_at:null};}
 if(sql.includes('cloud_notification_events'))return {event_json:JSON.stringify(event),source_ledger_revision:'a'.repeat(64)};
 if(sql.includes('cloud_member_preferences'))return {preferences_json:JSON.stringify({max_price:1000,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,notifications:{new_detection:optIn,reminder:false}})};
 if(sql.includes('cloud_push_subscriptions'))return deviceMissing?null:{...subscription,member_id:memberId,subscription_id:'my-device',vapid_public_key:AS,expires_at_ms:null};
 throw Error('unhandled_query');},async run(){const key=this.values.slice(sql.startsWith('UPDATE')?3:0,sql.startsWith('UPDATE')?6:3).join(':');if(sql.startsWith('INSERT OR IGNORE')){const exists=receipts.has(key);if(!exists)receipts.set(key,{status:'preparing'});return {success:true,meta:{changes:exists?0:1}};}if(sql.startsWith('UPDATE')){receipts.set(key,{status:this.values[0],reason:this.values[1]});return {success:true,meta:{changes:1}};}throw Error('unhandled_write');}};}};
 const api=m.load('./cloud-api');memberId=await api.cloudMemberId(subject);
 const env={...config,CLOUD_PUSH_AUDIENCE:audience,CLOUD_DB:db,CLOUD_PUSH_TEST_MEMBER_ID:wrongMember?'other-member':memberId,CLOUD_PUSH_TEST_RUN_ID:testRunId,SESSION_SECRET:'fixture-only-secret-long-enough',DISCORD_GUILD_ID:background?'345678901234567890':'guild',DISCORD_ALLOWED_ROLE_IDS:role,...(background||deviceTest?{CLOUD_PUSH_MEMBERSHIP_POLICY:'whop_managed_discord_role',...(background?{CLOUD_DISCORD_BOT_TOKEN:'fixture-only-bot',CLOUD_PUSH_TEST_DISCORD_USER_ID:wrongConfiguredSubject?'456789012345678901':subject}:{})}:{WHOP_API_KEY:'fixture-only-whop',WHOP_ACCOUNT_ID:'biz_1',WHOP_PRODUCT_IDS:'prod_1',WHOP_PAID_PLAN_IDS:'plan_1'})};
 const sec=Math.floor(now/1000);const session=await m.load('./shared-report-gate').__test.createSession({sub:subject,accessToken:'fixture',exp:sec+86400,tokenExp:sec+3600,roleCheckedAt:sec,roles:[role]},env.SESSION_SECRET);
 const req=new Request('https://cloud.example.invalid/',{headers:{cookie:'__Host-report_gate_session='+encodeURIComponent(session)}});
 const dispatch=m.load('./cloud-push-dispatch');
 const material=await fixture();const transport=async()=>{delivered++;if(transportFailure)throw Error('lost');return new Response('',{status:201});};
 return {call:()=>deviceTest?dispatch.dispatchPersonalDeviceTest(req,env,transport,material):background?dispatch.dispatchBackgroundPersonalCandidate(env,'trusted-server-source-event',transport,material):dispatch.dispatchPersonalCandidate(req,env,'trusted-server-source-event',transport,material),httpCall:()=>api.cloudApi(new Request('https://cloud.example.invalid/api/cloud/notifications/personal-test',{method:'POST',headers:{origin:'https://cloud.example.invalid','content-type':'application/json',cookie:req.headers.get('cookie')},body:'{}'}),env),receipts,get delivered(){return delivered;},get roleReads(){return roleReads;},get paymentReads(){return paymentReads;}};
}
test('dispatcher rechecks role/payment/opt-in before send and atomically prevents concurrent duplicates',async()=>{
 const h=await dispatchHarness();const results=await Promise.all([h.call(),h.call()]);assert.equal(h.delivered,1);assert.equal(results.filter(r=>r.status==='accepted').length,1);assert.equal(results.filter(r=>r.reason==='duplicate_or_uncertain_delivery').length,1);assert.ok(h.roleReads>=3);assert.ok(h.paymentReads>=6);assert.equal((await h.call()).status,'suppressed');assert.equal(h.delivered,1);
});
for(const [label,options] of [['OFF',{optIn:false}],['provider error',{providerStatus:503}],['provider429',{providerStatus:429}],['fresh role429',{roleStatus:429}],['revoked before send',{revokeBeforeSend:true}]])test('dispatcher holds/suppresses '+label+' with zero transport calls',async()=>{
 const h=await dispatchHarness(options);assert.notEqual((await h.call()).status,'accepted');assert.equal(h.delivered,0);
});
test('uncertain personal delivery is never retried even when called again',async()=>{
 const h=await dispatchHarness({transportFailure:true});assert.equal((await h.call()).status,'unknown');assert.equal((await h.call()).status,'suppressed');assert.equal(h.delivered,1);assert.equal([...h.receipts.values()][0].status,'unknown');
});
test('personal-test config cannot register or expose a VAPID key to a different paid member',async()=>{
 const db=database(),context={memberId:'another',roleAuthorized:true,membership:async()=>({status:'paid'})};
 const value=await (await push.pushApi(request('/api/cloud/push-config'),{...config,CLOUD_DB:db},context)).json();
 assert.equal(value.registration_available,false);assert.equal(value.public_key,undefined);
 const response=await push.pushApi(request('/api/cloud/push-subscriptions','POST',{opt_in:true,subscription:{endpoint:subscription.endpoint,keys:{p256dh:UA,auth:AUTH}}}),{...config,CLOUD_DB:db},context);
 assert.equal(response.status,403);assert.equal(db.batchCalls,0);
});

test('personal origin discovery is owner-only and cannot persist/send before an exact allowlist',async()=>{
 const env={...config,CLOUD_DB:database(),CLOUD_PUSH_ALLOWED_ORIGINS:''};
 const context={memberId:'mine',roleAuthorized:true,membership:async()=>({status:'paid'})};
 const value=await(await push.pushApi(request('/api/cloud/push-config'),env,context)).json();
 assert.equal(value.preparation_available,true);assert.equal(value.registration_available,false);
 assert.equal(value.public_key,AS);assert.deepEqual(value.allowed_origins,[]);assert.equal(value.personal_test_available,false);
 const post=await push.pushApi(request('/api/cloud/push-subscriptions','POST',{opt_in:true,subscription:{endpoint:subscription.endpoint,keys:{p256dh:UA,auth:AUTH}}}),env,context);
 assert.equal(post.status,503);assert.equal(env.CLOUD_DB.batchCalls,0);
 for(const context of [{memberId:'other',roleAuthorized:true,membership:async()=>({status:'paid'})},
   {memberId:'mine',roleAuthorized:false,membership:async()=>({status:'paid'})},
   {memberId:'mine',roleAuthorized:true,membership:async()=>({status:'unavailable'})}]) {
   const denied=await(await push.pushApi(request('/api/cloud/push-config'),env,context)).json();
   assert.equal(denied.preparation_available,false);assert.equal(denied.public_key,undefined);
 }
});

test('browser preparation displays origin only, preserves pending subscription and saves once after exact approval',async()=>{
 const elements=new Map();
 const windowEvents=new Map();
 const element=()=>({hidden:false,disabled:false,textContent:'',listeners:{},append(){},setAttribute(){},addEventListener(name,fn){this.listeners[name]=fn;}});
 const host=element();host.prepend=()=>{};
 const document={getElementById:()=>host,createElement:()=>{const e=element();Object.defineProperty(e,'id',{set(id){elements.set(id,e);}});return e;}};
 let permissions=0,registrations=0,subscriptions=0,saves=0,unsubscribes=0,saved=false,allowed=false;
 const sub={endpoint:'https://push.example.invalid/private-device-token',toJSON:()=>({endpoint:subscription.endpoint,keys:{p256dh:UA,auth:AUTH}}),unsubscribe:async()=>{unsubscribes++;}};
 const worker={pushManager:{getSubscription:async()=>subscriptions?sub:null,subscribe:async()=>{subscriptions++;return sub;}}};
 const configValue=async()=>({ok:true,registration_available:allowed,preparation_available:true,public_key:AS,allowed_origins:allowed?['https://push.example.invalid']:[],devices:saved?[{subscription_id:'mine-device',endpoint_hash:await push.endpointHash(sub.endpoint)}]:[]});
 const api=async(path,init)=>{
   if(path==='/api/cloud/push-config')return Response.json(await configValue());
   assert.equal(path,'/api/cloud/push-subscriptions');assert.equal(init.method,'POST');assert.equal(allowed,true);saves++;saved=true;return Response.json({ok:true});
 };
 vm.runInNewContext(fs.readFileSync(require('node:path').resolve(__dirname,'../reports/weak-early-beta-push.js'),'utf8'),{
   document,window:{isSecureContext:true,PushManager:{},Notification:{},addEventListener:(name,fn)=>windowEvents.set(name,fn)},navigator:{serviceWorker:{getRegistration:async()=>subscriptions?worker:null,register:async()=>{registrations++;return worker;},ready:Promise.resolve(worker)}},
   Notification:{requestPermission:async()=>{permissions++;return 'granted';}},fetch:api,URL,crypto:webcrypto,TextEncoder,Uint8Array,atob,
 });
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(permissions,0);assert.equal(registrations,0);assert.equal(subscriptions,0);
 const enable=()=>new Promise(resolve=>windowEvents.get('cloud-notification-enable')({detail:{complete:resolve}}));
 assert.equal(await enable(),false);
 assert.equal(saves,0);assert.equal(subscriptions,1);assert.equal(unsubscribes,0);
 assert.equal(elements.get('cloud-device-provider-origin').textContent,'通知サービスのorigin: https://push.example.invalid');
 assert.doesNotMatch(elements.get('cloud-device-provider-origin').textContent,/private-device-token/);
 allowed=true;assert.equal(await enable(),true);
 assert.equal(subscriptions,1);assert.equal(saves,1);assert.equal(unsubscribes,0);
 assert.equal(elements.get('cloud-device-register'),undefined);assert.equal(elements.get('cloud-device-registration').textContent,'登録済み');
});
test('persisted old detections and malformed canonical events cause no send or reservation',async()=>{
 for(const eventOverride of [{detection_date:'2020-01-02'},{detection_date:'2099-01-01'},{endpoints:null},{kind:'unexpected'}]) {
  const h=await dispatchHarness({eventOverride});assert.notEqual((await h.call()).status,'accepted');assert.equal(h.delivered,0);assert.equal(h.receipts.size,0);
 }
});

test('approved managed-role background path reads exact member twice, no Whop API/link, one device once',async()=>{
 const h=await dispatchHarness({background:true});assert.equal((await h.call()).status,'accepted');assert.equal(h.roleReads,2);assert.equal(h.paymentReads,0);assert.equal(h.delivered,1);
 assert.equal((await h.call()).status,'suppressed');assert.equal(h.delivered,1);
});
for(const [label,options] of [['revoked role',{roleStatus:200,removeRoleBeforeSend:true}],['Discord429',{roleStatus:429}],['Discord503',{roleStatus:503}],['wrong member response',{wrongReturnedSubject:true}],['wrong configured member',{wrongConfiguredSubject:true}],['missing device',{deviceMissing:true}],['opt-in OFF',{optIn:false}]])test('managed-role background '+label+' makes zero sends and no Whop reads',async()=>{
 const h=await dispatchHarness({background:true,...options});assert.notEqual((await h.call()).status,'accepted');assert.equal(h.delivered,0);assert.equal(h.paymentReads,0);
});
test('managed-role unknown outcome stays non-retryable',async()=>{
 const h=await dispatchHarness({background:true,transportFailure:true});assert.equal((await h.call()).status,'unknown');assert.equal((await h.call()).status,'suppressed');assert.equal(h.delivered,1);
});

test('explicit device test needs no Bot/Whop credentials and preserves a one-time receipt',async()=>{
 const h=await dispatchHarness({deviceTest:true});assert.equal((await h.call()).status,'accepted');assert.equal(h.roleReads,1);assert.equal(h.paymentReads,0);assert.equal(h.delivered,1);
 assert.equal((await h.call()).status,'suppressed');assert.equal(h.delivered,1);
 assert.match([...h.receipts.keys()][0],/personal-device-test:personal_test_20261004$/);
});
for(const [label,options] of [['opt-in OFF',{optIn:false}],['role removed',{removeRoleBeforeSend:true}],['Discord429',{roleStatus:429}],['missing device',{deviceMissing:true}],['wrong member',{wrongMember:true}],['no approved run ID',{testRunId:''}]])test('explicit device test '+label+' sends nothing',async()=>{
 const h=await dispatchHarness({deviceTest:true,...options});assert.notEqual((await h.call()).status,'accepted');assert.equal(h.delivered,0);assert.equal(h.paymentReads,0);
});
test('explicit device test unknown response never retries',async()=>{
 const h=await dispatchHarness({deviceTest:true,transportFailure:true});assert.equal((await h.call()).status,'unknown');assert.equal((await h.call()).status,'suppressed');assert.equal(h.delivered,1);
});

for(const options of [{removeRoleBeforeSend:true},{roleStatus:429},{roleStatus:503},{roleNetworkFailure:true}])test('manual HTTP dispatch never sends on cached paid roles when the one final lookup fails '+JSON.stringify(options),async()=>{
 const h=await dispatchHarness({deviceTest:true,...options});
 const response=await h.httpCall(),value=await response.json();
 assert.equal(value.status,'held');assert.equal(value.reason,options.removeRoleBeforeSend?'fresh_discord_role_required':'fresh_discord_role_unavailable');
 assert.equal(value.arrival_confirmed,false);assert.equal(h.roleReads,1);assert.equal(h.delivered,0);
 assert.equal(h.receipts.size,1);assert.equal([...h.receipts.values()][0].status,'held');
 assert.equal((await (await h.httpCall()).json()).status,'suppressed');assert.equal(h.roleReads,1);
});

for(const options of [{optIn:false},{optOutBeforeFinal:true}])test('manual HTTP dispatch stops when opt-in is OFF, including after reservation '+JSON.stringify(options),async()=>{
 const h=await dispatchHarness({deviceTest:true,...options});const value=await (await h.httpCall()).json();
 assert.equal(value.status,'held');assert.equal(value.reason,'notification_opt_in_required');assert.equal(h.delivered,0);
 assert.equal(h.roleReads,options.optOutBeforeFinal?1:0);assert.equal(h.receipts.size,options.optOutBeforeFinal?1:0);
});
test('device test HTTP route requires same-origin authenticated empty POST and never claims OS arrival',async()=>{
 const m=modules(),env={CLOUD_DB:database(),SESSION_SECRET:'fixture-only-secret-long-enough',DISCORD_GUILD_ID:'guild',DISCORD_ALLOWED_ROLE_IDS:'role'};
 const sec=Math.floor(Date.now()/1000),session=await m.load('./shared-report-gate').__test.createSession({sub:'mine',accessToken:'fixture',exp:sec+86400,tokenExp:sec+3600,roleCheckedAt:sec,roles:['role']},env.SESSION_SECRET);
 const req=(body={},origin='https://cloud.example.invalid',authenticated=true,method='POST')=>new Request('https://cloud.example.invalid/api/cloud/notifications/personal-test',{method,headers:{origin,'content-type':'application/json',...(authenticated?{cookie:'__Host-report_gate_session='+encodeURIComponent(session)}:{})},...(method==='POST'?{body:JSON.stringify(body)}:{})});
 const api=m.load('./cloud-api');
 assert.equal((await api.cloudApi(req({},'https://other.invalid'),env)).status,403);
 assert.equal((await api.cloudApi(req({},undefined,false),env)).status,401);
 assert.equal((await api.cloudApi(req({},undefined,true,'GET'),env)).status,405);
 for(const field of ['event','member_id','subscription_id','message'])assert.equal((await api.cloudApi(req({[field]:'forged'}),env)).status,400);
 const response=await api.cloudApi(req(),env),value=await response.json();assert.equal(response.status,200);assert.equal(value.status,'disabled');assert.equal(value.arrival_confirmed,false);assert.equal(response.headers.get('cache-control'),'private, no-store');
});

test('managed-role policy is explicit, requires fresh evidence, and never falls back to payment API',async()=>{
 const api=modules().load('./cloud-api'),env={CLOUD_PUSH_MEMBERSHIP_POLICY:'whop_managed_discord_role'};
 assert.equal((await api.currentMembership(env,'member')).status,'unavailable');
 assert.equal((await api.currentMembership(env,'member',true)).status,'paid');
 assert.equal((await api.currentMembership(env,'member',false)).status,'free');
 assert.equal((await api.currentMembership({CLOUD_PUSH_MEMBERSHIP_POLICY:'unknown'},'member',true)).status,'unavailable');
 assert.equal((await api.currentMembership({},'member',true)).status,'unavailable');
});
for(const audience of [undefined,'authenticated'])for(const [roleStatus,rolePresent] of [[200,true],[200,false],[401,true],[403,true],[404,true],[429,true],[503,true]])test('managed-role preference read/enable uses one fresh role; OFF save remains independent: '+roleStatus+'/'+rolePresent+'/'+audience,async()=>{
 let reads=0,writes=0;
 const m=modules({fetchMock:async input=>{assert.match(String(input),/^https:\/\/discord\.com\//);reads++;return Response.json({roles:rolePresent?['role']:[]},{status:roleStatus});}});
 const prefs={max_price:1000,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,notifications:{new_detection:false,reminder:false}};
 const db={prepare(){return {bind(){return this;},async first(){return null;},async run(){writes++;return {success:true,meta:{changes:1}};}};}};
 const env={CLOUD_PUSH_AUDIENCE:audience,CLOUD_DB:db,SESSION_SECRET:'fixture-only-secret-long-enough',DISCORD_GUILD_ID:'guild',DISCORD_ALLOWED_ROLE_IDS:'role',CLOUD_PUSH_MEMBERSHIP_POLICY:'whop_managed_discord_role'};
 const sec=Math.floor(Date.now()/1000),session=await m.load('./shared-report-gate').__test.createSession({sub:'member',accessToken:'fixture',exp:sec+86400,tokenExp:sec+3600,roleCheckedAt:sec-3600,roles:['role']},env.SESSION_SECRET);
 const req=(method,body)=>new Request('https://cloud.example.invalid/api/cloud/preferences',{method,headers:{cookie:'__Host-report_gate_session='+encodeURIComponent(session),origin:'https://cloud.example.invalid',...(body?{'content-type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const eligible=roleStatus===200&&(rolePresent||audience==='authenticated');
 const api=m.load('./cloud-api');const response=await api.cloudApi(req('GET'),env);assert.equal(response.status,200);const readBody=await response.json();assert.equal(readBody.membership.status,roleStatus===200?(rolePresent?'paid':'free'):'unavailable');assert.equal(readBody.membership.reason,roleStatus===200?(rolePresent?'verified_whop_managed_discord_role':'managed_role_revoked'):'discord_role_lookup_'+roleStatus);assert.equal(reads,1);
 const enabled=await api.cloudApi(req('PUT',{...prefs,notifications:{new_detection:true,reminder:false}}),env);assert.equal(enabled.status,eligible?200:403);assert.equal(reads,2);
 const before=reads;assert.equal((await api.cloudApi(req('PUT',prefs),env)).status,200);assert.equal(reads,before);assert.equal(writes,eligible?2:1);
});

for(const [label,options,sends] of [
 ['free confirmed',{removeRoleBeforeSend:true},1],['lookup401',{roleStatus:401},0],['lookup403',{roleStatus:403},0],
 ['lookup404',{roleStatus:404},0],['lookup429',{roleStatus:429},0],['lookup503',{roleStatus:503},0],
 ['network failure',{roleNetworkFailure:true},0],['OFF',{optIn:false},0],['wrong member',{wrongMember:true},0],
 ['missing device',{deviceMissing:true},0],['OFF immediately before transport',{optOutBeforeFinal:true},0],
])test('approved free generic notification audience: '+label,async()=>{
 const h=await dispatchHarness({deviceTest:true,audience:'authenticated',...options});
 const result=await h.call();assert.equal(h.delivered,sends);assert.equal(h.paymentReads,0);
 if(sends){assert.equal(result.status,'accepted');assert.equal(h.roleReads,1);assert.equal((await h.call()).status,'suppressed');assert.equal(h.delivered,1);}
 else assert.notEqual(result.status,'accepted');
});
for(const status of ['paid','free','unavailable','unverified'])test('free-audience config uses confirmed membership and retains fixed-person isolation: '+status,async()=>{
 const membership={status,reason:status==='free'?'managed_role_revoked':'fixture'};
 const env={...config,CLOUD_PUSH_AUDIENCE:'authenticated',CLOUD_DB:database(),ACCESS_PURCHASE_URL:'https://whop.com/existing/'};
 for(const memberId of ['mine','other']) {
  const value=await (await push.pushApi(request('/api/cloud/push-config'),env,{memberId,roleAuthorized:status==='paid',membership:async()=>membership})).json();
  assert.equal(value.registration_available,memberId==='mine'&&['paid','free'].includes(status));
  assert.equal(value.notification_eligible,['paid','free'].includes(status));
  assert.equal(value.purchase_url,undefined);assert.equal(value.personal_test_available,false);
 }
});

test('display-only save with existing notification ON does not invoke unavailable role lookup or change opt-in',async()=>{
 let writes=0;
 const prefs={max_price:1000,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,notifications:{new_detection:false,reminder:true}};
 const m=modules({fetchMock:async()=>assert.fail('display save must not look up Discord')});
 const env={CLOUD_PUSH_AUDIENCE:'authenticated',CLOUD_PUSH_MEMBERSHIP_POLICY:'whop_managed_discord_role',SESSION_SECRET:'fixture-only-secret-long-enough',CLOUD_DB:{prepare(sql){return {bind(...args){this.args=args;return this;},async first(){return {preferences_json:JSON.stringify(prefs)};},async run(){writes++;assert.equal(JSON.parse(this.args[1]).notifications.reminder,true);return {success:true};}};}}};
 const sec=Math.floor(Date.now()/1000), session=await m.load('./shared-report-gate').__test.createSession({sub:'member',accessToken:'fixture',exp:sec+86400,tokenExp:sec+3600,roleCheckedAt:sec,roles:[]},env.SESSION_SECRET);
 const req=new Request('https://cloud.example.invalid/api/cloud/preferences',{method:'PUT',headers:{cookie:'__Host-report_gate_session='+encodeURIComponent(session),origin:'https://cloud.example.invalid','content-type':'application/json'},body:JSON.stringify({...prefs,max_price:2000})});
 assert.equal((await m.load('./cloud-api').cloudApi(req,env)).status,200);assert.equal(writes,1);
});

test('Cloud Discord callback accepts a verified guild user with no paid role and no purchase redirect',async()=>{
 const m=modules({fetchMock:async input=>String(input).includes('/oauth2/token')?Response.json({access_token:'fixture-only-token',token_type:'Bearer',expires_in:3600,refresh_token:'fixture-only-refresh'}):Response.json({id:'fixture-discord-user',user:{id:'fixture-discord-user'},roles:[]})});
 const env={DISCORD_CLIENT_ID:'fixture-client',DISCORD_CLIENT_SECRET:'fixture-secret',SESSION_SECRET:'fixture-only-secret-long-enough',DISCORD_GUILD_ID:'fixture-guild',DISCORD_ALLOWED_ROLE_IDS:'paid-role',REPORT_ASSET_PATH:'/weak_early_beta_latest.html',ASSETS:{fetch:async()=>new Response('<html>FREE</html>')}};
 const gate=m.load('./shared-report-gate'),state=await gate.__test.createOAuthState('/weak_early_beta_latest.html',env.SESSION_SECRET);
 const response=await m.load('./index').default.fetch(new Request('https://cloud.example.invalid/auth/callback?code=fixture-code&state='+encodeURIComponent(state)),env);
 assert.equal(response.status,302);assert.equal(response.headers.get('location'),'/weak_early_beta_latest.html');assert.match(response.headers.get('set-cookie'),/__Host-report_gate_session=/);assert.doesNotMatch(response.headers.get('location'),/purchase|whop/);
});
