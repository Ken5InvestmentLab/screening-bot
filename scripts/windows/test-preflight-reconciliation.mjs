import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {createHash} from 'node:crypto';import{EventEmitter}from'node:events';
import{inspectApprovalTimeout,inspectPreflightFailure,issuePreflightReconciliation,verifyPreflightReconciliation,claimPreflightReconciliation,consumePreflightReconciliation}from'./preflight-reconciliation.mjs';
import{taskEntry}from'./weak-early-beta-task-entry.mjs';import{jstDay,recoveryPlan}from'./weak-early-beta-run-journal.mjs';import vm from'node:vm';import taskRoute from'./new-a-task-route.cjs';
const sha=v=>createHash('sha256').update(v).digest('hex');
const RealDate=Date;
class FrozenDate extends RealDate{constructor(...args){super(...(args.length?args:['2026-11-16T11:00:00Z']));}static now(){return RealDate.parse('2026-11-16T11:00:00Z');}}
globalThis.Date=FrozenDate;test.after(()=>{globalThis.Date=RealDate;});
function fixture(t){
 const repo=fs.mkdtempSync(path.join(os.tmpdir(),'cloud-preflight-proof-'));t.after(()=>fs.rmSync(repo,{recursive:true,force:true}));
 const runtime=path.join(repo,'runtime');fs.mkdirSync(runtime);const date=jstDay(),head='b'.repeat(40);
 const startedAt=new Date(Date.now()-60000).toISOString(),prior={identity:'WEAK_EARLY_CLOUD_DAILY_V1',date,startedAt,pid:123,ok:false,stage:'preflight',completedAt:new Date(Date.now()-30000).toISOString(),error:'local HEAD is not the latest origin/research/weak-early-beta',systemLogEvents:['error']};
 const folder=path.join(runtime,'daily-'+startedAt.replace(/[:.]/g,'-'));fs.mkdirSync(folder);const write=(name,v)=>fs.writeFileSync(path.join(folder,name),typeof v==='string'?v:JSON.stringify(v));
 write('invoked.json',{identity:'CLOUD_RUNNER_INVOKED_V1',startedAt,date,pid:123});write('result.json',prior);write('progress.jsonl',['branch','preflight','network-preflight','preflight'].map(stage=>JSON.stringify({stage})).join('\n'));
 for(const [stem,stdout]of Object.entries({'business-day':'{"business_day":true}','process-preflight':'','system-log-error':'{"posted":true,"duplicate":false,"message_id":"123456789012345678"}','git-1-branch':'research/weak-early-beta','git-2-status':'','git-3-remote':'https://github.com/Ken5InvestmentLab/screening-bot.git','git-4-rev-parse':'a'.repeat(40),'git-5-ls-remote':head+'\trefs/heads/research/weak-early-beta'})){
  write(stem+'.stdout',stdout);write(stem+'.stderr','');write(stem+'.process.json',{identity:'CLOUD_CHILD_PROCESS_V1',pid:22,status:'exited',code:0,completedAt:prior.completedAt});
 }
 const latest=path.join(runtime,'daily-latest.json');fs.writeFileSync(latest,JSON.stringify(prior,null,2)+'\n');const original=fs.readFileSync(latest);
 const text='Synthetic explicit owner recovery approval',binding={message_id:'synthetic-approval',room_id:'synthetic-room',author_id:'synthetic-owner',text_sha256:sha(JSON.stringify(text))};
 const receipt={partial:false,room_id:binding.room_id,message:{message_id:binding.message_id,author:'user',author_id:binding.author_id,channel:'chatgpt',content:{text},sent_at:startedAt}};
 const args={repo,runtime,date,head,prior,binding,authority:{author_id:binding.author_id,room_id:binding.room_id},reader:async()=>receipt,expiresAt:new Date(Date.now()+3600000).toISOString()};
 const inspect=()=>inspectPreflightFailure(repo,runtime,prior,date),issue=()=>issuePreflightReconciliation(args),verify=file=>verifyPreflightReconciliation({...args,file});
 return {...args,folder,latest,original,write,inspect,issue,verify,receipt};
}
test('full preflight proof, immutable original and typed operator evidence',async t=>{const f=fixture(t),r=await f.issue(),v=f.verify(r.file);assert.equal(v.record.platform_signature_claimed,false);assert.deepEqual(fs.readFileSync(f.latest),f.original);assert.deepEqual(fs.readFileSync(path.join(path.dirname(r.file),'original.json')),f.original);assert.equal(v.record.head,f.head);});
test('downstream evidence always refuses a fresh replay',t=>{const f=fixture(t);for(const k of ['new_a','deployment','notifications','notificationPreview','latestSession','selectorRows','acquisitionEvidence','generatedCommit','fundamentals']){f.prior[k]={};assert.throws(f.inspect,/downstream/);delete f.prior[k];}});
test('unknown artifacts and missing subprocess receipt are rejected',t=>{const f=fixture(t);f.write('unknown.stdout','');assert.throws(f.inspect,/unexpected/);fs.unlinkSync(path.join(f.folder,'unknown.stdout'));fs.unlinkSync(path.join(f.folder,'git-5-ls-remote.process.json'));assert.throws(f.inspect,/required child/);});
test('nonzero, pending and unconfirmed child processes refuse recovery',t=>{const f=fixture(t);for(const delta of [{code:1},{status:'running'},{identity:'unknown'},{completedAt:null}]){f.write('git-1-branch.process.json',{identity:'CLOUD_CHILD_PROCESS_V1',status:'exited',code:0,completedAt:f.prior.completedAt,...delta});assert.throws(f.inspect,/child outcome/);}});
test('stage entry or ambiguous error send rejects reconciliation',t=>{const f=fixture(t);f.write('progress.jsonl','{"stage":"detection"}');assert.throws(f.inspect,/pipeline/);f.write('progress.jsonl','{"stage":"preflight"}');f.write('system-log-error.stdout','{"posted":false}');assert.throws(f.inspect,/notification receipt/);});
test('same-day original bytes and identity must still agree',t=>{const f=fixture(t);fs.writeFileSync(f.latest,'{}');assert.throws(f.inspect,/identity/);});
test('original Git mismatch must be corroborated',t=>{const f=fixture(t);f.write('git-4-rev-parse.stdout',f.head);assert.throws(f.inspect,/corroborated/);});
test('live state forces separate reconciliation',t=>{const f=fixture(t),p=path.join(f.repo,'.cache/weak_early_beta/new-a-private');fs.mkdirSync(p,{recursive:true});fs.writeFileSync(path.join(p,'daily-live.sqlite'),'synthetic');assert.throws(f.inspect,/live store/);});
test('independent primary owner message required',async t=>{const f=fixture(t);for(const [obj,k,v]of [[f.receipt,'partial',true],[f.receipt,'room_id','other'],[f.receipt.message,'author','aeon'],[f.receipt.message,'author_id','other'],[f.receipt.message,'deleted_at','now'],[f.receipt.message.content,'text','changed']]){const old=obj[k];obj[k]=v;await assert.rejects(f.issue,/approval mismatch/);if(old===undefined)delete obj[k];else obj[k]=old;}await assert.rejects(()=>issuePreflightReconciliation({...f,reader:null}),/reader required/);});
test('reconciliation cannot use an arbitrary author instead of host-verified owner',async t=>{const f=fixture(t);await assert.rejects(()=>issuePreflightReconciliation({...f,authority:null}),/owner authority/);await assert.rejects(()=>issuePreflightReconciliation({...f,authority:{author_id:'ANOTHER_OWNER',room_id:f.binding.room_id}}),/owner authority/);});
test('expiry, head and tamper bindings are checked',async t=>{const f=fixture(t),r=await f.issue();assert.throws(()=>verifyPreflightReconciliation({...f,head:'c'.repeat(40),file:r.file}),/binding/);f.write('business-day.stdout','{"business_day":false}');assert.throws(()=>f.verify(r.file),/business day/);await assert.rejects(()=>issuePreflightReconciliation({...f,expiresAt:'2000-01-01Z'}),/validity/);});
test('approval expiry cannot extend into Nov17 or target another date',async t=>{const f=fixture(t);await assert.rejects(()=>issuePreflightReconciliation({...f,expiresAt:'2026-11-17T00:00:01+09:00'}),/validity/);await assert.rejects(()=>issuePreflightReconciliation({...f,date:'2026-11-17'}),/validity/);});
test('a valid unconsumed record expires at the next JST day',async t=>{const f=fixture(t),r=await f.issue();class NextDayDate extends RealDate{static now(){return RealDate.parse('2026-11-17T00:00:00+09:00');}}globalThis.Date=NextDayDate;try{assert.throws(()=>f.verify(r.file),/binding/);}finally{globalThis.Date=FrozenDate;}});
test('one claim, one consumption; uncertain outcomes never auto-retry',async t=>{const f=fixture(t),r=await f.issue(),v=f.verify(r.file);claimPreflightReconciliation(f.runtime,v,'invocation-one');assert.throws(()=>claimPreflightReconciliation(f.runtime,v,'invocation-two'),/EEXIST/);assert.throws(()=>consumePreflightReconciliation(f.runtime,v,'wrong','run'),/claim required/);consumePreflightReconciliation(f.runtime,v,'invocation-one','new-run');assert.throws(()=>consumePreflightReconciliation(f.runtime,v,'invocation-one','other-run'),/EEXIST/);assert.deepEqual(fs.readFileSync(f.latest),f.original);});
test('task-entry inspect cannot claim or launch; one start passes existing preflight',async t=>{const f=fixture(t),r=await f.issue();let launched=0,argsSeen,checks=0;
 const options={task:'cloud-3',reconciliationFile:r.file,auditDirectory:path.join(f.repo,'audit'),load:()=>({repoPath:f.repo,runtimeDir:f.runtime,nodePath:process.execPath}),check:async()=>{checks++;return{ok:true,head:f.head};},launch:(_exe,args)=>{launched++;argsSeen=args;const c=new EventEmitter();c.pid=222;c.unref=()=>{};queueMicrotask(()=>c.emit('spawn'));return c;}};
 assert.equal((await taskEntry('synthetic-config',options)).status,'ready');assert.equal(launched,0);assert.equal(fs.readdirSync(f.runtime).filter(n=>n.startsWith('preflight-claim-')).length,0);
 assert.equal((await taskEntry('synthetic-config',{...options,start:true})).status,'launched');assert.ok(argsSeen.includes('--reconcile-preflight'));assert.ok(argsSeen.includes('--reconcile-invocation'));assert.equal((await taskEntry('synthetic-config',{...options,start:true})).status,'recovery-required');assert.equal(launched,1);assert.equal(checks,3);assert.deepEqual(fs.readFileSync(f.latest),f.original);
});
test('normal preflight rejection cannot be overridden by recovery record',async t=>{const f=fixture(t),r=await f.issue();const x=await taskEntry('synthetic',{start:true,reconciliationFile:r.file,auditDirectory:path.join(f.repo,'audit'),load:()=>({repoPath:f.repo,runtimeDir:f.runtime}),check:async()=>{throw Error('Daily checkout is not clean');},launch:()=>{throw Error('MUST NOT LAUNCH');}});assert.equal(x.status,'recovery-required');assert.equal(fs.readdirSync(f.runtime).filter(n=>n.startsWith('preflight-claim-')).length,0);});
function rootHarness(f){
 const source=fs.readFileSync(new URL('./weak-early-beta-daily-runner.mjs',import.meta.url),'utf8'),writes=(p,v)=>fs.writeFileSync(p,JSON.stringify(v));let notifications=0;
 const context={fs,path,Date,JSON,console:{log(){},error(){}},process:{pid:444,env:{},platform:'linux',exitCode:0},loadDailyConfig:()=>({repoPath:f.repo,runtimeDir:f.runtime,date:f.date}),loadDotEnv(){},jstDate:()=>f.date,readJson:p=>JSON.parse(fs.readFileSync(p,'utf8')),writeJson:writes,atomicJson:writes,appendEvent:(p,v)=>fs.appendFileSync(p,JSON.stringify(v)+'\n'),newATaskPlan:taskRoute.newATaskPlan,recoveryPlan,verifyPreflightReconciliation,consumePreflightReconciliation,RESEARCH_BRANCH:'research/weak-early-beta',requireOk:async(exe,args)=>{assert.equal(exe,'git');return{stdout:args[0]==='rev-parse'?f.head:'wrong-branch'};},run:async()=>{notifications++;return{code:0};}};
 vm.createContext(context);vm.runInContext(source.slice(source.indexOf('async function main('),source.indexOf('if (process.argv[1]',source.indexOf('async function main(')))+'\nglobalThis.testMain=main;',context);
 return{context,notifications:()=>notifications,run:options=>context.testMain('synthetic',options)};
}
test('exact runner rejects unclaimed replay, preserves original, emits no error resend',async t=>{const f=fixture(t),r=await f.issue(),h=rootHarness(f);await h.run({reconciliationFile:r.file,reconciliationInvocation:'missing-claim'});assert.deepEqual(fs.readFileSync(f.latest),f.original);assert.equal(h.notifications(),0);assert.equal(fs.existsSync(path.join(f.runtime,'daily.lock')),false);});
test('exact runner consumes entry claim then still enforces ordinary branch check',async t=>{const f=fixture(t),r=await f.issue(),v=f.verify(r.file),h=rootHarness(f);claimPreflightReconciliation(f.runtime,v,'entry-one');await h.run({reconciliationFile:r.file,reconciliationInvocation:'entry-one'});const result=JSON.parse(fs.readFileSync(f.latest,'utf8'));assert.match(result.error,/refusing to run outside/);assert.equal(result.originalRunId,f.prior.startedAt);assert.equal(result.preflightReconciliation.reconciliation_sha256,v.digest);assert.equal(result.new_a,undefined);assert.equal(h.notifications(),1);assert.deepEqual(fs.readFileSync(path.join(path.dirname(r.file),'original.json')),f.original);assert.equal(fs.existsSync(path.join(f.runtime,'daily.lock')),false);});
test('entry arbitration observes another in-flight check rather than launching twice',async t=>{const f=fixture(t),r=await f.issue();let release,entered;const seen=new Promise(resolve=>{entered=resolve;}),barrier=new Promise(resolve=>{release=resolve;});const options={reconciliationFile:r.file,auditDirectory:path.join(f.repo,'audit'),load:()=>({repoPath:f.repo,runtimeDir:f.runtime}),check:async()=>{entered();await barrier;return{ok:true,head:f.head};},launch:()=>{throw Error('MUST NOT LAUNCH');}};const first=taskEntry('synthetic',options);await seen;assert.equal((await taskEntry('synthetic',options)).status,'observe');release();assert.equal((await first).status,'ready');});
test('Nov17 is a fresh normal day and never consumes the old Nov16 reconciliation',async t=>{
 const f=fixture(t);class Nov17Date extends RealDate{constructor(...args){super(...(args.length?args:['2026-11-17T08:00:00Z']));}static now(){return RealDate.parse('2026-11-17T08:00:00Z');}}
 globalThis.Date=Nov17Date;try{
  const r=await taskEntry('synthetic',{auditDirectory:path.join(f.repo,'audit'),load:()=>({repoPath:f.repo,runtimeDir:f.runtime}),check:async()=>({ok:true,head:f.head}),launch:()=>{throw Error('INSPECT MUST NOT LAUNCH');}});
  assert.equal(r.date,'2026-11-17');assert.equal(r.status,'ready');assert.equal(r.plan.action,'none');assert.deepEqual(fs.readFileSync(f.latest),f.original);assert.equal(fs.readdirSync(f.runtime).some(n=>n.startsWith('preflight-claim-')),false);
 }finally{globalThis.Date=FrozenDate;}
});
test('ordinary same-day completion stays complete while the next day starts normally',()=>{
 const receipt={identity:'WEAK_EARLY_CLOUD_DAILY_V1',date:'2026-11-16',ok:true,completedAt:'2026-11-16T13:00:00Z',new_a:{entry:'new-a-verified-daily-v1',strategy:'A_BASE',snapshot_sha256:'a'.repeat(64),owner_publication_verified:true}};
 assert.equal(taskRoute.newATaskPlan('cloud-3','2026-11-16',receipt,recoveryPlan).action,'complete');assert.equal(taskRoute.newATaskPlan('cloud-3','2026-11-17',receipt,recoveryPlan).action,'none');
});

function timeoutFixture(t) {
  class TimeoutDate extends RealDate {
    constructor(...args) { super(...(args.length ? args : ['2026-11-24T10:00:00Z'])); }
    static now() { return RealDate.parse('2026-11-24T10:00:00Z'); }
  }
  globalThis.Date = TimeoutDate;
  t.after(() => { globalThis.Date = RealDate; });
  const repo = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-approval-timeout-')));
  t.after(() => fs.rmSync(repo, {recursive:true, force:true}));
  const date = '2026-11-24', head = 'b'.repeat(40), originalHead = 'a'.repeat(40);
  const runtime = path.join(repo, '.cache/weak_early_beta/daily_runtime');
  const startedAt = '2026-11-24T07:46:43.195Z', completedAt = '2026-11-24T07:47:58.714Z';
  const folder = path.join(runtime, 'daily-' + startedAt.replace(/[:.]/g, '-'));
  fs.mkdirSync(folder, {recursive:true});
  const write = (name, bytes) => fs.writeFileSync(path.join(folder, name), bytes);
  const previous = {headSha:originalHead, status:'completed', conclusion:'success', databaseId:10};
  const prior = {identity:'WEAK_EARLY_CLOUD_DAILY_V1', startedAt, completedAt, date, pid:76792, stage:'preflight', ok:false,
    error:'timeout: approved-release-before-detection', businessDay:true, startCommit:originalHead,
    progressAt:'2026-11-24T07:46:54.459Z', networkPreflight:{blocked:false,groups:[],waitedMs:855}, previousSuccessfulDeployment:previous,
    fundamentals:[], fundamental:{ok:true,status:'NOT_REQUESTED',imported:0,posted:0}};
  const latest = path.join(runtime, 'daily-latest.json'), original = JSON.stringify(prior) + '\n';
  fs.writeFileSync(latest, original);
  write('result.json', original);
  write('invoked.json', JSON.stringify({identity:'CLOUD_RUNNER_INVOKED_V1',startedAt,pid:prior.pid,ok:false,date}));
  write('progress.jsonl', JSON.stringify({stage:'branch', at:startedAt}) + '\n'
    + JSON.stringify({stage:'network-preflight',at:'2026-11-24T07:46:54.448Z',
      networkPreflight:{blocked:false,groups:[],elapsedMs:855,status:'ready'}}) + '\n'
    + JSON.stringify({stage:'preflight',at:prior.progressAt}) + '\n');
  const children = {'business-day':'{"business_day":true}', 'process-preflight':'', 'gh-preflight':'synthetic valid auth',
    'previous-release':JSON.stringify([previous]), 'git-1-branch':'research/weak-early-beta', 'git-2-status':'',
    'git-3-remote':'https://github.com/Ken5InvestmentLab/screening-bot', 'git-4-rev-parse':originalHead,
    'git-5-ls-remote':originalHead+'\trefs/heads/research/weak-early-beta', 'approved-release-before-detection':''};
  for (const [index, [name, stdout]] of Object.entries(children).entries()) {
    const timeout = name === 'approved-release-before-detection';
    write(name+'.stdout', stdout);
    write(name+'.stderr', '');
    write(name+'.process.json', JSON.stringify({identity:'CLOUD_CHILD_PROCESS_V1',pid:200+index,status:'exited',code:timeout?1:0,
      completedAt:timeout?'2026-11-24T07:47:58.710Z':'2026-11-24T07:46:58.148Z'}));
  }

  const root = path.join(repo, '.cache/weak_early_beta/new-a-private'), application = 'c'.repeat(64);
  const archive = path.join(root, 'continuing-acceptance', 'applications', application);
  fs.mkdirSync(archive, {recursive:true});
  const activation = path.join(root, 'activation.json');
  fs.writeFileSync(activation, JSON.stringify({schema:'NEW_A_OWNER_ACTIVATION_V1',strategy:'A_BASE',active:true,
    external_actions_approved:true, owner_acceptance:{application_id:application}}));
  const approved = {schema:'NEW_A_ORDINARY_RUNTIME_RELEASE_V1',source_commit:head,worker:'tentei-kyokuchi-cloud',
    database:'tentei-cloud-settings',version_id:'00000000-0000-4000-8000-000000000002',activation_sha256:sha(fs.readFileSync(activation)),
    build_input_sha256:'d'.repeat(64),policy_sha256:'e'.repeat(64),ci_run_id:11,tag:'cloud-deploy-approval-timeout-fixture'};
  const audited = JSON.stringify({deployment:approved,predecessor:{source_commit:originalHead,version_id:'00000000-0000-4000-8000-000000000001'}});
  fs.writeFileSync(path.join(archive, 'member-ordinary.json'), audited);
  fs.writeFileSync(path.join(archive, 'completed.json'), JSON.stringify({schema:'NEW_A_MEMBER_ORDINARY_APPLICATION_V1',
    source_commit:head,after_sha256:approved.activation_sha256,member_ordinary_sha256:sha(audited)}));
  const effects = {schema:'CLOUD_APPROVAL_TIMEOUT_NO_EFFECTS_V1',date,original_started_at:startedAt,source_commit:head,
    worker_version_id:approved.version_id,observed_at:'2026-11-24T09:59:00Z',read_only:true,receipt_sha256:'f'.repeat(64),
    target_owner_datasets:0,target_member_datasets:0,target_outbox_entries:0,target_discord_results:0};
  const text = 'Synthetic same-day approval after failure', binding = {message_id:'synthetic-timeout', room_id:'synthetic-room',
    author_id:'synthetic-owner',text_sha256:sha(JSON.stringify(text))};
  const receipt = {partial:false,room_id:binding.room_id,message:{message_id:binding.message_id,author:'user',channel:'chatgpt',
    author_id:binding.author_id,content:{text},sent_at:'2026-11-24T09:57:00Z'}};
  const args = {repo,runtime,date,head,prior,binding,authority:binding,reader:async()=>receipt,expiresAt:'2026-11-24T10:30:00Z',
    approvedReleaseReader:async scope=>{assert.equal(scope.original_sha256,sha(original));return approved;},
    sideEffectReader:async scope=>{assert.equal(scope.worker_version_id,approved.version_id);return effects;}};
  return {repo,runtime,folder,write,date,head,prior,latest,original,activation,approved,effects,args,
    inspect:()=>inspectApprovalTimeout(runtime,prior,date), issue:overrides=>issuePreflightReconciliation({...args,...overrides}),
    verify:file=>verifyPreflightReconciliation({...args,file})};
}

test('approval timeout resumes exactly once through task-entry with immutable original and approved successor', async t => {
  const f = timeoutFixture(t), issued = await f.issue(), verified = f.verify(issued.file);
  assert.equal(verified.record.schema, 'CLOUD_APPROVAL_TIMEOUT_RECONCILIATION_V1');
  assert.equal(verified.record.original_source_commit, f.prior.startCommit);
  assert.equal(verified.record.original_started_at, f.prior.startedAt);
  assert.equal(fs.readFileSync(path.join(path.dirname(issued.file), 'original.json'), 'utf8'), f.original);
  let launches = 0, args;
  const options = {task:'cloud-3', reconciliationFile:issued.file, auditDirectory:path.join(f.repo,'audit'),
    load:()=>({repoPath:f.repo,runtimeDir:f.runtime,nodePath:process.execPath}), check:async()=>({ok:true,head:f.head}),
    launch:(_exe,argv)=>{launches++;args=argv;const child=new EventEmitter();child.pid=10;child.unref=()=>{};
      queueMicrotask(()=>child.emit('spawn'));return child;}};
  assert.equal((await taskEntry('synthetic',options)).status,'ready');
  assert.equal(launches,0);
  const result = await taskEntry('synthetic',{...options,start:true});
  assert.equal(result.status,'launched');
  assert.equal((await taskEntry('synthetic',{...options,start:true})).status,'recovery-required');
  assert.equal(launches,1);
  assert.equal(args[args.indexOf('--reconcile-preflight')+1], issued.file);
  const consumed = consumePreflightReconciliation(f.runtime,verified,result.id,'synthetic-run');
  assert.equal(consumed.originalRunId,f.prior.startedAt);
  assert.throws(()=>consumePreflightReconciliation(f.runtime,verified,result.id,'another'),/EEXIST/);
  assert.equal(fs.readFileSync(f.latest,'utf8'), f.original);
});

test('approval timeout refuses downstream, missing, or ambiguous original artifacts', async t => {
  const f = timeoutFixture(t), issued = await f.issue();
  const stdout = 'approved-release-before-detection.stdout';
  f.write(stdout, '{}');
  assert.throws(()=>f.verify(issued.file),/child output/);
  f.write(stdout, '');
  const detected = 'detect-1.stdout';
  f.write(detected, 'started');
  assert.throws(f.inspect,/artifact inventory/);
  fs.unlinkSync(path.join(f.folder,detected));
  fs.unlinkSync(path.join(f.folder,'approved-release-before-detection.process.json'));
  assert.throws(f.inspect,/artifact inventory/);
  f.prior.deployment = {};
  assert.throws(f.inspect,/only original approval preflight timeout/);
});

test('approval timeout binds host evidence, owner day, and immutable successor approval', async t => {
  const f = timeoutFixture(t);
  await assert.rejects(()=>f.issue({sideEffectReader:null}),/independent timeout evidence readers/);
  await assert.rejects(()=>f.issue({approvedReleaseReader:async()=>({...f.approved,source_commit:f.prior.startCommit})}),/approved successor release/);
  for (const field of ['target_owner_datasets','target_member_datasets','target_outbox_entries','target_discord_results']) {
    await assert.rejects(()=>f.issue({sideEffectReader:async()=>({...f.effects,[field]:1})}),/no-effect evidence/);
  }
  await assert.rejects(()=>f.issue({sideEffectReader:async()=>({...f.effects,observed_at:'2026-11-24T09:54:00Z'})}),/no-effect evidence/);
  await assert.rejects(()=>f.issue({expiresAt:'2026-11-25T00:00:01+09:00'}),/same JST day/);
  const issued=await f.issue();
  fs.appendFileSync(f.activation,'\n');
  assert.throws(()=>f.verify(issued.file),/successor activation changed/);
});
