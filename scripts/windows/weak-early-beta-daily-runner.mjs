import { runNewAFundamentalStage } from './new-a-fundamental-stage.mjs';
import { delayedBridge } from './delayed-run-bridge.mjs';
import { continuationForRunner, consumeAdmissionContinuation, beginAdmissionExecution } from './native-admission-continuation.mjs';
import fs from 'node:fs';
import { StringDecoder } from 'node:string_decoder';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createHash, randomBytes, randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';
import { cleanEnvironment, codexInvocation, FUNDAMENTAL_MODEL, FUNDAMENTAL_REASONING_EFFORT } from './weak-early-beta-fundamental-runner.mjs';
import { checkpointJpxRefresh } from './weak-early-beta-jpx-checkout.mjs';
import { networkFailureDetail, waitForNetworkCapacity } from './weak-early-beta-network-guard.mjs';
import { atomicJson, appendEvent, recoveryPlan, verifiedDetectionCache } from './weak-early-beta-run-journal.mjs';
import { verifyPreflightReconciliation, consumePreflightReconciliation } from './preflight-reconciliation.mjs';
import taskRoute from './new-a-task-route.cjs';
const { newATaskPlan } = taskRoute;

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
  atomicJson(file, value);
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
    'jpx_restricted_symbols_latest.json', 'latest_prices.json', 'latest_run_receipt.json', 'metrics.csv', 'monthly_metrics.csv']
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
    const stdoutDecoder = new StringDecoder('utf8');
    const stderrDecoder = new StringDecoder('utf8');
    atomicJson(`${log}.process.json`, { identity: 'CLOUD_CHILD_PROCESS_V1', parentPid: process.pid, executable: path.basename(exe), startedAt: new Date().toISOString(), status: 'planned' });
    const child = spawn(exe, args, { cwd, env, windowsHide: true, stdio: capture ? ['ignore', 'pipe', 'pipe'] : ['ignore', 'pipe', 'pipe'] });
    atomicJson(`${log}.process.json`, { identity: 'CLOUD_CHILD_PROCESS_V1', pid: child.pid || null, parentPid: process.pid, executable: path.basename(exe), startedAt: new Date().toISOString(), status: 'running' });
    child.stdout.on('data', chunk => {
      stdout += stdoutDecoder.write(chunk);
      fs.appendFileSync(`${log}.stdout`, chunk);
    });
    child.stderr.on('data', chunk => {
      stderr += stderrDecoder.write(chunk);
      fs.appendFileSync(`${log}.stderr`, chunk);
    });
    const timer = setTimeout(() => {
      if (process.platform === 'win32') {
        const killer = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
        killer.on('error', () => child.kill());
      } else child.kill('SIGTERM');
      reject(new Error(`timeout: ${path.basename(log)}`));
    }, timeoutMs);
    child.on('error', error => { clearTimeout(timer); atomicJson(`${log}.process.json`, { identity: 'CLOUD_CHILD_PROCESS_V1', pid: child.pid || null, completedAt: new Date().toISOString(), status: 'spawn_failed', error: error.code || 'unknown' }); reject(error); });
    child.on('close', code => {
      clearTimeout(timer);
      atomicJson(`${log}.process.json`, { identity: 'CLOUD_CHILD_PROCESS_V1', pid: child.pid || null, completedAt: new Date().toISOString(), status: 'exited', code });
      resolve({ code, stdout: stdout + stdoutDecoder.end(), stderr: stderr + stderrDecoder.end() });
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

async function verifyAcceptedWorker(release, head, fetchImpl = fetch) {
  const hex = /^[a-f0-9]{64}$/;
  const versionId = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
  if (release?.schema !== 'NEW_A_ORDINARY_RUNTIME_RELEASE_V1' ||
      !/^[a-f0-9]{40}$/.test(head) || release.source_commit !== head ||
      release.worker !== 'tentei-kyokuchi-cloud' || release.database !== 'tentei-cloud-settings' ||
      !versionId.test(release.version_id) || !hex.test(release.activation_sha256) ||
      !hex.test(release.build_input_sha256) || !hex.test(release.policy_sha256) ||
      !/^cloud-deploy-[A-Za-z0-9._-]{1,100}$/.test(release.tag) ||
      !Number.isSafeInteger(release.ci_run_id) || release.ci_run_id <= 0) {
    throw new Error('Completed Cloud approval has no exact Worker and build identity');
  }
  const nonce = randomBytes(32).toString('hex');
  const url = `${CLOUD_ORIGIN}/healthz?new_a_probe=${nonce}`;
  const response = await fetchImpl(url, {
    redirect: 'error', headers: { 'Cache-Control': 'no-cache' }, signal: AbortSignal.timeout(30_000),
  });
  if (response.status !== 200 || response.url !== url ||
      !response.headers.get('cache-control')?.includes('no-store')) {
    throw new Error('Approved Cloud Worker normal readback unavailable');
  }
  const proof = await response.json();
  if (proof?.schema !== 'NEW_A_OPERATIONAL_READBACK_V1' || proof.nonce !== nonce ||
      proof.source_commit !== head || proof.build_input_sha256 !== release.build_input_sha256 ||
      proof.target?.worker !== release.worker || proof.target?.database !== release.database ||
      proof.version?.id !== release.version_id || proof.version?.tag !== head ||
      typeof proof.version?.timestamp !== 'string' || !Number.isFinite(Date.parse(proof.version.timestamp)) ||
      proof.policy_sha256 !== release.policy_sha256 || !hex.test(proof.d1_active_sha256) ||
      proof.owner_http_observed !== false || proof.authentication_probe !== false || proof.d1_writes !== 0) {
    throw new Error('Approved Cloud Worker version, build or policy drifted');
  }
  const identity = ['NEW_A_OPERATIONAL_CHALLENGE_V1', nonce, release.worker, release.database,
    release.version_id, head, proof.version.timestamp, head, release.build_input_sha256];
  const challenge = (kind, sha) => createHash('sha256').update(JSON.stringify([...identity, kind, sha])).digest('hex');
  if (proof.policy_challenge_sha256 !== challenge('policy', proof.policy_sha256) ||
      proof.d1_challenge_sha256 !== challenge('d1-active', proof.d1_active_sha256)) {
    throw new Error('Approved Cloud Worker readback challenge mismatch');
  }
  return { origin: CLOUD_ORIGIN, sourceCommit: head, versionId: release.version_id,
    buildInputSha256: release.build_input_sha256, observedAt: new Date().toISOString() };
}

function assertNotificationReceipt(receipt, date, dryRun) {
  const hasLogicalEvents = receipt?.signal_notifications > 0 || receipt?.completion_notifications > 0;
  if (receipt?.date !== date || receipt.dry_run !== dryRun ||
      !['signal_notifications', 'completion_notifications'].every(key => Number.isInteger(receipt[key]) && receipt[key] >= 0) ||
      receipt.pending_discord_messages !== Number(dryRun && hasLogicalEvents) ||
      receipt.external_sends !== Number(!dryRun && hasLogicalEvents)) {
    throw new Error('invalid Cloud notification receipt; reconcile saved receipts before retrying');
  }
}

async function reconcileNotifications({ date, preview, send, onProgress = () => {} }) {
  const before = await preview('preview');
  assertNotificationReceipt(before, date, true);
  await onProgress({ phase: 'preview', receipt: before });
  const hasPending = before.pending_discord_messages === 1;
  const notifications = hasPending ? await send() : {
    date, signal_notifications: 0, completion_notifications: 0, pending_discord_messages: 0, external_sends: 0,
    dry_run: false, skipped: 'no_pending_results',
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

async function main(configFile, { resumeReceipt = null, reconciliationFile = null, reconciliationInvocation = null, delayedClaimFile = null, admissionContinuationFile = null, continuationInvocation = null } = {}) {
  if(Boolean(admissionContinuationFile)!==Boolean(continuationInvocation))throw Error('Missing native admission continuation invocation');
  if(admissionContinuationFile&&(resumeReceipt||reconciliationFile||delayedClaimFile||!continuationInvocation))throw Error('Distinct native admission continuation invocation required');
  if (delayedClaimFile && (resumeReceipt || reconciliationFile)) throw new Error('Delayed recovery cannot mix ordinary recovery');
  if (reconciliationFile && (resumeReceipt || !reconciliationInvocation)) throw new Error('Distinct task-entry reconciliation invocation required');
  const config = loadDailyConfig(configFile);
  const repo = path.resolve(config.repoPath);
  const runtime = path.resolve(config.runtimeDir);
  const continuation=admissionContinuationFile?continuationForRunner({repo,runtime,file:admissionContinuationFile}):null;
  if(continuation)resumeReceipt=continuation.record.proof.original_input;
  const startedAt = new Date().toISOString();
  const runDir = path.join(runtime, `daily-${startedAt.replace(/[:.]/g, '-')}`);
  const resultPath = path.join(runtime, 'daily-latest.json');
  const terminalPath = path.join(runDir, 'result.json');
  const result = { identity: 'WEAK_EARLY_CLOUD_DAILY_V1', startedAt, pid: process.pid, ok: false };
  const prior = resumeReceipt ? readJson(resumeReceipt) : null;
  if (prior) {
    const resolved = fs.realpathSync(resumeReceipt);
    if (path.dirname(resolved) !== fs.realpathSync(runtime) || !path.basename(resolved).startsWith('recovery-input-')) throw new Error('Recovery receipt must be an immutable task-entry runtime receipt');
    const latest = readJson(resultPath);
    if (!continuation && !isDeepStrictEqual(prior, latest)) throw new Error('Recovery receipt is no longer the latest terminal run; reconcile first');
  }
  fs.mkdirSync(runDir, { recursive: true });
  const lock = path.join(runtime, 'daily.lock');
  let ownsLock = false;
  let preservePriorCompletion = false;
  let reconciliationAccepted = false;
  let approvedWorkerReadbackFailed = false;
  const env = { ...process.env };
  loadDotEnv(env, path.join(repo, '.env'));
  loadDotEnv(env, path.join(repo, 'weak-early-beta-gate', '.env'));
  const executionDate=jstDate();
  const nativeDelayed=continuation&&(continuation.record.execution_date||continuation.record.date)!==continuation.record.date;
  const delayedPlan=delayedClaimFile?delayedBridge(config,'inspect-claim',delayedClaimFile):nativeDelayed?{target_date:continuation.record.date,execution_date:continuation.record.execution_date,original_run_id:continuation.record.proof.original_run_id}:null;
  if(delayedPlan && (delayedPlan.execution_date!==executionDate || (config.date && config.date!==delayedPlan.target_date))) throw new Error('Delayed actual execution or configured date mismatch');
  const today = delayedPlan?.target_date || config.date || executionDate;
  if (!delayedPlan && today !== executionDate) throw new Error('Cloud daily cannot replay a different JST date');
  if (prior && recoveryPlan(prior, today).action !== 'resume-detection') throw new Error('Only a terminal same-day detection failure may resume automatically');
  if (prior) result.originalRunId = prior.originalRunId || prior.startedAt;
  result.date = today;
  if(delayedPlan) Object.assign(result,{executionDate,observationKind:'DELAYED_SCHEDULED_OBSERVATION',originalRunId:delayedPlan.original_run_id,delayedClaim:delayedPlan.claim});
  atomicJson(path.join(runDir, 'invoked.json'), { ...result, identity: 'CLOUD_RUNNER_INVOKED_V1' });
  const python = config.pythonPath;
  const activationFile = path.join(repo, '.cache/weak_early_beta/new-a-private/activation.json');
  const inspectApprovedRelease = async (label) => {
    try {
      const inspection = await requireOk(python, ['-B', '-m', 'weak_early_beta.new_a.continuing_transition', 'inspect-worker'],
        { cwd: repo, env, log: path.join(runDir, label), capture: true, timeoutMs: 60_000 });
      return JSON.parse(inspection.stdout.trim());
    } catch (error) {
      approvedWorkerReadbackFailed = true;
      throw error;
    }
  };
  const checkApprovedWorker = async (release, head, label, recheck = true) => {
    try {
      if (recheck && !isDeepStrictEqual(await inspectApprovedRelease(label), release)) {
        throw new Error('Ordinary Cloud approval changed during the run');
      }
      return await verifyAcceptedWorker(release, head);
    } catch (error) {
      approvedWorkerReadbackFailed = true;
      throw error;
    }
  };
  let stage = 'lock';
  let commandNumber = 0;
  const saveProgress = (nextStage, extra = {}) => {
    if (ownsLock && (!fs.existsSync(lock) || fs.readFileSync(lock, 'utf8') !== startedAt)) {
      throw new Error('Cloud daily lock ownership changed; reconcile the active run');
    }
    stage = nextStage;
    Object.assign(result, extra, { stage, progressAt: new Date().toISOString() });
    writeJson(path.join(runDir, 'result.json'), result);
    if (ownsLock) writeJson(resultPath, result);
    appendEvent(path.join(runDir, 'progress.jsonl'), { stage, ...extra, at: result.progressAt });
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
    let delayedExecuting=null;
    if(delayedPlan&&!nativeDelayed) { delayedExecuting=delayedBridge(config,'begin',delayedClaimFile,['--root-pid',String(process.pid),'--started-at',startedAt]);result.delayedRecovery=delayedExecuting; }
    if (reconciliationFile) preservePriorCompletion = true;
    if (!delayedPlan && fs.existsSync(resultPath)) {
      const saved = readJson(resultPath); let plan = newATaskPlan("cloud-2", today, saved, recoveryPlan);
      if (reconciliationFile) {
        if (plan.action !== 'reconcile') throw new Error('Only unresolved preflight may use reconciliation');
        const head = (await git(['rev-parse', 'HEAD'])).stdout.trim();
        const verified = verifyPreflightReconciliation({repo,runtime,date:today,head,prior:saved,file:reconciliationFile});
        result.preflightReconciliation = consumePreflightReconciliation(runtime,verified,reconciliationInvocation,startedAt);
        result.originalRunId = saved.startedAt;
        reconciliationAccepted = true; preservePriorCompletion = false;
        plan = {action:'none'};
      }
      if (saved.date === today && plan.action === "complete") { preservePriorCompletion = true; Object.assign(result, { ok: true, skippedAlreadyCompleted: true, new_a: saved.new_a }); return; }
      if (saved.date === today && ["observe", "reconcile"].includes(plan.action)) { preservePriorCompletion = true; throw new Error("Same-day New A receipt requires reconciliation"); }
      if (saved.date === today && plan.action === "resume-detection" && !prior) { preservePriorCompletion = true; throw new Error("Detection recovery requires the immutable task-entry receipt"); }
    } else if (reconciliationFile) throw new Error('Original preflight record missing');
    for (const other of ['exit-reminder-runner.lock', 'exit-reminder.lock']) {
      if (fs.existsSync(path.join(repo, '.cache', 'weak_early_beta', other))) throw new Error('another Cloud reminder lock exists');
    }
    if(continuation){result.nativeAdmissionContinuation=consumeAdmissionContinuation(runtime,continuation,continuationInvocation,startedAt,process.pid);if(nativeDelayed){delayedExecuting=beginAdmissionExecution(config,result.nativeAdmissionContinuation,startedAt,process.pid,env);result.delayedRecovery=delayedExecuting;}}
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
      expectedDate: executionDate,
      timeoutMs: Number(config.networkWaitTimeoutMs ?? 900_000),
      pollMs: Number(config.networkPollMs ?? 30_000),
      onProgress: progress => saveProgress('network-preflight', { networkPreflight: progress }),
    });
    saveProgress('preflight');
    result.startCommit = await requireRemoteHead(git);
    result.fundamentals = []; result.fundamental = { ok: true, status: 'NOT_REQUESTED', imported: 0, posted: 0 };
    if (readJson(path.join(repo, 'weak-early-beta-gate', 'wrangler.jsonc')).name !== 'tentei-kyokuchi-cloud') throw new Error('unexpected Cloud Worker target');
    const checkCommand = npmInvocation(config, 'check');
    const ghPath = config.ghPath || (process.platform === 'win32' ? 'C:\\Program Files\\GitHub CLI\\gh.exe' : 'gh');
    await requireOk(ghPath, ['auth', 'status', '--hostname', 'github.com'],
      { cwd: repo, env, log: path.join(runDir, 'gh-preflight'), capture: true, timeoutMs: 30_000 });
    const previous = await requireOk(ghPath, ['run', 'list', '--repo', GITHUB_REPOSITORY, '--workflow', DEPLOY_WORKFLOW,
      '--status', 'success', '--limit', '1', '--json', 'databaseId,headSha,headBranch,status,conclusion,url'],
    { cwd: repo, env, log: path.join(runDir, 'previous-release'), capture: true, timeoutMs: 60_000 });
    result.previousSuccessfulDeployment = JSON.parse(previous.stdout.trim())[0] || null;
    const initialActivation = fs.existsSync(activationFile) ? readJson(activationFile) : {};
    const approvedRelease = initialActivation.owner_acceptance?.application_id && !initialActivation.operational_admission
      ? await inspectApprovedRelease('approved-release-before-detection') : null;
    if (approvedRelease !== null) {
      if (delayedPlan) throw new Error('Ordinary Cloud approval cannot be used for a delayed continuation');
      saveProgress('approved-worker-preflight');
      result.approvedWorkerPreflight = await checkApprovedWorker(
        approvedRelease, result.startCommit, 'approved-release-before-detection', false);
    }
    if (!prior && !delayedPlan) await sendSystemLog('started');
    saveProgress('new-a-preflight');
    result.new_a = { strategy: 'A_BASE', entry: 'new-a-verified-daily-v1', owner_publication_verified: false };


    const regularAnalysis = !delayedPlan && today === executionDate;
    if (regularAnalysis && config.fundamentalConfigPath) {
      saveProgress('model-preflight');
      await probeFundamentalModel(config, runDir, env);
    }
    saveProgress('detection');
    const cacheRecovery = prior ? await verifiedDetectionCache(repo, today) : null;
    if (cacheRecovery) saveProgress('detection', { recoveryCache: cacheRecovery });
    let nativeRecovery = null;
    if (prior) {
      const inspected = await requireOk(python, ['-m', 'weak_early_beta.new_a.native_recovery', repo, runtime,
        resumeReceipt, today, cacheRecovery.sha256, startedAt, String(process.pid)], {
        cwd: repo, env, log: path.join(runDir, 'native-source-recovery'), capture: true,
      });
      nativeRecovery = JSON.parse(inspected.stdout.trim());
      if (nativeRecovery) saveProgress('detection', { nativeSourceRecovery: nativeRecovery });
    }
    const attempts = prior || delayedPlan ? 1 : Number(config.maxFreshnessAttempts || 3);
    if (!Number.isInteger(attempts) || attempts < 1 || attempts > 3) throw new Error('invalid bounded OHLCV freshness attempts');
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      const acquisitionDirectory = path.join(runDir, `acquisition-${attempt}`);
      result.acquisitionEvidence ??= [];
      result.acquisitionEvidence.push(delayedPlan ? {attempt,recovery:'verified-retained-parts',originalRunId:delayedPlan.original_run_id} : nativeRecovery ? {attempt,recovery:'verified-native-source-parts',...nativeRecovery} : prior ? { attempt, recovery: 'verified-cache-no-download', sourceSha256: cacheRecovery.sha256 } : { attempt, directory: acquisitionDirectory });
      saveProgress('detection', { acquisitionEvidence: result.acquisitionEvidence });
      const delayedFile=delayedExecuting?path.resolve(repo,delayedExecuting.path):null;
      const replayDirectory=delayedFile?path.join(path.dirname(delayedFile),'replay-acquisition'):null;
      await requireOk(python, ['-m', 'weak_early_beta.cli', 'daily', '--strategy', 'new-a', ...(delayedPlan?['--as-of',today,'--retained-acquisition',replayDirectory,'--delayed-recovery',delayedFile]:nativeRecovery?['--as-of',today,'--retained-acquisition',nativeRecovery.directory]:prior?[]:['--refresh-live'])], {
        cwd: repo, env: { ...env, PYTHONFAULTHANDLER: '1', CLOUD_DAILY_ACQUISITION_DIR: acquisitionDirectory }, log: path.join(runDir, `detect-${attempt}`),
      });
      const receipt = readJson(path.join(repo, '.cache', 'weak_early_beta', 'new-a-private', 'latest-run.json'));
      if (receipt.strategy !== 'A_BASE' || receipt.entry !== 'new-a-verified-daily-v1') throw new Error('unexpected New A daily receipt');
      if (receipt.latest_session === today && (receipt.dry_run === true || receipt.detection_executed !== true)) throw new Error('isolated or unexecuted receipt cannot complete a live New A day');
      result.latestSession = receipt.latest_session;
      result.selectorRows = receipt.selector_rows_latest;
      if (receipt.latest_session === today) break;
      if (attempt === attempts) throw new Error(`OHLCV freshness gate failed: expected ${today}, got ${receipt.latest_session}`);
      await waitInShortChunks(Number(config.freshnessRetryDelayMs || 300_000));
    }
    if (approvedRelease !== null) {
      saveProgress('approved-worker-after-detection');
      await checkApprovedWorker(approvedRelease, result.startCommit, 'approved-release-after-detection');
    }
    await sendSystemLog('detected', ['--count', String(result.selectorRows)]);
    if (regularAnalysis) {
      saveProgress('fundamental');
      result.fundamental = await runNewAFundamentalStage({ config, repo, runtime, today, startedAt, runDir, env,
        runStep: requireOk, expectedCount: result.selectorRows });
    }


    saveProgress('report');
    await requireOk(python, ['-m', 'weak_early_beta.cli', 'report', '--strategy', 'new-a'], { cwd: repo, env, log: path.join(runDir, 'report') });
    saveProgress('canonical-input');
    await buildCanonicalInput('canonical-before-deploy');
    saveProgress('gate-check');
    await requireOk(checkCommand.exe, checkCommand.args, { cwd: path.join(repo, 'weak-early-beta-gate'), env,
      log: path.join(runDir, 'gate-check'), timeoutMs: 600_000 });
    saveProgress('code-only-pre-deploy');
    await requireBranch();
    const clean = await git(['status', '--porcelain=v1', '--untracked-files=all']);
    if (clean.stdout.trim()) throw new Error('New A refuses any generated commit; reconcile local changes');
    result.generatedCommit = null; result.generatedFilesSent = 0;
    const headSha = await requireRemoteHead(git);
    const activation = fs.existsSync(activationFile)?readJson(activationFile):{};
    if (approvedRelease !== null) {
      result.deployment = { tag: approvedRelease.tag, headSha, workflow: DEPLOY_WORKFLOW,
        worker: approvedRelease.worker, versionId: approvedRelease.version_id,
        run: { databaseId: approvedRelease.ci_run_id, status: 'completed', conclusion: 'success' },
        reusedApprovedCodeOnly: true };
    } else if (activation.operational_admission) {
      if (!nativeDelayed || today !== '2026-11-17' || executionDate !== '2026-11-18') throw Error('Finite predeployed continuity is restricted to the approved Nov17 native continuation');
      const proofResult = await requireOk(python,['-B','-m','weak_early_beta.new_a.operational_admission','inspect'],{cwd:repo,env,log:path.join(runDir,'finite-predeployed-readback'),capture:true,timeoutMs:300000});
      const proof=JSON.parse(proofResult.stdout.trim());
      if(proof.schema!=='NEW_A_FINITE_OPERATIONAL_READY_V1'||proof.source_commit!==headSha||proof.target_date!==today||proof.owner_http_observed!==false||proof.ci.conclusion!=='success'||proof.ci.source_commit!==headSha)throw Error('Finite predeployed Worker proof differs');
      result.deployment={tag:proof.ci.tag,headSha,workflow:DEPLOY_WORKFLOW,worker:'tentei-kyokuchi-cloud',run:{databaseId:proof.ci.run_id,status:'completed',conclusion:'success'},reusedPredeployedCodeOnly:true,versionId:proof.ci.version_id,operationalObservation:proof.observation};
      saveProgress('finite-predeployed-verification');
    } else {
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
    }
    saveProgress('live-verification');
    result.deployment.live = await verifyLiveWorker({});
    if (approvedRelease !== null) {
      result.deployment.approvedWorkerReadback = await checkApprovedWorker(
        approvedRelease, headSha, 'approved-release-before-publication');
    }
    saveProgress('private-data-publication');
    await requireOk(python, ['-m', 'weak_early_beta.new_a.cli', 'publish', '--remote'], { cwd: repo, env, log: path.join(runDir, 'new-a-publish'), capture: true });
    const published = readJson(path.join(repo, '.cache', 'weak_early_beta', 'new-a-private', 'latest-publication.json'));
    const detected = readJson(path.join(repo, '.cache', 'weak_early_beta', 'new-a-private', 'latest-run.json'));
    const operational = published.operational_gate_continuity_verified === true && published.existing_owner_gate_verified === false && published.owner_http_observed === false && isDeepStrictEqual(published.operational_admission,activation.operational_admission);
    if (published.published !== true || published.active_readback_verified !== true || (published.existing_owner_gate_verified !== true && !operational) || published.snapshot_sha256 !== detected.snapshot_sha256 || published.source_version !== detected.source_version) throw new Error('New A publication readback mismatch');
    Object.assign(result.new_a, { owner_publication_verified: !operational, ...(operational?{operational_publication_verified:true,operational_scope:'FINITE_NOV17_NATIVE_ONCE',owner_http_observed:false}:{}), snapshot_sha256: published.snapshot_sha256, source_version: published.source_version, dataset_id: published.dataset_id });
    saveProgress('notification');
    await reconcileNotifications({ date: today,
      preview: async phase => {
        const attempt = await requireOk(python, ['-m', 'weak_early_beta.new_a.cli', 'notify', '--date', today, '--dry-run'],
          { cwd: repo, env, log: path.join(runDir, `notify-${phase}`), capture: true });
        return JSON.parse(attempt.stdout.trim());
      },
      send: async () => {
        if (approvedRelease !== null) {
          await checkApprovedWorker(approvedRelease, headSha, 'approved-release-before-notification');
        }
        const attempt = await requireOk(python, ['-m', 'weak_early_beta.new_a.cli', 'notify', '--date', today],
          { cwd: repo, env, log: path.join(runDir, 'notify'), capture: true });
        return JSON.parse(attempt.stdout.trim());
      },
      onProgress: ({ phase, receipt }) => {
        const key = { preview: 'notificationPreview', sent: 'notifications', reconcile: 'notificationReconciliation' }[phase];
        saveProgress('notification', { [key]: receipt });
      },
    });
    // New-A outbox receipts remain private; never stage notification or price data in Git.

    result.ok = true;
  } catch (error) {
    result.error = error.message;
    if (error.failureType) result.failureType = error.failureType;
    result.stage = stage;
    if (ownsLock && stage === 'detection') result.privateSourceCacheRetained = true;
    if (!approvedWorkerReadbackFailed && (!reconciliationFile || reconciliationAccepted)) {
      await sendSystemLog('error', ['--stage', stage, '--detail', error.message]);
    }
    process.exitCode = 1;
  } finally {
    result.completedAt = new Date().toISOString();
    writeJson(terminalPath, result);
    if (ownsLock && !preservePriorCompletion) writeJson(resultPath, result);
    const stillOwnsLock = () => ownsLock && fs.existsSync(lock) && fs.readFileSync(lock, 'utf8') === startedAt;
    try {
      const noticeConfig = path.join(path.dirname(activationFile), 'owner-notice-host.json');
      if (result.ok && result.latestSession === today && result.new_a?.owner_publication_verified === true &&
          result.deployment?.reusedApprovedCodeOnly === true && !preservePriorCompletion && !prior &&
          !continuation && !delayedPlan && !reconciliationFile && fs.existsSync(noticeConfig) && stillOwnsLock()) {
        const noticePath = path.join(runDir, 'owner-notices-staging.json');
        const terminalHash = () => createHash('sha256').update(fs.readFileSync(terminalPath)).digest('hex');
        const receipt = { identity: 'CLOUD_OWNER_NOTICE_STAGING_V1', date: today, startedAt,
          resultSha256: terminalHash(), status: 'staging', deliveryConfirmed: false };
        writeJson(noticePath, receipt);
        try {
          const child = await requireOk(python, ['-B', '-m', 'weak_early_beta.new_a.owner_notice_host',
            '--after-publication', terminalPath], {
            cwd: repo, env, log: path.join(runDir, 'owner-notice-host'), capture: true, timeoutMs: 300_000,
          });
          const staged = JSON.parse(child.stdout.trim());
          const summarize = (slot, kind) => {
            const statuses = ['staged', 'no-notices', 'held', 'bank_non_business_day', 'bank_calendar_unavailable',
              'outside_reminder_window', 'not_current_jst_day', 'current_live_publication_required',
              'previous_market_session_not_published', 'market_non_business_day', 'virtual_model_not_current'];
            const target = new Date(`${slot?.target_date}T00:00:00Z`);
            if (!statuses.includes(slot?.status) || slot.kind !== kind || !Number.isFinite(target.valueOf()) ||
                target.toISOString().slice(0, 10) !== slot.target_date ||
                !Number.isSafeInteger(slot.staged) || slot.staged < 0 || slot.staged > 1_000 ||
                (slot.status === 'staged' ? slot.staged === 0 || !/^[a-f0-9]{64}$/.test(slot.payload_sha256) : slot.staged !== 0)) {
              throw new Error('Owner notice staging readback did not match its contract');
            }
            return { status: slot.status, targetDate: slot.target_date, count: slot.staged,
              ...(slot.status === 'staged' ? { payloadSha256: slot.payload_sha256 } : {}) };
          };
          const holding = summarize(staged.holding, 'WATCH_TO_SIMULATED_HOLDING');
          const morning = summarize(staged.morning, 'EVALUATION_DAY_MORNING');
          if (staged.source_date !== today || holding.targetDate !== today || morning.targetDate <= today ||
              !stillOwnsLock() || terminalHash() !== receipt.resultSha256) throw new Error('Owner notice staging run identity changed');
          const confirmed = [holding, morning].every(slot => ['staged', 'no-notices'].includes(slot.status));
          Object.assign(receipt, { status: confirmed ? 'verified' : 'held', holding, morning });
        } catch {
          // Staging may have reached D1 before an interruption. Always reconcile first.
          receipt.status = 'reconcile-required';
        }
        writeJson(noticePath, { ...receipt, observedAt: new Date().toISOString() });
        console.error(`Cloud owner notification staging: ${receipt.status}`);
      }
    } catch {
      console.error('Cloud owner notification staging receipt unavailable; reconcile the run before retrying');
    } finally {
      if (stillOwnsLock()) fs.rmSync(lock);
      console.log(JSON.stringify(result));
    }
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('usage: node weak-early-beta-daily-runner.mjs <config.json>');
  const resumeIndex = process.argv.indexOf('--resume-detection');
  if (resumeIndex >= 0 && !process.argv[resumeIndex + 1]) throw new Error('Missing terminal receipt path');
  const reconcileIndex=process.argv.indexOf('--reconcile-preflight'),invocationIndex=process.argv.indexOf('--reconcile-invocation');
  if ((reconcileIndex>=0)!==(invocationIndex>=0) || (reconcileIndex>=0&&(!process.argv[reconcileIndex+1]||!process.argv[invocationIndex+1]))) throw Error('Missing reconciliation record or invocation');
  const delayedIndex=process.argv.indexOf('--delayed-recovery');
  if(delayedIndex>=0&&!process.argv[delayedIndex+1]) throw Error('Missing private delayed claim');
  const continuationIndex=process.argv.indexOf('--native-admission-continuation'),continuationInvocationIndex=process.argv.indexOf('--continuation-invocation');
  if((continuationIndex>=0)!==(continuationInvocationIndex>=0))throw Error('Missing native admission continuation invocation');
  await main(process.argv[2], { admissionContinuationFile:continuationIndex>=0?process.argv[continuationIndex+1]:null, continuationInvocation:continuationInvocationIndex>=0?process.argv[continuationInvocationIndex+1]:null, delayedClaimFile:delayedIndex>=0?process.argv[delayedIndex+1]:null, resumeReceipt: resumeIndex >= 0 ? process.argv[resumeIndex + 1] : null, reconciliationFile:reconcileIndex>=0?process.argv[reconcileIndex+1]:null, reconciliationInvocation:invocationIndex>=0?process.argv[invocationIndex+1]:null });
}

export { npmInvocation, probeFundamentalModel, run, parseGitStatus, assertGeneratedChanges, GENERATED_PATHS,
  queueIdentities, drainFundamentalQueue, assertHtmlImports, selectWorkflowRun, waitForTagWorkflow,
  verifyLiveWorker, verifyAcceptedWorker, commitGeneratedChanges, requireRemoteHead, assertValidatedFundamentalOutput, reconcileNotifications, loadDotEnv };
