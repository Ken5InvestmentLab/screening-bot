import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

const poster = path.resolve('weak_early_beta/scripts/post_historical_snapshot.mjs');

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
