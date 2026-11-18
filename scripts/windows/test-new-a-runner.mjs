// Exact staged function bodies, local filesystem, injected subprocess/network boundaries only.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { isDeepStrictEqual } from 'node:util';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import taskRoute from './new-a-task-route.cjs';
const HERE=path.dirname(fileURLToPath(import.meta.url)),ROOT=path.resolve(HERE,'../..');
const source=fs.readFileSync(path.join(HERE,'weak-early-beta-daily-runner.mjs'),'utf8');
const preflight=fs.readFileSync(path.join(HERE,'weak-early-beta-launch-preflight.mjs'),'utf8');
const journalPath=fs.existsSync(path.join(HERE,'weak-early-beta-run-journal.mjs'))?path.join(HERE,'weak-early-beta-run-journal.mjs'):path.join(process.env.NEW_A_READONLY_BASELINE_ROOT||ROOT,'scripts/windows/weak-early-beta-run-journal.mjs');
const journal=fs.readFileSync(journalPath,'utf8');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const privateBase=path.join(ROOT,'.cache/new-a-runner-tests');fs.mkdirSync(privateBase,{recursive:true});
const receipts=[];
const write=(p,v)=>{fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(v));};
function fixture(){const repo=fs.mkdtempSync(path.join(privateBase,'case-')),runtime=path.join(repo,'.cache/runtime');fs.mkdirSync(runtime,{recursive:true});fs.mkdirSync(path.join(repo,'weak-early-beta-gate'));write(path.join(repo,'weak-early-beta-gate/wrangler.jsonc'),{name:'tentei-kyokuchi-cloud'});return{repo,runtime};}
export function runnerFixture({pending=0,gateAccepted=true,nativeProof=null,nativeInspector=null,dateOverride=null,detected=0,fundamentalOK=true}={}){
 const {repo,runtime}=fixture(),today=dateOverride||'2026-11-13',head='f'.repeat(40),calls=[];let sent=false;
 const config={repoPath:repo,runtimeDir:runtime,nodePath:'FAKE_NODE_NO_EXEC',pythonPath:'FAKE_PYTHON_NO_EXEC',npmPath:'FAKE_NPM_NO_EXEC',ghPath:'FAKE_GH_NO_EXEC',date:today};
 const local=path.join(repo,'.cache/weak_early_beta/new-a-private');fs.mkdirSync(local,{recursive:true});
 let metadata={identity:'NEW_A_CLOUD_DAILY_V1',strategy:'A_BASE',entry:'new-a-verified-daily-v1',latest_session:today,selector_rows_latest:detected,detection_executed:true,source_version:'a'.repeat(64),snapshot_sha256:'b'.repeat(64),source_sha256:'c'.repeat(64),dry_run:false};
 if(process.env.NEW_A_REAL_E2E_RECEIPT){const proof=JSON.parse(fs.readFileSync(process.env.NEW_A_REAL_E2E_RECEIPT,'utf8'));assert.equal(proof.passed,true);const bundle=JSON.parse(fs.readFileSync(path.join(proof.private_bundle_directory,'receipt.json'),'utf8'));metadata={...metadata,source_version:bundle.source_version,snapshot_sha256:proof.snapshot_sha256,source_sha256:proof.source_sha256};}
 // No external process is ever created. Optional real receipt is injected by tests below as metadata only.
 const context={fs,path,isDeepStrictEqual,console:{log(){},error(){}},process:{pid:1234,platform:'linux',env:{},exitCode:0},Date,JSON,randomUUID:crypto.randomUUID,
  loadDailyConfig:()=>config,readJson:p=>JSON.parse(fs.readFileSync(p,'utf8')),writeJson:write,atomicJson:write,appendEvent:(p,v)=>{fs.mkdirSync(path.dirname(p),{recursive:true});fs.appendFileSync(p,JSON.stringify(v)+'\n');},
  loadDotEnv:()=>{},jstDate:()=>today,newATaskPlan:taskRoute.newATaskPlan,parseGitStatus:s=>s.trim()?['dirty']:[],
  probeFundamentalModel:async()=>{assert(detected>0);calls.push({args:['fundamental-model-preflight']});},
  runNewAFundamentalStage:async({expectedCount})=>{
   assert.equal(expectedCount,detected);calls.push({args:['new-a-fundamental']});
   if(!fundamentalOK)throw Error('synthetic analysis failed');
   if(detected>0){metadata={...metadata,source_version:'e'.repeat(64)};write(path.join(local,'latest-run.json'),metadata);}
   return {ok:true,status:detected?'COMPLETE':'NO_NEW_SIGNALS',imported:detected,posted:0};
  },drainFundamentalQueue:()=>{throw Error('FUNDAMENTAL_QUEUE_MUST_NOT_RUN');},assertHtmlImports:()=>{throw Error('FUNDAMENTAL_STATE_MUST_NOT_READ');},
  commitGeneratedChanges:()=>{throw Error('GENERATED_GIT_COMMIT_FORBIDDEN');},checkpointJpxRefresh:()=>{throw Error('OLD_TRACKED_JPX_COMMIT_FORBIDDEN');},
  networkFailureDetail:()=>null,waitForNetworkCapacity:async()=>({ok:true,synthetic:true}),waitInShortChunks:async()=>{},verifiedDetectionCache:async()=>({sha256:metadata.source_sha256}),
  npmInvocation:()=>({exe:'FAKE_NPM_NO_EXEC',args:['run','check']}),requireRemoteHead:async()=>head,
  waitForTagWorkflow:async({headSha,tag,listRuns})=>{const runs=await listRuns();assert.equal(runs[0].headSha,headSha);assert.equal(runs[0].headBranch,tag);return runs[0];},verifyLiveWorker:async()=>({synthetic:true,healthOnly:true}),
  RESEARCH_BRANCH:'research/weak-early-beta',GITHUB_REPOSITORY:'Ken5InvestmentLab/screening-bot',DEPLOY_WORKFLOW:'weak-early-beta-report-deploy.yml',
  run:async(...args)=>context.requireOk(...args),
  requireOk:async(exe,args,options)=>{
   calls.push({exe,args:[...args],pythonFaulthandler:options?.env?.PYTHONFAULTHANDLER});
   if(exe==='git'){
    assert(!['add','commit'].includes(args[0]),'No generated files may be committed');
    if(args[0]==='push')assert(/^refs\/tags\/cloud-deploy-daily-/.test(args[2]),'Only the existing code deploy tag is planned');
    if(args[0]==='tag')context.lastTag=args[1];
    return{code:0,stdout:args[0]==='branch'?'research/weak-early-beta':args[0]==='remote'?'https://github.com/Ken5InvestmentLab/screening-bot.git':'',stderr:''};
   }
   if(exe==='FAKE_GH_NO_EXEC')return{code:0,stdout:args[0]==='run'?JSON.stringify(args.includes('--status')?[]:[{headSha:head,headBranch:context.lastTag,status:'completed',conclusion:'success'}]):'',stderr:''};
   if(exe==='FAKE_NPM_NO_EXEC')return{code:0,stdout:'local checks mocked',stderr:''};
   assert.equal(exe,'FAKE_PYTHON_NO_EXEC');
   if(args[1]==='weak_early_beta.new_a.native_recovery'){
    const active=JSON.parse(fs.readFileSync(path.join(runtime,'daily-latest.json'),'utf8'));
    assert.equal(args[7],active.startedAt,'bind inspector to the newly written live progress, not the old terminal latest');
    assert.equal(args[8],String(active.pid));assert.equal(active.stage,'detection');assert.equal(active.completedAt,undefined);
    assert.equal(fs.readFileSync(path.join(runtime,'daily.lock'),'utf8'),active.startedAt);
    const preserved=JSON.parse(fs.readFileSync(args[4],'utf8'));assert.equal(active.originalRunId,preserved.originalRunId||preserved.startedAt);
    return nativeInspector?nativeInspector(args):{code:0,stdout:JSON.stringify(nativeProof),stderr:''};
   }
   if(args.includes('is-business-day'))return{code:0,stdout:'{"business_day":true}',stderr:''};
   if(args.includes('system-log'))return{code:0,stdout:'{"synthetic":true}',stderr:''};
   if(args[1]==='weak_early_beta.cli'&&args[2]==='daily'){
    assert(args.includes('--strategy')&&args[args.indexOf('--strategy')+1]==='new-a');write(path.join(local,'latest-run.json'),metadata);return{code:0,stdout:JSON.stringify(metadata),stderr:''};
   }
   if(args[1]==='weak_early_beta.cli'&&args[2]==='report'){assert(args.includes('new-a'));return{code:0,stdout:'{"data_free_frame":true}',stderr:''};}
   if(args.some(a=>a.endsWith('build-canonical-input.py')))return{code:0,stdout:'{"privateInputsRead":0}',stderr:''};
   if(args[1]==='weak_early_beta.new_a.cli'&&args[2]==='publish'){
    // This is a synthetic production-shape projection, never a remote D1 publication.
    const publication={schema:'SYNTHETIC_OWNER_PUBLICATION_FOR_RUNNER_TEST',published:true,active_readback_verified:true,existing_owner_gate_verified:gateAccepted,dataset_id:'a-'+'d'.repeat(24),source_version:metadata.source_version,snapshot_sha256:metadata.snapshot_sha256};write(path.join(local,'latest-publication.json'),publication);return{code:0,stdout:JSON.stringify(publication),stderr:''};
   }
   if(args[1]==='weak_early_beta.new_a.cli'&&args[2]==='notify'){
    const dry=args.includes('--dry-run'),n=sent?0:pending;if(!dry)sent=true;return{code:0,stdout:JSON.stringify({date:today,dry_run:dry,signal_notifications:n,completion_notifications:n?1:0,pending_discord_messages:dry&&n?1:0,external_sends:!dry&&n?1:0,synthetic:true}),stderr:''};
   }
   throw Error('Unexpected subprocess boundary: '+exe+' '+args.slice(0,3).join(' '));
  }};
 vm.createContext(context);
 vm.runInContext(journal.slice(journal.indexOf('export function recoveryPlan')).replace('export function','function'),context);
 const reconcile=source.slice(source.indexOf('function assertNotificationReceipt'),source.indexOf('function assertValidatedFundamentalOutput'));
 vm.runInContext(reconcile,context);const body=source.slice(source.indexOf('async function main('),source.indexOf('if (process.argv[1]',source.indexOf('async function main(')));vm.runInContext(body+'\nglobalThis.runnerMain=main;',context);
 return{context,calls,config,repo,runtime,today,async run(){await context.runnerMain(path.join(repo,'synthetic-daily-config.json'));return JSON.parse(fs.readFileSync(path.join(runtime,'daily-latest.json'),'utf8'));}};
}
test('New A main finishes without fundamental config, model, queue or generated commit',async()=>{
 const f=runnerFixture();assert.equal(f.config.fundamentalConfigPath,undefined);const result=await f.run();assert.equal(result.ok,true);assert.equal(result.fundamental.status,'NO_NEW_SIGNALS');assert.equal(result.generatedFilesSent,0);assert.equal(result.new_a.owner_publication_verified,true);assert(f.calls.some(c=>c.args.includes('weak_early_beta.new_a.cli')&&c.args.includes('publish')));assert(!f.calls.some(c=>c.args.includes('notify-day')));assert(!f.calls.some(c=>c.args.includes('add')||c.args.includes('commit')));receipts.push({case:'main_fundamental_unconfigured',passed:true,subprocesses:f.calls.length});
 const before=fs.readFileSync(path.join(f.runtime,'daily-latest.json'),'utf8'),calls=f.calls.length;await f.context.runnerMain(path.join(f.repo,'synthetic-daily-config.json'));assert.equal(f.calls.length,calls);assert.equal(fs.readFileSync(path.join(f.runtime,'daily-latest.json'),'utf8'),before);receipts.push({case:'direct_main_same_day_completion_no_repeat',passed:true});
});
test('Fundamental analysis covers the current batch before report and publication',async()=>{
 const f=runnerFixture({detected:2});f.config.fundamentalConfigPath='SYNTHETIC';
 const result=await f.run();
 assert.equal(result.ok,true);assert.equal(result.fundamental.imported,2);assert.equal(result.fundamental.posted,0);
 const before=f.calls.findIndex(c=>c.args.includes('fundamental-model-preflight'));
 const detection=f.calls.findIndex(c=>c.args.includes('daily')&&c.args.includes('--strategy'));
 const analysis=f.calls.findIndex(c=>c.args.includes('new-a-fundamental'));
 const publish=f.calls.findIndex(c=>c.args.includes('publish'));
 assert(before>=0&&before<detection&&detection<analysis&&analysis<publish);
 assert.equal(result.new_a.source_version,'e'.repeat(64));
});
test('Fundamental failure retains detection without starting report deployment or notifications',async()=>{
 const f=runnerFixture({detected:2,fundamentalOK:false});f.config.fundamentalConfigPath='SYNTHETIC';
 const result=await f.run();
 assert.equal(result.ok,false);assert.equal(result.stage,'fundamental');
 assert.equal(f.calls.filter(c=>c.args.includes('daily')&&c.args.includes('--strategy')).length,1);
 assert(!f.calls.some(c=>c.args.includes('publish')||c.args.includes('notify')||c.args[0]==='tag'));
});
test('Health success alone cannot complete owner publication or trigger notify',async()=>{
 const f=runnerFixture({gateAccepted:false});const result=await f.run();assert.equal(result.ok,false);assert(!f.calls.some(c=>c.args.includes('weak_early_beta.new_a.cli')&&c.args.includes('notify')));receipts.push({case:'owner_proof_required_beyond_health',passed:true});
});
test('Existing notification preview-send-reconcile ordering is kept with synthetic callbacks',async()=>{
 const f=runnerFixture({pending:1});assert.equal((await f.run()).ok,true);const notify=f.calls.filter(c=>c.args.includes('weak_early_beta.new_a.cli')&&c.args.includes('notify'));assert.equal(notify.length,3);assert(notify[0].args.includes('--dry-run'));assert(!notify[1].args.includes('--dry-run'));assert(notify[2].args.includes('--dry-run'));receipts.push({case:'new_a_notify_order',passed:true,realExternalCalls:0});
});

test('Native source recovery uses retained packets, one normal publication and no repeated completed run',async()=>{
 const proof={schema:'CLOUD_NATIVE_SOURCE_REPLAY_V1',directory:'SYNTHETIC_RETAINED_PRIVATE_PARTS',requests:1,network_fallback:false};
 const f=runnerFixture({nativeProof:proof}),prior={identity:'WEAK_EARLY_CLOUD_DAILY_V1',date:f.today,startedAt:'2026-11-13T08:00:00.000Z',completedAt:'2026-11-13T09:00:00.000Z',stage:'detection',ok:false,new_a:{strategy:'A_BASE',entry:'new-a-verified-daily-v1'}};
 const receipt=path.join(f.runtime,'recovery-input-synthetic.json');write(receipt,prior);write(path.join(f.runtime,'daily-latest.json'),prior);const preserved=fs.readFileSync(receipt,'utf8');
 await f.context.runnerMain(path.join(f.repo,'synthetic-daily-config.json'),{resumeReceipt:receipt});
 const result=JSON.parse(fs.readFileSync(path.join(f.runtime,'daily-latest.json'),'utf8'));assert.equal(result.ok,true);
 const daily=f.calls.filter(c=>c.args[1]==='weak_early_beta.cli'&&c.args[2]==='daily');assert.equal(daily.length,1);assert(!daily[0].args.includes('--refresh-live'));assert.equal(daily[0].args[daily[0].args.indexOf('--as-of')+1],f.today);assert.equal(daily[0].args[daily[0].args.indexOf('--retained-acquisition')+1],proof.directory);assert.equal(daily[0].pythonFaulthandler,'1');
 assert.equal(f.calls.filter(c=>c.args[1]==='weak_early_beta.new_a.cli'&&c.args[2]==='publish').length,1);assert.equal(fs.readFileSync(receipt,'utf8'),preserved);
 const count=f.calls.length;await f.context.runnerMain(path.join(f.repo,'synthetic-daily-config.json'));assert.equal(f.calls.length,count);
 receipts.push({case:'native_recovery_exact_retained_args_one_publication',passed:true,actualExternalCalls:0});
});
test('A-only launch preflight passes with absent fundamental config; legacy still requires it',async()=>{
 const {repo,runtime}=fixture(),configPath=path.join(repo,'daily.json');write(configPath,{});const python=path.join(repo,'python.fixture'),node=path.join(repo,'node.fixture');for(const p of [python,node,path.join(repo,'.env'),path.join(repo,'weak-early-beta-gate/.env')])fs.writeFileSync(p,'');const corpus=path.join(repo,'.cache/weak_early_beta/tse_daily.csv');fs.mkdirSync(path.dirname(corpus),{recursive:true});fs.writeFileSync(corpus,'SYNTHETIC_NOT_A_PRICE_CORPUS');write(corpus.replace('.csv','.source-quality.json'),{identity:'CLOUD_SOURCE_QUALITY_V1',daily_sha256:hash(fs.readFileSync(corpus)),sourceRows:0});const config={repoPath:repo,runtimeDir:runtime,pythonPath:python,nodePath:node};
 const context={fs,path,process:{platform:'linux'},runnerRepo:repo,createHash:crypto.createHash,loadDailyConfig:()=>config,readJson:p=>JSON.parse(fs.readFileSync(p,'utf8')),real:p=>fs.realpathSync.native(p),npmInvocation:()=>({exe:node,args:['NO_EXEC']}),execFileSync:()=>{throw Error('REAL_EXEC_FORBIDDEN');}};vm.createContext(context);vm.runInContext(preflight.slice(preflight.indexOf('function inside('),preflight.indexOf('// Read-only:')),context);vm.runInContext(preflight.slice(preflight.indexOf('export async function launchPreflight'),preflight.indexOf('if (process.argv[1]')).replace('export async function','async function')+'\nglobalThis.check=launchPreflight;',context);
 const command=(_,args)=>args.includes('branch')?'research/weak-early-beta':args.includes('remote')?'https://github.com/Ken5InvestmentLab/screening-bot.git':args.includes('rev-parse')?'f'.repeat(40):'';
 assert.equal((await context.check(configPath,{strategy:'A_BASE',platform:'linux',command})).ok,true);await assert.rejects(context.check(configPath,{strategy:'legacy',platform:'linux',command}));receipts.push({case:'launch_preflight_no_fundamental_A_only',passed:true,credentialsRead:false});
});
test.after(()=>{write(path.join(ROOT,'.cache/new-a-runner-tests/verification.json'),{passed:true,groups:receipts.length,checks:receipts,scope:'EXACT_STAGED_MAIN_AND_PREFLIGHT_WITH_SYNTHETIC_CONFIG_EMPTY_ENV_FAKE_SUBPROCESS_NETWORK_BOUNDARIES',actualSubprocessesExecuted:0,actualNotifications:0,actualGitWrites:0,actualDeployments:0,sourceHashes:{runner:hash(source),preflight:hash(preflight),journal:hash(journal)}});});
