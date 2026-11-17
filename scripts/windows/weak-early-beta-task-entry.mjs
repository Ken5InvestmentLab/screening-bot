import { delayedBridge } from './delayed-run-bridge.mjs';
import { verifyAdmissionContinuation, claimAdmissionContinuation } from './native-admission-continuation.mjs';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { loadDailyConfig } from './weak-early-beta-daily-runner.mjs';
import taskRoute from './new-a-task-route.cjs';
const { newATaskPlan } = taskRoute;
import { launchPreflight } from './weak-early-beta-launch-preflight.mjs';
import { startInvocation, boundedPreflight, readRecord, recoveryPlan, atomicJson, jstDay } from './weak-early-beta-run-journal.mjs';
import { verifyPreflightReconciliation, claimPreflightReconciliation } from './preflight-reconciliation.mjs';

// The audit file is written before reading config, inspecting processes, or hashing data.
export async function taskEntry(configPath, { task = 'cloud-3', start = false, reconciliationFile = null, delayedRecord = null, acceptanceApplication = null, admissionContinuationFile = null,
  auditDirectory = path.join(os.homedir(), 'Documents', 'Codex', 'Cloud_task_invocations'),
  bridge = delayedBridge, check = file => launchPreflight(file, { strategy: task === "cloud-5" ? "legacy" : "A_BASE" }), load = loadDailyConfig, launch = spawn, retryOptions = {}, continuationOptions = {} } = {}) {
  const invocation = startInvocation(auditDirectory, { task, configPath });
  let fd, guard;
  try {
    const config = load(configPath);
    const runtime = path.resolve(config.runtimeDir);
    fs.mkdirSync(runtime, { recursive: true });
    guard = path.join(runtime, 'task-entry.lock');
    try { fd = fs.openSync(guard, 'wx'); fs.writeFileSync(fd, invocation.value.id); fs.fsyncSync(fd); }
    catch (error) { if (error.code !== 'EEXIST') throw error; return invocation.update({ status: 'observe', reason: 'Another task-entry owns launch arbitration; inspect its record, do not delete the lock' }); }
    if(admissionContinuationFile && (task!=='cloud-2'||delayedRecord||reconciliationFile||acceptanceApplication))throw Error('Distinct cloud-2 native admission continuation required');
    if(delayedRecord) {
      if(task!=='cloud-2' || reconciliationFile || !acceptanceApplication || !start) throw Error('Delayed recovery requires exact cloud-2 one-shot accepted application');
      invocation.update({status:'checking-stopped-run',targetDate:'2026-11-16',executionDate:invocation.value.date});
      const claim=bridge(config,'claim',path.resolve(delayedRecord),['--invocation',invocation.value.id,'--config',path.resolve(configPath),'--acceptance-application',path.resolve(acceptanceApplication)]);
      const claimFile=path.resolve(config.repoPath,claim.path), log=path.join(runtime,`task-entry-${invocation.value.id}.log`), output=fs.openSync(log,'a');
      try {
        const child=launch(config.nodePath,[path.join(config.repoPath,'scripts/windows/weak-early-beta-daily-runner.mjs'),path.resolve(configPath),'--delayed-recovery',claimFile],{cwd:config.repoPath,detached:true,windowsHide:true,stdio:['ignore',output,output]});
        await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});
        invocation.update({status:'launched-delayed',targetDate:'2026-11-16',executionDate:invocation.value.date,childPid:child.pid,log,claim});
        const until=Date.now()+30000;let rootObserved=false;
        while(Date.now()<until) {
          const latest=path.join(runtime,'daily-latest.json');
          if(fs.existsSync(latest)) {const value=readRecord(latest);if(value.pid===child.pid && value.delayedRecovery && fs.existsSync(path.join(runtime,'daily.lock'))) {rootObserved=true;break;}}
          await new Promise(resolve=>setTimeout(resolve,100));
        }
        invocation.update({status:rootObserved?'launched-delayed':'launched-delayed-unconfirmed',rootLockObserved:rootObserved});
        child.unref();
      } finally {fs.closeSync(output);}
      return invocation.value;
    }
    const readiness = await boundedPreflight(() => check(configPath), { ...retryOptions,
      date: invocation.value.date, onAttempt: attempt => invocation.update({ status: 'checking', preflight: attempt }) });
    if (readiness.status !== 'ready') return invocation.update({ status: 'recovery-required', preflight: readiness });
    const latest = path.join(runtime, 'daily-latest.json');
    const prior = fs.existsSync(latest) ? readRecord(latest) : null;
    if(admissionContinuationFile){
      const verified=verifyAdmissionContinuation({repo:config.repoPath,runtime,date:invocation.value.date,head:readiness.result.head,sourceSha256:readiness.result.sourceSha256,prior,file:path.resolve(admissionContinuationFile),auditDirectory,processReader:continuationOptions.processReader});
      if(!start)return invocation.update({status:'ready-continuation',externalSideEffects:false,record:verified.digest});
      if(jstDay()!==invocation.value.date)throw Error('Target JST day changed');
      claimAdmissionContinuation(runtime,verified,invocation.value.id);
      const args=[path.join(config.repoPath,'scripts/windows/weak-early-beta-daily-runner.mjs'),path.resolve(configPath),'--native-admission-continuation',verified.file,'--continuation-invocation',invocation.value.id];
      const log=path.join(runtime,`task-entry-${invocation.value.id}.log`),output=fs.openSync(log,'a');
      try{const child=launch(config.nodePath,args,{cwd:config.repoPath,detached:true,windowsHide:true,stdio:['ignore',output,output]});await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});invocation.update({status:'launched-continuation',childPid:child.pid,log,continuation:verified.digest});child.unref();}finally{fs.closeSync(output);}
      return invocation.value;
    }
    let plan = task === 'cloud-5' ? recoveryPlan(prior, invocation.value.date) : newATaskPlan(task, invocation.value.date, prior, recoveryPlan);
    let reconciliation;
    if (reconciliationFile) {
      if (task === 'cloud-5' || plan.action !== 'reconcile' || !prior) throw new Error('Preflight reconciliation requires the exact unresolved New A day');
      reconciliation = verifyPreflightReconciliation({repo:config.repoPath,runtime,date:invocation.value.date,head:readiness.result.head,prior,file:reconciliationFile});
      plan = { action:'resume-preflight', originalRunId:prior.startedAt, reconciliation_sha256:reconciliation.digest };
    }
    if (!['none', 'resume-detection', 'resume-preflight'].includes(plan.action)) return invocation.update({ status: plan.action, plan });
    if (task === 'cloud-5') return invocation.update({ status: 'reconcile', reason: 'Reminder recovery must reconcile its own delivery receipts; daily launcher not used' });
    if (!start) return invocation.update({ status: 'ready', plan, externalSideEffects: false });
    if (jstDay() !== invocation.value.date) throw new Error('Target JST day changed');
    if (reconciliation) claimPreflightReconciliation(runtime,reconciliation,invocation.value.id);
    let receipt;
    if (plan.action === 'resume-detection') {
      // Immutable reservation bounds automatic retry to once per failed run, including ambiguous spawn.
      const key = String(prior.originalRunId || prior.startedAt || '').replace(/[^0-9TZ-]/g, '');
      if (!key) throw new Error('Missing failed run identity');
      const claim = path.join(runtime, `recovery-${key}.json`);
      let claimFd;
      try { claimFd = fs.openSync(claim, 'wx'); }
      catch (error) { if (error.code !== 'EEXIST') throw error; return invocation.update({ status: 'reconcile', reason: 'Recovery already claimed; inspect saved PID/receipt before any repeat' }); }
      fs.writeFileSync(claimFd, JSON.stringify({ invocation: invocation.value.id, priorStartedAt: prior.startedAt })); fs.fsyncSync(claimFd); fs.closeSync(claimFd);
      receipt = path.join(runtime, `recovery-input-${key}.json`); atomicJson(receipt, prior);
    }
    const args = [path.join(config.repoPath, 'scripts', 'windows', 'weak-early-beta-daily-runner.mjs'), path.resolve(configPath)];
    if (receipt) args.push('--resume-detection', receipt);
    if (reconciliation) args.push('--reconcile-preflight', reconciliation.file, '--reconcile-invocation', invocation.value.id);
    const log = path.join(runtime, `task-entry-${invocation.value.id}.log`);
    const output = fs.openSync(log, 'a');
    try {
      const child = launch(config.nodePath, args, { cwd: config.repoPath, detached: true, windowsHide: true, stdio: ['ignore', output, output] });
      await new Promise((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
      invocation.update({ status: 'launched', childPid: child.pid, log, plan });
      child.unref();
    } finally { fs.closeSync(output); }
    return invocation.value;
  } catch (error) { return invocation.update({ status: 'recovery-required', reason: String(error.message || error).slice(0, 1500) }); }
  finally { if (fd !== undefined) { fs.closeSync(fd); if (fs.readFileSync(guard, 'utf8') === invocation.value.id) fs.unlinkSync(guard); } }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('Expected daily config path');
  const index=process.argv.indexOf('--reconcile-preflight');
  if(index>=0&&!process.argv[index+1])throw Error('Missing reconciliation record');
  const delayedIndex=process.argv.indexOf('--delayed-recovery'),applicationIndex=process.argv.indexOf('--acceptance-application');
  const continuationIndex=process.argv.indexOf('--native-admission-continuation');
  if(continuationIndex>=0&&(!process.argv[continuationIndex+1]||process.argv[continuationIndex+1].startsWith('--')))throw Error('Missing native admission continuation record');
  console.log(JSON.stringify(await taskEntry(process.argv[2], { admissionContinuationFile:continuationIndex>=0?process.argv[continuationIndex+1]:null, delayedRecord:delayedIndex>=0?process.argv[delayedIndex+1]:null, acceptanceApplication:applicationIndex>=0?process.argv[applicationIndex+1]:null, task: process.argv[3] || 'cloud-3', start: process.argv.includes('--start'), reconciliationFile:index>=0?process.argv[index+1]:null })));
}
