import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';
import { cleanEnvironment, codexInvocation, FUNDAMENTAL_MODEL, FUNDAMENTAL_REASONING_EFFORT } from './weak-early-beta-fundamental-runner.mjs';
import { checkpointJpxRefresh } from './weak-early-beta-jpx-checkout.mjs';
import { networkFailureDetail, waitForNetworkCapacity } from './weak-early-beta-network-guard.mjs';

function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); }
const DEFAULT_RUNNER_REPO = fileURLToPath(new URL('../../', import.meta.url));

export function loadDailyConfig(
  configFile,
  runnerRepo = DEFAULT_RUNNER_REPO,
) {
  // Preserve existing resolution of relative config paths against cwd.
  const configPath = path.resolve(configFile);
  const config = readJson(configPath);

  if (
    typeof config?.repoPath !== 'string' ||
    config.repoPath.trim() === ''
  ) {
    throw new Error(
      `Daily runner config "${configPath}" requires a non-empty repoPath.`,
    );
  }

  // Preserve existing resolution of relative repoPath values against cwd.
  const configuredRepo = path.resolve(config.repoPath);

  let configuredReal;
  let runnerReal;

  try {
    configuredReal = fs.realpathSync.native(configuredRepo);
  } catch (cause) {
    throw new Error(
      `Daily runner config "${configPath}" repoPath cannot be resolved: ` +
        `"${configuredRepo}". Refusing to run.`,
      { cause },
    );
  }

  try {
    runnerReal = fs.realpathSync.native(path.resolve(runnerRepo));
  } catch (cause) {
    throw new Error(
      `Daily runner repository cannot be resolved: "${runnerRepo}". ` +
        'Refusing to run.',
      { cause },
    );
  }

  if (configuredReal !== runnerReal) {
    throw new Error(
      `Daily runner repository mismatch: config "${configPath}" targets ` +
        `"${configuredReal}", but this runner belongs to "${runnerReal}". ` +
        'Pass the config belonging to this runner repository. Refusing to run.',
    );
  }

  return config;
}

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
const RESEARCH_BRANCH = 'research/weak-early-beta';
const GITHUB_REPOSITORY = 'Ken5InvestmentLab/screening-bot';
const DEPLOY_WORKFLOW = 'weak-early-beta-report-deploy.yml';
const CLOUD_ORIGIN = 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
// Exact generated leaves: neither historical research inputs nor arbitrary worker output.
const GENERATED_PATHS = new Set([
  ...['latest', 'analytics', 'guide', 'balance', 'dive', 'fusion', 'shadow', 'silence']
    .flatMap(name => [`reports/weak_early_beta_${name}.html`, `reports/weak_early_beta_${name}_free.html`]),
  ...['daily_notifications.json', 'detections.csv', 'excluded_detections.csv', 'fundamental_queue.json',
    'jpx_restricted_symbols_latest.json', 'latest_run_receipt.json', 'metrics.csv', 'monthly_metrics.csv']
    .map(name => `weak_early_beta/state/${name}`),
  'weak_early_beta/fundamental_worker/out/fundamental_receipts.json',
  'weak_early_beta/fundamental_worker/out/latest_claim.json',
  'weak_early_beta/fundamental_worker/out/premium_reports.json',
  'weak_early_beta/fundamental_worker/state/premium_alert_state.json',
  'weak-early-beta-gate/src/cloud-canonical-input.generated.ts',
]);

function npmInvocation(config, script = 'check', platform = process.platform) {
  if (platform !== 'win32') {
    return { exe: config.npmPath, args: ['run', script] };
  }
  const npmCli = config.npmCliPath || (/\.js$/i.test(config.npmPath)
    ? config.npmPath : path.join(path.dirname(config.npmPath), 'node_modules', 'npm', 'bin', 'npm-cli.js'));
  if (!fs.existsSync(npmCli)) throw new Error(`Windows npm CLI not found: ${npmCli}`);
  return { exe: config.nodePath, args: [npmCli, 'run', script] };
}
async function run(exe, args, { cwd, env, log, capture = false, timeoutMs = 12_000_000 }) {
  fs.mkdirSync(path.dirname(log), { recursive: true });
  fs.writeFileSync(`${log}.stdout`, '');
  fs.writeFileSync(`${log}.stderr`, '');
  return await new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    const child = spawn(exe, args, { cwd, env, windowsHide: true, stdio: capture ? ['ignore', 'pipe', 'pipe'] : ['ignore', 'pipe', 'pipe'] });
    child.stdout.on('data', chunk => {
      stdout += chunk;
      fs.appendFileSync(`${log}.stdout`, chunk);
    });
    child.stderr.on('data', chunk => {
      stderr += chunk;
      fs.appendFileSync(`${log}.stderr`, chunk);
    });
    const timer = setTimeout(() => {
      if (process.platform === 'win32') {
        const killer = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
        killer.on('error', () => child.kill());
      } else child.kill('SIGTERM');
      reject(new Error(`timeout: ${path.basename(log)}`));
    }, timeoutMs);
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('exit', code => {
      clearTimeout(timer);
      resolve({ code, stdout, stderr });
    });
  });
}
async function requireOk(exe, args, options) {
  const result = await run(exe, args, options);
  if (result.code !== 0) {
    const detail = networkFailureDetail(result.stderr);
    throw Object.assign(new Error(`${path.basename(options.log)} failed; ${detail?.message || 'inspect bounded local logs'}`),
      detail ? { failureType: detail.failureType } : {});
  }
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

function parseGitStatus(value) {
  const fields = value.split('\0');
  const entries = [];
  for (let index = 0; index < fields.length; index += 1) {
    const field = fields[index];
    if (!field) continue;
    if (field.length < 4 || field[2] !== ' ') throw new Error('invalid git status receipt');
    const entry = { status: field.slice(0, 2), path: field.slice(3) };
    if (/[RC]/.test(entry.status)) entry.oldPath = fields[++index];
    entries.push(entry);
  }
  return entries;
}

function assertGeneratedChanges(entries, { allowStaged = false, allowedPaths = GENERATED_PATHS } = {}) {
  for (const entry of entries) {
    if (!allowedPaths.has(entry.path) || entry.oldPath || !/^(?: M|\?\?|M |A )$/.test(entry.status)) {
      throw new Error(`unexpected working tree change: ${entry.path}`);
    }
    if (!allowStaged && entry.status !== '??' && entry.status[0] !== ' ') {
      throw new Error(`pre-existing staged change: ${entry.path}`);
    }
  }
  return entries.map(entry => entry.path);
}

function queueIdentities(queue) {
  if (!Array.isArray(queue)) throw new Error('invalid forward fundamental queue');
  const identities = queue.map(item => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(item.signal_date) || !/^\d{3}[\dA-Z]$/.test(String(item.symbol))) {
      throw new Error('invalid forward fundamental queue identity');
    }
    return `${item.signal_date}|${item.symbol}`;
  });
  if (new Set(identities).size !== identities.length) throw new Error('duplicate forward fundamental queue identity');
  return identities;
}

async function drainFundamentalQueue({ readQueue, runChild, verifyImported, onProgress = () => {} }) {
  const initial = queueIdentities(await readQueue());
  const initialSet = new Set(initial);
  let remaining = initial;
  const receipts = [];
  // At least one original company must finish each child; never replay an empty/nonprogressing batch.
  for (let batch = 1; remaining.length && batch <= initial.length; batch += 1) {
    await onProgress({ batch, remaining: remaining.length, total: initial.length });
    const child = await runChild(batch);
    if (child.code !== 0) throw new Error('fundamental runner failed; reconcile retained claim before resuming');
    let receipt;
    try { receipt = JSON.parse(child.stdout.trim().split(/\r?\n/).at(-1)); }
    catch { throw new Error('invalid fundamental runner receipt'); }
    if (receipt.ok !== true || !Number.isInteger(receipt.imported) || receipt.imported <= 0 || receipt.posted !== 0) {
      throw new Error('fundamental runner did not confirm an HTML-only import');
    }
    const next = queueIdentities(await readQueue());
    if (next.some(id => !initialSet.has(id) || !remaining.includes(id)) ||
        next.length >= remaining.length || remaining.length - next.length !== receipt.imported) {
      throw new Error('fundamental queue made no matching import progress');
    }
    const finished = remaining.filter(id => !next.includes(id));
    await verifyImported(finished);
    receipts.push(receipt);
    remaining = next;
    await onProgress({ batch, remaining: next.length, total: initial.length, receipt });
  }
  if (remaining.length) throw new Error('bounded fundamental queue remains incomplete');
  return receipts;
}

function assertHtmlImports(state, identities) {
  if (Object.keys(state.claims || {}).length || Object.keys(state.failed || {}).length || (state.pendingLogEvents || []).length) {
    throw new Error('beta fundamental state remains incomplete');
  }
  for (const identity of identities) {
    const [date, symbol] = identity.split('|');
    const saved = state.completed?.[`weak-early-beta:${date}:${symbol}`];
    if (saved?.delivery !== 'html' || saved.analysisBasis !== 'analysis_start' ||
        saved.report?.auditStatus !== 'pass' || saved.report.signalDate !== date ||
        String(saved.report.symbolCode) !== symbol || typeof saved.analysisCutoff !== 'string' ||
        !Number.isFinite(Date.parse(saved.analysisCutoff)) || saved.report.analysisCutoff !== saved.analysisCutoff) {
      throw new Error(`missing verified HTML import: ${identity}`);
    }
  }
}

function selectWorkflowRun(runs, { tag, headSha }) {
  if (!Array.isArray(runs)) throw new Error('invalid deployment workflow receipt');
  const matching = runs.filter(item => item.headBranch === tag && item.headSha === headSha);
  if (matching.length > 1) throw new Error('ambiguous deployment workflow runs');
  return matching[0] || null;
}

async function waitForTagWorkflow({ tag, headSha, listRuns, wait = waitInShortChunks, now = Date.now,
  timeoutMs = 5_400_000, pollMs = 30_000, onProgress = () => {} }) {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || !Number.isFinite(pollMs) || pollMs <= 0) {
    throw new Error('invalid deployment polling bounds');
  }
  const deadline = now() + timeoutMs;
  while (now() < deadline) {
    const matching = selectWorkflowRun(await listRuns(), { tag, headSha });
    await onProgress({ tag, runId: matching?.databaseId, status: matching?.status || 'awaiting_workflow', conclusion: matching?.conclusion || null });
    if (matching?.status === 'completed') {
      if (matching.conclusion !== 'success') throw new Error(`Cloud deployment workflow ${matching.conclusion || 'failed'}; inspect run ${matching.databaseId}`);
      return matching;
    }
    const remaining = deadline - now();
    if (remaining > 0) await wait(Math.min(pollMs, remaining, 60_000));
  }
  throw new Error('Cloud deployment workflow timed out; reconcile the existing tag/run before retrying');
}

async function verifyLiveWorker({ origin = CLOUD_ORIGIN, fetchImpl = fetch }) {
  if (origin !== CLOUD_ORIGIN) throw new Error('unexpected live Cloud origin');
  const health = await fetchImpl(`${origin}/healthz`, { redirect: 'manual', signal: AbortSignal.timeout(30_000) });
  if (health.status !== 200 || (await health.text()).trim() !== 'ok') throw new Error('Cloud health check failed');
  const root = await fetchImpl(`${origin}/`, { redirect: 'manual', signal: AbortSignal.timeout(30_000) });
  const location = root.headers.get('location');
  let target;
  try { target = new URL(location, origin); } catch { /* handled below */ }
  const oauth = target?.origin === 'https://discord.com' && /^\/(?:api\/)?oauth2\/authorize$/.test(target.pathname);
  const login = target?.origin === origin && target.pathname === '/auth/login';
  if (![302, 303, 307].includes(root.status) || !location || (!oauth && !login)) throw new Error('Cloud root OAuth redirect check failed');
  await root.body?.cancel();
  return { origin, healthStatus: health.status, rootStatus: root.status, oauthRedirect: true };
}

function assertNotificationReceipt(receipt, date, dryRun) {
  if (receipt?.date !== date || receipt.dry_run !== dryRun ||
      !['signal_notifications', 'completion_notifications'].every(key => Number.isInteger(receipt[key]) && receipt[key] >= 0)) {
    throw new Error('invalid Cloud notification receipt; reconcile saved receipts before retrying');
  }
}

async function reconcileNotifications({ date, preview, send, onProgress = () => {} }) {
  const before = await preview('preview');
  assertNotificationReceipt(before, date, true);
  await onProgress({ phase: 'preview', receipt: before });
  const hasPending = before.signal_notifications + before.completion_notifications > 0;
  const notifications = hasPending ? await send() : {
    date, signal_notifications: 0, completion_notifications: 0, dry_run: false, skipped: 'no_new_symbols',
  };
  assertNotificationReceipt(notifications, date, false);
  await onProgress({ phase: 'sent', receipt: notifications });
  if (notifications.signal_notifications !== before.signal_notifications ||
      notifications.completion_notifications !== before.completion_notifications) {
    throw new Error('Cloud notification counts differ from preview; reconcile saved receipts before retrying');
  }
  const remaining = await preview('reconcile');
  assertNotificationReceipt(remaining, date, true);
  await onProgress({ phase: 'reconcile', receipt: remaining });
  if (remaining.signal_notifications || remaining.completion_notifications) {
    throw new Error('Cloud notifications remain pending after delivery; reconcile saved receipts before retrying');
  }
  return { preview: before, notifications, remaining };
}

function assertValidatedFundamentalOutput({ raw, state, receipt, env }) {
  if (!/^[a-f0-9]{64}$/.test(receipt.validatedReportSha256) ||
      createHash('sha256').update(raw).digest('hex') !== receipt.validatedReportSha256) {
    throw new Error('fundamental output differs from the validated local report receipt');
  }
  const text = raw.toString('utf8').replace(/^\uFEFF/, '');
  for (const [key, value] of Object.entries(env)) {
    if (/(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY|CREDENTIAL|WEBHOOK)/i.test(key) &&
        typeof value === 'string' && value.length >= 8 &&
        (text.includes(value) || text.includes(JSON.stringify(value).slice(1, -1)))) {
      throw new Error('fundamental output contains a configured secret; refusing generated commit');
    }
  }
  const reports = JSON.parse(text).reports;
  if (!Array.isArray(reports) || reports.length !== receipt.imported) throw new Error('fundamental output report count differs from imported receipt');
  for (const report of reports) {
    const saved = state.completed?.[report.alertId];
    if (!saved || !isDeepStrictEqual(saved.report, report)) throw new Error('fundamental output differs from the imported HTML snapshot');
  }
}

async function commitGeneratedChanges({ git, message }) {
  const entries = parseGitStatus((await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout);
  const initialPaths = assertGeneratedChanges(entries);
  if (!initialPaths.length) return { committed: false, paths: [] };
  // Compare Git-normalized contents before choosing exact staging leaves.
  // Windows CRLF/LF rewrites can appear dirty but produce no index change.
  const changed = new Set((await git(['diff', '--name-only', '-z', '--', ...initialPaths])).stdout.split('\0').filter(Boolean));
  if ([...changed].some(file => !initialPaths.includes(file))) throw new Error('unexpected normalized generated diff');
  const paths = entries.filter(entry => entry.status === '??' || changed.has(entry.path)).map(entry => entry.path);
  // Stage the exact audited leaves, including normalized no-ops, to refresh
  // Git's stat cache. Only the normalized changed set may enter the commit.
  await git(['add', '--', ...initialPaths]);
  const staged = (await git(['diff', '--cached', '--name-only', '-z'])).stdout.split('\0').filter(Boolean);
  const after = parseGitStatus((await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout);
  assertGeneratedChanges(after, { allowStaged: true });
  if (staged.length !== paths.length || staged.some(file => !paths.includes(file)) ||
      after.length !== paths.length || after.some(entry => !paths.includes(entry.path) || !/^[MA] $/.test(entry.status))) {
    throw new Error('working/staged changes changed during generated-file staging');
  }
  if (!paths.length) return { committed: false, paths: [] };
  await git(['commit', '-m', message]);
  if (parseGitStatus((await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout).length) {
    throw new Error('working tree changed during generated-file commit; refusing push');
  }
  await git(['push', 'origin', `HEAD:refs/heads/${RESEARCH_BRANCH}`]);
  return { committed: true, paths };
}

async function requireRemoteHead(git) {
  const headSha = (await git(['rev-parse', 'HEAD'])).stdout.trim();
  const remote = (await git(['ls-remote', '--exit-code', 'origin', `refs/heads/${RESEARCH_BRANCH}`])).stdout.trim();
  const match = remote.match(/^([0-9a-f]{40})\s+refs\/heads\/research\/weak-early-beta$/);
  if (!/^[0-9a-f]{40}$/.test(headSha) || !match || match[1] !== headSha) throw new Error('local HEAD is not the latest origin/research/weak-early-beta');
  return headSha;
}

async function probeFundamentalModel(config, runDir, env) {
  const fundamentalConfig = readJson(path.resolve(config.fundamentalConfigPath));
  const probeEnv = cleanEnvironment(env);
  probeEnv.CODEX_HOME = fundamentalConfig.codexHome;
  const invocation = codexInvocation(fundamentalConfig, [
    '--search', '-a', 'never', 'exec', '--ignore-user-config',
    '--cd', runDir, '--skip-git-repo-check', '--sandbox', 'read-only',
    '-m', FUNDAMENTAL_MODEL,
    '-c', `model_reasoning_effort="${FUNDAMENTAL_REASONING_EFFORT}"`,
    '-c', 'forced_login_method="chatgpt"', '--json', 'Return exactly MODEL_READY.',
  ]);
  const probe = await run(invocation.exe, invocation.args, {
    cwd: runDir,
    env: probeEnv,
    log: path.join(runDir, 'model-preflight'),
    capture: true,
    timeoutMs: 120_000,
  });
  if (probe.code !== 0 || !probe.stdout.split(/\r?\n/).some(line => {
    try { return JSON.parse(line).type === 'turn.completed'; } catch { return false; }
  })) {
    throw new Error(`${FUNDAMENTAL_MODEL} ${FUNDAMENTAL_REASONING_EFFORT} model preflight failed; inspect ${path.join(runDir, 'model-preflight.stdout')}`);
  }
}

async function main(configFile) {
  const config = loadDailyConfig(configFile);
  const repo = path.resolve(config.repoPath);
  const runtime = path.resolve(config.runtimeDir);
  const startedAt = new Date().toISOString();
  const runDir = path.join(runtime, `daily-${startedAt.replace(/[:.]/g, '-')}`);
  const resultPath = path.join(runtime, 'daily-latest.json');
  const result = { identity: 'WEAK_EARLY_CLOUD_DAILY_V1', startedAt, ok: false };
  fs.mkdirSync(runDir, { recursive: true });
  const lock = path.join(runtime, 'daily.lock');
  let ownsLock = false;
  const env = { ...process.env };
  loadDotEnv(env, path.join(repo, '.env'));
  loadDotEnv(env, path.join(repo, 'weak-early-beta-gate', '.env'));
  const today = config.date || jstDate();
  const python = config.pythonPath;
  let stage = 'lock';
  let commandNumber = 0;
  const saveProgress = (nextStage, extra = {}) => {
    if (ownsLock && (!fs.existsSync(lock) || fs.readFileSync(lock, 'utf8') !== startedAt)) {
      throw new Error('Cloud daily lock ownership changed; reconcile the active run');
    }
    stage = nextStage;
    Object.assign(result, extra, { stage, progressAt: new Date().toISOString() });
    if (ownsLock) writeJson(resultPath, result);
    fs.appendFileSync(path.join(runDir, 'progress.jsonl'), `${JSON.stringify({ stage, ...extra, at: result.progressAt })}\n`);
    console.error(`Cloud daily stage: ${stage}`);
  };
  const git = async args => requireOk('git', args, { cwd: repo, env,
    log: path.join(runDir, `git-${++commandNumber}-${args[0]}`), capture: true,
    timeoutMs: args[0] === 'push' ? 300_000 : args[0] === 'commit' ? 120_000 : 60_000 });
  const requireBranch = async () => {
    if ((await git(['branch', '--show-current'])).stdout.trim() !== RESEARCH_BRANCH) throw new Error('refusing to run outside research/weak-early-beta');
  };
  const buildCanonicalInput = async name => requireOk(python, [
    '-B', path.join(repo, 'weak-early-beta-gate', 'scripts', 'build-canonical-input.py'),
    '--output', path.join(repo, 'weak-early-beta-gate', 'src', 'cloud-canonical-input.generated.ts'),
  ], { cwd: repo, env, log: path.join(runDir, name), timeoutMs: 120_000 });
  const sendSystemLog = async (event, extra = []) => {
    try {
      const attempt = await run(python, [
        '-m', 'weak_early_beta.cli', 'system-log', '--date', today,
        '--event', event, '--run-id', startedAt, ...extra,
      ], { cwd: repo, env, log: path.join(runDir, `system-log-${event}`), capture: true, timeoutMs: 60_000 });
      if (attempt.code !== 0) throw new Error(`system-log ${event} failed`);
      result.systemLogEvents ??= [];
      result.systemLogEvents.push(event);
    } catch {
      result.systemLogErrors ??= [];
      result.systemLogErrors.push(event);
    }
  };
  try {
    try {
      fs.writeFileSync(lock, startedAt, { flag: 'wx' });
    } catch (error) {
      if (error.code === 'EEXIST') throw new Error('Cloud daily runner lock exists; inspect the previous run before retrying');
      throw error;
    }
    ownsLock = true;
    for (const other of ['exit-reminder-runner.lock', 'exit-reminder.lock']) {
      if (fs.existsSync(path.join(repo, '.cache', 'weak_early_beta', other))) throw new Error('another Cloud reminder lock exists');
    }
    saveProgress('branch');
    await requireBranch();
    stage = 'business-day';
    const gate = await requireOk(python, ['-m', 'weak_early_beta.cli', 'is-business-day', '--date', today], { cwd: repo, env, log: path.join(runDir, 'business-day'), capture: true, timeoutMs: 60_000 });
    const businessDay = JSON.parse(gate.stdout.trim()).business_day;
    result.date = today;
    result.businessDay = businessDay;
    if (!businessDay) { result.ok = true; result.skipped = 'bank_holiday'; return; }
    saveProgress('preflight');
    if (process.platform === 'win32') {
      const processCheck = await requireOk('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
        `@(Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" | Where-Object { $_.ProcessId -ne ${process.pid} -and $_.CommandLine -match 'weak-early-beta-(?:exit-reminder|daily)-runner\\.mjs' } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress`],
      { cwd: repo, env, log: path.join(runDir, 'process-preflight'), capture: true, timeoutMs: 30_000 });
      if (processCheck.stdout.trim() && !/^\[\s*\]$/.test(processCheck.stdout.trim())) throw new Error('another Cloud daily Node process exists');
    }
    if (parseGitStatus((await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout).length) {
      throw new Error('daily checkout is not clean; use a clean research clone without changing user files');
    }
    const origin = (await git(['remote', 'get-url', 'origin'])).stdout.trim();
    if (!/^(?:https:\/\/github\.com\/|git@github\.com:)Ken5InvestmentLab\/screening-bot(?:\.git)?$/i.test(origin)) throw new Error('unexpected Cloud Git origin');
    // Check local socket pressure before GitHub, model, JPX or Yahoo requests.
    // A waiting preflight owns this run's lock and never replays daily work.
    saveProgress('network-preflight');
    result.networkPreflight = await waitForNetworkCapacity({
      expectedDate: today,
      timeoutMs: Number(config.networkWaitTimeoutMs ?? 900_000),
      pollMs: Number(config.networkPollMs ?? 30_000),
      onProgress: progress => saveProgress('network-preflight', { networkPreflight: progress }),
    });
    saveProgress('preflight');
    result.startCommit = await requireRemoteHead(git);
    const fundamentalConfig = readJson(path.resolve(config.fundamentalConfigPath));
    if (path.resolve(fundamentalConfig.repoPath) !== repo) throw new Error('fundamental runner configuration points outside the daily checkout');
    const betaStatePath = path.join(repo, 'weak_early_beta', 'fundamental_worker', 'state', 'premium_alert_state.json');
    const stateBefore = readJson(betaStatePath);
    assertHtmlImports(stateBefore, []);
    if (readJson(path.join(repo, 'weak-early-beta-gate', 'wrangler.jsonc')).name !== 'tentei-kyokuchi-cloud') throw new Error('unexpected Cloud Worker target');
    const checkCommand = npmInvocation(config, 'check');
    const ghPath = config.ghPath || (process.platform === 'win32' ? 'C:\\Program Files\\GitHub CLI\\gh.exe' : 'gh');
    await requireOk(ghPath, ['auth', 'status', '--hostname', 'github.com'],
      { cwd: repo, env, log: path.join(runDir, 'gh-preflight'), capture: true, timeoutMs: 30_000 });
    const previous = await requireOk(ghPath, ['run', 'list', '--repo', GITHUB_REPOSITORY, '--workflow', DEPLOY_WORKFLOW,
      '--status', 'success', '--limit', '1', '--json', 'databaseId,headSha,headBranch,status,conclusion,url'],
    { cwd: repo, env, log: path.join(runDir, 'previous-release'), capture: true, timeoutMs: 60_000 });
    result.previousSuccessfulDeployment = JSON.parse(previous.stdout.trim())[0] || null;
    await sendSystemLog('started');
    saveProgress('model-preflight');
    await probeFundamentalModel(config, runDir, env);

    saveProgress('detection');
    const attempts = Number(config.maxFreshnessAttempts || 3);
    if (!Number.isInteger(attempts) || attempts < 1 || attempts > 3) throw new Error('invalid bounded OHLCV freshness attempts');
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      await requireOk(python, ['-m', 'weak_early_beta.cli', 'daily', '--refresh-live'], { cwd: repo, env, log: path.join(runDir, `detect-${attempt}`) });
      const receipt = readJson(path.join(repo, 'weak_early_beta', 'state', 'latest_run_receipt.json'));
      result.latestSession = receipt.latest_session;
      result.selectorRows = receipt.selector_rows_latest;
      if (receipt.latest_session === today) break;
      if (attempt === attempts) throw new Error(`OHLCV freshness gate failed: expected ${today}, got ${receipt.latest_session}`);
      await waitInShortChunks(Number(config.freshnessRetryDelayMs || 300_000));
    }
    await sendSystemLog('detected', ['--count', String(result.selectorRows)]);

    saveProgress('fundamental');
    const queuePath = path.join(repo, 'weak_early_beta', 'state', 'fundamental_queue.json');
    result.fundamentals = [];
    result.fundamentals = await drainFundamentalQueue({
      readQueue: () => readJson(queuePath),
      runChild: batch => run(config.nodePath,
        [path.join(repo, 'scripts', 'windows', 'weak-early-beta-fundamental-runner.mjs'), config.fundamentalConfigPath],
        { cwd: repo, env, log: path.join(runDir, `fundamental-${batch}`) }),
      verifyImported: identities => assertHtmlImports(readJson(betaStatePath), identities),
      onProgress: progress => {
        if (progress.receipt) result.fundamentals.push(progress.receipt);
        saveProgress('fundamental', { fundamentalProgress: { batch: progress.batch, remaining: progress.remaining, total: progress.total } });
      },
    });
    result.fundamental = result.fundamentals.at(-1) || { ok: true, imported: 0, posted: 0 };
    if (result.fundamentals.length) assertValidatedFundamentalOutput({
      raw: fs.readFileSync(path.join(repo, 'weak_early_beta', 'fundamental_worker', 'out', 'premium_reports.json')),
      state: readJson(betaStatePath), receipt: result.fundamental, env,
    });

    saveProgress('report');
    await requireOk(python, ['-m', 'weak_early_beta.cli', 'report'], { cwd: repo, env, log: path.join(runDir, 'report') });
    saveProgress('canonical-input');
    await buildCanonicalInput('canonical-before-deploy');
    saveProgress('gate-check');
    await requireOk(checkCommand.exe, checkCommand.args, { cwd: path.join(repo, 'weak-early-beta-gate'), env,
      log: path.join(runDir, 'gate-check'), timeoutMs: 600_000 });
    saveProgress('git-sync-before-deploy');
    await requireBranch();
    result.generatedCommit = await commitGeneratedChanges({ git, message: `chore: refresh Cloud beta ${today}` });
    const headSha = await requireRemoteHead(git);
    const tag = `cloud-deploy-daily-${new Date().toISOString().replace(/[-:.]/g, '')}-${headSha.slice(0, 8)}-${randomUUID().slice(0, 8)}`;
    result.deployment = { tag, headSha, workflow: DEPLOY_WORKFLOW, worker: 'tentei-kyokuchi-cloud' };
    saveProgress('deploy-tag');
    // One lightweight tag, one exact tag push. A failed/ambiguous run is reconciled manually.
    await git(['tag', tag, headSha]);
    await git(['push', 'origin', `refs/tags/${tag}:refs/tags/${tag}`]);
    saveProgress('deploy-workflow');
    result.deployment.run = await waitForTagWorkflow({ tag, headSha,
      timeoutMs: Number(config.deployWorkflowTimeoutMs ?? 5_400_000),
      pollMs: Number(config.deployPollMs ?? 30_000),
      listRuns: async () => {
        const runs = await requireOk(ghPath, ['run', 'list', '--repo', GITHUB_REPOSITORY, '--workflow', DEPLOY_WORKFLOW,
          '--limit', '50', '--json', 'databaseId,headSha,headBranch,status,conclusion,url'],
        { cwd: repo, env, log: path.join(runDir, `workflow-${++commandNumber}`), capture: true, timeoutMs: 60_000 });
        return JSON.parse(runs.stdout.trim());
      },
      onProgress: progress => saveProgress('deploy-workflow', { deploymentProgress: progress }),
    });
    saveProgress('live-verification');
    result.deployment.live = await verifyLiveWorker({});
    saveProgress('notification');
    await reconcileNotifications({ date: today,
      preview: async phase => {
        const attempt = await requireOk(python, ['-m', 'weak_early_beta.cli', 'notify-day', '--date', today, '--dry-run'],
          { cwd: repo, env, log: path.join(runDir, `notify-${phase}`), capture: true });
        return JSON.parse(attempt.stdout.trim());
      },
      send: async () => {
        const attempt = await requireOk(python, ['-m', 'weak_early_beta.cli', 'notify-day', '--date', today],
          { cwd: repo, env, log: path.join(runDir, 'notify'), capture: true });
        return JSON.parse(attempt.stdout.trim());
      },
      onProgress: ({ phase, receipt }) => {
        const key = { preview: 'notificationPreview', sent: 'notifications', reconcile: 'notificationReconciliation' }[phase];
        saveProgress('notification', { [key]: receipt });
      },
    });
    if (result.notifications.signal_notifications || result.notifications.completion_notifications) {
      // Discord receipts change the CSV byte hash without changing event economics. No second deploy.
      saveProgress('canonical-after-notification');
      await buildCanonicalInput('canonical-after-notify');
      await requireOk(config.nodePath, [path.join(repo, 'weak-early-beta-gate', 'scripts', 'verify-canonical-input.mjs')],
        { cwd: path.join(repo, 'weak-early-beta-gate'), env, log: path.join(runDir, 'canonical-after-notify-check'), timeoutMs: 60_000 });
    }
    saveProgress('git-sync-receipts');
    await requireBranch();
    result.receiptCommit = await commitGeneratedChanges({ git, message: `chore: save Cloud beta ${today} notification receipts [skip ci]` });
    result.finalCommit = await requireRemoteHead(git);
    result.committed = result.generatedCommit.committed || result.receiptCommit.committed;
    result.ok = true;
  } catch (error) {
    result.error = error.message;
    if (error.failureType) result.failureType = error.failureType;
    result.stage = stage;
    if (ownsLock && stage === 'detection') {
      try {
        result.failedJpxRefresh = await checkpointJpxRefresh({ repo, git, startedAt, startCommit: result.startCommit, date: today, checkSafety: () => {
          if (!fs.existsSync(lock) || fs.readFileSync(lock, 'utf8') !== startedAt) throw new Error('Cloud daily lock ownership changed');
          for (const other of ['exit-reminder-runner.lock', 'exit-reminder.lock']) {
            if (fs.existsSync(path.join(repo, '.cache', 'weak_early_beta', other))) throw new Error('another Cloud reminder lock exists');
          }
        } });
      } catch (cleanupError) {
        result.jpxRefreshError = cleanupError.message;
      }
    }
    await sendSystemLog('error', ['--stage', stage, '--detail', error.message]);
    process.exitCode = 1;
  } finally {
    result.completedAt = new Date().toISOString();
    writeJson(ownsLock ? resultPath : path.join(runDir, 'result.json'), result);
    if (ownsLock && fs.existsSync(lock) && fs.readFileSync(lock, 'utf8') === startedAt) fs.rmSync(lock);
    console.log(JSON.stringify(result));
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('usage: node weak-early-beta-daily-runner.mjs <config.json>');
  await main(process.argv[2]);
}

export { npmInvocation, probeFundamentalModel, run, parseGitStatus, assertGeneratedChanges, GENERATED_PATHS,
  queueIdentities, drainFundamentalQueue, assertHtmlImports, selectWorkflowRun, waitForTagWorkflow,
  verifyLiveWorker, commitGeneratedChanges, requireRemoteHead, assertValidatedFundamentalOutput, reconcileNotifications };
