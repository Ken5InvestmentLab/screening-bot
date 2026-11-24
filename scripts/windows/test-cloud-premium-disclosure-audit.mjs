import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { createCloudPremiumDisclosureAudit, VERIFIED_ZERO_LINK_FIELD } from './cloud-premium-disclosure-audit.mjs';

const origin = 'https://official.example.invalid';
const listUrl = origin + '/news.json';
const sameTime = '2026-11-24T15:50:00+09:00';
const updates = [
  { id: 'financial', title: '第2四半期決算短信', url: origin + '/financial.html', publishedAt: sameTime },
  { id: 'capital', title: '資本政策の更新', url: origin + '/capital.html', publishedAt: sameTime },
  { id: 'new', title: '業績予想修正', url: origin + '/after.html', publishedAt: '2026-11-24T17:15:00+09:00' },
];
const quote = '売上高が前年同期比10％増加した。';
const reflection = '売上高の前年同期比は10％増加し、会社は今期の増収要因を説明している。';

function setup(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-premium-disclosure-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const claim = {
    claimId: 'cloud-claim-example',
    symbolCode: '1234',
    analysisCutoff: '2026-11-24T16:15:00+09:00',
    receivedAt: '2026-11-24T15:40:00+09:00',
    documentDirectory: path.join(directory, 'documents'),
    sources: [{
      kind: 'issuer', format: 'json-records-v1', symbolCode: '1234',
      identityMarker: 'officialDisclosureExample', recordsPath: 'officialDisclosureExample',
      url: listUrl, coverageComplete: true, coverageFrom: '2026-10-09', coverageThrough: '2026-11-24',
    }],
  };
  const source = { officialDisclosureExample: structuredClone(updates) };
  const originals = new Map(updates.map(row => [row.url, '<html><body><p>' + quote + '</p></body></html>']));
  const requests = [];
  const audit = createCloudPremiumDisclosureAudit({
    evidenceDirectory: path.join(directory, 'cache'),
    fetcher: async url => {
      requests.push(url);
      const body = url === listUrl ? JSON.stringify(source) : originals.get(url);
      return { status: body ? 200 : 404, url, body, contentType: 'text/html; charset=utf-8' };
    },
  });
  return { audit, claim, source, originals, requests };
}

function draft(claim, preparation) {
  const documents = preparation.documents;
  const publicDocument = documents.find(item => item.title === '第2四半期決算短信');
  return {
    symbolCode: claim.symbolCode,
    analysisCutoff: claim.analysisCutoff,
    disclosureLinkPolicy: 'key-materials-v1',
    fields: [
      { name: '足元材料', value: reflection },
      { name: '開示リンク', value: '[' + publicDocument.cloudLabel + '](' + publicDocument.url + ')' },
    ],
    disclosures: [{ url: publicDocument.url, publishedAt: sameTime, contentReviewed: true }],
    disclosureEvidence: documents.map(item => ({
      id: item.id, contentRead: true, contentSha256: item.sha256, contentEvidence: quote,
      reflections: [{ field: '足元材料', text: reflection }],
    })),
  };
}

test('prepares only pre-cutoff originals and requires both important same-time disclosures', async t => {
  const { audit, claim, requests } = setup(t);
  const preparation = await audit.prepare(claim);
  assert.equal(preparation.inventory.receivedAtMs, Date.parse(claim.receivedAt));
  assert.deepEqual(preparation.documents.map(item => item.title).sort(), ['第2四半期決算短信', '資本政策の更新']);
  assert.equal(preparation.requiredIds.length, 2);
  assert.ok(preparation.documents.every(item => item.contentRead === false && fs.readFileSync(item.textFile, 'utf8').includes(quote)));
  assert.equal(requests.includes(origin + '/after.html'), false);

  const report = draft(claim, preparation);
  const proof = await audit.validate({ ...claim, inventory: preparation.inventory, report });
  assert.deepEqual(proof.publicUrls, [origin + '/financial.html']);
  assert.deepEqual(new Set(proof.requiredIds), new Set(proof.selectedIds));
  await assert.rejects(audit.validate({
    ...claim, inventory: preparation.inventory, report: { ...report, disclosureEvidence: report.disclosureEvidence.slice(0, 1) },
  }), /missing important official disclosure IDs/u);
  const wrongTime = structuredClone(report);
  wrongTime.disclosures[0].publishedAt = '2026-11-24T15:51:00+09:00';
  await assert.rejects(audit.validate({
    ...claim, inventory: preparation.inventory, report: wrongTime,
  }), /receipt publication time differs/u);
  await assert.rejects(audit.validate({
    ...claim, receivedAt: claim.analysisCutoff, inventory: preparation.inventory, report,
  }), /does not match the prepared claim/u);
});

test('audits the fresh source and original body again after targeted draft repair', async t => {
  const { audit, claim, originals, requests } = setup(t);
  const preparation = await audit.prepare(claim);
  const report = draft(claim, preparation);
  await audit.validate({ ...claim, inventory: preparation.inventory, report });
  assert.equal(requests.filter(url => url === listUrl).length, 2);
  originals.set(origin + '/financial.html', '<p>売上高が前年同期比10％減少した。</p>');
  audit.restartValidation();
  await assert.rejects(audit.validate({ ...claim, inventory: preparation.inventory, report }), /official disclosure content changed/u);
  assert.equal(requests.filter(url => url === listUrl).length, 3);
});

test('does not invent a publication time for a same-day date-only disclosure', async t => {
  const { audit, claim, source } = setup(t);
  source.officialDisclosureExample[0] = {
    id: 'financial', title: '第2四半期決算短信', url: origin + '/financial.html', date: '2026-11-24',
  };
  await assert.rejects(audit.prepare(claim), /date-only disclosure has no verified visibility by cutoff/u);
});

test('does not request a literal local address declared as an official source', async t => {
  const { audit, claim, requests } = setup(t);
  claim.sources[0].url = 'https://127.0.0.1/news.json';
  await assert.rejects(audit.prepare(claim), /requires a public hostname/u);
  assert.deepEqual(requests, []);
});

test('only a genuine EIR calendar1 placeholder can leave the official material list empty', async t => {
  const { audit, claim, source } = setup(t);
  Object.assign(claim.sources[0], {
    format: 'eir-announcements-v1', identityMarker: '"customer_code":"1234"',
    recordsPath: 'item', keys: { publisherId: 'guid', url: 'link' },
  });
  delete source.officialDisclosureExample;
  Object.assign(source, {
    header: [{ customer_code: claim.symbolCode }], item_count: '1',
    item: [{
      title: '第2四半期決算短信の発表予定', guid: 'calendar_9999',
      news_type: 'calendar', sub_type: 'calendar1', type: 'space',
      link: '', attachment_count: '0', attachment: [], publishedAt: sameTime,
    }],
  });
  const preparation = await audit.prepare(claim);
  assert.equal(preparation.inventory.items[0].recordKind, 'scheduled-event');
  assert.deepEqual(preparation.documents, []);
  const report = {
    symbolCode: claim.symbolCode,
    analysisCutoff: claim.analysisCutoff,
    fields: [{ name: '開示リンク', value: VERIFIED_ZERO_LINK_FIELD }],
    disclosures: [],
    disclosureEvidence: [],
    noMaterialDisclosureReason: '発表予定の記載のみで、対象時点で公表された開示ではない。',
  };
  const proof = await audit.validate({ ...claim, inventory: preparation.inventory, report });
  assert.deepEqual(proof.publicUrls, []);

  source.item[0].attachment_count = '1';
  audit.restartValidation();
  await assert.rejects(audit.validate({
    ...claim, inventory: preparation.inventory, report,
  }), /requires verified zero official materials/u);
  audit.restartPreparation();
  await assert.rejects(audit.prepare(claim), /lacks an available direct original/u);
});

test('blocks DNS names that resolve to loopback, private, link-local or mapped addresses', async t => {
  const { claim } = setup(t);
  for (const entry of [
    { address: '127.0.0.1', family: 4 }, { address: '10.0.1.1', family: 4 },
    { address: '169.254.169.254', family: 4 }, { address: '::ffff:127.0.0.1', family: 6 },
    { address: 'fe80::1', family: 6 },
  ]) {
    let resolved = 0;
    const audit = createCloudPremiumDisclosureAudit({
      evidenceDirectory: path.join(claim.documentDirectory, 'dns-cache'),
      resolveHostname(host, options, callback) {
        assert.equal(host, 'official.example.invalid');
        assert.deepEqual(options, { all: true });
        resolved++;
        callback(null, [entry]);
      },
    });
    await assert.rejects(audit.prepare(claim), /DNS did not resolve exclusively to public addresses/u);
    assert.equal(resolved, 1);
  }
});
