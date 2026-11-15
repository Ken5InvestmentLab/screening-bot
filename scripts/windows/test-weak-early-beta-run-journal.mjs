import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { boundedPreflight, startInvocation, readRecord, recoveryPlan, jstDay } from './weak-early-beta-run-journal.mjs';
import { taskEntry } from './weak-early-beta-task-entry.mjs';
const temp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-journal-'));
test('invocation persists before config failure', async () => {
 const directory=temp(); const result=await taskEntry('missing.json',{auditDirectory:directory,load:()=>{throw new Error('missing config');}});
 assert.equal(result.status,'recovery-required'); const record=readRecord(path.join(directory,fs.readdirSync(directory)[0])); assert.equal(record.identity,'CLOUD_TASK_INVOCATION_V1'); assert.ok(record.startedAt);
});
test('unknown retries bounded, affirmative readiness required',async()=>{
 let calls=0, waits=0;
 const r=await boundedPreflight(()=>{calls++;throw new Error('inspection unavailable');},{delayMs:0,wait:async()=>{waits++;}});
 assert.equal(r.status,'unknown');assert.equal(calls,3);assert.equal(waits,2);
});
test('confirmed lock abnormal is not retried',async()=>{
 let calls=0;const r=await boundedPreflight(()=>{calls++;throw new Error('lock exists');});assert.equal(r.status,'abnormal');assert.equal(calls,1);
});
test('unknown can resolve but changing date never launches',async()=>{
 let calls=0; const r=await boundedPreflight(()=> ++calls===1 ? {} : {ok:true},{delayMs:0,wait:async()=>{}});assert.equal(r.status,'ready');
 const changed=await boundedPreflight(()=>{throw new Error('must not run');},{date:'2000-01-01'});assert.equal(changed.status,'abnormal');
});
test('terminal stage receipt refuses deployment and send replay',()=>{
 const base={identity:'WEAK_EARLY_CLOUD_DAILY_V1',date:'2026-11-12',stage:'detection',completedAt:'2026-11-12T09:00:00Z',ok:false};
 assert.equal(recoveryPlan(base,base.date).action,'resume-detection');
 for(const delta of [{stage:'notification'},{deployment:{}},{notifications:{}},{fundamentals:[{}]}]) assert.equal(recoveryPlan({...base,...delta},base.date).action,'reconcile');
 assert.equal(recoveryPlan({...base,completedAt:null},base.date).action,'observe');
 assert.equal(recoveryPlan({...base,ok:true},base.date).action,'complete');
});
test('task inspect cannot launch and launch arbitration cannot be stolen',async()=>{
 const directory=temp(),runtime=path.join(directory,'runtime');fs.mkdirSync(runtime);
 const options={auditDirectory:path.join(directory,'audit'),load:()=>({runtimeDir:runtime}),check:async()=>({ok:true}),launch:()=>{throw new Error('MUST NOT SPAWN');}};
 assert.equal((await taskEntry('test.json',options)).status,'ready');
 fs.writeFileSync(path.join(runtime,'task-entry.lock'),'other-owner');
 assert.equal((await taskEntry('test.json',{...options,start:true})).status,'observe');assert.equal(fs.readFileSync(path.join(runtime,'task-entry.lock'),'utf8'),'other-owner');
});
test('reminder invocation never falls through to daily launcher',async()=>{
 const directory=temp();const r=await taskEntry('test.json',{task:'cloud-5',start:true,auditDirectory:path.join(directory,'audit'),load:()=>({runtimeDir:path.join(directory,'runtime')}),check:async()=>({ok:true}),launch:()=>{throw new Error('MUST NOT SPAWN');}});assert.equal(r.status,'reconcile');
});
test('same original failure cannot cause an endless recovery chain', async()=>{
 const directory=temp(), runtime=path.join(directory,'runtime');fs.mkdirSync(runtime);
 const { EventEmitter }=await import('node:events');let launches=0;
 const prior={new_a:{strategy:'A_BASE',entry:'new-a-verified-daily-v1'},identity:'WEAK_EARLY_CLOUD_DAILY_V1',date:jstDay(),startedAt:'2026-11-12T08:34:03Z',stage:'detection',completedAt:'2026-11-12T09:46:00Z',ok:false};
 const latest=path.join(runtime,'daily-latest.json');fs.writeFileSync(latest,JSON.stringify(prior));
 const options={start:true,auditDirectory:path.join(directory,'audit'),load:()=>({runtimeDir:runtime,repoPath:directory,nodePath:process.execPath}),check:async()=>({ok:true}),launch:()=>{launches++;const c=new EventEmitter();c.pid=12345;c.unref=()=>{};queueMicrotask(()=>c.emit('spawn'));return c;}};
 assert.equal((await taskEntry('test.json',options)).status,'launched');
 fs.writeFileSync(latest,JSON.stringify({...prior,startedAt:'2026-11-12T10:30:00Z',originalRunId:prior.startedAt}));
 assert.equal((await taskEntry('test.json',options)).status,'reconcile');assert.equal(launches,1);
});

test('same-day legacy or unknown receipt is never proof for New A recovery',async()=>{
 const directory=temp(),runtime=path.join(directory,'runtime');fs.mkdirSync(runtime);
 const prior={identity:'WEAK_EARLY_CLOUD_DAILY_V1',date:jstDay(),startedAt:'synthetic-old-run',stage:'detection',completedAt:'synthetic-complete',ok:false};
 fs.writeFileSync(path.join(runtime,'daily-latest.json'),JSON.stringify(prior));
 const r=await taskEntry('test.json',{start:true,auditDirectory:path.join(directory,'audit'),load:()=>({runtimeDir:runtime,repoPath:directory,nodePath:process.execPath}),check:async()=>({ok:true}),launch:()=>{throw Error('MUST NOT SPAWN');}});
 assert.equal(r.status,'reconcile');assert.match(r.plan.reason,/legacy or unknown/);
});
