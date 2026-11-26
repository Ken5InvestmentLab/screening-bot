import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { pathToFileURL } from 'node:url';
import {
  CLOUD_LEGACY_REPORT_CONTRACT, cleanEnvironment, codexInvocation, command,
  FUNDAMENTAL_MODEL, FUNDAMENTAL_REASONING_EFFORT,
} from './weak-early-beta-fundamental-runner.mjs';
const REFERENCE_FILES = {
  'COPY_MANIFEST.json': '6bd82aaf3928c2f4e5ddfb5366b1d69da9b3af60d8caff0205a1ed20efd6e6db',
  'verified-untimed-disclosures.json': 'a2316766f691fffe25c48846872ab3017eed57404c9e830331b588364ac7e2b8',
  'PREMIUM_PM_SAVED_PROMPT.txt': 'af31b0175e968a8fe17354339a899e2f988ecf6c37dbc30958037b25f493c317',
  'AUTOMATION_PROMPT.md': 'a5da617d30b3f0ea0c40a0cf4bb07d94c81d70945c0f98669478aa1e05dff1c7',
  'FUNDAMENTAL_EXAMPLES.md': 'c49243cc7ee6685d3dedf2789fc452ce4d610f463edcc54b48001487a39d77fb',
  'PREMIUM_LEGACY_WORKER.mjs': '98edbc6921dfcad6b853660a1d1bc6e508ef684f71d29732960330a53cb80dc3',
  'PREMIUM_CLOUD_WORKER.mjs': '5cfe4152365d419891115e7c4f0249855b3b4ab64ae5f3698e7f55ec172a19f0',
  'SOURCE_COMPANION_REVIEW.md': '110e80ccaee9fe0ea433e42ec1a206145ea1596bac4d53a9c25dd8edfd11c28a',
  'PREMIUM_NO_SEND_PRELOAD.mjs': '2121ad3d3301524762efe3e10970006ce1e2fa792c7caa47ba0f61aa1b2ee5e0',
  'report_quality.md': '6df031fabe3d309b0f2c7c317734920ba1450926c344987491e0fc14b5c7a6fb',
};
const MAX_REPAIR_PASSES = 2;
const MODEL_FILE_BYTES = 8 * 1024 * 1024;
const SECRET_KEY = /(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY|CREDENTIAL|WEBHOOK|COOKIE|SESSION_KEY)/i;
const PYTHON_DRAFT_CHECK = `
import json, pathlib, sys
from weak_early_beta.historical_fundamentals import validate_forward_report
claim, draft = [json.loads(pathlib.Path(p).read_text(encoding="utf-8-sig")) for p in sys.argv[1:]]
reports = {report["alertId"]: report for report in draft["reports"]}
failures = {}
for alert in claim["alerts"]:
    try:
        validate_forward_report(reports[alert["alertId"]], alert, html_only=True)
    except (KeyError, TypeError, ValueError) as error:
        failures[alert["alertId"]] = str(error)[:400]
print(json.dumps(failures))
`;

export class FundamentalResearchHeldError extends Error {
  constructor(cause) {
    super('Premium legacy research is held; retain claim and verified output', { cause });
    this.cloudFundamentalHeld = true;
  }
}

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
}

function readOwnedBytes(file) {
  if (fs.realpathSync(file) !== file || !fs.statSync(file).isFile() || fs.statSync(file).size > MODEL_FILE_BYTES) {
    throw new Error('New A fundamental output is not a bounded claim-local file');
  }
  return fs.readFileSync(file);
}

function readModelFile(file, env) {
  const text = readOwnedBytes(file).toString('utf8').replace(/^\uFEFF/, '');
  for (const [key, value] of Object.entries(env)) {
    if (SECRET_KEY.test(key) && typeof value === 'string' && value.length >= 8 &&
        (text.includes(value) || text.includes(JSON.stringify(value).slice(1, -1)))) {
      throw new Error('New A fundamental output contains a configured credential');
    }
  }
  return JSON.parse(text);
}

function writeJson(file, value) {
  const temporary = `${file}.tmp-${randomUUID()}`;
  try {
    fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, { flag: 'wx', mode: 0o600 });
    fs.renameSync(temporary, file);
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

function checkedReferences() {
  return Object.entries(REFERENCE_FILES).map(([name, expected]) => {
    const file = path.join(import.meta.dirname, 'cloud-premium-references', name);
    if (sha256(fs.readFileSync(file)) !== expected) throw new Error(`Pinned Premium reference changed: ${name}`);
    return file;
  });
}

function safeChildEnvironment(fundamentalConfig) {
  const env = cleanEnvironment(process.env);
  for (const key of Object.keys(env)) {
    if (/^(?:DISCORD|CLOUDFLARE|GH_|GITHUB_|GOOGLE_APPLICATION_CREDENTIALS|WHOP|SSH_|AZURE_|AWS_)/i.test(key) ||
        SECRET_KEY.test(key)) {
      delete env[key];
    }
  }
  env.CODEX_HOME = fundamentalConfig.codexHome;
  const pathKey = Object.keys(env).find(key => /^path$/i.test(key));
  const inheritedPath = pathKey ? env[pathKey] : '';
  if (pathKey) delete env[pathKey];
  env.PATH = `${path.dirname(fundamentalConfig.nodePath)}${path.delimiter}${inheritedPath}`;
  return env;
}

function indexedRows(payload, field, alerts, key) {
  const rows = new Map();
  const allowed = new Set(alerts.map(alert => alert[key]));
  if (Array.isArray(payload?.[field])) {
    for (const row of payload[field]) {
      if (!allowed.has(row?.[key]) || rows.has(row[key])) {
        throw new Error(`Cloud fundamental ${field} contains unknown or duplicate ${key}`);
      }
      rows.set(row[key], row);
    }
  }
  return rows;
}

function repairTarget(alert, message) {
  return { alertId: alert.alertId, symbolCode: alert.symbolCode, reason: String(message).slice(0, 400) };
}

function dryRunFailure(log, fallback) {
  const file = `${log}.stderr`;
  if (!fs.existsSync(file)) return fallback;
  const handle = fs.openSync(file, 'r');
  try {
    const buffer = Buffer.alloc(4096);
    const length = fs.readSync(handle, buffer);
    return buffer.toString('utf8', 0, length).match(/^Error: ([^\r\n]+)/m)?.[1] || fallback;
  } finally {
    fs.closeSync(handle);
  }
}

function saveBatch(claim, reports, file) {
  writeJson(file, { claimId: claim.claimId, reports: claim.alerts.map(alert => reports.get(alert.alertId)).filter(Boolean) });
}


export function premiumBatchRepairTargets(error, directory, pass, alerts) {
  let value;
  try { value = readJson(path.join(directory, `legacy-${pass}-full.stderr`)); }
  catch { throw error; } // Operational failures must not start N per-company retries.
  if (value.ok !== false || !Array.isArray(value.repairTargets) || !value.repairTargets.length) throw error;
  const owned = new Map(alerts.map(alert => [alert.alertId, alert]));
  const seen = new Set();
  return value.repairTargets.map(row => {
    const alert = owned.get(row.alertId);
    if (!alert || seen.has(row.alertId) || !Array.isArray(row.issues) || !row.issues.length ||
        row.issues.some(issue => typeof issue.rule !== 'string' || typeof issue.message !== 'string')) {
      throw new Error('Premium batch diagnostic does not match the owned Cloud reports');
    }
    seen.add(row.alertId);
    return { ...repairTarget(alert, row.issues.map(issue => issue.message).join('\n')), issues: row.issues };
  });
}

export async function verifyPremiumDirectUrls(reports, fetchImpl = fetch) {
  const urls = new Set();
  for (const report of reports) {
    const links = report.fields?.find(field => field.name === '開示リンク')?.value || '';
    for (const match of links.matchAll(/\]\((https:\/\/[^)]+)\)/g)) urls.add(match[1]);
  }
  const pending = [...urls];
  await Promise.all(Array.from({ length: Math.min(4, pending.length) }, async () => {
    while (pending.length) {
      const url = pending.shift();
      const parsed = new URL(url);
      if (parsed.protocol !== 'https:' || parsed.username || parsed.password ||
          !parsed.hostname.includes('.') || /^(?:localhost|127\.|0\.|169\.254\.|10\.|192\.168\.)/i.test(parsed.hostname)) {
        throw new Error('Disclosure URL is not a public HTTPS address');
      }
      const response = await fetchImpl(url, { method: 'GET', signal: AbortSignal.timeout(20_000),
        headers: { 'User-Agent': 'Mozilla/5.0' } });
      try {
        if (!response.ok) throw new Error(`Disclosure direct URL returned HTTP ${response.status}: ${url}`);
      } finally { await response.body?.cancel(); }
    }
  }));
}

export async function runPremiumResearch({ claim, claimPath, reportPath, config, repo, runDir, env, runStep,
  invokeAnalysis, checkDirectUrls }) {
  if (!config.fundamentalConfigPath) throw new Error('Configured Cloud fundamental runtime is required');
  const fundamentalConfigPath = fs.realpathSync(path.resolve(config.fundamentalConfigPath));
  if (!fundamentalConfigPath.startsWith(fs.realpathSync(repo) + path.sep)) {
    throw new Error('Cloud fundamental configuration escapes the daily checkout');
  }
  const fundamentalConfig = readJson(fundamentalConfigPath);
  if (fs.realpathSync(fundamentalConfig.repoPath) !== fs.realpathSync(repo)) {
    throw new Error('Cloud fundamental configuration targets another daily checkout');
  }
  const claimDir = path.dirname(claimPath);
  const attempt = randomUUID();
  const claimHash = sha256(readOwnedBytes(claimPath));
  const assertClaim = () => {
    if (sha256(readOwnedBytes(claimPath)) !== claimHash) throw new Error('Owned Cloud fundamental claim changed');
  };
  const references = checkedReferences();
  const childEnv = safeChildEnvironment(fundamentalConfig);
  const invocation = codexInvocation(fundamentalConfig, [
    '--search', '-a', 'never', 'exec',
    '--cd', claimDir, '--skip-git-repo-check',
    '-m', FUNDAMENTAL_MODEL, '-c', `model_reasoning_effort="${FUNDAMENTAL_REASONING_EFFORT}"`,
    '-c', 'forced_login_method="chatgpt"', '--json', '-',
  ]);
  // Keep the installed user's normal permission policy, including Windows
  // sandbox initialization. Never silently substitute a different runtime.
  // Confirm actual file I/O before passing any claim or research instructions.
  const probeInput = path.join(claimDir, 'runtime-probe-input-' + attempt + '.txt');
  const probeOutput = path.join(claimDir, 'runtime-probe-output-' + attempt + '.json');
  const probeValue = randomUUID();
  fs.writeFileSync(probeInput, probeValue, { flag: 'wx', mode: 0o600 });
  const probeExit = await invokeAnalysis(invocation.exe, invocation.args, {
    cwd: claimDir, env: childEnv,
    input: `実行環境の読み書き確認だけを行います。分析・Web検索・外部送信はしません。${probeInput} を読み、その全文を値とする {"probe":"読んだ文字列"} を ${probeOutput} に保存してください。他のファイルは読み書きしないでください。`,
    log: path.join(runDir, 'new-a-fundamental-runtime-probe'), timeoutMs: 120_000,
  });
  assertClaim();
  if (probeExit !== 0 || !fs.existsSync(probeOutput)
      || readModelFile(probeOutput, env).probe !== probeValue) {
    throw new Error('Configured Premium runtime cannot read/write its workspace; retain the claim without research');
  }
  const prompt = [
    'Cloud 2.0が既に取得した不変claimだけを使用します。claimの読み取り元: ' + claimPath,
    '11/2版Premiumを基礎に修正済みの現行Premiumと完全照合した保存済みタスク、手順書、見本、品質チェックの次の固定資料を最初に読んでください:\n' + references.join('\n'),
    '照合、調査、初稿、指名された修正、全件再検証の手順と品質を適用してください。Cloudが所有権、時刻、HTML保存を管理します。Premium資料で言及される収集、スケジュール、GAS、Discord、実送信、状態変更、fail処理、Git操作は実行しないでください。例示用の銘柄、リンク、JSON識別子は実データとして使わないでください。',
    '元のPREMIUM_LEGACY_WORKER.mjsは不変のコピー元です。全件検証には、現行Premiumと同じバイト列のPREMIUM_CLOUD_WORKER.mjsを使います。SOURCE_COMPANION_REVIEW.mdを読み、COPY_MANIFEST.jsonでコピー元を照合し、資料の掲載日精度と資本状況の観測日を保持してください。時刻や残高を推測して埋めず、根拠資料や引用を検証回避のために削除しないでください。',
    '実際の公式IR/ニュース、IRBANKとTDnet/JPX相当一覧を会社ごとに照合します。最新の開示は定型の題名でも原本を見て重要性を確認し、最も新しい重要開示と同時公表の関連資料をまとめます。資料本文を読み、一次資料に基づく具体的なKPI、材料、リスクを日本語で記載します。',
    'analysisCutoffはCloudの実着手時刻で固定します。これを過ぎた公表と、公表時刻未確認の当日資料は採用しません。増資、ワラント、CB、MSワラント、行使・失効・潜在株式数と確定できない残高も追跡します。',
    '調査不足と会社固有の希薄化リスクを混同しません。発行・残存する商品があるという一次資料の根拠がない銘柄へ、「潜在株式残高・希薄化リスクは未確認」等の定型文を注意点や材料インパクトへ追加しないでください。調査未了の事実は内部記録へ残して必要な調査を続け、未確認だけを理由に混在/要確認へ分類しません。根拠なく希薄化なしとも断定しません。',
    '実在するCB・新株予約権等を確認した銘柄は、商品名と直近に確認できた基準日・残高・行使条件を具体的に記載します。発行額、簿価、未転換元本、潜在株式数を区別し、期末残高を検出日現在の確定値へ読み替えません。未公表の更新だけが残る場合は確認済みの時点と数値を先に示し、一般的な未確認文で置き換えません。',
  ];
  const model = async (name, file, instructions) => {
    const exitCode = await invokeAnalysis(invocation.exe, invocation.args, {
      cwd: claimDir, env: childEnv, input: [...prompt, ...instructions, `今回の書き込み先は ${file} のみです。`].join('\n\n'),
      log: path.join(runDir, 'new-a-fundamental-' + name), timeoutMs: 12_000_000,
    });
    assertClaim();
    if (exitCode !== 0 || !fs.existsSync(file)) {
      throw new Error(`New A fundamental ${name} did not complete; retain the exact claim and output for review`);
    }
    return readModelFile(file, env);
  };

  const validator = path.join(repo, 'weak_early_beta', 'scripts', 'post_historical_snapshot.mjs');
  const validationDir = path.join(runDir, 'fundamental-validation');
  fs.mkdirSync(validationDir, { recursive: true });
  const pendingFile = path.join(claimDir, 'pending-reports.json');
  const prior = fs.existsSync(pendingFile) ? pendingFile : reportPath;
  const reports = fs.existsSync(prior) ? indexedRows(readModelFile(prior, env), 'reports', claim.alerts, 'alertId') : new Map();
  const draftContract = [
    'コピーしたAUTOMATION_PROMPT.mdとFUNDAMENTAL_EXAMPLES.mdの分析手順・7項目の書式をそのまま適用します。各社の公式IR一覧、IRBANK・TDnet相当の一覧、採用原本を実際に開いてから全件を執筆してください。',
    '11/2版の手順を使い、後から追加されたdisclosureAuditPath、disclosureEvidence、audit-disclosures、research-*、公式一覧全件の機械的監査や時刻分類の追加工程を要求しません。採用資料の事実確認、最新重要資料、希薄化確認と直接リンク到達確認は行います。',
    'Cloud保存に必要なalertId、symbolCode、signalDate、analysisCutoffは不変claimに一致させ、sourceChecksとdisclosuresは実際に確認した情報から作ります。公表時刻不明の当日開示は確定できるまで保留し、時刻を推測しません。',
    CLOUD_LEGACY_REPORT_CONTRACT,
    `トップレベルは {"claimId":"${claim.claimId}","reports":[…]} です。各分析に既存の日本語項目をすべて入れてください。`,
  ];
  const draft = async (name, targets, failures = []) => {
    const file = path.join(claimDir, `${name}-${attempt}.json`);
    const result = await model(name, file, [
      ...draftContract, '執筆対象のalertId: ' + JSON.stringify(targets.map(alert => alert.alertId)),
      `既存の原稿 ${pendingFile} は参照できます。修正指名（引用した検証データ）: ${JSON.stringify(failures)}。指名外の原稿は出力に含めません。`,
    ]);
    if (result.claimId !== claim.claimId) throw new Error('Cloud fundamental draft claim ID differs');
    for (const [id, report] of indexedRows(result, 'reports', targets, 'alertId')) reports.set(id, report);
    saveBatch(claim, reports, pendingFile);
  };
  const missing = claim.alerts.filter(alert => !reports.has(alert.alertId));
  if (missing.length) await draft('initial-drafts', missing);

  const validHtmlReports = new Set();
  const validateBatch = async pass => {
    const failures = [];
    saveBatch(claim, reports, pendingFile);
    const pyCheck = await runStep(config.pythonPath, ['-B', '-c', PYTHON_DRAFT_CHECK, claimPath, pendingFile], {
      cwd: repo, env: childEnv, capture: true, timeoutMs: 60_000, log: path.join(validationDir, `python-validated-${pass}`),
    });
    const pythonFailures = JSON.parse(pyCheck.stdout);
    for (const [index, alert] of claim.alerts.entries()) {
      const report = reports.get(alert.alertId);
      try {
        if (!report || report.symbolCode !== alert.symbolCode || report.signalDate !== alert.signalDate ||
            report.analysisCutoff !== alert.analysisCutoff || (alert.symbolName && report.symbolName !== alert.symbolName)) {
          throw new Error('report must match the exact owned alert identity, company, date and cutoff');
        }
        if (Object.hasOwn(pythonFailures, alert.alertId)) throw new Error(pythonFailures[alert.alertId]);
        const reportKey = sha256(Buffer.from(JSON.stringify({ claimHash, report })));
        if (validHtmlReports.has(reportKey)) continue;
        const state = path.join(validationDir, `claim-${pass}-${index}.json`);
        const input = path.join(validationDir, `report-${pass}-${index}.json`);
        fs.writeFileSync(state, JSON.stringify({ claims: { [alert.alertId]: alert } }));
        fs.writeFileSync(input, JSON.stringify({ reports: [report] }));
        const log = path.join(validationDir, `validated-${pass}-${index}`);
        let dryRun;
        try {
          dryRun = await runStep(config.nodePath, [validator, '--dry-run', '--save-only', '--input', input, '--state', state], {
            cwd: repo, env: childEnv, capture: true, timeoutMs: 60_000, log,
          });
        } catch (error) {
          throw new Error(dryRunFailure(log, error.message), { cause: error });
        }
        const result = JSON.parse(dryRun.stdout);
        if (result.ok !== true || result.dryRun !== true || result.alertId !== alert.alertId ||
            result.analysisCutoff !== alert.analysisCutoff) throw new Error('Cloud HTML-only validation receipt differs');
        validHtmlReports.add(reportKey);
      } catch (error) {
        failures.push(repairTarget(alert, error.message));
      }
    }
    // Run the shared batch validator even when a Cloud-specific check found a
    // report error, so one repair prompt receives every layer's diagnostics.
    if (claim.alerts.every(alert => reports.has(alert.alertId))) {
      const state = path.join(claimDir, 'legacy-dry-run-state.json');
      writeJson(state, { posted: {}, failed: {}, claims: Object.fromEntries(claim.alerts.map(alert =>
        [alert.alertId, { ...alert, claimId: claim.claimId }])) });
      const legacyDirectory = path.join(claimDir, 'legacy-dry-run');
      fs.mkdirSync(legacyDirectory, { recursive: true });
      const legacyWorker = path.join(legacyDirectory, 'worker.mjs');
      if (fs.realpathSync(legacyDirectory) !== legacyDirectory ||
          (fs.existsSync(legacyWorker) && fs.realpathSync(legacyWorker) !== legacyWorker) ||
          [path.join(claimDir, '.env'), path.join(legacyDirectory, '.env')].some(file => fs.existsSync(file))) {
        throw new Error('Legacy dry-run directory must be isolated from environment files');
      }
      fs.copyFileSync(references.find(file => file.endsWith('PREMIUM_CLOUD_WORKER.mjs')), legacyWorker);
      fs.copyFileSync(references.find(file => file.endsWith('verified-untimed-disclosures.json')),
        path.join(legacyDirectory, 'verified-untimed-disclosures.json'));
      const legacyStateHash = sha256(readOwnedBytes(state));
      const legacyEnv = { ...childEnv, PREMIUM_STATE_PATH: state };
      const checkLegacy = async (input, alerts, suffix) => {
        const log = path.join(validationDir, `legacy-${pass}-${suffix}`);
        const result = await runStep(config.nodePath, ['--import', pathToFileURL(references.find(file => file.endsWith('PREMIUM_NO_SEND_PRELOAD.mjs'))).href, legacyWorker, 'post', '--input', input, '--dry-run', '--html-only'], {
          cwd: legacyDirectory, env: legacyEnv, capture: true, timeoutMs: 300_000, log,
        });
        const receipt = JSON.parse(result.stdout);
        assertClaim();
        if (sha256(readOwnedBytes(state)) !== legacyStateHash) throw new Error('Legacy dry-run changed its isolated state');
        if (receipt.ok !== true || receipt.posted !== 0 || receipt.results?.length !== alerts.length ||
            alerts.some(alert => !receipt.results.some(item => item.alertId === alert.alertId && item.dryRun === true && !item.skipped))) {
          throw new Error('Exact Premium legacy full dry-run did not validate every owned alert');
        }
      };
      try {
        // Shared Premium validation checks every direct URL and retains all
        // errors. Do not repeat those HTTP requests via a second URL checker.
        await checkLegacy(pendingFile, claim.alerts, 'full');
      } catch (error) {
        failures.push(...premiumBatchRepairTargets(error, validationDir, pass, claim.alerts));
      }
    }
    writeJson(path.join(claimDir, 'validation-targets.json'), { claimId: claim.claimId, pass, repairTargets: failures });
    return failures;
  };
  let failures = await validateBatch(0);
  for (let pass = 1; failures.length && pass <= MAX_REPAIR_PASSES; pass++) {
    const targets = claim.alerts.filter(alert => failures.some(item => item.alertId === alert.alertId));
    await draft(`repair-${pass}`, targets, failures);
    failures = await validateBatch(pass);
  }
  if (failures.length) {
    throw new Error('Cloud fundamental full validation blocked: ' + failures.map(item => item.symbolCode).join(', '));
  }
  assertClaim();
  saveBatch(claim, reports, reportPath);
  return sha256(readOwnedBytes(reportPath));
}

/** Complete the exact New A detection batch in its private workspace. */
export async function runNewAFundamentalStage({
  config, repo, runtime, today, startedAt, runDir, env, runStep, expectedCount,
  invokeAnalysis = command,
  checkDirectUrls = verifyPremiumDirectUrls,
  completedRecoverySha256 = null,
}) {
  const payload = ['--runtime', runtime, '--date', today, '--owner-start', startedAt];
  if (completedRecoverySha256 !== null) {
    if (!/^[a-f0-9]{64}$/.test(completedRecoverySha256)) throw new Error('Invalid completed fundamental recovery owner');
    payload.push('--completed-recovery-sha256',completedRecoverySha256);
  }
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
    const claim = JSON.parse(readOwnedBytes(claimPath).toString('utf8').replace(/^\uFEFF/, ''));
    if (claim.claimedCount !== expectedCount || claim.alerts.length !== expectedCount ||
        !/^[a-f0-9]{64}$/.test(claim.claimId) ||
        new Set(claim.alerts.map(alert => alert.alertId)).size !== expectedCount ||
        new Set(claim.alerts.map(alert => alert.symbolCode)).size !== expectedCount ||
        claim.alerts.some(alert => !alert.alertId || !/^[0-9A-Z]{4}$/.test(alert.symbolCode)) ||
        claim.rules.model !== FUNDAMENTAL_MODEL || claim.rules.reasoningEffort !== FUNDAMENTAL_REASONING_EFFORT ||
        claim.rules.destination !== 'html' || claim.rules.workflow !== 'premium-legacy-1fa6d89') {
      throw new Error('New A fundamental model, identity or audit contract differs');
    }
    const priorReceipt = path.resolve(privateRuns, '..', '..', 'fundamentals', 'verified', `${today}.json`);
    if (fs.existsSync(priorReceipt)) {
      // Python finish re-verifies the immutable receipt and the exact owned bytes.
      const saved = readJson(priorReceipt);
      const reports = readModelFile(reportPath, env).reports;
      if (!isDeepStrictEqual(saved.claim, claim) || !isDeepStrictEqual(saved.reports, reports)) {
        throw new Error('Retry does not match the retained Cloud fundamental receipt');
      }
      reportHash = sha256(readOwnedBytes(reportPath));
    } else {
      try {
        reportHash = await runPremiumResearch({
          claim, claimPath, reportPath, config, repo, runDir, env, runStep, invokeAnalysis, checkDirectUrls,
        });
      } catch (error) {
        throw new FundamentalResearchHeldError(error);
      }
    }
  }
  const receipt = await step('finish', reportHash ? ['--reports-sha256', reportHash] : []);
  if (!receipt.ok || receipt.imported !== expectedCount || receipt.posted !== 0 ||
      receipt.status !== (expectedCount ? 'COMPLETE' : 'NO_NEW_SIGNALS')) {
    throw new Error('New A fundamental stage did not prove exact HTML-only import');
  }
  return receipt;
}
