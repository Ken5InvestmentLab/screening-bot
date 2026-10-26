import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { CLOUD_REPORT_CONTRACT, finalizeHtmlSnapshots } from './weak-early-beta-fundamental-runner.mjs';

const poster = path.resolve('weak_early_beta/scripts/post_historical_snapshot.mjs');

test('long forward evidence is preserved for HTML and rejected before Discord send', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-long-evidence-'));
  try {
    const report = validReport();
    report.auditStatus = 'pass';
    report.disclosures = Array.from({length:20}, (_,i) => ({title:`資料${i}`, publishedAt:'2026-09-30T15:30:00+09:00', url:`https://example.com/primary-evidence-document-${i}.pdf`, contentReviewed:true}));
    const links = report.disclosures.map((d,i)=>`・[2026-09-30 資料${i}(15:30)](${d.url})`).join('\n');
    report.fields.find(f=>f.name==='開示リンク').value = links;
    assert.ok([...links].length>1024);
    const statePath=path.join(fixture,'state.json'), reportPath=path.join(fixture,'report.json');
    const initial={claims:{[report.alertId]:{claimId:'long-evidence', symbolCode:report.symbolCode, signalDate:report.signalDate, signalType:'WEAK_EARLY_BETA', receivedAt:report.analysisCutoff, analysisCutoff:report.analysisCutoff}},posted:{},failed:{}};
    fs.writeFileSync(statePath,JSON.stringify(initial));fs.writeFileSync(reportPath,JSON.stringify({reports:[report]}));
    const run=args=>spawnSync(process.execPath,[poster,'--input',reportPath,'--state',statePath,...args],{encoding:'utf8',env:{...process.env,WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL:'http://127.0.0.1:1/must-not-send'}});
    const denied=run([]);assert.notEqual(denied.status,0);assert.match(denied.stderr,/1,000-character safety limit/);
    assert.deepEqual(JSON.parse(fs.readFileSync(statePath,'utf8')),initial);
    const saved=run(['--save-only']);assert.equal(saved.status,0,saved.stderr);assert.equal(JSON.parse(saved.stdout).posted,false);
    const state=JSON.parse(fs.readFileSync(statePath,'utf8'));assert.deepEqual(state.completed[report.alertId].report,report);assert.deepEqual(state.claims,initial.claims);assert.deepEqual(state.posted,{});
  } finally {fs.rmSync(fixture,{recursive:true,force:true});}
});

function validReport() {
  return {
    alertId: 'weak-early-beta:2026-09-30:4052',
    signalDate: '2026-09-30',
    symbolCode: '4052',
    symbolName: 'フィーチャ',
    analysisCutoff: '2026-09-30T16:15:00+09:00',
    fields: [
      { name: '材料インパクト', value: '様子見：一次資料の確認が必要。' },
      { name: '事業概要', value: '画像認識ソフトウェア。' },
      { name: '足元材料', value: '当日開示を確認。' },
      { name: 'ファンダ要点', value: '受注状況。' },
      { name: '注意点', value: '顧客集中。' },
      { name: '開示リンク', value: '・[2026-09-30 開示タイトル(15:30)](https://example.com/disclosure.pdf)' },
      { name: 'Sources', value: '・[IR一覧](https://example.com/ir)' },
    ],
  };
}

test('HTML snapshots need no webhook and retain claim ownership until import succeeds', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-html-snapshot-'));
  try {
    const statePath = path.join(fixture, 'state.json');
    const reportPath = path.join(fixture, 'report.json');
    const report = validReport();
    const claim = { claimId: 'test-claim', alerts: [{ alertId: report.alertId }] };
    const initial = {
      claims: { [report.alertId]: { claimId: claim.claimId, symbolCode: report.symbolCode, receivedAt: report.analysisCutoff } },
      posted: {}, failed: {},
    };
    fs.writeFileSync(statePath, JSON.stringify(initial));
    fs.writeFileSync(reportPath, JSON.stringify({ reports: [report] }));
    const run = (webhook = '') => spawnSync(process.execPath, [poster, '--input', reportPath, '--state', statePath, '--save-only'], {
      encoding: 'utf8',
      env: { ...process.env, WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL: webhook },
    });
    const saved = run();
    assert.equal(saved.status, 0, saved.stderr);
    assert.equal(JSON.parse(saved.stdout).posted, false);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    assert.deepEqual(state.posted, {});
    assert.deepEqual(state.claims, initial.claims);
    assert.deepEqual(state.completed[report.alertId].report, report);
    // An interrupted HTML import can safely reuse the immutable saved snapshot.
    assert.equal(run().status, 0);
    assert.equal(run('http://127.0.0.1:1/do-not-post').status, 0);
    assert.deepEqual(JSON.parse(fs.readFileSync(statePath, 'utf8')), state);
    report.fields[4].value = '顧客の集中に注意。';
    fs.writeFileSync(reportPath, JSON.stringify({ reports: [report] }));
    assert.match(run().stderr, /different HTML snapshot already exists/);
    assert.deepEqual(JSON.parse(fs.readFileSync(statePath, 'utf8')), state);
    assert.throws(() => finalizeHtmlSnapshots(statePath, { ...claim, claimId: 'wrong-owner' }), /ownership mismatch/);
    assert.deepEqual(JSON.parse(fs.readFileSync(statePath, 'utf8')), state);
    finalizeHtmlSnapshots(statePath, claim);
    const finalized = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    assert.deepEqual(finalized.claims, {});
    assert.deepEqual(finalized.posted, {});
    assert.equal(finalized.completed[report.alertId].delivery, 'html');
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-html-snapshot-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('HTML snapshots reject a cutoff later than the scheduled claim', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-html-cutoff-'));
  try {
    const report = validReport();
    const statePath = path.join(fixture, 'state.json');
    const reportPath = path.join(fixture, 'report.json');
    const state = { claims: { [report.alertId]: { symbolCode: report.symbolCode, receivedAt: report.analysisCutoff } }, posted: {} };
    fs.writeFileSync(statePath, JSON.stringify(state));
    report.analysisCutoff = '2026-09-30T23:59:59+09:00';
    fs.writeFileSync(reportPath, JSON.stringify({ reports: [report] }));
    const result = spawnSync(process.execPath, [poster, '--input', reportPath, '--state', statePath, '--save-only'], {
      encoding: 'utf8', env: { ...process.env, WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL: '' },
    });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /HTML snapshot analysisCutoff must match/);
    assert.deepEqual(JSON.parse(fs.readFileSync(statePath, 'utf8')), state);
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-html-cutoff-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('Cloud beta posting accepts claim cutoff and rejects later disclosures', () => {
  const parent = path.resolve(os.tmpdir());
  const fixture = fs.mkdtempSync(path.join(parent, 'weak-early-beta-point-in-time-'));
  try {
    const statePath = path.join(fixture, 'state.json');
    const reportPath = path.join(fixture, 'report.json');
    const alertId = 'weak-early-beta:2026-09-30:4052';
    fs.writeFileSync(statePath, JSON.stringify({
      claims: { [alertId]: { symbolCode: '4052', receivedAt: '2026-09-30T16:15:00+09:00' } },
      posted: {},
    }));
    const report = {
      alertId,
      signalDate: '2026-09-30',
      symbolCode: '4052',
      symbolName: 'フィーチャ',
      analysisCutoff: '2026-09-30T16:15:00+09:00',
      url: 'https://jp.tradingview.com/chart/?symbol=TSE%3A4052',
      fields: [
        { name: '材料インパクト', value: '様子見：一次資料の確認が必要。' },
        { name: '事業概要', value: '画像認識ソフトウェア。' },
        { name: '足元材料', value: '当日開示を確認。' },
        { name: 'ファンダ要点', value: '受注状況。' },
        { name: '注意点', value: '顧客集中。' },
        { name: '開示リンク', value: '・[2026-09-30 開示タイトル(15:30)](https://example.com/disclosure.pdf)' },
        { name: 'Sources', value: '・[IR一覧](https://example.com/ir)' },
      ],
    };
    const run = () => spawnSync(process.execPath, [poster, '--input', reportPath, '--state', statePath, '--dry-run'], {
      encoding: 'utf8',
      env: { ...process.env, WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL: 'https://example.com/webhook' },
    });
    fs.writeFileSync(reportPath, JSON.stringify({ reports: [report] }));
    assert.equal(run().status, 0);
    report.fields[5].value = '・[2026-09-30 開示タイトル(16:30)](https://example.com/disclosure.pdf)';
    fs.writeFileSync(reportPath, JSON.stringify({ reports: [report] }));
    const laterDisclosure = run();
    assert.notEqual(laterDisclosure.status, 0);
    assert.match(laterDisclosure.stderr, /post-cutoff disclosure found/);
    assert.deepEqual(JSON.parse(fs.readFileSync(statePath, 'utf8')).posted, {});
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${parent}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-point-in-time-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('forward HTML snapshots use exact analysis start and later-day publication receipts', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-forward-cutoff-'));
  try {
    const statePath = path.join(fixture, 'state.json');
    const reportPath = path.join(fixture, 'report.json');
    const report = validReport();
    const receivedAt = report.analysisCutoff;
    const cutoff = '2026-10-01T06:00:00.123Z';
    const claim = { claimId: 'forward-claim', symbolCode: report.symbolCode, signalDate: report.signalDate,
      signalType: 'WEAK_EARLY_BETA', receivedAt, analysisCutoff: cutoff };
    const state = { claims: { [report.alertId]: claim }, posted: {}, failed: {} };
    fs.writeFileSync(statePath, JSON.stringify(state));
    report.analysisCutoff = cutoff;
    report.auditStatus = 'pass';
    report.fields[5].value = '・[2026-10-01 開示タイトル(15:00)](https://example.com/disclosure.pdf)';
    report.disclosures = [{ url: 'https://example.com/disclosure.pdf', publishedAt: '2026-10-01T15:00:00.123+09:00', contentReviewed: true }];
    const run = (mode = '--dry-run') => {
      fs.writeFileSync(reportPath, JSON.stringify({ reports: [report] }));
      return spawnSync(process.execPath, [poster, '--input', reportPath, '--state', statePath, '--save-only', mode], {
        encoding: 'utf8', env: { ...process.env, WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL: '' },
      });
    };
    assert.equal(run().status, 0);
    report.disclosures[0].publishedAt = '2026-10-01T15:00:00.124+09:00';
    assert.match(run().stderr, /post-cutoff disclosure found/);
    report.disclosures[0].publishedAt = '2026-10-01T15:00:00.123+09:00';
    report.analysisCutoff = '2026-10-01T15:00:00.123+09:00';
    assert.match(run().stderr, /must match claim.analysisCutoff/);
    report.analysisCutoff = cutoff;
    report.disclosures[0].url = 'https://example.com/other.pdf';
    assert.match(run().stderr, /must match selected publication receipts/);
    report.disclosures[0].url = 'https://example.com/disclosure.pdf';
    assert.equal(run('--save-only').status, 0);
    const saved = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    assert.equal(saved.completed[report.alertId].analysisBasis, 'analysis_start');
    assert.equal(saved.completed[report.alertId].analysisCutoff, cutoff);
    assert.deepEqual(saved.claims, state.claims);
    assert.deepEqual(saved.posted, {});
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-forward-cutoff-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('forward date-only receipts use the analysis-start JST day and legacy types stay historical', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-forward-date-only-'));
  try {
    const statePath = path.join(fixture, 'state.json');
    const reportPath = path.join(fixture, 'report.json');
    const report = validReport();
    const receivedAt = report.analysisCutoff;
    const cutoff = '2026-10-01T15:00:00.123Z'; // JST 2026-10-02, after the signal date.
    const claim = { symbolCode: report.symbolCode, signalDate: report.signalDate,
      signalType: 'WEAK_EARLY_BETA', receivedAt, analysisCutoff: cutoff };
    report.analysisCutoff = cutoff;
    report.auditStatus = 'pass';
    report.fields[5].value = '・[2026-10-01 開示タイトル(時刻未確認)](https://example.com/disclosure.pdf)';
    report.disclosures = [{ url: 'https://example.com/disclosure.pdf', publishedAt: '2026-10-01', publishedAtPrecision: 'date_only', contentReviewed: true }];
    const run = () => {
      fs.writeFileSync(statePath, JSON.stringify({ claims: { [report.alertId]: claim }, posted: {} }));
      fs.writeFileSync(reportPath, JSON.stringify({ reports: [report] }));
      return spawnSync(process.execPath, [poster, '--input', reportPath, '--state', statePath, '--save-only', '--dry-run'], {
        encoding: 'utf8', env: { ...process.env, WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL: '' },
      });
    };
    assert.equal(run().status, 0);
    report.disclosures[0].publishedAt = '2026-10-02';
    assert.match(run().stderr, /predate the analysis-start JST date/);
    claim.signalType = 'HISTORICAL';
    report.analysisCutoff = receivedAt;
    assert.match(run().stderr, /post-signal date found in historical report/);
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-forward-date-only-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

// Exercise the actual JSON shape supplied to the analysis model.
test('Cloud generation supplies explicit role-array evidence contract', () => {
  const exampleLine = CLOUD_REPORT_CONTRACT.split('\n').find(line => line.startsWith('{'));
  const evidence = JSON.parse(exampleLine).sourceChecks;
  assert.equal(Array.isArray(evidence), true);
  assert.deepEqual(evidence.map(row => row.role), ['official_ir', 'irbank_or_tdnet']);
  for (const row of evidence) {
    assert.equal(row.checked, true);
    assert.match(row.url, /^https:\/\//);
    assert.ok(row.checkedUrls.length);
    assert.ok(row.result);
  }
  const source = fs.readFileSync(new URL('./weak-early-beta-fundamental-runner.mjs', import.meta.url), 'utf8');
  assert.match(source, /\s+CLOUD_REPORT_CONTRACT,\s/);
});
