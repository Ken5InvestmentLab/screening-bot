import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { validateCapitalRiskReview, validateClaimCapitalRiskReviews } from './weak-early-beta-capital-risk.mjs';
import { stampAnalysisStart, CLOUD_REPORT_CONTRACT } from './weak-early-beta-fundamental-runner.mjs';

const cutoff = '2026-10-09T01:00:00.123456789Z';
const alert = { alertId: 'weak-early-beta:2026-10-08:1234', signalType: 'WEAK_EARLY_BETA',
  signalDate: '2026-10-08', analysisCutoff: cutoff };
const riskNote = '第2回新株予約権の未行使対象株式8万株が残存し、全て新株で交付されるかは未確認。';

function document(id, kind, publishedAt, finding = '一次資料の確認記述') {
  return { id, kind, source: 'official_ir', title: `${id}資料`,
    url: `https://issuer.example/ir/${id}.pdf`, publishedAt,
    contentReviewed: true, locator: '資本政策の注記', finding };
}

function fixture() {
  return { ...alert, fields: [{ name: '注意点', value: riskNote }], capitalRiskReview: {
    version: 1, analysisCutoff: cutoff, status: 'outstanding', historyCheckedThrough: cutoff,
    documents: [document('financial', 'financial_baseline', '2026-08-13T15:00:00+09:00'),
      { ...document('issue', 'issuance', '2014-07-10', '第2回予約権の発行'), publishedAtPrecision: 'date_only' },
      document('balance', 'status', '2026-10-08T15:00:00+09:00', '未行使対象株式80,000株')],
    instruments: [{ id: 'series-2', type: 'warrant', status: 'outstanding', issueDocumentId: 'issue',
      statusDocumentId: 'balance', asOfDate: '2026-09-30', remainingUnderlyingShares: 80000,
      summary: '第2回の未行使分が残存する。新株交付分は未確認。' }], riskNote,
  } };
}

function none() {
  const report = fixture();
  report.capitalRiskReview.status = 'none_confirmed';
  report.capitalRiskReview.instruments = [];
  report.capitalRiskReview.documents = report.capitalRiskReview.documents.filter(item => item.kind === 'financial_baseline');
  report.capitalRiskReview.documents[0].finding = '新株予約権・転換社債等の潜在株式は全て残存していない。';
  report.capitalRiskReview.absenceEvidence = { documentId: 'financial', scope: 'all_dilutive_instruments',
    statement: '新株予約権・転換社債等の潜在株式は全て残存していない。' };
  return report;
}

test('an outstanding issue from twelve years ago is accepted without a lookback cap', () => {
  assert.equal(validateCapitalRiskReview(fixture(), alert), 'outstanding');
});

test('no recent financing notice cannot be used as proof of no outstanding instruments', () => {
  const report = none();
  delete report.capitalRiskReview.absenceEvidence;
  assert.throws(() => validateCapitalRiskReview(report, alert), /explicit all-instrument absence evidence/);
  report.capitalRiskReview.absenceEvidence = { documentId: 'issue', scope: 'all_dilutive_instruments', statement: '古い発行だけ確認' };
  assert.throws(() => validateCapitalRiskReview(report, alert), /absence evidence/);
});

test('a discovered issuance cannot be dropped from the instrument inventory to claim absence', () => {
  const report = none();
  report.capitalRiskReview.documents.push(fixture().capitalRiskReview.documents[1]);
  assert.throws(() => validateCapitalRiskReview(report, alert), /every reviewed issuance must be accounted for/);
});

test('a claimed zero verdict needs the latest financial baseline and history checked through cutoff', () => {
  assert.equal(validateCapitalRiskReview(none(), alert), 'none_confirmed');
  for (const change of [review => { review.historyCheckedThrough = null; },
    review => { review.documents = review.documents.filter(item => item.kind !== 'financial_baseline'); }]) {
    const report = none();
    change(report.capitalRiskReview);
    assert.throws(() => validateCapitalRiskReview(report, alert), /financial baseline and history checked through cutoff/);
  }
});

test('an outstanding or unknown series cannot coexist with confirmed absence', () => {
  for (const status of ['outstanding', 'unresolved']) {
    const report = fixture();
    report.capitalRiskReview.status = 'none_confirmed';
    report.capitalRiskReview.absenceEvidence = none().capitalRiskReview.absenceEvidence;
    report.capitalRiskReview.instruments[0].status = status;
    if (status === 'unresolved') report.capitalRiskReview.instruments[0].unresolvedReason = '最新残高を確認できない';
    assert.throws(() => validateCapitalRiskReview(report, alert), /absence evidence|unresolved instruments/);
  }
});

test('partial exercise or cancellation does not close the remaining issue', () => {
  const report = fixture();
  report.capitalRiskReview.instruments[0].status = 'closed';
  report.capitalRiskReview.instruments[0].closureKind = 'cancelled';
  report.capitalRiskReview.documents[2].kind = 'closure';
  assert.throws(() => validateCapitalRiskReview(report, alert), /explicit full closure evidence and zero/);
  report.capitalRiskReview.instruments[0].remainingUnderlyingShares = 0;
  report.capitalRiskReview.status = 'none_confirmed';
  report.capitalRiskReview.absenceEvidence = none().capitalRiskReview.absenceEvidence;
  assert.equal(validateCapitalRiskReview(report, alert), 'none_confirmed');
});

test('a resolved remaining balance requires both original issue and current-status references', () => {
  for (const key of ['issueDocumentId', 'statusDocumentId']) {
    const report = fixture();
    report.capitalRiskReview.instruments[0][key] = 'missing';
    assert.throws(() => validateCapitalRiskReview(report, alert), /issuance and current-status document/);
  }
});

test('unknown quantities remain null with a reason; no zero or fabricated number is forced', () => {
  const report = fixture();
  report.capitalRiskReview.instruments[0].remainingUnderlyingShares = null;
  assert.throws(() => validateCapitalRiskReview(report, alert), /quantityUncertainty/);
  report.capitalRiskReview.instruments[0].quantityUncertainty = '残存は確認できたが分割後の対象株数は照合不能';
  assert.equal(validateCapitalRiskReview(report, alert), 'outstanding');
  for (const quantity of [0, -1, 1.5, '80000', undefined, true]) {
    report.capitalRiskReview.instruments[0].remainingUnderlyingShares = quantity;
    assert.throws(() => validateCapitalRiskReview(report, alert), /remainingUnderlyingShares|zero balance/);
  }
});

test('unresolved research can be saved only with its specific uncertainty visible in 注意点', () => {
  const report = fixture();
  report.capitalRiskReview = { version: 1, analysisCutoff: cutoff, status: 'unresolved',
    historyCheckedThrough: null, documents: [], instruments: [],
    unresolvedReason: '第2回新株予約権の取得消却後の残高資料が確認できない',
    riskNote: '第2回新株予約権の現在残高を確認できず、希薄化リスクの有無は未確認。' };
  assert.throws(() => validateCapitalRiskReview(report, alert), /must appear in 注意点/);
  report.fields[0].value = report.capitalRiskReview.riskNote;
  assert.equal(validateCapitalRiskReview(report, alert), 'unresolved');
  delete report.capitalRiskReview.unresolvedReason;
  assert.throws(() => validateCapitalRiskReview(report, alert), /missing-evidence reason/);
});

test('confirmed remaining risks cannot silently disappear from the public caveats', () => {
  const report = fixture();
  report.fields[0].value = '通常の売上変動に注意。';
  assert.throws(() => validateCapitalRiskReview(report, alert), /must appear in 注意点/);
});

test('capital evidence follows the exact cutoff including nanosecond precision', () => {
  const report = fixture();
  report.capitalRiskReview.documents[2].publishedAt = cutoff;
  assert.equal(validateCapitalRiskReview(report, alert), 'outstanding');
  report.capitalRiskReview.documents[2].publishedAt = '2026-10-09T01:00:00.123456790Z';
  assert.throws(() => validateCapitalRiskReview(report, alert), /post-cutoff document/);
});

test('date-only primary evidence is allowed before cutoff day, never on that day', () => {
  const report = fixture();
  report.capitalRiskReview.documents[2].publishedAtPrecision = 'date_only';
  report.capitalRiskReview.documents[2].publishedAt = '2026-10-08';
  assert.equal(validateCapitalRiskReview(report, alert), 'outstanding');
  report.capitalRiskReview.documents[2].publishedAt = '2026-10-09';
  assert.throws(() => validateCapitalRiskReview(report, alert), /must predate/);
});

test('future or invalid balance dates and reversed issuance/status ordering are rejected', () => {
  for (const asOfDate of ['2026-10-10', '2026-02-30', '2010-01-01']) {
    const report = fixture();
    report.capitalRiskReview.instruments[0].asOfDate = asOfDate;
    assert.throws(() => validateCapitalRiskReview(report, alert), /balance date|valid YYYY/);
  }
  const report = fixture();
  report.capitalRiskReview.documents[2].publishedAt = '2013-01-01T15:00:00+09:00';
  assert.throws(() => validateCapitalRiskReview(report, alert), /cannot precede issuance/);
});

test('unreviewed, ambiguous and direct EDINET evidence is rejected', () => {
  for (const change of [doc => { doc.contentReviewed = false; }, doc => { doc.locator = ''; },
    doc => { doc.finding = ''; }, doc => { doc.url = 'https://disclosure.edinet-fsa.go.jp/filing.pdf'; },
    doc => { doc.publishedAt = '2026-02-30T15:00:00+09:00'; }, doc => { doc.publishedAt = '2026-10-08'; }]) {
    const report = fixture();
    change(report.capitalRiskReview.documents[2]);
    assert.throws(() => validateCapitalRiskReview(report, alert));
  }
});

test('new-generation claims require the review; older completed/import-only snapshots are preserved', () => {
  const reports = [{ ...alert }];
  assert.equal(validateClaimCapitalRiskReviews({ alerts: [alert] }, reports), 0);
  assert.throws(() => validateClaimCapitalRiskReviews({ capitalRiskReviewVersion: 1, alerts: [alert] }, reports), /requires version 1/);
  assert.throws(() => validateClaimCapitalRiskReviews({ alerts: [alert] }, reports,
    { claims: { [alert.alertId]: { capitalRiskReviewVersion: 1 } } }), /requires version 1/);
  assert.equal(validateClaimCapitalRiskReviews({ capitalRiskReviewVersion: 1, alerts: [alert] }, [fixture()]), 1);
});

test('new stamp persists the capital contract into owned state and survives report reuse', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-capital-risk-'));
  try {
    const statePath = path.join(root, 'state.json');
    const claim = { claimId: 'owned', alerts: [{ ...alert }] };
    fs.writeFileSync(statePath, JSON.stringify({ claims: { [alert.alertId]: { claimId: 'owned' } } }));
    const stamped = stampAnalysisStart(statePath, claim, cutoff);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    assert.equal(stamped.capitalRiskReviewVersion, 1);
    assert.equal(stamped.alerts[0].capitalRiskReviewVersion, 1);
    assert.equal(state.claims[alert.alertId].capitalRiskReviewVersion, 1);
    assert.throws(() => validateClaimCapitalRiskReviews(stamped, [{ ...alert }], state), /requires version 1/);
    assert.equal(validateClaimCapitalRiskReviews(stamped, [fixture()], state), 1);
    assert.equal(claim.capitalRiskReviewVersion, undefined);
  } finally {
    const resolved = path.resolve(root);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('cloud-capital-risk-')) throw new Error('unexpected fixture path');
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('the actual runner rejects a reused new-contract report before any save/import child starts', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-capital-risk-runner-'));
  try {
    const beta = path.join(root, 'repo', 'weak_early_beta', 'fundamental_worker');
    const statePath = path.join(beta, 'state', 'premium_alert_state.json');
    const out = path.join(beta, 'out');
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.mkdirSync(out, { recursive: true });
    fs.mkdirSync(path.join(root, 'premium'), { recursive: true });
    const claim = { claimId: 'owned', claimedCount: 1, capitalRiskReviewVersion: 1, alerts: [{ ...alert }] };
    const state = { claims: { [alert.alertId]: { claimId: 'owned', capitalRiskReviewVersion: 1, ...alert } }, completed: {} };
    const stateText = JSON.stringify(state);
    fs.writeFileSync(statePath, stateText);
    fs.writeFileSync(path.join(out, 'latest_claim.json'), JSON.stringify(claim));
    fs.writeFileSync(path.join(out, 'premium_reports.json'), JSON.stringify({ reports: [{ ...alert }] }));
    const config = path.join(root, 'config.json');
    fs.writeFileSync(config, JSON.stringify({ repoPath: path.join(root, 'repo'),
      premiumWorkerRepoPath: path.join(root, 'premium'), runtimeDir: path.join(root, 'runtime'),
      nodePath: process.execPath, pythonPath: path.join(root, 'must-never-start-python'), codexHome: root }));
    const runner = fileURLToPath(new URL('./weak-early-beta-fundamental-runner.mjs', import.meta.url));
    const result = spawnSync(process.execPath, [runner, config], { encoding: 'utf8', timeout: 10000, windowsHide: true });
    assert.equal(result.status, 1, result.stderr);
    const receipt = JSON.parse(result.stdout.trim());
    assert.equal(receipt.reusedClaimMatchedReport, true);
    assert.match(receipt.error, /capitalRiskReview .*requires version 1/);
    assert.equal(receipt.validatedReportPath, undefined);
    assert.equal(fs.readFileSync(statePath, 'utf8'), stateText);
    assert.equal(fs.existsSync(path.join(receipt.runDir, 'save-snapshot.stdout')), false);
    assert.equal(fs.existsSync(path.join(receipt.runDir, 'validate-analysis-start.stdout')), false);
  } finally {
    const resolved = path.resolve(root);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('cloud-capital-risk-runner-')) throw new Error('unexpected fixture path');
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('the Cloud prompt preserves sourceChecks and requires historical capital lifecycle research', () => {
  const example = JSON.parse(CLOUD_REPORT_CONTRACT.split('\n').find(line => line.startsWith('{')));
  assert.ok(Array.isArray(example.sourceChecks));
  assert.match(CLOUD_REPORT_CONTRACT, /年数上限を設けません/);
  assert.match(CLOUD_REPORT_CONTRACT, /一部消却や一部行使を全数終了と扱わない/);
  assert.match(CLOUD_REPORT_CONTRACT, /自己株式の交付/);
  assert.match(CLOUD_REPORT_CONTRACT, /未公表・照合不能の数値は推定せずnull/);
  assert.match(CLOUD_REPORT_CONTRACT, /capitalRiskReview/);
});
