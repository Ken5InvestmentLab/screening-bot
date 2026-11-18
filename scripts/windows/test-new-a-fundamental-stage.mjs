import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { runNewAFundamentalStage } from './new-a-fundamental-stage.mjs';

test('same-login xhigh model, exact owned report bytes and HTML-only dry-run are wired', async t => {
  const repo = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'new-a-fundamental-stage-')));
  t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
  const today = '2026-11-18';
  const cutoff = today + 'T08:10:00.000Z';
  const claimDir = path.join(repo, '.cache', 'weak_early_beta', 'new-a-private', 'runs', today, 'source', 'live', 'fundamental-analysis');
  fs.mkdirSync(claimDir, { recursive: true });
  const claimPath = path.join(claimDir, 'claim.json');
  const reportsPath = path.join(claimDir, 'reports.json');
  const runtime = path.join(repo, '.cache', 'runtime');
  const runDir = path.join(runtime, 'run-1');
  const modelPath = path.join(repo, 'synthetic-codex.exe');
  const configPath = path.join(repo, 'synthetic-fundamental.json');
  fs.writeFileSync(modelPath, '');
  fs.writeFileSync(configPath, JSON.stringify({ repoPath: repo, premiumWorkerRepoPath: repo, codexHome: repo,
    nodePath: process.execPath, codexExecutable: modelPath }));
  const alert = {
    alertId: 'test-owned-event', analysisCutoff: cutoff, signalType: 'WEAK_EARLY_BETA',
    capitalRiskReviewVersion: 1, longTermMaterialReviewVersion: 1,
  };
  fs.writeFileSync(claimPath, JSON.stringify({
    alerts: [alert], claimedCount: 1, capitalRiskReviewVersion: 1, longTermMaterialReviewVersion: 1,
    rules: { model: 'gpt-6.1-sol', reasoningEffort: 'xhigh', destination: 'html' },
  }));
  fs.writeFileSync(path.join(repo, '.env'), 'DISCORD_TEST_TOKEN=FIXTURE_SECRET_VALUE\n');
  const report = {
    ...alert,
    fields: [{ name: '注意点', value: '未確認の資本政策と長期材料。' }],
    capitalRiskReview: { version: 1, analysisCutoff: cutoff, status: 'unresolved', historyCheckedThrough: null,
      instruments: [], documents: [], riskNote: '未確認の資本政策', unresolvedReason: '情報不足' },
    longTermMaterialReview: { version: 1, analysisCutoff: cutoff, conclusion: 'unresolved', historyCheckedThrough: null,
      items: [], reviewedCategories: [], documents: [], reviewScopeNote: '部分照合', riskNote: '長期材料',
      unresolvedReason: '情報不足' },
  };
  const calls = [];
  const received = await runNewAFundamentalStage({
    config: { pythonPath: 'synthetic-python', nodePath: 'synthetic-node', fundamentalConfigPath: configPath },
    repo, runtime, today, startedAt: today + 'T08:00:00Z', runDir, env: {}, expectedCount: 1,
    async runStep(_exe, args) {
      if (args.includes('prepare')) {
        calls.push('prepare');
        return { stdout: JSON.stringify({ claimed: 1, claimPath, reportsPath }) };
      }
      if (args.includes('finish')) {
        calls.push('finish');
        assert.equal(args[args.indexOf('--reports-sha256') + 1],
          createHash('sha256').update(fs.readFileSync(reportsPath)).digest('hex'));
        return { stdout: JSON.stringify({ ok: true, imported: 1, posted: 0, status: 'COMPLETE' }) };
      }
      assert(args.includes('--dry-run') && args.includes('--save-only'));
      const state = JSON.parse(fs.readFileSync(args[args.indexOf('--state') + 1], 'utf8'));
      assert.deepEqual(state.claims[alert.alertId], alert);
      calls.push('audited-html-only');
      return { stdout: '' };
    },
    async invokeAnalysis(exe, args, options) {
      calls.push('model');
      assert.equal(exe, modelPath);
      assert(args.includes('gpt-6.1-sol') && args.includes('model_reasoning_effort="xhigh"'));
      assert(args.includes('forced_login_method="chatgpt"') && args.includes('workspace-write'));
      assert.equal(options.env.DISCORD_TEST_TOKEN, undefined);
      assert.equal(options.cwd, claimDir);
      fs.writeFileSync(reportsPath, JSON.stringify({ reports: [report] }));
      return 0;
    },
  });
  assert.deepEqual(calls, ['prepare', 'model', 'audited-html-only', 'finish']);
  assert.equal(received.imported, 1);
});
