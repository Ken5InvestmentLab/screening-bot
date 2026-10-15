import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadDailyConfig, parseGitStatus, requireRemoteHead, run } from './weak-early-beta-daily-runner.mjs';
import { prepareJpxCheckout } from './weak-early-beta-jpx-checkout.mjs';

const RUNNER_REPO = fileURLToPath(new URL('../../', import.meta.url));
const BRANCH = 'research/weak-early-beta';
const LEDGER = 'weak_early_beta/state/detections.csv';

export function loadReminderConfig(configFile, runnerRepo = RUNNER_REPO) {
  const config = loadDailyConfig(configFile, runnerRepo);
  if (typeof config.pythonPath !== 'string' || !config.pythonPath.trim()) throw new Error('reminder config requires pythonPath');
  return config;
}
function loadDotEnv(env, file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!match || env[match[1]] !== undefined) continue;
    let value = match[2];
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    env[match[1]] = value;
  }
}
export function assertReminderChanges(entries, { staged = false } = {}) {
  if (entries.some(entry => entry.path !== LEDGER || entry.oldPath || entry.status !== (staged ? 'M ' : ' M'))) {
    throw new Error('unexpected change during Cloud reminder delivery; only detection receipts may be committed');
  }
}
export async function commitReminderReceipts(git, date, { startCommit, checkLock }) {
  if (!/^[a-f0-9]{40}$/.test(startCommit)) throw new Error('missing frozen reminder start commit');
  const requireBranch = async () => {
    checkLock();
    if ((await git(['branch', '--show-current'])).stdout.trim() !== BRANCH) throw new Error('Cloud reminder branch changed during delivery');
  };
  const requireStart = async () => {
    await requireBranch();
    if ((await requireRemoteHead(git)) !== startCommit) throw new Error('Cloud reminder HEAD changed during delivery');
  };
  const status = async () => parseGitStatus((await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout);
  const before = await status();
  assertReminderChanges(before);
  await requireStart();
  if (!before.length) return { committed: false };
  await git(['add', '--', LEDGER]);
  const staged = (await git(['diff', '--cached', '--name-only', '-z'])).stdout.split('\0').filter(Boolean);
  const after = await status();
  assertReminderChanges(after, { staged: true });
  if (!staged.length && !after.length) return { committed: false };
  if (staged.length !== 1 || staged[0] !== LEDGER || after.length !== 1) throw new Error('Cloud reminder staging changed; refusing commit');
  await requireStart();
  await git(['commit', '-m', `chore: record Cloud exit reminders ${date} [skip ci]`]);
  if ((await status()).length) throw new Error('checkout changed during reminder commit; refusing push');
  await requireBranch();
  const committedSha = (await git(['rev-parse', 'HEAD'])).stdout.trim();
  const parent = (await git(['rev-parse', 'HEAD^'])).stdout.trim();
  const leaves = (await git(['diff-tree', '--no-commit-id', '--name-only', '-r', '-z', 'HEAD'])).stdout.split('\0').filter(Boolean);
  if (!/^[a-f0-9]{40}$/.test(committedSha) || parent !== startCommit || leaves.length !== 1 || leaves[0] !== LEDGER) throw new Error('Cloud reminder commit differs from the frozen start or receipt leaf');
  checkLock();
  // Push the verified commit itself; a later branch switch cannot add commits.
  await git(['push', 'origin', `${committedSha}:refs/heads/${BRANCH}`]);
  return { committed: true, paths: [LEDGER], commit: committedSha };
}
export async function main(configFile, {
  runnerRepo = RUNNER_REPO, runImpl = run, now = () => new Date(),
  platform = process.platform, log = line => console.error(line), prepareOnly = false,
} = {}) {
  const config = loadReminderConfig(configFile, runnerRepo);
  const repo = path.resolve(config.repoPath);
  const startedAt = now().toISOString();
  const today = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(now());
  if (config.date && config.date !== today) throw new Error('Cloud reminders cannot replay a different date');
  const runtime = path.join(repo, '.cache', 'weak_early_beta', 'exit_reminder_runtime');
  const runDir = path.join(runtime, `reminder-${startedAt.replace(/[:.]/g, '-')}`);
  const lock = path.join(repo, '.cache', 'weak_early_beta', 'exit-reminder-runner.lock');
  const resultPath = path.join(runtime, prepareOnly ? 'checkout-latest.json' : 'exit-reminder-latest.json');
  const result = { identity: 'WEAK_EARLY_CLOUD_EXIT_REMINDER_V1', startedAt, date: today, ok: false };
  fs.mkdirSync(runDir, { recursive: true });
  const env = { ...process.env, PYTHONUNBUFFERED: '1' };
  loadDotEnv(env, path.join(repo, '.env'));
  let ownsLock = false;
  let commandNumber = 0;
  const save = () => fs.writeFileSync(ownsLock ? resultPath : path.join(runDir, 'result.json'), `${JSON.stringify(result, null, 2)}\n`);
  const checkLock = () => {
    if (ownsLock && (!fs.existsSync(lock) || fs.readFileSync(lock, 'utf8') !== startedAt)) throw new Error('Cloud reminder lock ownership changed');
  };
  const progress = stage => {
    checkLock();
    Object.assign(result, { stage, progressAt: now().toISOString() });
    save();
    fs.appendFileSync(path.join(runDir, 'progress.jsonl'), `${JSON.stringify({ stage, at: result.progressAt })}\n`);
    log(`Cloud reminder stage: ${stage}`);
  };
  const execute = async (exe, args, label, timeoutMs = 60_000) => {
    const output = await runImpl(exe, args, { cwd: repo, env, log: path.join(runDir, `${++commandNumber}-${label}`), capture: true, timeoutMs });
    if (output.code !== 0) throw new Error(`${label} failed; inspect the captured run logs and reconcile receipts before retrying`);
    return output;
  };
  const git = args => execute('git', args, `git-${args[0]}`, args[0] === 'push' ? 300_000 : 60_000);
  try {
    try { fs.writeFileSync(lock, startedAt, { flag: 'wx' }); }
    catch (error) {
      if (error.code === 'EEXIST') throw new Error('Cloud reminder lock exists; inspect the previous run before retrying');
      throw error;
    }
    ownsLock = true;
    progress('preflight');
    for (const otherLock of [path.join(repo, '.cache', 'weak_early_beta', 'exit-reminder.lock'), path.join(repo, '.cache', 'weak_early_beta', 'daily_runtime', 'daily.lock')]) {
      if (fs.existsSync(otherLock)) throw new Error('another Cloud runner lock exists; reconcile the active run');
    }
    if ((await git(['branch', '--show-current'])).stdout.trim() !== BRANCH) throw new Error('refusing to run outside research/weak-early-beta');
    if (prepareOnly) {
      // Preparation never invokes Python or sends a Discord message.
      if (platform === 'win32') {
        const processes = await execute('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
          `$ErrorActionPreference = 'Stop'; @(Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction Stop | Where-Object { $_.ProcessId -ne ${process.pid} -and $_.CommandLine -match 'weak-early-beta-(?:exit-reminder|daily)-runner\\.mjs' } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress`], 'process-preflight', 30_000);
        if (processes.stdout.trim() && !/^\[\s*\]$/.test(processes.stdout.trim())) throw new Error('another Cloud reminder or daily Node process exists');
      }
      const checkSafety = () => {
        checkLock();
        for (const other of ['exit-reminder.lock', 'daily_runtime/daily.lock']) {
          if (fs.existsSync(path.join(repo, '.cache', 'weak_early_beta', other))) throw new Error('another Cloud runner lock exists');
        }
      };
      result.checkout = await prepareJpxCheckout({ repo, git, checkSafety, auditDir: runDir });
      result.ok = true;
      progress('complete');
      return result;
    }
    if (parseGitStatus((await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout).length) throw new Error('reminder checkout is not clean; use a clean research checkout without changing user files');
    const origin = (await git(['remote', 'get-url', 'origin'])).stdout.trim();
    if (!/^(?:https:\/\/github\.com\/|git@github\.com:)Ken5InvestmentLab\/screening-bot(?:\.git)?$/i.test(origin)) throw new Error('unexpected Cloud Git origin');
    result.startCommit = await requireRemoteHead(git);
    if (platform === 'win32') {
      const processes = await execute('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
        `$ErrorActionPreference = 'Stop'; @(Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction Stop | Where-Object { $_.ProcessId -ne ${process.pid} -and $_.CommandLine -match 'weak-early-beta-(?:exit-reminder|daily)-runner\\.mjs' } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress`], 'process-preflight', 30_000);
      if (processes.stdout.trim() && !/^\[\s*\]$/.test(processes.stdout.trim())) throw new Error('another Cloud reminder or daily Node process exists');
    }
    progress('delivery');
    const output = await execute(config.pythonPath, ['-B', '-m', 'weak_early_beta.cli', 'remind-exits', '--date', today], 'remind-exits', 600_000);
    const summary = JSON.parse(output.stdout.trim());
    if (summary.date !== today || typeof summary.business_day !== 'boolean' || summary.dry_run !== false || !Number.isInteger(summary.reminders) || summary.reminders < 0) throw new Error('invalid Cloud reminder completion receipt');
    Object.assign(result, summary);
    progress('receipt-sync');
    if (summary.reminders === 0 && parseGitStatus((await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout).length) throw new Error('zero reminders unexpectedly changed the checkout');
    result.receiptCommit = await commitReminderReceipts(git, today, { startCommit: result.startCommit, checkLock });
    result.ok = true;
    progress('complete');
    return result;
  } catch (error) {
    result.ok = false;
    result.error = error.message;
    throw error;
  } finally {
    result.completedAt = now().toISOString();
    save();
    if (ownsLock && fs.existsSync(lock) && fs.readFileSync(lock, 'utf8') === startedAt) fs.rmSync(lock);
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('usage: node weak-early-beta-exit-reminder-runner.mjs <config.json>');
  if (process.argv.slice(3).some(arg => arg !== '--prepare-only') || process.argv.length > 4) throw new Error('unexpected Cloud reminder option');
  try { console.log(JSON.stringify(await main(process.argv[2], { prepareOnly: process.argv[3] === '--prepare-only' }))); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
