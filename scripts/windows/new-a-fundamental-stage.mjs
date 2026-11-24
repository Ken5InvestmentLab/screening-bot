import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { createCloudPremiumDisclosureAudit, VERIFIED_ZERO_LINK_FIELD } from './cloud-premium-disclosure-audit.mjs';
import {
  CLOUD_REPORT_CONTRACT, cleanEnvironment, codexInvocation, command,
  FUNDAMENTAL_MODEL, FUNDAMENTAL_REASONING_EFFORT,
} from './weak-early-beta-fundamental-runner.mjs';
import {
  CAPITAL_RISK_REVIEW_VERSION, validateClaimCapitalRiskReviews,
} from './weak-early-beta-capital-risk.mjs';
import {
  LONG_TERM_MATERIAL_REVIEW_VERSION, validateClaimLongTermMaterialReviews,
} from './weak-early-beta-long-term-materials.mjs';

const REFERENCE_FILES = {
  'PREMIUM_PM_SAVED_PROMPT.txt': '8c6567770f3426b3125a293448bb0a350ba3ed0eb1649136c96249c0d90f3099',
  'AUTOMATION_PROMPT.md': '521ca6d22aa5c732abb1fd2ab5d0b2bed61a9ab0a2515c6b77d637b4a62217e1',
  'DISCLOSURE_AUDIT.md': '2f8f4ba46567f38eacfc2ac1f324ce6568ef28f5d7487587538d358a9d7757e3',
  'FUNDAMENTAL_EXAMPLES.md': '8dc6af5c0e12ea33e2672dcbf080395ff11e7c21365763f7d84194ccbcb1c990',
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

async function runPremiumResearch({ claim, claimPath, reportPath, config, repo, runDir, env, runStep,
  invokeAnalysis, createDisclosureAudit }) {
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
    '--search', '-a', 'never', 'exec', '--ignore-user-config',
    '--cd', claimDir, '--skip-git-repo-check', '--sandbox', 'workspace-write',
    '-m', FUNDAMENTAL_MODEL, '-c', `model_reasoning_effort="${FUNDAMENTAL_REASONING_EFFORT}"`,
    '-c', 'forced_login_method="chatgpt"', '--json', '-',
  ]);
  const prompt = [
    'Cloud 2.0が既に取得した不変claimだけを使用します。claimの読み取り元: ' + claimPath,
    '保存済みPremium 15:36タスク、復元済み手順書、公式開示監査、見本、品質チェックの次の固定資料を最初に読んでください:\n' + references.join('\n'),
    '照合、調査、初稿、指名された修正、全件再検証の手順と品質を適用してください。Cloudが所有権、時刻、HTML保存を管理します。Premium資料で言及される収集、スケジュール、GAS、Discord、実送信、状態変更、fail処理、Git操作は実行しないでください。例示用の銘柄、リンク、JSON識別子は実データとして使わないでください。',
    '実際の公式IR/ニュース、IRBANKとTDnet/JPX相当一覧を会社ごとに照合します。最新の開示は定型の題名でも原本を見て重要性を確認し、最も新しい重要開示と同時公表の関連資料をまとめます。資料本文を読み、一次資料に基づく具体的なKPI、材料、リスクを日本語で記載します。',
    'analysisCutoffはCloudの実着手時刻で固定します。これを過ぎた公表と、公表時刻未確認の当日資料は採用しません。増資、ワラント、CB、MSワラント、行使・失効・潜在株式数と確定できない残高も追跡します。',
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

  const evidenceDirectory = path.join(claimDir, 'premium-disclosures');
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  if (fs.realpathSync(evidenceDirectory) !== evidenceDirectory) throw new Error('Cloud disclosure evidence escaped the claim');
  const disclosureAudit = createDisclosureAudit({ evidenceDirectory, pythonPath: config.pythonPath });
  const sourceFile = path.join(claimDir, 'official-sources.json');
  const sourcesBySymbol = fs.existsSync(sourceFile)
    ? indexedRows(readModelFile(sourceFile, env), 'symbols', claim.alerts, 'symbolCode')
    : new Map();
  const audits = new Map();
  const prepareAudits = async targets => {
    const failures = [];
    disclosureAudit.restartPreparation();
    for (const alert of targets) {
      audits.delete(alert.alertId);
      const sources = sourcesBySymbol.get(alert.symbolCode)?.sources;
      if (!Array.isArray(sources) || !sources.length) {
        failures.push(repairTarget(alert, '会社固有の公式開示一覧の設定がありません。'));
        continue;
      }
      const input = {
        claimId: claim.claimId, symbolCode: alert.symbolCode, receivedAt: alert.receivedAt,
        analysisCutoff: alert.analysisCutoff, sources,
        documentDirectory: path.join(evidenceDirectory, alert.symbolCode),
      };
      fs.mkdirSync(input.documentDirectory, { recursive: true });
      if (fs.realpathSync(input.documentDirectory) !== input.documentDirectory) {
        throw new Error('Cloud disclosure originals escaped the owned symbol directory');
      }
      try {
        const audit = await disclosureAudit.prepare(input);
        if (audit.missingDocumentIds.length) {
          throw new Error('必須原本を取得できません: ' + audit.missingDocumentIds.join(', '));
        }
        audits.set(alert.alertId, { input, ...audit });
      } catch (error) {
        failures.push(repairTarget(alert, error.message));
      }
    }
    return failures;
  };
  let sourceTargets = claim.alerts;
  let sourceFailures = [];
  if (sourcesBySymbol.size) {
    sourceFailures = await prepareAudits(sourceTargets);
    sourceTargets = claim.alerts.filter(alert => !audits.has(alert.alertId));
  }
  for (let pass = 0; sourceTargets.length && pass <= MAX_REPAIR_PASSES; pass++) {
    const sourceDraft = path.join(claimDir, `official-sources-${pass}-${attempt}.json`);
    const sourceOutput = await model(`sources-${pass}`, sourceDraft, [
      '公式IR一覧の会社と対象範囲をまず確認し、観測した一覧の厳密なscope、全ページ、発行体識別、時刻根拠、ゼロの場合の根拠を調べてください。最低45日の期間を確認します。分析本文はまだ書きません。',
      'DISCLOSURE_AUDIT.md の Source config contract と同じ {"symbols":[{"symbolCode":"…","sources":[…]}]} を出力してください。担当対象: ' + JSON.stringify(sourceTargets.map(alert => alert.symbolCode)),
      '前回に指名された修正項目（引用した検証データ）: ' + JSON.stringify(sourceFailures),
    ]);
    for (const [symbol, row] of indexedRows(sourceOutput, 'symbols', sourceTargets, 'symbolCode')) {
      sourcesBySymbol.set(symbol, row);
    }
    writeJson(sourceFile, { symbols: [...sourcesBySymbol.values()] });
    sourceFailures = await prepareAudits(sourceTargets);
    sourceTargets = claim.alerts.filter(alert => !audits.has(alert.alertId));
  }
  if (sourceFailures.length) {
    throw new Error('Cloud official disclosure audit blocked: ' + sourceFailures.map(item => item.symbolCode).join(', '));
  }

  const researchFile = path.join(claimDir, 'verified-disclosures.json');
  const writeResearchIndex = () => writeJson(researchFile, {
    claimId: claim.claimId, alerts: claim.alerts.map(alert => {
      const audit = audits.get(alert.alertId);
      return { alertId: alert.alertId, symbolCode: alert.symbolCode, requiredIds: audit.requiredIds, documents: audit.documents };
    }),
  });

  const validator = path.join(repo, 'weak_early_beta', 'scripts', 'post_historical_snapshot.mjs');
  const validationDir = path.join(runDir, 'fundamental-validation');
  fs.mkdirSync(validationDir, { recursive: true });
  const pendingFile = path.join(claimDir, 'pending-reports.json');
  const prior = fs.existsSync(pendingFile) ? pendingFile : reportPath;
  const reports = fs.existsSync(prior) ? indexedRows(readModelFile(prior, env), 'reports', claim.alerts, 'alertId') : new Map();
  const draftContract = [
    `検証済み公式開示一覧と原本の索引: ${researchFile} 。必須文書の実際の本文を全件読んでから、対象銘柄の分析をまとめて書いてください。`,
    'reportに不変alertId、symbolCode、signalDate、analysisCutoff、会社名を入れます。公式の原本、SHA256、実際の短い引用、分析本文の該当箇所を disclosureEvidence に入れます。checkedUrlsとSourcesの一覧ページを区別し、確認した全ての直接リンクは開示リンクとdisclosuresで一致させます。',
    '索引にあるCloud用表記を使い、リンクの公開ラベルには開示公表時刻を付けます。分析に使う補足原本は supplementalBodyEvidence に記録し、正確な直接開示URLが現在開けることを全件確認してください。',
    `公式一覧を検証して対象開示が実際にゼロの場合だけ、開示リンクを「${VERIFIED_ZERO_LINK_FIELD}」とし、disclosuresとdisclosureEvidenceを空にして noMaterialDisclosureReason に確認根拠を書いてください。`,
    CLOUD_REPORT_CONTRACT,
    `トップレベルは {"claimId":"${claim.claimId}","reports":[…]} です。各分析に既存の日本語項目をすべて入れてください。`,
  ];
  const draft = async (name, targets, failures = []) => {
    const file = path.join(claimDir, `${name}-${attempt}.json`);
    writeResearchIndex();
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

  const validateBatch = async pass => {
    const failures = [];
    saveBatch(claim, reports, pendingFile);
    const pyCheck = await runStep(config.pythonPath, ['-B', '-c', PYTHON_DRAFT_CHECK, claimPath, pendingFile], {
      cwd: repo, env: childEnv, capture: true, timeoutMs: 60_000, log: path.join(validationDir, `python-validated-${pass}`),
    });
    const pythonFailures = JSON.parse(pyCheck.stdout);
    disclosureAudit.restartValidation();
    for (const [index, alert] of claim.alerts.entries()) {
      const report = reports.get(alert.alertId);
      const audit = audits.get(alert.alertId);
      try {
        if (!report || report.symbolCode !== alert.symbolCode || report.signalDate !== alert.signalDate ||
            report.analysisCutoff !== alert.analysisCutoff || (alert.symbolName && report.symbolName !== alert.symbolName)) {
          throw new Error('report must match the exact owned alert identity, company, date and cutoff');
        }
        if (Object.hasOwn(pythonFailures, alert.alertId)) throw new Error(pythonFailures[alert.alertId]);
        const oneAlert = { ...claim, alerts: [alert] };
        validateClaimCapitalRiskReviews(oneAlert, [report]);
        validateClaimLongTermMaterialReviews(oneAlert, [report]);
        const proof = await disclosureAudit.validate({ ...audit.input, inventory: audit.inventory, report });
        const state = path.join(validationDir, `claim-${pass}-${index}.json`);
        const input = path.join(validationDir, `report-${pass}-${index}.json`);
        fs.writeFileSync(state, JSON.stringify({ claims: { [alert.alertId]: proof.publicUrls.length
          ? alert : { ...alert, officialInventoryVerifiedZero: true } } }));
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
      } catch (error) {
        failures.push(repairTarget(alert, error.message));
      }
    }
    writeJson(path.join(claimDir, 'validation-targets.json'), { claimId: claim.claimId, pass, repairTargets: failures });
    return failures;
  };
  let failures = await validateBatch(0);
  for (let pass = 1; failures.length && pass <= MAX_REPAIR_PASSES; pass++) {
    const targets = claim.alerts.filter(alert => failures.some(item => item.alertId === alert.alertId));
    const blocked = await prepareAudits(targets);
    if (blocked.length) throw new Error('Cloud official disclosure repair blocked: ' + blocked.map(item => item.symbolCode).join(', '));
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
  createDisclosureAudit = createCloudPremiumDisclosureAudit,
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
    const claim = JSON.parse(readOwnedBytes(claimPath).toString('utf8').replace(/^\uFEFF/, ''));
    if (claim.claimedCount !== expectedCount || claim.alerts.length !== expectedCount ||
        !/^[a-f0-9]{64}$/.test(claim.claimId) ||
        new Set(claim.alerts.map(alert => alert.alertId)).size !== expectedCount ||
        new Set(claim.alerts.map(alert => alert.symbolCode)).size !== expectedCount ||
        claim.alerts.some(alert => !alert.alertId || !/^[0-9A-Z]{4}$/.test(alert.symbolCode)) ||
        claim.rules.model !== FUNDAMENTAL_MODEL || claim.rules.reasoningEffort !== FUNDAMENTAL_REASONING_EFFORT ||
        claim.rules.destination !== 'html' || claim.capitalRiskReviewVersion !== CAPITAL_RISK_REVIEW_VERSION ||
        claim.longTermMaterialReviewVersion !== LONG_TERM_MATERIAL_REVIEW_VERSION) {
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
      reportHash = await runPremiumResearch({
        claim, claimPath, reportPath, config, repo, runDir, env, runStep, invokeAnalysis, createDisclosureAudit,
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
