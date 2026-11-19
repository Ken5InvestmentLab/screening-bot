'use strict';

const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const { test } = require('node:test');

const gate = path.resolve(__dirname, '../weak-early-beta-gate');
const script = path.join(gate, 'scripts/prepare-new-a-member-projection.cjs');
const { prepareNewAMemberProjection } = require(script);
const { createNewAMemberProjectionReader } = require('../weak-early-beta-gate/src/new-a-member-projection.ts');
const digest = value => createHash('sha256').update(value).digest('hex');
const day = '2026-11-19';
const calendar = ['2026-11-17', '2026-11-18', day];
const sourceVersion = 'a'.repeat(64);

async function fixture(t, { hasMissingMark = true, logical = true } = {}) {
  const base = await fs.realpath(os.tmpdir());
  const root = await fs.mkdtemp(path.join(base, 'new-a-member-projection-'));
  t.after(async () => {
    assert.equal(path.dirname(await fs.realpath(root)), base);
    assert(path.basename(root).startsWith('new-a-member-projection-'));
    await fs.rm(root, { recursive: true });
  });
  async function save(name, value) {
    const json = JSON.stringify(value);
    await fs.writeFile(path.join(root, name), json);
    return { name, sha256: digest(json), rows: value.length, bytes: Buffer.byteLength(json) };
  }
  const episode = { symbol: '123A', candidate_date: calendar[0], trigger_date: calendar[0], episode_id: 1, priority_score: 10 };
  const watches = [{
    ...episode, watch_status: 'TRIGGERED', company_name: 'PRIVATE_COMPANY_MARKER', settings: 'PRIVATE_SETTINGS_MARKER',
  }];
  const quoteFields = ['open', 'high', 'low', 'close', 'actual_close', 'source_usable', 'volume', 'actual_volume'];
  const quoteRows = [
    ['123A', calendar[0], [100, 110, 98, 102, 102, true, 1000, 1000]],
    ['123A', calendar[1], [103, 110, 101, 104, 104, true, 1000, 1000]],
    ['123A', day, null],
  ];
  const manifest = {
    schema: 'A_BROWSER_PRIVATE_INPUT_V1', audience: 'EXISTING_CLOUD_OWNER_ONLY', strategy: 'A_BASE',
    as_of: day, source_version: sourceVersion, live: false,
    input_header: { calendar, source_version: sourceVersion, limits: { identityUnverifiedBefore: {} } },
    quote_fields: quoteFields,
    expected_quote_keys: quoteRows.length,
    quotes: [await save('quotes-000.json', quoteRows)],
    collections: {
      episodes: [await save('episodes-000.json', [episode])],
      intents: [await save('intents-000.json', hasMissingMark ? [episode] : [])],
      watches: [await save('watches-000.json', watches)],
      presentation: [await save('presentation-000.json', [{ secret: 'PRIVATE_PRESENTATION_MARKER' }])],
      current_daily: [],
    },
  };
  const bundle = await save('manifest.json', manifest);
  const storedHash = logical ? 'b'.repeat(64) : bundle.sha256;
  const datasetId = 'a-' + storedHash.slice(0, 24);
  const proof = {
    schema: 'NEW_A_OPERATIONAL_OBSERVATION_V1',
    observed_at: day + 'T12:00:00+09:00',
    raw_response_sha256: 'c'.repeat(64),
    active_dataset_id: datasetId, active_revision: 4, active_as_of: day,
    active_source_version: sourceVersion,
    active_manifest_sha256: storedHash, active_logical_manifest_sha256: bundle.sha256,
    d1_active_sha256: digest(JSON.stringify(['NEW_A_ACTIVE_METADATA_V1', datasetId, 4, 'READY', sourceVersion, storedHash, day])),
  };
  const input = {
    bundle: root,
    readyProof: path.join(root, 'readback.json'),
    readyProofSha256: (await save('readback.json', proof)).sha256,
  };
  return { root, input, proof, save };
}

test('reproduces sanitized common projection from a pinned logical READY generation and keeps unresolved marks empty', async t => {
  const f = await fixture(t);
  const result = await prepareNewAMemberProjection(f.input);
  assert.deepEqual(await prepareNewAMemberProjection(f.input), result);
  const source = { status: 'READY', dataset_id: f.proof.active_dataset_id, revision: 4, as_of: day, source_version: sourceVersion };
  assert.deepEqual(result.receipt.source, source);
  assert.equal(result.receipt.owner_readback_sha256, f.input.readyProofSha256);
  assert.equal(result.receipt.projection_manifest_sha256, digest(result.manifestJson));
  assert.equal(result.receipt.activated, false);
  assert.equal(result.parts.length, 5);
  assert.doesNotMatch(JSON.stringify(result), /PRIVATE_COMPANY_MARKER|PRIVATE_SETTINGS_MARKER|PRIVATE_PRESENTATION_MARKER|actual_close|entry_cost/);

  const manifest = JSON.parse(result.manifestJson);
  const identity = JSON.stringify(source);
  const db = new DatabaseSync(':memory:');
  t.after(() => db.close());
  db.exec(await fs.readFile(path.join(gate, 'member-migrations/0001_new_a_member_storage.sql'), 'utf8'));
  db.prepare('INSERT INTO private_projection_manifest VALUES (?, ?, ?)')
    .run(identity, result.receipt.projection_manifest_sha256, result.manifestJson);
  for (const part of result.parts) {
    assert.equal(part.sha256, digest(part.json));
    db.prepare('INSERT INTO private_projection_part VALUES (?, ?, ?, ?)').run(identity, part.kind, part.index, part.json);
  }
  let current = source;
  const read = createNewAMemberProjectionReader({ withSession(mode) {
    assert.equal(mode, 'first-primary');
    return { prepare(sql) {
      const statement = db.prepare(sql);
      let values = [];
      return {
        bind(...args) { values = args; return this; },
        async first() { return statement.get(...values) ?? null; },
      };
    } };
  } }, async () => current);
  assert.equal(await read(source, 'history', 0), null, 'staged offline artifacts do not become active');
  db.prepare('INSERT INTO private_projection_ready VALUES (1, ?, ?)')
    .run(identity, result.receipt.projection_manifest_sha256);
  assert.deepEqual((await read(source, 'history', 0)).rows, [{ date: calendar[0], symbol: '123A', state: 'TRIGGERED' }]);
  const analytics = await read(source, 'analytics', 0);
  assert.deepEqual(analytics.rows.map(row => [row.preset, row.from, row.resolved, row.metrics]), [
    ['defensive', calendar[0], false, null],
    ['medium', calendar[0], false, null],
    ['return_priority', calendar[0], false, null],
  ]);
  for (const [index, preset] of manifest.parts.filter(part => part.kind === 'chart').entries()) {
    assert.equal(preset.rows, calendar.length);
    const chart = await read(source, 'chart', index);
    assert.equal(chart.rows[1].holding_count, 1);
    assert.deepEqual(chart.rows.at(-1), { date: day, equity_yen: null, holding_count: null });
  }
  current = { ...source, revision: 5 };
  assert.equal(await read(source, 'analytics', 0), null, 'the marker cannot serve after a same-day owner pointer change');
});

test('accepts the exact READY manifest, and CLI output is deterministic and cannot overwrite', async t => {
  const f = await fixture(t, { hasMissingMark: false, logical: false });
  const out = path.join(f.root, 'projection');
  const args = [script, '--bundle', f.input.bundle, '--ready-proof', f.input.readyProof,
    '--ready-proof-sha256', f.input.readyProofSha256, '--out', out];
  const result = spawnSync(process.execPath, args, { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const artifact = await prepareNewAMemberProjection(f.input);
  assert.deepEqual(await fs.readdir(out), ['analytics-0.json', 'chart-0.json', 'chart-1.json', 'chart-2.json', 'history-0.json', 'manifest.json', 'receipt.json']);
  assert.equal(await fs.readFile(path.join(out, 'manifest.json'), 'utf8'), artifact.manifestJson);
  assert.deepEqual(JSON.parse(await fs.readFile(path.join(out, 'receipt.json'), 'utf8')), artifact.receipt);
  const analytics = JSON.parse(await fs.readFile(path.join(out, 'analytics-0.json'), 'utf8'));
  assert(analytics.rows.every(row => row.resolved && row.metrics.net_profit === 0 && row.metrics.win_rate_pct === null));
  assert.notEqual(spawnSync(process.execPath, args).status, 0);
});

test('rejects unpinned evidence, invalid owner READY digest and retained source mutation before output', async t => {
  const f = await fixture(t);
  await assert.rejects(() => prepareNewAMemberProjection({ ...f.input, readyProofSha256: '0'.repeat(64) }), /proof pin mismatch/);
  const changed = await f.save('proof-with-new-revision.json', { ...f.proof, active_revision: 5 });
  await assert.rejects(() => prepareNewAMemberProjection({
    ...f.input, readyProof: path.join(f.root, changed.name), readyProofSha256: changed.sha256,
  }), /metadata digest mismatch/);
  await fs.appendFile(path.join(f.root, 'presentation-000.json'), ' ');
  await assert.rejects(() => prepareNewAMemberProjection(f.input), /source part hash or size mismatch/);
  await fs.appendFile(path.join(f.root, 'manifest.json'), ' ');
  await assert.rejects(() => prepareNewAMemberProjection(f.input), /differs from the verified owner READY manifest/);
});
