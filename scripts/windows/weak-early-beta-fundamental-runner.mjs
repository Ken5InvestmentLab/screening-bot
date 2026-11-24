import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { CAPITAL_RISK_REVIEW_VERSION, CLOUD_CAPITAL_RISK_CONTRACT, validateClaimCapitalRiskReviews } from './weak-early-beta-capital-risk.mjs';
import { LONG_TERM_MATERIAL_REVIEW_VERSION, CLOUD_LONG_TERM_MATERIAL_CONTRACT, validateClaimLongTermMaterialReviews } from './weak-early-beta-long-term-materials.mjs';

const SIGNAL_CHANNEL_ID = '1550876104917520505';
const FUNDAMENTAL_CHANNEL_ID = '1550876675884060702';
const FUNDAMENTAL_MODEL = 'gpt-6.1-sol';
const FUNDAMENTAL_REASONING_EFFORT = 'xhigh';

export const CLOUD_LEGACY_REPORT_CONTRACT = [
  'CloudはHTML保存専用です。長期材料と増資の主要根拠を開示リンクとdisclosuresに欠落なく保持し、Discord向け文字数制限のために証跡を削除・省略しないでください。Discordへの投稿は行いません。',
  'Cloud固有のJSON契約: sourceChecksは必ずオブジェクトの配列です。role名をキーにしたオブジェクトにはしません。',
  '実際に確認した公式IRとIRBANKまたはTDnetについて、次の形の確認記録を必ず含めてください。例のURLや本文は確認した実値へ置き換え、未確認の資料を確認済みにしないでください。',
  JSON.stringify({ sourceChecks: [
    { role: 'official_ir', checked: true, url: 'https://example.com/ir', checkedUrls: ['https://example.com/filing.pdf'], result: '実際に行った一覧照合と本文確認の記録' },
    { role: 'irbank_or_tdnet', checked: true, url: 'https://example.com/disclosures', checkedUrls: ['https://example.com/disclosures'], result: '実際に行った開示一覧と公表日時の照合記録' },
  ] }),
  '各記録のurlは確認したhttps URLとし、disclosuresには採用資料ごとのtitle、publishedAt、url、contentReviewed:trueを保存します。開示リンクのURLはdisclosuresと一致させます。開示がない場合は確認根拠をnoMaterialDisclosureReasonに記録します。',
  'alertId、signalDate、analysisCutoffは不変claimの値と文字列まで一致させ、auditStatusは監査を通過した場合だけpassにしてください。',
].join('\n');
const CLOUD_REPORT_CONTRACT = [CLOUD_LEGACY_REPORT_CONTRACT,
  CLOUD_CAPITAL_RISK_CONTRACT, CLOUD_LONG_TERM_MATERIAL_CONTRACT].join('\n');


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
  return expected.size > 0 && reports.length === expected.size && expected.size === actual.size && [...expected].every(id => actual.has(id)) &&
    (claim.alerts || []).every(alert => reports.some(report =>
      report.alertId === alert.alertId && report.signalDate === alert.signalDate &&
      report.analysisCutoff === (alert.analysisCutoff || alert.receivedAt)));
}

function stampAnalysisStart(statePath, claim, analysisStartedAt) {
  if (!Number.isFinite(Date.parse(analysisStartedAt))) throw new Error('invalid analysis start time');
  const state = readJson(statePath);
  for (const alert of claim.alerts || []) {
    if (state.claims?.[alert.alertId]?.claimId !== claim.claimId ||
        state.completed?.[alert.alertId]?.delivery === 'html') {
      throw new Error(`analysis-start claim ownership mismatch: ${alert.alertId}`);
    }
  }
  const stamped = {
    ...claim, analysisStartedAt, capitalRiskReviewVersion: CAPITAL_RISK_REVIEW_VERSION,
    longTermMaterialReviewVersion: LONG_TERM_MATERIAL_REVIEW_VERSION,
    rules: { ...claim.rules, model: FUNDAMENTAL_MODEL, reasoningEffort: FUNDAMENTAL_REASONING_EFFORT },
    alerts: (claim.alerts || []).map(alert => ({ ...alert, analysisCutoff: analysisStartedAt,
      capitalRiskReviewVersion: CAPITAL_RISK_REVIEW_VERSION,
      longTermMaterialReviewVersion: LONG_TERM_MATERIAL_REVIEW_VERSION })),
  };
  for (const alert of stamped.alerts) {
    state.claims[alert.alertId].analysisCutoff = analysisStartedAt;
    state.claims[alert.alertId].capitalRiskReviewVersion = CAPITAL_RISK_REVIEW_VERSION;
    state.claims[alert.alertId].longTermMaterialReviewVersion = LONG_TERM_MATERIAL_REVIEW_VERSION;
  }
  writeJson(statePath, state);
  return stamped;
}

function reusableClaimReport(reportsPath, claim, savedState) {
  const validatedLegacyImport = (claim.alerts || []).every(alert => {
    const saved = savedState.completed?.[alert.alertId];
    return saved?.delivery === 'html' && saved.analysisCutoff === (alert.analysisCutoff || alert.receivedAt);
  });
  return ((claim.alerts || []).every(alert => alert.analysisCutoff) || validatedLegacyImport) &&
    reportsMatchClaim(reportsPath, claim);
}

function finalizeHtmlSnapshots(statePath, claim) {
  const state = readJson(statePath);
  for (const alert of claim.alerts || []) {
    const id = alert.alertId;
    if (state.completed?.[id]?.delivery !== 'html' ||
        state.claims?.[id]?.claimId !== claim.claimId) {
      throw new Error(`HTML snapshot/claim ownership mismatch: ${id}`);
    }
    delete state.claims[id];
    delete state.failed?.[id];
  }
  if (Object.keys(state.claims || {}).length || Object.keys(state.failed || {}).length || (state.pendingLogEvents || []).length) {
    throw new Error('beta worker state remains incomplete; do not retry blindly');
  }
  writeJson(statePath, state);
}

function cleanEnvironment(source) {
  const result = { ...source };
  for (const key of Object.keys(result)) {
    if (/^(OPENAI_API_KEY|CODEX_API_KEY)$/i.test(key)) delete result[key];
  }
  return result;
}

function codexInvocation(config, args) {
  if (config.codexExecutable !== undefined) {
    if (typeof config.codexExecutable !== 'string' || !config.codexExecutable.trim()) throw new Error('invalid configured native Codex executable');
    const executable = path.resolve(config.codexExecutable);
    if (!fs.existsSync(executable)) throw new Error('configured native Codex executable is unavailable; do not substitute another runtime');
    return { exe: executable, args: [...args] };
  }
  if (!config.nodePath || !config.cliJs) throw new Error('Codex requires codexExecutable or nodePath plus cliJs');
  return { exe: config.nodePath, args: [config.cliJs, ...args] };
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

function loadFundamentalEnvironment(config, source = process.env) {
  const loaded = cleanEnvironment(source);
  loadDotEnv(loaded, path.join(config.repoPath, '.env'));
  loadDotEnv(loaded, path.join(config.premiumWorkerRepoPath, '.env'));
  loadDotEnv(loaded, path.join(config.premiumWorkerRepoPath, 'premium_worker', '.env'));
  // Dotenv files can reintroduce API credentials after the inherited-env pass.
  // Every child uses this final sanitized environment, including save/import.
  const env = cleanEnvironment(loaded);
  env.CODEX_HOME = config.codexHome;
  const pathKey = Object.keys(env).find(key => /^path$/i.test(key));
  const inheritedPath = pathKey ? env[pathKey] : '';
  for (const key of Object.keys(env)) if (/^path$/i.test(key)) delete env[key];
  env.PATH = `${path.dirname(config.nodePath)}${path.delimiter}${inheritedPath}`;
  return env;
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
    identity: 'WEAK_EARLY_FUNDAMENTAL_SOL_XHIGH_V2',
    startedAt: now,
    ok: false,
    model: FUNDAMENTAL_MODEL,
    reasoningEffort: FUNDAMENTAL_REASONING_EFFORT,
    delivery: 'html',
    runDir,
  };

  const env = loadFundamentalEnvironment(config);

  const betaRoot = path.join(config.repoPath, 'weak_early_beta', 'fundamental_worker');
  const statePath = path.join(betaRoot, 'state', 'premium_alert_state.json');
  const outDir = path.join(betaRoot, 'out');
  const claimPath = path.join(outDir, 'latest_claim.json');
  const reportsPath = path.join(outDir, 'premium_reports.json');
  const receiptsPath = path.join(outDir, 'fundamental_receipts.json');
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
      result.imported = 0;
      result.posted = 0;
      return;
    }

    // Capture the fundamental analysis start, independently of detection time.
    // A validated-output import retry retains the original analysis timestamp.
    const savedState = readJson(statePath);
    const reuseReport = reusableClaimReport(reportsPath, claim, savedState);
    if (!reuseReport) {
      const analysisStartedAt = new Date().toISOString();
      claim = stampAnalysisStart(statePath, claim, analysisStartedAt);
      writeJson(claimPath, claim);
      writeJson(path.join(runDir, 'claim.json'), claim);
    }
    result.analysisStartedAt = claim.analysisStartedAt || claim.alerts?.[0]?.analysisCutoff || claim.alerts?.[0]?.receivedAt;

    const prompt = [
      'Weak+Early betaのclaimに含まれる検出銘柄を、現行Premium Workerと同じ会社固有の品質でファンダ分析してください。$premium-fundamental-snapshot を使います。',
      `不変claimは ${path.join(runDir, 'claim.json')} です。ここにあるalertIdだけを対象にしてください。`,
      `必ず ${path.join(config.premiumWorkerRepoPath, 'premium_worker', 'AUTOMATION_PROMPT.md')} と ${path.join(config.premiumWorkerRepoPath, 'premium_worker', 'FUNDAMENTAL_EXAMPLES.md')} を全文読み、skillのreferences/report_quality.mdも読んでください。`,
      '各銘柄の分析基準時点はclaimのanalysisCutoff（今回のファンダ分析を開始する直前の日時）です。銘柄検出の開始時刻やreceivedAtを分析基準にしないでください。その時点までに公表されたIR・適時開示・ニュース・決算資料を含め、それ以後の情報は検索で見つかっても使わないでください。各社の公式IR、IRBANKまたはTDnet相当の開示一覧を基準時点まで確認し、選んだ一次資料の本文を読んでください。検索スニペットだけで作らないでください。',
      '検出日より後の公表資料でもanalysisCutoff以前なら対象です。本文と開示リンクには採用資料の公表日時を示し、基準時点後の資料を使わないでください。同じ基準日の開示時刻が確認できなければ採用しないでください。',
      '各レポートのsignalDateはclaimのsignalDate、analysisCutoffはclaimのanalysisCutoffへ文字列まで正確に合わせてください。receivedAtは検出日時として保持します。既存本文が出力先にあれば参考として読み、新しい分析基準時点までの追加開示を確認してから更新してください。分析はHTMLへの保存だけに使い、Discordへ通知しません。',
      '売買推奨、目標株価、追加スコアは禁止。現行契約の全7フィールドとSourcesを満たしてください。',
      CLOUD_REPORT_CONTRACT,
      `最終JSONは ${reportsPath} だけに書き込んでください。Discord投稿、worker state、Sheets、Git、workflow、ソースコードは変更しないでください。`,
      '報告は有界に保ち、出力JSON作成後は日本語で簡潔に完了を報告してください。',
    ].join('\n\n');
    fs.writeFileSync(path.join(runDir, 'prompt.txt'), prompt);
    if (!reuseReport) {
      const analysisCommand = codexInvocation(config, [
        '--search', '-a', 'never', 'exec', '--ignore-user-config',
        '--cd', config.premiumWorkerRepoPath, '--skip-git-repo-check',
        '--sandbox', 'danger-full-access', '-m', FUNDAMENTAL_MODEL,
        '-c', `model_reasoning_effort="${FUNDAMENTAL_REASONING_EFFORT}"`,
        '-c', 'forced_login_method="chatgpt"', '--json',
        '-o', path.join(runDir, 'codex.final.txt'), '-',
      ]);
      const analysisExit = await command(analysisCommand.exe, analysisCommand.args, {
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
    result.capitalRiskReviewsValidated = validateClaimCapitalRiskReviews(
      claim, readJson(reportsPath).reports || [], readJson(statePath));
    result.longTermMaterialReviewsValidated = validateClaimLongTermMaterialReviews(
      claim, readJson(reportsPath).reports || [], readJson(statePath));

    if ((claim.alerts || []).every(alert => alert.signalType === 'WEAK_EARLY_BETA' && alert.analysisCutoff)) {
      await run(config.pythonPath || 'py', [
        '-m', 'weak_early_beta.cli', 'validate-forward-fundamentals',
        '--claim', claimPath, '--input', reportsPath, '--html-only',
      ], 'validate-analysis-start');
    }
    result.validatedReportPath = path.join(runDir, 'validated-reports.json');
    fs.copyFileSync(reportsPath, result.validatedReportPath);
    result.validatedReportSha256 = createHash('sha256').update(fs.readFileSync(result.validatedReportPath)).digest('hex');

    // Reuse the beta point-in-time validator, then persist without a Discord request.
    await run(config.nodePath, [historicalPosterPath, '--input', reportsPath, '--state', statePath, '--save-only'], 'save-snapshot', {
      cwd: config.repoPath, env, timeoutMs: 180_000,
    });

    await run(config.pythonPath || 'py', [
      '-m', 'weak_early_beta.cli', 'export-fundamentals',
      '--worker-state', statePath, '--receipts', receiptsPath, '--claim', claimPath,
    ], 'export-receipts');
    await run(config.pythonPath || 'py', [
      '-m', 'weak_early_beta.cli', 'import-fundamentals', '--receipts', receiptsPath,
    ], 'import-receipts');
    result.importedReceiptPath = path.join(runDir, 'imported-receipts.json');
    fs.copyFileSync(receiptsPath, result.importedReceiptPath);
    result.importedReceiptSha256 = createHash('sha256').update(fs.readFileSync(result.importedReceiptPath)).digest('hex');
    finalizeHtmlSnapshots(statePath, claim);
    result.imported = claim.claimedCount;
    result.posted = 0;
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

export { CLOUD_REPORT_CONTRACT, command, assertIsolated, cleanEnvironment, loadFundamentalEnvironment, codexInvocation, finalizeHtmlSnapshots, reportsMatchClaim, reusableClaimReport, stampAnalysisStart, FUNDAMENTAL_MODEL, FUNDAMENTAL_REASONING_EFFORT };
