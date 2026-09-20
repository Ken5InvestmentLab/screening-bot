import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); }
function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
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
async function run(exe, args, { cwd, env, log, capture = false, timeoutMs = 12_000_000 }) {
  fs.mkdirSync(path.dirname(log), { recursive: true });
  return await new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    const child = spawn(exe, args, { cwd, env, windowsHide: true, stdio: capture ? ['ignore', 'pipe', 'pipe'] : ['ignore', 'pipe', 'pipe'] });
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    const timer = setTimeout(() => {
      spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
      reject(new Error(`timeout: ${path.basename(log)}`));
    }, timeoutMs);
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('exit', code => {
      clearTimeout(timer);
      fs.writeFileSync(`${log}.stdout`, stdout);
      fs.writeFileSync(`${log}.stderr`, stderr);
      resolve({ code, stdout, stderr });
    });
  });
}
async function requireOk(exe, args, options) {
  const result = await run(exe, args, options);
  if (result.code !== 0) throw new Error(`${path.basename(options.log)} failed; inspect bounded local logs`);
  return result;
}
async function waitInShortChunks(ms) {
  let remaining = ms;
  while (remaining > 0) {
    const chunk = Math.min(remaining, 60_000);
    await new Promise(resolve => setTimeout(resolve, chunk));
    remaining -= chunk;
  }
}
function jstDate() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

async function main(configFile) {
  const config = readJson(path.resolve(configFile));
  const repo = path.resolve(config.repoPath);
  const runtime = path.resolve(config.runtimeDir);
  const startedAt = new Date().toISOString();
  const runDir = path.join(runtime, `daily-${startedAt.replace(/[:.]/g, '-')}`);
  const resultPath = path.join(runtime, 'daily-latest.json');
  const result = { identity: 'WEAK_EARLY_CLOUD_DAILY_V1', startedAt, ok: false };
  fs.mkdirSync(runDir, { recursive: true });
  const lock = path.join(runtime, 'daily.lock');
  if (fs.existsSync(lock)) throw new Error('Cloud daily runner lock exists; inspect the previous run before retrying');
  fs.writeFileSync(lock, startedAt);
  const env = { ...process.env };
  loadDotEnv(env, path.join(repo, '.env'));
  loadDotEnv(env, path.join(repo, 'weak-early-beta-gate', '.env'));
  const today = config.date || jstDate();
  const python = config.pythonPath;
  try {
    const branch = await requireOk('git', ['branch', '--show-current'], { cwd: repo, env, log: path.join(runDir, 'branch'), capture: true, timeoutMs: 30_000 });
    if (branch.stdout.trim() !== 'research/weak-early-beta') throw new Error(`refusing to run outside research/weak-early-beta: ${branch.stdout.trim()}`);
    const gate = await requireOk(python, ['-m', 'weak_early_beta.cli', 'is-business-day', '--date', today], { cwd: repo, env, log: path.join(runDir, 'business-day'), capture: true, timeoutMs: 60_000 });
    const businessDay = JSON.parse(gate.stdout.trim()).business_day;
    result.date = today;
    result.businessDay = businessDay;
    if (!businessDay) { result.ok = true; result.skipped = 'bank_holiday'; return; }

    const attempts = Number(config.maxFreshnessAttempts || 3);
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      await requireOk(python, ['-m', 'weak_early_beta.cli', 'daily', '--refresh-live'], { cwd: repo, env, log: path.join(runDir, `detect-${attempt}`) });
      const receipt = readJson(path.join(repo, 'weak_early_beta', 'state', 'latest_run_receipt.json'));
      result.latestSession = receipt.latest_session;
      result.selectorRows = receipt.selector_rows_latest;
      if (receipt.latest_session === today) break;
      if (attempt === attempts) throw new Error(`OHLCV freshness gate failed: expected ${today}, got ${receipt.latest_session}`);
      await waitInShortChunks(Number(config.freshnessRetryDelayMs || 300_000));
    }

    const fundamental = await run(config.nodePath, [path.join(repo, 'scripts', 'windows', 'weak-early-beta-fundamental-runner.mjs'), config.fundamentalConfigPath], { cwd: repo, env, log: path.join(runDir, 'fundamental') });
    if (fundamental.code !== 0) throw new Error('fundamental runner failed; do not notify signals before reconciliation');
    result.fundamental = JSON.parse(fundamental.stdout.trim().split(/\r?\n/).at(-1));

    await requireOk(python, ['-m', 'weak_early_beta.cli', 'report'], { cwd: repo, env, log: path.join(runDir, 'report') });
    await requireOk(config.npmPath, ['run', 'deploy'], { cwd: path.join(repo, 'weak-early-beta-gate'), env, log: path.join(runDir, 'deploy'), timeoutMs: 600_000 });
    const notify = await requireOk(python, ['-m', 'weak_early_beta.cli', 'notify-day', '--date', today], { cwd: repo, env, log: path.join(runDir, 'notify'), capture: true });
    result.notifications = JSON.parse(notify.stdout.trim());

    await requireOk('git', ['add', '-A', '--', 'reports/weak_early_beta*.html', 'weak_early_beta/state', 'weak_early_beta/fundamental_worker'], { cwd: repo, env, log: path.join(runDir, 'git-add'), timeoutMs: 60_000 });
    const staged = await run('git', ['diff', '--cached', '--quiet'], { cwd: repo, env, log: path.join(runDir, 'git-diff'), timeoutMs: 60_000 });
    if (staged.code === 1) {
      await requireOk('git', ['commit', '-m', `chore: refresh Cloud beta ${today} [skip ci]`], { cwd: repo, env, log: path.join(runDir, 'git-commit'), timeoutMs: 120_000 });
      await requireOk('git', ['push', 'origin', 'research/weak-early-beta'], { cwd: repo, env, log: path.join(runDir, 'git-push'), timeoutMs: 300_000 });
      result.committed = true;
    } else if (staged.code === 0) result.committed = false;
    else throw new Error('git diff --cached failed');
    result.ok = true;
  } catch (error) {
    result.error = error.message;
    process.exitCode = 1;
  } finally {
    result.completedAt = new Date().toISOString();
    writeJson(resultPath, result);
    if (fs.existsSync(lock)) fs.rmSync(lock);
    console.log(JSON.stringify(result));
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('usage: node weak-early-beta-daily-runner.mjs <config.json>');
  await main(process.argv[2]);
}
