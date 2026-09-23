import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SIGNAL_CHANNEL_ID = '1550876104917520505';
const FUNDAMENTAL_CHANNEL_ID = '1550876675884060702';

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`);
  fs.renameSync(temporary, file);
}

function reportsMatchClaim(reportsPath, claim) {
  if (!fs.existsSync(reportsPath)) return false;
  const reports = readJson(reportsPath).reports || [];
  const expected = new Set((claim.alerts || []).map(alert => alert.alertId));
  const actual = new Set(reports.map(report => report.alertId));
  return expected.size > 0 && expected.size === actual.size && [...expected].every(id => actual.has(id));
}

function cleanEnvironment(source) {
  const result = { ...source };
  for (const key of Object.keys(result)) {
    if (/^(OPENAI_API_KEY|CODEX_API_KEY)$/i.test(key)) delete result[key];
  }
  return result;
}

function loadDotEnv(target, file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!match || target[match[1]] !== undefined) continue;
    let value = match[2];
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    target[match[1]] = value;
  }
}

async function command(exe, args, { cwd, env, log, input = '', timeoutMs = 12_000_000 }) {
  fs.mkdirSync(path.dirname(log), { recursive: true });
  const stdout = fs.openSync(`${log}.stdout`, 'w');
  const stderr = fs.openSync(`${log}.stderr`, 'w');
  try {
    return await new Promise((resolve, reject) => {
      const child = spawn(exe, args, {
        cwd, env, windowsHide: true, stdio: ['pipe', stdout, stderr],
      });
      const timer = setTimeout(() => {
        if (process.platform === 'win32') {
          spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], {
            windowsHide: true, stdio: 'ignore',
          });
        } else child.kill('SIGTERM');
        reject(new Error('execution timeout; inspect the beta claim and Discord before retrying'));
      }, timeoutMs);
      child.on('error', error => { clearTimeout(timer); reject(error); });
      child.on('exit', code => { clearTimeout(timer); resolve(code); });
      child.stdin.on('error', () => {});
      child.stdin.end(input);
    });
  } finally {
    fs.closeSync(stdout);
    fs.closeSync(stderr);
  }
}

function assertIsolated(config) {
  const beta = path.resolve(config.repoPath, 'weak_early_beta', 'fundamental_worker');
  const production = path.resolve(config.premiumWorkerRepoPath, 'premium_worker');
  if (beta === production || beta.startsWith(`${production}${path.sep}`)) {
    throw new Error('beta worker state must not be inside the production Premium Worker directory');
  }
  if (SIGNAL_CHANNEL_ID === FUNDAMENTAL_CHANNEL_ID) {
    throw new Error('signal and fundamental Discord channels must remain separate');
  }
}

async function main(configFile) {
  const config = readJson(path.resolve(configFile));
  assertIsolated(config);
  const now = new Date().toISOString();
  const runtimeDir = path.resolve(config.runtimeDir);
  const runDir = path.join(runtimeDir, `run-${now.replace(/[:.]/g, '-')}`);
  fs.mkdirSync(runDir, { recursive: true });
  const resultPath = path.join(runtimeDir, 'latest.json');
  const result = {
    identity: 'WEAK_EARLY_FUNDAMENTAL_LUNA_XHIGH_V1',
    startedAt: now,
    ok: false,
    model: 'gpt-6-luna',
    reasoningEffort: 'xhigh',
    channelId: FUNDAMENTAL_CHANNEL_ID,
    runDir,
  };

  const env = cleanEnvironment(process.env);
  loadDotEnv(env, path.join(config.repoPath, '.env'));
  loadDotEnv(env, path.join(config.premiumWorkerRepoPath, '.env'));
  loadDotEnv(env, path.join(config.premiumWorkerRepoPath, 'premium_worker', '.env'));
  env.CODEX_HOME = config.codexHome;
  const pathKey = Object.keys(env).find(key => /^path$/i.test(key));
  const inheritedPath = pathKey ? env[pathKey] : '';
  for (const key of Object.keys(env)) if (/^path$/i.test(key)) delete env[key];
  env.PATH = `${path.dirname(config.nodePath)}${path.delimiter}${inheritedPath}`;

  const betaRoot = path.join(config.repoPath, 'weak_early_beta', 'fundamental_worker');
  const statePath = path.join(betaRoot, 'state', 'premium_alert_state.json');
  const outDir = path.join(betaRoot, 'out');
  const claimPath = path.join(outDir, 'latest_claim.json');
  const reportsPath = path.join(outDir, 'premium_reports.json');
  const receiptsPath = path.join(outDir, 'fundamental_receipts.json');
  const workerPath = path.join(config.premiumWorkerRepoPath, 'premium_worker', 'worker.mjs');
  const historicalPosterPath = path.join(config.repoPath, 'weak_early_beta', 'scripts', 'post_historical_snapshot.mjs');

  const run = async (exe, args, name, options = {}) => {
    const exit = await command(exe, args, {
      cwd: options.cwd || config.repoPath,
      env: options.env || env,
      log: path.join(runDir, name),
      input: options.input || '',
      timeoutMs: options.timeoutMs,
    });
    if (exit !== 0) throw new Error(`${name} failed; inspect bounded local logs`);
  };

  try {
    const stateBefore = fs.existsSync(statePath) ? readJson(statePath) : { claims: {} };
    let claim;
    if (Object.keys(stateBefore.claims || {}).length) {
      if (!fs.existsSync(claimPath)) throw new Error('active beta claims exist without latest_claim.json');
      claim = readJson(claimPath);
      const activeIds = new Set(Object.keys(stateBefore.claims || {}));
      const claimIds = new Set((claim.alerts || []).map(alert => alert.alertId));
      if (activeIds.size !== claimIds.size || [...activeIds].some(id => !claimIds.has(id))) {
        throw new Error('active beta claims do not match latest_claim.json');
      }
      result.resumedExistingClaim = true;
    } else {
      await run(config.pythonPath || 'py', [
        '-m', 'weak_early_beta.cli', 'prepare-fundamentals',
        '--worker-state', statePath, '--claim', claimPath,
        '--max-alerts', String(config.maxAlertsPerRun || 0),
      ], 'prepare-claim');
      claim = readJson(claimPath);
      if (fs.existsSync(reportsPath)) fs.rmSync(reportsPath);
    }
    writeJson(path.join(runDir, 'claim.json'), claim);
    result.claimed = claim.claimedCount;
    if (!claim.claimedCount) {
      result.ok = true;
      result.posted = 0;
      return;
    }

    const prompt = [
      'Weak+Early betaのclaimに含まれる検出銘柄を、現行Premium Workerと同じ会社固有の品質でファンダ分析してください。$premium-fundamental-snapshot を使います。',
      `不変claimは ${path.join(runDir, 'claim.json')} です。ここにあるalertIdだけを対象にしてください。`,
      `必ず ${path.join(config.premiumWorkerRepoPath, 'premium_worker', 'AUTOMATION_PROMPT.md')} と ${path.join(config.premiumWorkerRepoPath, 'premium_worker', 'FUNDAMENTAL_EXAMPLES.md')} を全文読み、skillのreferences/report_quality.mdも読んでください。`,
      '各銘柄の分析基準時点はclaimのreceivedAt（検出日の日本時間16:15）です。その時点より後に公表されたIR・適時開示・ニュース・決算資料は、検索で見つかっても絶対に使わないでください。各社の公式IR、IRBANKまたはTDnet相当の開示一覧を基準時点まで確認し、選んだ一次資料の本文を読んでください。検索スニペットだけで作らないでください。',
      'レポート本文と開示リンクには、採用した資料の公表日がsignal_date以前であることが分かるようにし、基準時点後の資料を参照していないことを守ってください。',
      '売買推奨、目標株価、追加スコアは禁止。現行契約の全7フィールドとSourcesを満たしてください。',
      `最終JSONは ${reportsPath} だけに書き込んでください。Discord投稿、worker state、Sheets、Git、workflow、ソースコードは変更しないでください。`,
      '報告は有界に保ち、出力JSON作成後は日本語で簡潔に完了を報告してください。',
    ].join('\n\n');
    fs.writeFileSync(path.join(runDir, 'prompt.txt'), prompt);
    if (!reportsMatchClaim(reportsPath, claim)) {
      const analysisExit = await command(config.nodePath, [
        config.cliJs, '--search', '-a', 'never', 'exec', '--ignore-user-config',
        '--cd', config.premiumWorkerRepoPath, '--skip-git-repo-check',
        '--sandbox', 'danger-full-access', '-m', 'gpt-6-luna',
        '-c', 'model_reasoning_effort="xhigh"',
        '-c', 'forced_login_method="chatgpt"', '--json',
        '-o', path.join(runDir, 'codex.final.txt'), '-',
      ], {
        cwd: config.premiumWorkerRepoPath,
        env,
        log: path.join(runDir, 'codex'),
        input: prompt,
        timeoutMs: 12_000_000,
      });
      result.analysisExit = analysisExit;
      if (analysisExit !== 0 && !reportsMatchClaim(reportsPath, claim)) {
        throw new Error('codex failed before producing a claim-matched report; inspect bounded local logs');
      }
      if (analysisExit !== 0) result.recoveredValidatedOutputAfterAnalysisLimit = true;
    } else {
      result.reusedClaimMatchedReport = true;
    }
    if (!fs.existsSync(reportsPath)) throw new Error('Codex completed without premium_reports.json');

    const reportPayload = readJson(reportsPath);
    const historicalSnapshot = (reportPayload.reports || reportPayload).every(report =>
      /^\d{4}-\d{2}-\d{2}T16:15:00\+09:00$/.test(String(report.analysisCutoff || ''))
    );
    if (historicalSnapshot) {
      // Historical snapshots are intentionally posted by the beta-only sidecar:
      // the production worker rejects any report that omits a later disclosure,
      // while this sidecar enforces signal_date 23:59 JST as the evidence cutoff.
      await run(config.nodePath, [historicalPosterPath, '--input', reportsPath, '--state', statePath], 'historical-post', {
        cwd: config.repoPath, env, timeoutMs: 180_000,
      });
    } else {
      const postEnv = { ...env };
      postEnv.PREMIUM_STATE_PATH = statePath;
      postEnv.PREMIUM_OUT_DIR = outDir;
      postEnv.DISCORD_PREMIUM_WEBHOOK_URL = env.WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL || '';
      postEnv.DISCORD_PREMIUM_USERNAME = '天底極致 -Cloud- | ファンダ分析';
      postEnv.DISCORD_PREMIUM_CHANNEL_ID = FUNDAMENTAL_CHANNEL_ID;
      postEnv.PREMIUM_LOG_SPREADSHEET_ID = '';
      // Webhook-only keeps the beta post independent from the production bot and /scan button.
      delete postEnv.DISCORD_PREMIUM_BOT_TOKEN;
      delete postEnv.DISCORD_BOT_TOKEN;
      delete postEnv.DISCORD_TOKEN;
      await run(config.nodePath, [workerPath, 'post', '--input', reportsPath, '--dry-run'], 'validate', {
        cwd: config.premiumWorkerRepoPath, env: postEnv, timeoutMs: 180_000,
      });
      if (!postEnv.DISCORD_PREMIUM_WEBHOOK_URL) {
        throw new Error('WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL is missing; validation passed but nothing was posted');
      }
      await run(config.nodePath, [workerPath, 'post', '--input', reportsPath], 'post', {
        cwd: config.premiumWorkerRepoPath, env: postEnv, timeoutMs: 300_000,
      });
    }

    await run(config.pythonPath || 'py', [
      '-m', 'weak_early_beta.cli', 'export-fundamentals',
      '--worker-state', statePath, '--receipts', receiptsPath, '--claim', claimPath,
    ], 'export-receipts');
    await run(config.pythonPath || 'py', [
      '-m', 'weak_early_beta.cli', 'import-fundamentals', '--receipts', receiptsPath,
    ], 'import-receipts');
    const state = readJson(statePath);
    if (Object.keys(state.claims || {}).length || Object.keys(state.failed || {}).length || (state.pendingLogEvents || []).length) {
      throw new Error('beta worker state remains incomplete; do not retry blindly');
    }
    result.posted = claim.claimedCount;
    result.ok = true;
  } catch (error) {
    result.error = error.message;
    process.exitCode = 1;
  } finally {
    result.completedAt = new Date().toISOString();
    writeJson(resultPath, result);
    console.log(JSON.stringify(result));
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('usage: node weak-early-beta-fundamental-runner.mjs <config.json>');
  await main(process.argv[2]);
}

export { assertIsolated, cleanEnvironment };
