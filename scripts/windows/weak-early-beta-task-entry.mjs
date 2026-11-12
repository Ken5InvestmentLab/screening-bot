import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { loadDailyConfig } from './weak-early-beta-daily-runner.mjs';
import { launchPreflight } from './weak-early-beta-launch-preflight.mjs';
import { startInvocation, boundedPreflight, readRecord, recoveryPlan, atomicJson, jstDay } from './weak-early-beta-run-journal.mjs';

// The audit file is written before reading config, inspecting processes, or hashing data.
export async function taskEntry(configPath, { task = 'cloud-3', start = false,
  auditDirectory = path.join(os.homedir(), 'Documents', 'Codex', 'Cloud_task_invocations'),
  check = launchPreflight, load = loadDailyConfig, launch = spawn, retryOptions = {} } = {}) {
  const invocation = startInvocation(auditDirectory, { task, configPath });
  let fd, guard;
  try {
    const config = load(configPath);
    const runtime = path.resolve(config.runtimeDir);
    fs.mkdirSync(runtime, { recursive: true });
    guard = path.join(runtime, 'task-entry.lock');
    try { fd = fs.openSync(guard, 'wx'); fs.writeFileSync(fd, invocation.value.id); fs.fsyncSync(fd); }
    catch (error) { if (error.code !== 'EEXIST') throw error; return invocation.update({ status: 'observe', reason: 'Another task-entry owns launch arbitration; inspect its record, do not delete the lock' }); }
    const readiness = await boundedPreflight(() => check(configPath), { ...retryOptions,
      date: invocation.value.date, onAttempt: attempt => invocation.update({ status: 'checking', preflight: attempt }) });
    if (readiness.status !== 'ready') return invocation.update({ status: 'recovery-required', preflight: readiness });
    const latest = path.join(runtime, 'daily-latest.json');
    const prior = fs.existsSync(latest) ? readRecord(latest) : null;
    const plan = recoveryPlan(prior, invocation.value.date);
    if (!['none', 'resume-detection'].includes(plan.action)) return invocation.update({ status: plan.action, plan });
    if (task === 'cloud-5') return invocation.update({ status: 'reconcile', reason: 'Reminder recovery must reconcile its own delivery receipts; daily launcher not used' });
    if (!start) return invocation.update({ status: 'ready', plan, externalSideEffects: false });
    if (jstDay() !== invocation.value.date) throw new Error('Target JST day changed');
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
  console.log(JSON.stringify(await taskEntry(process.argv[2], { task: process.argv[3] || 'cloud-3', start: process.argv.includes('--start') })));
}
