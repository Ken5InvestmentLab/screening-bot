import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { runNewAFundamentalStage, verifyPremiumDirectUrls } from './new-a-fundamental-stage.mjs';

test('Cloud copies the completed legacy workflow, repairs named reports, validates the full batch without posting', async t => {
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
    alertId: 'test-owned-event', symbolCode: '1234', symbolName: '試験企業', signalDate: today,
    receivedAt: today + 'T08:09:00.000Z', analysisCutoff: cutoff, signalType: 'WEAK_EARLY_BETA',
    capitalRiskReviewVersion: 1, longTermMaterialReviewVersion: 1,
  };
  const secondAlert = { ...alert, alertId: 'second-owned-event', symbolCode: '2345' };
  const claimId = 'a'.repeat(64);
  const claim = {
    claimId, alerts: [alert, secondAlert], claimedCount: 2, capitalRiskReviewVersion: 1, longTermMaterialReviewVersion: 1,
    rules: { model: 'gpt-6.1-sol', reasoningEffort: 'xhigh', destination: 'html', workflow: 'premium-legacy-1fa6d89' },
  };
  fs.writeFileSync(claimPath, JSON.stringify(claim));
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
  const secondReport = { ...report, ...secondAlert };
  const calls = [];
  let repaired = false;
  const options = {
    config: { pythonPath: 'synthetic-python', nodePath: 'synthetic-node', fundamentalConfigPath: configPath },
    repo, runtime, today, startedAt: today + 'T08:00:00Z', runDir, env: { TEST_API_TOKEN: 'PARENT_SECRET_FIXTURE' }, expectedCount: 2,
    async runStep(_exe, args, options) {
      if (args.includes('prepare')) {
        calls.push('prepare');
        return { stdout: JSON.stringify({ claimed: 2, claimPath, reportsPath }) };
      }
      if (args.includes('finish')) {
        calls.push('finish');
        assert.equal(args[args.indexOf('--reports-sha256') + 1],
          createHash('sha256').update(fs.readFileSync(reportsPath)).digest('hex'));
        assert.deepEqual(JSON.parse(fs.readFileSync(reportsPath, 'utf8')),
          { claimId, reports: [report, { ...secondReport, repaired: true }] });
        return { stdout: JSON.stringify({ ok: true, imported: 2, posted: 0, status: 'COMPLETE' }) };
      }
      if (args.includes('-c')) {
        assert.equal(args.at(-2), claimPath);
        assert.equal(path.basename(args.at(-1)), 'pending-reports.json');
        calls.push('python-check-all');
        return { stdout: '{}' };
      }
      if (args.includes('post')) {
        assert(args.includes('--dry-run') && !args.includes('--save-only') && args[0] === '--import');
        assert(options.env.DISCORD_PREMIUM_WEBHOOK_URL === undefined);
        assert.equal(createHash('sha256').update(fs.readFileSync(args[2])).digest('hex'),
          '98edbc6921dfcad6b853660a1d1bc6e508ef684f71d29732960330a53cb80dc3');
        const input = JSON.parse(fs.readFileSync(args[args.indexOf('--input') + 1]));
        calls.push('legacy:' + input.reports.map(r => r.symbolCode).join(','));
        if (input.reports.some(r => r.alertId === secondAlert.alertId && !repaired)) throw Error('company-specific KPI is missing');
        return { stdout: JSON.stringify({ ok: true, posted: 0,
          results: input.reports.map(report => ({ alertId: report.alertId, dryRun: true })) }) };
      }
      assert(args.includes('--dry-run') && args.includes('--save-only'));
      const state = JSON.parse(fs.readFileSync(args[args.indexOf('--state') + 1], 'utf8'));
      const [alertId] = Object.keys(state.claims);
      assert.deepEqual(state.claims[alertId], alertId === alert.alertId ? alert : secondAlert);
      calls.push('audited-html-only:' + state.claims[alertId].symbolCode);
      return { stdout: JSON.stringify({ ok: true, dryRun: true, alertId, analysisCutoff: cutoff }) };
    },
    async invokeAnalysis(exe, args, options) {
      assert.equal(exe, modelPath);
      assert(args.includes('gpt-6.1-sol') && args.includes('model_reasoning_effort="xhigh"'));
      assert(args.includes('forced_login_method="chatgpt"') && args.includes('workspace-write'));
      assert.equal(options.env.DISCORD_TEST_TOKEN, undefined);
      assert.equal(options.env.TEST_API_TOKEN, undefined);
      assert.equal(options.cwd, claimDir);
      assert.match(options.input, /PREMIUM_PM_SAVED_PROMPT.txt/);
      assert.match(options.input, /11\/2版Premium/);
      assert(!options.input.includes('DISCLOSURE_AUDIT.md'));
      assert(!options.input.includes('capitalRiskReview') && !options.input.includes('longTermMaterialReview'));
      const output = options.input.match(/今回の書き込み先は (.+) のみです。$/u)[1];
      assert.equal(path.dirname(output), claimDir);
      const stage = path.basename(output);
      if (stage.startsWith('initial-drafts-')) {
        calls.push('model-draft-all');
        fs.writeFileSync(output, JSON.stringify({ claimId, reports: [report, secondReport] }));
      } else {
        assert(stage.startsWith('repair-1-'));
        calls.push('model-repair-one');
        assert.match(options.input, /執筆対象のalertId: \["second-owned-event"\]/);
        assert.match(options.input, /company-specific KPI is missing/);
        repaired = true;
        fs.writeFileSync(output, JSON.stringify({ claimId, reports: [{ ...secondReport, repaired: true }] }));
      }
      return 0;
    },
    async checkDirectUrls(reports) {
      calls.push('direct-urls-all');
      assert(reports.length === 1 || reports.length === 2);
    },
  };
  const received = await runNewAFundamentalStage(options);
  assert.deepEqual(calls, [
    'prepare', 'model-draft-all', 'python-check-all', 'audited-html-only:1234', 'audited-html-only:2345',
    'direct-urls-all', 'legacy:1234,2345', 'direct-urls-all', 'legacy:1234', 'direct-urls-all', 'legacy:2345',
    'model-repair-one', 'python-check-all', 'audited-html-only:1234', 'audited-html-only:2345',
    'direct-urls-all', 'legacy:1234,2345', 'finish',
  ]);
  assert.equal(received.imported, 2);

  const retained = path.join(repo, '.cache', 'weak_early_beta', 'new-a-private', 'fundamentals', 'verified', `${today}.json`);
  fs.mkdirSync(path.dirname(retained), { recursive: true });
  fs.writeFileSync(retained, JSON.stringify({ claim, reports: JSON.parse(fs.readFileSync(reportsPath)).reports }));
  calls.length = 0;
  assert.equal((await runNewAFundamentalStage(options)).imported, 2);
  assert.deepEqual(calls, ['prepare', 'finish']);
  fs.unlinkSync(retained);
  fs.unlinkSync(path.join(claimDir, 'pending-reports.json'));
  fs.unlinkSync(reportsPath);
  calls.length = 0;
  options.invokeAnalysis = async () => 1;
  await assert.rejects(runNewAFundamentalStage(options), error => error.cloudFundamentalHeld === true);
  assert.deepEqual(calls, ['prepare']);
  assert(fs.existsSync(claimPath));

});


test('all direct disclosure URLs are requested, deduplicated and failures remain failures', async () => {
  const report = { fields: [{ name: '開示リンク', value:
    '[資料](https://example.com/a.pdf)\n[同じ資料](https://example.com/a.pdf)\n[別資料](https://example.com/b.pdf)' }] };
  const requested = [];
  await verifyPremiumDirectUrls([report], async (url, options) => {
    requested.push(url);
    assert.equal(options.method, 'GET');
    return { ok: true, status: 200, body: { async cancel() {} } };
  });
  assert.deepEqual(requested.sort(), ['https://example.com/a.pdf', 'https://example.com/b.pdf']);
  await assert.rejects(verifyPremiumDirectUrls([report], async () => ({ok:false,status:404})), /HTTP 404/);
  await assert.rejects(verifyPremiumDirectUrls([{ fields: [{name:'開示リンク',value:'[bad](https://127.0.0.1/a)'}] }],
    async () => { throw Error('must not request private address'); }), /public HTTPS/);
});
