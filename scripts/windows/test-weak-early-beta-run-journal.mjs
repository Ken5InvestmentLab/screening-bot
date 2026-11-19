import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { boundedPreflight, startInvocation, readRecord, recoveryPlan, jstDay } from './weak-early-beta-run-journal.mjs';
import { taskEntry } from './weak-early-beta-task-entry.mjs';
import { capturePreProviderCacheFailure, verifyPreProviderCacheRecovery } from './new-a-pre-provider-cache-recovery.mjs';
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

function preProviderFixture() {
  const directory = temp(), runtime = path.join(directory, 'runtime');
  const date = jstDay(), startedAt = date + 'T09:34:03.000Z';
  const run = path.join(runtime, 'daily-' + startedAt.replace(/[:.]/g, '-'));
  fs.mkdirSync(run, { recursive: true });
  const archive = path.join(run, 'acquisition-1');
  const processFile = path.join(run, 'detect-1.process.json');
  const stderr = path.join(run, 'detect-1.stderr');
  const prior = {
    new_a: { strategy: 'A_BASE', entry: 'new-a-verified-daily-v1', owner_publication_verified: false },
    identity: 'WEAK_EARLY_CLOUD_DAILY_V1', date, startedAt, stage: 'detection', pid: 123,
    completedAt: date + 'T09:46:00Z', ok: false, startCommit: 'd'.repeat(40), privateSourceCacheRetained: true,
    acquisitionEvidence: [{ attempt: 1, directory: archive }], approvedWorkerPreflight: { sourceCommit: 'd'.repeat(40) },
  };
  fs.writeFileSync(processFile, JSON.stringify({
    identity: 'CLOUD_CHILD_PROCESS_V1', pid: 234, status: 'exited', code: 1, completedAt: date + 'T09:45:00Z',
  }));
  fs.writeFileSync(stderr, JSON.stringify({
    identity: 'NEW_A_PRE_PROVIDER_CACHE_FAILURE_V1', reason: 'memory', phase: 'previous-cache-read',
  }) + '\n');
  const sha = 'a'.repeat(64);
  prior.preProviderCacheFailure = capturePreProviderCacheFailure(runtime, prior, sha);
  const raw = JSON.stringify(prior);
  fs.writeFileSync(path.join(run, 'result.json'), raw);
  fs.writeFileSync(path.join(runtime, 'daily-latest.json'), raw);
  return { directory, runtime, run, archive, processFile, stderr, prior, sha };
}

test('task entry validates pre-provider evidence before reserving the one allowed acquisition', async () => {
  const f = preProviderFixture();
  const { EventEmitter } = await import('node:events');
  let launches = 0;
  const options = {
    auditDirectory: path.join(f.directory, 'audit'), load: () => ({ runtimeDir: f.runtime, repoPath: f.directory, nodePath: process.execPath }),
    check: async () => ({ ok: true, sourceSha256: f.sha }),
    launch(exe, args) {
      launches++;
      assert.equal(exe, process.execPath);
      const receipt = args[args.indexOf('--resume-detection') + 1];
      assert.equal(verifyPreProviderCacheRecovery(f.runtime, f.prior, f.sha, receipt).sourceSha256, f.sha);
      const child = new EventEmitter();
      child.pid = 12345;
      child.unref = () => {};
      queueMicrotask(() => child.emit('spawn'));
      return child;
    },
  };
  const checked = await taskEntry('test.json', options);
  assert.equal(checked.status, 'ready');
  assert.equal(checked.plan.acquisition, 'first-live-after-verified-cache-failure');
  assert.equal(launches, 0);
  assert.equal((await taskEntry('test.json', { ...options, start: true })).status, 'launched');
  assert.equal((await taskEntry('test.json', { ...options, start: true })).status, 'reconcile');
  assert.equal(launches, 1);
});

test('a changed cache, original terminal receipt, child receipt, marker or archive refuses fresh acquisition', () => {
  for (const alter of [
    f => { f.sha = 'b'.repeat(64); },
    f => fs.writeFileSync(path.join(f.run, 'result.json'), '{}'),
    f => fs.writeFileSync(f.processFile, fs.readFileSync(f.processFile, 'utf8') + '\n'),
    f => fs.appendFileSync(f.stderr, 'changed\n'),
    f => fs.mkdirSync(f.archive),
    f => { f.prior.completedAt = null; },
    f => { f.prior.notifications = {}; },
  ]) {
    const f = preProviderFixture();
    assert.equal(verifyPreProviderCacheRecovery(f.runtime, f.prior, f.sha).sourceSha256, f.sha);
    alter(f);
    assert.throws(() => verifyPreProviderCacheRecovery(f.runtime, f.prior, f.sha));
  }
});

test('legacy detection evidence without the typed marker cannot opt into a fresh acquisition', () => {
  const f = preProviderFixture();
  fs.writeFileSync(f.stderr, 'numpy._core._exceptions._ArrayMemoryError: Unable to allocate 395. MiB');
  assert.equal(capturePreProviderCacheFailure(f.runtime, f.prior, f.sha), null);
  assert.throws(() => verifyPreProviderCacheRecovery(f.runtime, f.prior, f.sha), /exact previous-cache memory failure marker/i);
});
