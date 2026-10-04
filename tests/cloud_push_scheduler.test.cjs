const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {DatabaseSync}=require('node:sqlite');
const {webcrypto}=require('node:crypto');
const {modules}=require('./helpers/cloud-worker-modules.cjs');
const root=path.resolve(__dirname,'..'),m=modules(),feed=m.load('./cloud-canonical-feed'),scheduler=m.load('./cloud-push-scheduler');
function event(kind='new_detection') { return {adapter_version:'cloud-ledger-v1',source_ledger_revision:'a'.repeat(64),
  signal_id:'2026-10-02|9999',detection_date:'2026-10-02',kind,signal_actual_close:900,signal_price_status:'verified',
  endpoints:{d5_close:{date:'2026-10-09',actual_price:null,status:'missing',fetched_at:null,source:null},
    d6_open:{date:'2026-10-13',actual_price:null,status:'missing',fetched_at:null,source:null}}}; }
function input(events=[event()]) { return {schema_version:1,adapter_version:'cloud-ledger-v1',source_ledger_revision:'a'.repeat(64),observed_at:'2026-10-02T08:00:00.000Z',events}; }
function database(){
 const sqlite=new DatabaseSync(':memory:');
 for(const name of fs.readdirSync(path.join(root,'weak-early-beta-gate/migrations')).filter(name=>name.endsWith('.sql')).sort())sqlite.exec(fs.readFileSync(path.join(root,'weak-early-beta-gate/migrations',name),'utf8'));
 const db={prepare(sql){const statement=sqlite.prepare(sql);return{values:[],bind(...values){this.values=values;return this;},async run(){const result=statement.run(...this.values);return{success:true,meta:{changes:Number(result.changes)}};},async first(){return statement.get(...this.values)??null;},async all(){return{success:true,results:statement.all(...this.values)};}};},async batch(rows){return Promise.all(rows.map(row=>row.run()));}};
 return {db,sqlite};
}
test('private manifest imports into actual SQLite exactly once and preserves availability/preferences/unknown receipts',async()=>{
 const {db,sqlite}=database(),now=Date.parse('2026-10-03T00:00:00Z');
 sqlite.exec("INSERT INTO cloud_member_preferences VALUES ('member','{}','unchanged'); INSERT INTO cloud_push_dispatch_receipts VALUES ('member','device','private-event','unknown','no_auto_retry','unchanged');");
 assert.equal((await feed.importCanonicalInput(db,input(),now)).imported,1);
 assert.equal((await feed.importCanonicalInput(db,input(),now)).imported,0);
 const revised=input();revised.source_ledger_revision='b'.repeat(64);revised.observed_at='2026-10-02T09:00:00.000Z';revised.events[0].source_ledger_revision=revised.source_ledger_revision;
 assert.equal((await feed.importCanonicalInput(db,revised,now)).imported,1);
 const row=sqlite.prepare('SELECT * FROM cloud_notification_events').get();assert.equal(row.available_at,'2026-10-02T08:00:00.000Z');assert.equal(row.source_ledger_revision,'b'.repeat(64));assert.equal(JSON.parse(row.event_json).signal_id,'2026-10-02|9999');
 assert.equal(sqlite.prepare('SELECT count(*) AS n FROM cloud_notification_events').get().n,1);
 assert.equal(sqlite.prepare('SELECT updated_at FROM cloud_member_preferences').get().updated_at,'unchanged');
 assert.equal(sqlite.prepare('SELECT status FROM cloud_push_dispatch_receipts').get().status,'unknown');sqlite.close();
});
for(const [label,change] of [['future cutoff',value=>value.observed_at='2099-01-01T00:00:00.000Z'],['result kind',value=>value.events[0].kind='result'],['missing revision',value=>value.source_ledger_revision=''],['mismatched revision',value=>value.events[0].source_ledger_revision='b'.repeat(64)],['duplicate event',value=>value.events.push(value.events[0])],['nonbusiness detection',value=>{value.events[0].detection_date='2026-10-03';value.events[0].signal_id='2026-10-03|9999';}],['wrong endpoint date',value=>value.events[0].endpoints.d6_open.date='2026-10-12'],['future price evidence',value=>Object.assign(value.events[0].endpoints.d5_close,{actual_price:901,status:'verified',fetched_at:'2026-10-09T07:00:00Z',source:'c'.repeat(64)})],['invalid price',value=>value.events[0].signal_actual_close=-1],['partial manifest',value=>value.events.push({kind:'new_detection'})]])test('manifest '+label+' is rejected before any writes',async()=>{
 const {db,sqlite}=database(),value=input();change(value);await assert.rejects(feed.importCanonicalInput(db,value,Date.parse('2026-10-03T00:00:00Z')));
 assert.equal(sqlite.prepare('SELECT count(*) AS n FROM cloud_notification_events').get().n,0);sqlite.close();
});
for(const [day,expected] of [['2026-10-09',true],['2026-10-10',false],['2026-10-12',false],['2026-12-31',false],['2027-01-01',false],['2027-01-04',true],['2027-09-20',false],['2031-01-06',undefined],['2026-02-30',undefined]])test('bank calendar '+day+' = '+expected,()=>assert.equal(feed.bankBusinessDate(day),expected));
const config={CLOUD_PUSH_SCHEDULER_ENABLED:'true',CLOUD_PUSH_MODE:'personal_test',CLOUD_PUSH_MEMBERSHIP_POLICY:'whop_managed_discord_role',CLOUD_DB:{},CLOUD_DISCORD_BOT_TOKEN:'fixture-only-bot',CLOUD_PUSH_TEST_DISCORD_USER_ID:'123456789012345678',CLOUD_PUSH_TEST_MEMBER_ID:'fixture-member',CLOUD_PUSH_TEST_SUBSCRIPTION_ID:'fixture-device'};
function schedule(day,scheduled='08:00',actual=scheduled,cron=scheduler.MORNING_CRON){return{controller:{cron,scheduledTime:Date.parse(`${day}T${scheduled}:00+09:00`)},now:Date.parse(`${day}T${actual}:00+09:00`)};}
function dependencies(){const calls=[];return{calls,importInput:async()=>{calls.push('import');return{imported:1};},runBatch:async(env,transport,fixture,kind)=>{calls.push(kind);return{processed:1,accepted:1,held:0,suppressed:0,failed:0,more:false};}};}
test('08JST handler imports canonical input then calls only reminder batch, aggregate output only',async()=>{
 const d=dependencies(),s=schedule('2026-10-09');const result=await scheduler.runScheduledPersonalNotifications(s.controller,config,s.now,d);
 assert.deepEqual(d.calls,['import','reminder']);assert.equal(result.status,'processed');assert.equal(result.accepted,1);assert.equal(result.arrival_confirmed,false);assert.doesNotMatch(JSON.stringify(result),/fixture-member|fixture-device|token|signal|endpoint/);
});
for(const [label,s,env] of [['disabled',schedule('2026-10-09'),{...config,CLOUD_PUSH_SCHEDULER_ENABLED:'false'}],['no Bot',schedule('2026-10-09'),{...config,CLOUD_DISCORD_BOT_TOKEN:undefined}],['weekend',schedule('2026-10-10'),config],['holiday',schedule('2026-10-12'),config],['year end',schedule('2026-12-31'),config],['out of range',schedule('2031-01-06'),config],['09JST late',schedule('2026-10-09','08:00','09:00'),config],['wrong nominal time',schedule('2026-10-09','08:10'),config],['unapproved new detection time',schedule('2026-10-09','17:00','17:00','0 8 * * *'),config]])test('scheduler '+label+' does not import or dispatch',async()=>{
 const d=dependencies();assert.notEqual((await scheduler.runScheduledPersonalNotifications(s.controller,env,s.now,d)).status,'processed');assert.deepEqual(d.calls,[]);
});
test('late previous-day invocation does not send',async()=>{const s=schedule('2026-10-09'),d=dependencies();const result=await scheduler.runScheduledPersonalNotifications(s.controller,config,s.now+86400000,d);assert.equal(result.reason,'late_previous_day_schedule');assert.deepEqual(d.calls,[]);});
test('new detection cron is used only when explicitly supplied, distinct from morning',async()=>{const s=schedule('2026-10-09','17:00','17:00','operator-selected'),d=dependencies();const result=await scheduler.runScheduledPersonalNotifications(s.controller,{...config,CLOUD_PUSH_NEW_DETECTION_CRON:'operator-selected'},s.now,d);assert.equal(result.kind,'new_detection');assert.deepEqual(d.calls,['import','new_detection']);});
test('bounded scheduler continues all pages and holds importer failure without scanning',async()=>{
 const s=schedule('2026-10-09'),d=dependencies();let calls=0;d.runBatch=async()=>({processed:20,accepted:0,held:20,suppressed:0,failed:0,more:++calls<3});
 const result=await scheduler.runScheduledPersonalNotifications(s.controller,config,s.now,d);assert.equal(result.pages,3);assert.equal(result.processed,60);
 calls=0;d.importInput=async()=>{throw Error('private-input-must-not-leak');};assert.equal((await scheduler.runScheduledPersonalNotifications(s.controller,config,s.now,d)).reason,'canonical_import_or_scan_failed');assert.equal(calls,0);
});
test('private compiler input is excluded from the public asset sync allowlist',()=>{
 const source=fs.readFileSync(path.join(root,'weak-early-beta-gate/scripts/sync-report.mjs'),'utf8');assert.doesNotMatch(source,/cloud-canonical-input|build-canonical-input/);
});
test('unavailable storage holds an enabled schedule without dispatch',async()=>{
 let dispatched=false; const s=schedule('2026-10-09');const result=await scheduler.runScheduledPersonalNotifications(s.controller,config,s.now,{importInput:feed.importCanonicalInput,runBatch:async()=>{dispatched=true;throw Error('must not dispatch');}});
 assert.equal(result.status,'held');assert.equal(result.reason,'canonical_import_or_scan_failed');
 assert.equal(dispatched,false);
});
test('approved generated manifest imports into isolated SQLite without any provider access',async()=>{
 const {CANONICAL_MANIFEST}=m.load('./cloud-canonical-input.generated');
 const {db,sqlite}=database();
 try {
  const result=await feed.importCanonicalInput(db,CANONICAL_MANIFEST,Date.now());
  assert.equal(result.imported,CANONICAL_MANIFEST.events.length);
  assert.equal(sqlite.prepare('SELECT count(*) AS n FROM cloud_notification_events').get().n,result.imported);
  assert.equal(sqlite.prepare('SELECT count(*) AS n FROM cloud_push_dispatch_receipts').get().n,0);
 } finally {sqlite.close();}
});
test('actual SQLite canonical import -> 08JST runner -> fresh-role -> encrypted fixture push is once-only',async()=>{
 // Published RFC8291 keys, synthetic identity/subscription, no real provider.
 const AS='BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8',D='yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw';
 const UA='BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4',AUTH='BTBZMqHH6r4Tts7J_aSIgg';
 const clock={now:Date.parse('2026-10-13T08:00:00+09:00')},subject='123456789012345678';let roles=0,sends=0;
 const local=modules({clock,fetchMock:async url=>{assert.equal(String(url),`https://discord.com/api/v10/guilds/345678901234567890/members/${subject}`);roles++;return Response.json({user:{id:subject},roles:['234567890123456789']});}});
 const {db,sqlite}=database(),api=local.load('./cloud-api'),member=await api.cloudMemberId(subject),sender=local.load('./cloud-web-push');
 const endpoint='https://push.example.invalid/device',device='11111111-1111-4111-8111-111111111111';
 sqlite.prepare('INSERT INTO cloud_member_preferences VALUES (?, ?, ?)').run(member,JSON.stringify({max_price:1000,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,notifications:{new_detection:false,reminder:true}}),'fixture');
 sqlite.prepare('INSERT INTO cloud_push_subscriptions VALUES (?, ?, ?, ?, ?, ?, NULL)').run(device,member,endpoint,UA,AUTH,'fixture');
 sqlite.prepare('INSERT INTO cloud_push_subscription_metadata VALUES (?, ?, ?, NULL, ?)').run(device,'fixture-hash',AS,'fixture');
 const point=sender.decode(AS,65),privateKey=await webcrypto.subtle.importKey('jwk',{kty:'EC',crv:'P-256',x:sender.encode(point.slice(1,33)),y:sender.encode(point.slice(33)),d:D},{name:'ECDH',namedCurve:'P-256'},false,['deriveBits']);
 const fixture={privateKey,publicKey:point,salt:sender.decode('DGv6ra1nlYgDCS1FRnbzlw',16)};
 const env={...config,CLOUD_DB:db,CLOUD_PUSH_TEST_MEMBER_ID:member,CLOUD_PUSH_TEST_SUBSCRIPTION_ID:device,CLOUD_PUSH_TEST_DISCORD_USER_ID:subject,DISCORD_GUILD_ID:'345678901234567890',DISCORD_ALLOWED_ROLE_IDS:'234567890123456789',CLOUD_VAPID_PUBLIC_KEY:AS,CLOUD_VAPID_PRIVATE_KEY:D,CLOUD_VAPID_SUBJECT:'https://cloud.example.invalid/',CLOUD_PUSH_ALLOWED_ORIGINS:'https://push.example.invalid'};
 const transport=async(url,init)=>{assert.equal(url,endpoint);assert.equal(init.headers['Content-Encoding'],'aes128gcm');assert.ok(init.body.length>86);sends++;return new Response('',{status:201});};
 const deps={importInput:(_db,_input,now)=>local.load('./cloud-canonical-feed').importCanonicalInput(_db,input([event('reminder')]),now),runBatch:(_env,_transport,_fixture,kind)=>local.load('./cloud-push-runner').runPersonalNotificationBatch(_env,transport,fixture,kind)};
 const controller={cron:scheduler.MORNING_CRON,scheduledTime:clock.now},scheduleModule=local.load('./cloud-push-scheduler');
 const first=await scheduleModule.runScheduledPersonalNotifications(controller,env,clock.now,deps);assert.equal(first.accepted,1);assert.equal(first.processed,1);assert.equal(first.arrival_confirmed,false);assert.equal(roles,2);assert.equal(sends,1);
 clock.now+=10*60000;const second=await scheduleModule.runScheduledPersonalNotifications(controller,env,clock.now,deps);assert.equal(second.accepted,0);assert.equal(sends,1);assert.equal(sqlite.prepare('SELECT status FROM cloud_push_dispatch_receipts').get().status,'accepted');sqlite.close();
});
