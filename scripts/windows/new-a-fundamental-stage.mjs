import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import {
  CLOUD_REPORT_CONTRACT, cleanEnvironment, codexInvocation, command,
  FUNDAMENTAL_MODEL, FUNDAMENTAL_REASONING_EFFORT, loadFundamentalEnvironment,
} from './weak-early-beta-fundamental-runner.mjs';
import {
  CAPITAL_RISK_REVIEW_VERSION, validateClaimCapitalRiskReviews,
} from './weak-early-beta-capital-risk.mjs';
import {
  LONG_TERM_MATERIAL_REVIEW_VERSION, validateClaimLongTermMaterialReviews,
} from './weak-early-beta-long-term-materials.mjs';

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
}

function safeChildEnvironment(fundamentalConfig) {
  const env = cleanEnvironment(loadFundamentalEnvironment(fundamentalConfig));
  for (const key of Object.keys(env)) {
    if (/^(?:DISCORD|CLOUDFLARE|GH_|GITHUB_|GOOGLE_APPLICATION_CREDENTIALS|WHOP)/i.test(key) ||
        /(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY|CREDENTIAL|WEBHOOK)/i.test(key)) {
      delete env[key];
    }
  }
  return env;
}

/** Complete the exact New A detection batch in its private workspace. */
export async function runNewAFundamentalStage({
  config, repo, runtime, today, startedAt, runDir, env, runStep, expectedCount,
  invokeAnalysis = command,
}) {
  const payload = ['--runtime', runtime, '--date', today, '--owner-start', startedAt];
  const python = ['-B', '-m', 'weak_early_beta.new_a.fundamentals'];
  const step = async (phase, rest = []) => {
    const result = await runStep(config.pythonPath, [...python, phase, ...payload, ...rest], {
      cwd: repo, env, capture: true, timeoutMs: 300_000, log: path.join(runDir, 'fundamental-' + phase),
    });
    return JSON.parse(result.stdout.trim());
  };
  const prepared = await step('prepare', ['--analysis-start', new Date().toISOString()]);
  if (prepared.claimed !== expectedCount || !Number.isSafeInteger(expectedCount) || expectedCount < 0) {
    throw new Error('New A fundamental claim does not cover the current detection batch');
  }
  const claimPath = path.resolve(prepared.claimPath);
  const reportPath = path.resolve(prepared.reportsPath);
  const claimDir = path.dirname(claimPath);
  const privateRuns = path.resolve(repo, '.cache', 'weak_early_beta', 'new-a-private', 'runs', today);
  if (!claimDir.startsWith(privateRuns + path.sep) || fs.realpathSync(claimDir) !== claimDir ||
      path.basename(claimDir) !== 'fundamental-analysis' || path.basename(claimPath) !== 'claim.json' ||
      path.join(claimDir, 'reports.json') !== reportPath) {
    throw new Error('New A fundamental outputs must stay inside the owned snapshot workspace');
  }
  let reportHash;
  if (expectedCount > 0) {
    const claim = readJson(claimPath);
    if (claim.claimedCount !== expectedCount || claim.alerts.length !== expectedCount ||
        claim.rules.model !== FUNDAMENTAL_MODEL || claim.rules.reasoningEffort !== FUNDAMENTAL_REASONING_EFFORT ||
        claim.rules.destination !== 'html' || claim.capitalRiskReviewVersion !== CAPITAL_RISK_REVIEW_VERSION ||
        claim.longTermMaterialReviewVersion !== LONG_TERM_MATERIAL_REVIEW_VERSION) {
      throw new Error('New A fundamental model, identity or audit contract differs');
    }
    if (!fs.existsSync(reportPath)) {
      if (!config.fundamentalConfigPath) throw new Error('Configured Cloud fundamental runtime is required');
      const fundamentalConfigPath = fs.realpathSync(path.resolve(config.fundamentalConfigPath));
      if (!fundamentalConfigPath.startsWith(fs.realpathSync(repo) + path.sep)) {
        throw new Error('Cloud fundamental configuration escapes the daily checkout');
      }
      const fundamentalConfig = readJson(fundamentalConfigPath);
      if (fs.realpathSync(fundamentalConfig.repoPath) !== fs.realpathSync(repo)) {
        throw new Error('Cloud fundamental configuration targets another daily checkout');
      }
      const references = path.join(fundamentalConfig.premiumWorkerRepoPath, 'premium_worker');
      const prompt = [
        '新Aの検出銘柄を、現行Premium Workerと同じ会社固有の品質でファンダ分析してください。$premium-fundamental-snapshot を使います。',
        '次に示す不変claim内のalertIdだけを対象とし、全件を分析してください: ' + claimPath,
        '必ず参照するルール: ' + path.join(references, 'AUTOMATION_PROMPT.md') + ' と ' +
          path.join(references, 'FUNDAMENTAL_EXAMPLES.md') + '。skillのreferences/report_quality.mdも読みます。',
        '各銘柄のanalysisCutoffは実際のファンダ着手時刻です。その時点までの公式IR、IRBANKまたはTDnet相当の開示一覧と一次資料本文を確認します。公表日時の確認できない同日開示は含めません。',
        'claimのalertId、signalDate、analysisCutoffを正確に保持してください。売買推奨、目標株価、追加スコアの記載は禁止です。',
        CLOUD_REPORT_CONTRACT,
        '書き込みは ' + reportPath + ' に {"reports":[...]} を保存することに限ります。送信、設定変更、状態編集、公開、Git操作は行いません。',
      ].join('\n\n');
      const invocation = codexInvocation(fundamentalConfig, [
        '--search', '-a', 'never', 'exec', '--ignore-user-config',
        '--cd', claimDir, '--skip-git-repo-check', '--sandbox', 'workspace-write',
        '-m', FUNDAMENTAL_MODEL, '-c', `model_reasoning_effort="${FUNDAMENTAL_REASONING_EFFORT}"`,
        '-c', 'forced_login_method="chatgpt"', '--json', '-',
      ]);
      const exitCode = await invokeAnalysis(invocation.exe, invocation.args, {
        cwd: claimDir, env: safeChildEnvironment(fundamentalConfig), input: prompt,
        log: path.join(runDir, 'new-a-fundamental-model'), timeoutMs: 12_000_000,
      });
      if (exitCode !== 0 || !fs.existsSync(reportPath)) {
        throw new Error('New A fundamental model did not complete; retain the exact claim and output for review');
      }
    }
    if (fs.realpathSync(reportPath) !== reportPath || !fs.statSync(reportPath).isFile() ||
        fs.statSync(reportPath).size > 8 * 1024 * 1024) {
      throw new Error('New A fundamental output is not a bounded claim-local file');
    }
    const reportBytes = fs.readFileSync(reportPath);
    reportHash = createHash('sha256').update(reportBytes).digest('hex');
    const reportText = reportBytes.toString('utf8').replace(/^\uFEFF/, '');
    for (const [key, value] of Object.entries(env)) {
      if (/(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY|CREDENTIAL|WEBHOOK)/i.test(key) &&
          typeof value === 'string' && value.length >= 8 &&
          (reportText.includes(value) || reportText.includes(JSON.stringify(value).slice(1, -1)))) {
        throw new Error('New A fundamental report contains a configured credential');
      }
    }
    const reports = JSON.parse(reportText).reports;
    validateClaimCapitalRiskReviews(claim, reports);
    validateClaimLongTermMaterialReviews(claim, reports);
    const validator = path.join(repo, 'weak_early_beta', 'scripts', 'post_historical_snapshot.mjs');
    const validationDir = path.join(runDir, 'fundamental-validation');
    fs.mkdirSync(validationDir, { recursive: true });
    for (const [index, alert] of claim.alerts.entries()) {
      const report = reports.find(item => item.alertId === alert.alertId);
      if (!report) throw new Error('No existing report for fundamental validation');
      const state = path.join(validationDir, 'claim-' + index + '.json');
      const input = path.join(validationDir, 'report-' + index + '.json');
      fs.writeFileSync(state, JSON.stringify({ claims: { [alert.alertId]: alert } }));
      fs.writeFileSync(input, JSON.stringify({ reports: [report] }));
      await runStep(config.nodePath, [validator, '--dry-run', '--save-only', '--input', input, '--state', state], {
        cwd: repo, env, timeoutMs: 60_000, log: path.join(validationDir, 'validated-' + index),
      });
    }
  }
  const receipt = await step('finish', reportHash ? ['--reports-sha256', reportHash] : []);
  if (!receipt.ok || receipt.imported !== expectedCount || receipt.posted !== 0 ||
      receipt.status !== (expectedCount ? 'COMPLETE' : 'NO_NEW_SIGNALS')) {
    throw new Error('New A fundamental stage did not prove exact HTML-only import');
  }
  return receipt;
}
