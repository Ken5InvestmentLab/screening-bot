import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { recoverCompletedFundamentals } from './new-a-completed-fundamental-recovery.mjs';
const hash=data=>createHash('sha256').update(data).digest('hex');
function fixture(t) {
 const repo=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'cloud-fundamental-recovery-')));
 t.after(()=>{assert(path.basename(repo).startsWith('cloud-fundamental-recovery-'));fs.rmSync(repo,{recursive:true,force:true});});
 const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data)+'\n');};
 const runtime=path.join(repo,'.cache/weak_early_beta/daily_runtime');
 const root=path.join(repo,'.cache/weak_early_beta/new-a-private');
 const claim=path.join(root,'runs/2026-11-24/source/live/fundamental-analysis/claim.json');
 const daily=path.join(runtime,'daily-latest.json'),producer=path.join(root,'latest-run.json');
 const fconfig=path.join(repo,'.cache/weak_early_beta/fundamental-runner.config.json');
 write(fconfig,{});
 write(path.join(repo,'.cache/weak_early_beta/daily-runner.config.json'),{repoPath:repo,runtimeDir:runtime,
  fundamentalConfigPath:fconfig,pythonPath:'synthetic-python',nodePath:'synthetic-node'});
 write(daily,{ok:true,completedAt:'2026-11-24T14:46:31Z',date:'2026-11-24',startedAt:'2026-11-24T13:27:14Z',selectorRows:3});
 write(producer,{latest_session:'2026-11-24',source_sha256:'source',identity:'NEW_A_CLOUD_DAILY_V1',
  detection_executed:true,dry_run:false});
 write(claim,{claimedCount:3,analysisStartedAt:'2026-11-24T14:18:20Z'});
 const outbox=path.join(root,'notification-outbox.sqlite');fs.writeFileSync(outbox,'SENT:immutable-fixture');
 return {repo,runtime,claim,daily,producer,outbox,write};
}
test('completed analysis recovery uses its own lease and preserves the original daily, claim and SENT outbox',async t=>{
 const f=fixture(t),original=[f.claim,f.daily,f.outbox].map(p=>hash(fs.readFileSync(p)));
 let calls=0;
 const result=await recoverCompletedFundamentals({repo:f.repo,date:'2026-11-24',loadEnvironment:()=>({}),
  runStep:async()=>({stdout:'a'.repeat(40)}),runAnalysis:async options=>{
   calls++;assert.equal(options.expectedCount,3);
   assert.equal(options.startedAt,'2026-11-24T13:27:14Z');
   const lease=path.join(f.runtime,'fundamental-recovery.lock');
   assert.equal(hash(fs.readFileSync(lease)),options.completedRecoverySha256);
   assert.equal(fs.existsSync(path.join(f.runtime,'daily.lock')),false);
   return {ok:true,imported:3,posted:0};
  }});
 assert.equal(calls,1);assert.equal(result.ok,true);assert.equal(result.notificationsSent,0);
 assert.deepEqual([f.claim,f.daily,f.outbox].map(p=>hash(fs.readFileSync(p))),original);
 assert.equal(fs.existsSync(path.join(f.runtime,'fundamental-recovery.lock')),false);
});
test('failed research remains held with the same claim and can never restart detection or send',async t=>{
 const f=fixture(t),original=fs.readFileSync(f.claim,'utf8');
 await assert.rejects(recoverCompletedFundamentals({repo:f.repo,date:'2026-11-24',loadEnvironment:()=>({}),
  runStep:async()=>({stdout:'a'.repeat(40)}),runAnalysis:async()=>{throw Error('runtime probe denied');}}),/runtime probe denied/);
 assert.equal(fs.readFileSync(f.claim,'utf8'),original);
 assert.equal(fs.existsSync(path.join(f.runtime,'daily.lock')),false);
 const folder=path.join(f.runtime,'fundamental-recovery');
 const result=JSON.parse(fs.readFileSync(path.join(folder,fs.readdirSync(folder)[0],'result.json')));
 assert.equal(result.status,'HELD');assert.equal(result.detectionExecuted,false);assert.equal(result.notificationsSent,0);
});
test('another recovery owner or active daily runner blocks before analysis',async t=>{
 const f=fixture(t);let calls=0;
 const options={repo:f.repo,date:'2026-11-24',loadEnvironment:()=>({}),runStep:async()=>({stdout:'a'.repeat(40)}),
  runAnalysis:async()=>{calls++;}};
 const lock=path.join(f.runtime,'fundamental-recovery.lock');fs.writeFileSync(lock,'another owner');
 await assert.rejects(recoverCompletedFundamentals(options),/EEXIST/);
 assert.equal(fs.readFileSync(lock,'utf8'),'another owner');assert.equal(calls,0);
 fs.writeFileSync(path.join(f.runtime,'daily.lock'),'daily owner');
 await assert.rejects(recoverCompletedFundamentals(options),/still-current completed daily/);
 assert.equal(calls,0);
});
