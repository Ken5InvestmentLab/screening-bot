import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { LONG_TERM_MATERIAL_CATEGORIES, validateLongTermMaterialReview,
  validateClaimLongTermMaterialReviews } from './weak-early-beta-long-term-materials.mjs';
import { stampAnalysisStart, CLOUD_REPORT_CONTRACT } from './weak-early-beta-fundamental-runner.mjs';

const cutoff = '2026-10-09T01:00:00.123456789Z';
const alert = { alertId: 'weak-early-beta:2026-10-08:1234', signalType: 'WEAK_EARLY_BETA',
  signalDate: '2026-10-08', analysisCutoff: cutoff };
const assessment = '新工場は商業稼働予定の時期に達しているが、製品売上への反映実績は未確認。';

function document(id, kind, publishedAt) {
  return { id, kind, source: 'official_ir', title: `${id}資料`,
    url: `https://issuer.example/ir/${id}.pdf`, publishedAt,
    contentReviewed: true, locator: '事業進捗の説明', finding: '会社が公表した具体的な計画と進捗' };
}

function fixture() {
  return { ...alert, fields: [{ name: 'ファンダ要点', value: assessment }, { name: '注意点', value: assessment }],
    longTermMaterialReview: { version: 1, analysisCutoff: cutoff, conclusion: 'active_materials',
      historyCheckedThrough: cutoff, reviewedCategories: [...LONG_TERM_MATERIAL_CATEGORIES],
      reviewScopeNote: '最新決算の新工場計画と公式IR事業進捗を照合し、各カテゴリの継続事項を確認。',
      documents: [document('financial', 'financial_baseline', '2026-08-13T15:00:00+09:00'),
        { ...document('original', 'original_announcement', '2014-07-10'), publishedAtPrecision: 'date_only' },
        document('progress', 'progress', '2026-09-15T15:00:00+09:00')],
      items: [{ id: 'plant', category: 'investment_capacity', direction: 'positive', status: 'in_progress',
        originalDocumentId: 'original', latestProgressDocumentId: 'progress', currentAssessment: assessment,
        reportedTiming: { documentId: 'progress', statement: '商業稼働を2026年9月30日に開始する予定。', dueDate: '2026-09-30' },
        timingReachedButContributionUnconfirmed: true, riskNote: assessment }],
    } };
}

function noRelevant() {
  const report = fixture();
  report.longTermMaterialReview.conclusion = 'no_relevant_found';
  report.longTermMaterialReview.items = [];
  report.longTermMaterialReview.documents = report.longTermMaterialReview.documents.filter(doc => doc.kind === 'financial_baseline');
  return report;
}

test('an old positive investment is tracked to current progress without a year cap', () => {
  assert.equal(validateLongTermMaterialReview(fixture(), alert), 'active_materials');
});

test('negative and mixed long-running matters use the same current assessment contract', () => {
  for (const [category, direction, status] of [['legal_regulatory', 'negative', 'delayed'],
    ['orders_contracts', 'mixed', 'in_progress'], ['approvals_subsidies', 'positive', 'planned']]) {
    const report = fixture();
    Object.assign(report.longTermMaterialReview.items[0], { category, direction, status });
    assert.equal(validateLongTermMaterialReview(report, alert), 'active_materials');
  }
});

test('elapsed announced timing remains distinct from actual contribution', () => {
  const report = fixture();
  report.longTermMaterialReview.items[0].status = 'contributing';
  assert.throws(() => validateLongTermMaterialReview(report, alert), /reported actual revenue\/profit evidence/);
  report.longTermMaterialReview.items[0].actualContribution = { documentId: 'progress', metric: 'revenue',
    basis: 'company_forecast', statement: '売上に寄与する予定。' };
  assert.throws(() => validateLongTermMaterialReview(report, alert), /reported actual revenue\/profit evidence/);
  report.longTermMaterialReview.items[0].actualContribution.basis = 'reported_actual';
  assert.throws(() => validateLongTermMaterialReview(report, alert), /elapsed timing/);
  delete report.longTermMaterialReview.items[0].timingReachedButContributionUnconfirmed;
  report.longTermMaterialReview.items[0].actualContribution.statement = '会社は新工場製品の売上計上を実績として説明。';
  assert.equal(validateLongTermMaterialReview(report, alert), 'active_materials');
});

test('an original promise or future source is insufficient for realized contribution', () => {
  const report = fixture();
  const item = report.longTermMaterialReview.items[0];
  item.status = 'contributing';
  delete item.timingReachedButContributionUnconfirmed;
  item.actualContribution = { documentId: 'original', metric: 'profit', basis: 'reported_actual', statement: '利益寄与予定' };
  assert.throws(() => validateLongTermMaterialReview(report, alert), /reported actual revenue\/profit evidence/);
  item.actualContribution.documentId = 'progress';
  report.longTermMaterialReview.documents[2].publishedAt = '2026-10-09T01:00:00.123456790Z';
  assert.throws(() => validateLongTermMaterialReview(report, alert), /post-cutoff document/);
});

test('actual contribution and reported timing cannot use evidence predating the original event', () => {
  const contribution = fixture();
  const item = contribution.longTermMaterialReview.items[0];
  item.status = 'contributing';
  delete item.timingReachedButContributionUnconfirmed;
  contribution.longTermMaterialReview.documents.push(document('older-financial', 'financial_baseline', '2013-07-01T15:00:00+09:00'));
  item.actualContribution = { documentId: 'older-financial', metric: 'revenue', basis: 'reported_actual', statement: '売上に反映済み。' };
  assert.throws(() => validateLongTermMaterialReview(contribution, alert), /contribution evidence cannot predate/);
  const timing = fixture();
  timing.longTermMaterialReview.documents.push(document('older-progress', 'progress', '2013-07-01T15:00:00+09:00'));
  timing.longTermMaterialReview.items[0].reportedTiming.documentId = 'older-progress';
  assert.throws(() => validateLongTermMaterialReview(timing, alert), /timing evidence cannot predate/);
});

test('unconfirmed statuses cannot carry a claimed actual contribution', () => {
  const report = fixture();
  report.longTermMaterialReview.items[0].actualContribution = { documentId: 'progress', metric: 'revenue',
    basis: 'reported_actual', statement: '寄与済み' };
  assert.throws(() => validateLongTermMaterialReview(report, alert), /unconfirmed statuses/);
});

test('an ambiguous company timetable is preserved without inventing a reached date', () => {
  const report = fixture();
  const item = report.longTermMaterialReview.items[0];
  item.reportedTiming = { documentId: 'progress', statement: '2026年度内の収益化を予定。', dueDate: null };
  assert.throws(() => validateLongTermMaterialReview(report, alert), /elapsed timing/);
  delete item.timingReachedButContributionUnconfirmed;
  assert.equal(validateLongTermMaterialReview(report, alert), 'active_materials');
  item.reportedTiming.dueDate = '2026-02-30';
  assert.throws(() => validateLongTermMaterialReview(report, alert), /valid YYYY-MM-DD/);
});

test('a future or same-day due date cannot be called reached at the analysis start', () => {
  for (const dueDate of ['2026-10-09', '2026-10-10']) {
    const report = fixture();
    report.longTermMaterialReview.items[0].reportedTiming.dueDate = dueDate;
    assert.throws(() => validateLongTermMaterialReview(report, alert), /elapsed timing/);
  }
});

test('continuing items need current assessment in the report and origins/latest progress references', () => {
  for (const change of [item => { item.currentAssessment = '本文にない会社固有の進捗'; },
    item => { item.originalDocumentId = 'missing'; }, item => { item.latestProgressDocumentId = 'missing'; }]) {
    const report = fixture();
    change(report.longTermMaterialReview.items[0]);
    assert.throws(() => validateLongTermMaterialReview(report, alert), /public analysis|original and latest progress/);
  }
});

test('an original-only announcement can remain planned after baseline/history review, not in-progress', () => {
  const report = fixture();
  const item = report.longTermMaterialReview.items[0];
  item.status = 'planned';
  item.latestProgressDocumentId = 'original';
  assert.equal(validateLongTermMaterialReview(report, alert), 'active_materials');
  item.status = 'in_progress';
  assert.throws(() => validateLongTermMaterialReview(report, alert), /original and latest progress references/);
});

test('empty reviewed results are valid only after baseline/history and broad category coverage', () => {
  assert.equal(validateLongTermMaterialReview(noRelevant(), alert), 'no_relevant_found');
  for (const change of [review => { review.reviewedCategories.pop(); }, review => { review.documents = []; },
    review => { review.historyCheckedThrough = null; }]) {
    const report = noRelevant();
    change(report.longTermMaterialReview);
    assert.throws(() => validateLongTermMaterialReview(report, alert), /all categories, latest official financial baseline/);
  }
});

test('a discovered original announcement cannot be omitted to claim no relevant matter found', () => {
  const report = noRelevant();
  report.longTermMaterialReview.documents.push(fixture().longTermMaterialReview.documents[1]);
  assert.throws(() => validateLongTermMaterialReview(report, alert), /every reviewed original announcement/);
  const active = fixture();
  active.longTermMaterialReview.conclusion = 'no_relevant_found';
  assert.throws(() => validateLongTermMaterialReview(active, alert), /continuing items prohibit/);
});

test('a verified ended matter can explain why it is not current material', () => {
  const report = fixture();
  const item = report.longTermMaterialReview.items[0];
  item.status = 'ended';
  delete item.timingReachedButContributionUnconfirmed;
  report.longTermMaterialReview.conclusion = 'no_relevant_found';
  report.longTermMaterialReview.documents[2].finding = '新工場計画の撤回を会社が公表。';
  assert.equal(validateLongTermMaterialReview(report, alert), 'no_relevant_found');
});

test('missing long-term evidence is reported as unresolved, never as no relevant matter', () => {
  const report = fixture();
  const review = report.longTermMaterialReview;
  review.conclusion = 'unresolved';
  review.historyCheckedThrough = null;
  review.unresolvedReason = '古い設備計画の最新の収益化実績が確認できない';
  review.riskNote = assessment;
  review.items[0].status = 'unresolved';
  review.items[0].originalDocumentId = null;
  review.items[0].unresolvedReason = review.unresolvedReason;
  assert.equal(validateLongTermMaterialReview(report, alert), 'unresolved');
  review.conclusion = 'no_relevant_found';
  review.historyCheckedThrough = cutoff;
  assert.throws(() => validateLongTermMaterialReview(report, alert), /unresolved items/);
  review.conclusion = 'unresolved';
  report.fields[1].value = '通常の需給に注意。';
  assert.throws(() => validateLongTermMaterialReview(report, alert), /must appear in 注意点/);
});

test('both directions are researched in the prompt with timing-based as-of meaning, not title listing', () => {
  assert.match(CLOUD_REPORT_CONTRACT, /好材料・悪材料の両方/);
  assert.match(CLOUD_REPORT_CONTRACT, /提携\/大型受注\/契約\/設備投資/);
  assert.match(CLOUD_REPORT_CONTRACT, /原発表/);
  assert.match(CLOUD_REPORT_CONTRACT, /公表計画どおりなら今は収益化期に近い/);
  assert.match(CLOUD_REPORT_CONTRACT, /未公表の将来業績を予測/);
  assert.match(CLOUD_REPORT_CONTRACT, /世の中に材料が全くないと断定する値ではありません/);
});

test('new stamps enforce long-term review on reuse while old imports stay unchanged', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-long-term-stamp-'));
  try {
    const statePath = path.join(root, 'state.json');
    const claim = { claimId: 'owned', alerts: [alert] };
    fs.writeFileSync(statePath, JSON.stringify({ claims: { [alert.alertId]: { claimId: 'owned' } } }));
    const stamped = stampAnalysisStart(statePath, claim, cutoff);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    assert.equal(stamped.longTermMaterialReviewVersion, 1);
    assert.equal(stamped.alerts[0].longTermMaterialReviewVersion, 1);
    assert.equal(state.claims[alert.alertId].longTermMaterialReviewVersion, 1);
    assert.equal(validateClaimLongTermMaterialReviews(claim, [{ ...alert }]), 0);
    assert.throws(() => validateClaimLongTermMaterialReviews(stamped, [{ ...alert }], state), /requires version 1/);
    assert.equal(validateClaimLongTermMaterialReviews(stamped, [fixture()], state), 1);
    assert.throws(() => validateClaimLongTermMaterialReviews(claim, [{ ...alert }], state), /requires version 1/);
  } finally {
    const resolved = path.resolve(root);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('cloud-long-term-stamp-')) throw new Error('unexpected fixture path');
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('actual runner stops a reused long-term-contract report before state save/import', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-long-term-runner-'));
  try {
    const beta = path.join(root, 'repo', 'weak_early_beta', 'fundamental_worker');
    const statePath = path.join(beta, 'state', 'premium_alert_state.json');
    const out = path.join(beta, 'out');
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.mkdirSync(out, { recursive: true });
    fs.mkdirSync(path.join(root, 'premium'), { recursive: true });
    const claim = { claimId: 'owned', claimedCount: 1, longTermMaterialReviewVersion: 1, alerts: [alert] };
    const stateText = JSON.stringify({ claims: { [alert.alertId]: { claimId: 'owned', longTermMaterialReviewVersion: 1, ...alert } } });
    fs.writeFileSync(statePath, stateText);
    fs.writeFileSync(path.join(out, 'latest_claim.json'), JSON.stringify(claim));
    fs.writeFileSync(path.join(out, 'premium_reports.json'), JSON.stringify({ reports: [{ ...alert }] }));
    const config = path.join(root, 'config.json');
    fs.writeFileSync(config, JSON.stringify({ repoPath: path.join(root, 'repo'), premiumWorkerRepoPath: path.join(root, 'premium'),
      runtimeDir: path.join(root, 'runtime'), nodePath: process.execPath, pythonPath: path.join(root, 'must-not-start'), codexHome: root }));
    const runner = fileURLToPath(new URL('./weak-early-beta-fundamental-runner.mjs', import.meta.url));
    const result = spawnSync(process.execPath, [runner, config], { encoding: 'utf8', timeout: 10000, windowsHide: true });
    assert.equal(result.status, 1, result.stderr);
    const receipt = JSON.parse(result.stdout.trim());
    assert.equal(receipt.capitalRiskReviewsValidated, 0);
    assert.equal(receipt.reusedClaimMatchedReport, true);
    assert.match(receipt.error, /longTermMaterialReview .*requires version 1/);
    assert.equal(fs.readFileSync(statePath, 'utf8'), stateText);
    assert.equal(fs.existsSync(path.join(receipt.runDir, 'save-snapshot.stdout')), false);
  } finally {
    const resolved = path.resolve(root);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('cloud-long-term-runner-')) throw new Error('unexpected fixture path');
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});
