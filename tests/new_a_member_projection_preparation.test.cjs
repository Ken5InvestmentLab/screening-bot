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
  assert.equal(result.parts.length, 6);
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
  assert.deepEqual((await read(source, 'completed-history', 0)).rows, []);
  assert.deepEqual((await read(source, 'dashboard', 0)).rows, []);
  assert.deepEqual((await read(source, 'history', 1)).rows, []);
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
  assert.deepEqual(await fs.readdir(out), ['analytics-0.json', 'chart-0.json', 'chart-1.json', 'chart-2.json', 'history-0.json', 'history-1.json', 'manifest.json', 'receipt.json']);
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

test('separates prior completed evidence, unresolved/active episodes and current paid dashboard actions', async t => {
  const f = await fixture(t, { logical: false });
  const sessions = ['2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06',
    '2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13',
    '2026-11-16', '2026-11-17', '2026-11-18', day];
  const watch = (symbol, at, status, terminal, trigger = null) => ({
    symbol, candidate_date: sessions[at], episode_id: 1, priority_score: 10,
    watch_status: status, terminal_date: terminal, trigger_date: trigger,
  });
  const watches = [
    watch('1111', 1, 'EXPIRED', sessions[7]),
    watch('2222', 9, 'WATCHING', null),
    watch('3333', 0, 'TRIGGERED', sessions[0], sessions[0]),
    watch('4444', 10, 'TRIGGERED', day, day),
    watch('5555', 6, 'DATA_GAP', sessions[8]),
    watch('6666', 8, 'UP_ESCAPED', day),
    watch('7777', 12, 'WATCHING', null),
    watch('8888', 11, 'TRIGGERED', sessions[11], sessions[11]),
  ];
  const frame = JSON.parse(await fs.readFile(path.join(f.root, 'manifest.json'), 'utf8'));
  frame.input_header = { calendar: sessions, source_version: sourceVersion,
    limits: { identityUnverifiedBefore: {}, completeThrough: day } };
  frame.live = true;
  frame.daily_snapshot_sha256 = '8'.repeat(64);
  frame.collections.episodes = [await f.save('episodes-000.json', watches)];
  frame.collections.watches = [await f.save('watches-000.json', watches)];
  frame.collections.intents = [await f.save('intents-000.json', watches.filter(row => row.trigger_date))];
  const quotes = watches.map(watch => watch.symbol).flatMap(symbol =>
    sessions.map(date => [symbol, date, [100, 105, 99, 102, 102, true, 1000, 1000]]));
  frame.quotes = [await f.save('quotes-000.json', quotes)];
  frame.expected_quote_keys = quotes.length;
  const display = {
    schema: 'NEW_A_OWNER_DAILY_DISPLAY_V1', strategy: 'A_BASE', audience: 'EXISTING_CLOUD_OWNER_ONLY',
    as_of: day, source_snapshot_sha256: frame.daily_snapshot_sha256,
    events: [
      { ...watches[3], kind: 'ENTRY_CANDIDATE', session: day, private_price: 69253 },
      { ...watches[5], kind: 'WATCH_TERMINAL', session: day, reason: 'UP_ESCAPED' },
      { ...watches[6], kind: 'WATCH_STARTED', session: day },
    ],
    monitor_state: { schema: 'NEW_A_CURRENT_MONITOR_STATE_V1', strategy: 'A_BASE', actual_fills: false,
      watches: { '2222|1': { episode: watches[1] }, '7777|1': { episode: watches[6] } },
      pending_references: [
        { ...watches[3], price_status: 'UNCONFIRMED_NEXT_OPEN', reference_exit_date: null },
        { ...watches[2], price_status: 'HISTORICAL_REFERENCE_ONLY', reference_entry_date: sessions[1],
          reference_exit_date: '2026-12-03' },
      ] },
  };
  const bytes = Buffer.from(JSON.stringify(display));
  frame.collections.current_daily = [await f.save('current_daily-000.json', [{
    schema: 'NEW_A_CURRENT_JSON_FRAGMENT_V1', index: 0, count: 1, bytes_total: bytes.length,
    display_sha256: digest(bytes), payload_base64: bytes.toString('base64'),
  }])];
  const updated = await f.save('manifest.json', frame);
  const datasetId = 'a-' + updated.sha256.slice(0, 24);
  const observed = await f.save('readback.json', { ...f.proof, active_dataset_id: datasetId,
    active_manifest_sha256: updated.sha256, active_logical_manifest_sha256: updated.sha256,
    d1_active_sha256: digest(JSON.stringify(['NEW_A_ACTIVE_METADATA_V1', datasetId, 4, 'READY',
      sourceVersion, updated.sha256, day])),
  });
  const result = await prepareNewAMemberProjection({ ...f.input, readyProofSha256: observed.sha256 });
  const manifest = JSON.parse(result.manifestJson);
  assert.deepEqual(manifest.history_layout, { premium_pages: 1, completed_pages: 1 });
  const histories = result.parts.filter(part => part.kind === 'history').map(part => JSON.parse(part.json).rows);
  assert.equal(histories[0].length, 8);
  assert.deepEqual(histories[1], [
    { date: sessions[1], symbol: '1111', state: 'EXPIRED', completed_on: sessions[7] },
    { date: sessions[0], symbol: '3333', state: 'HOLD_ENDED', completed_on: sessions[6] },
  ]);
  assert.deepEqual(histories[2].filter(row => row.lane === 'today').map(({ symbol, state }) => [symbol, state]), [
    ['4444', 'ENTRY_CANDIDATE'], ['6666', 'WATCH_TERMINAL'], ['7777', 'WATCH_STARTED'], ['8888', 'HOLD_STARTED'],
  ]);
  assert.deepEqual(histories[2].filter(row => row.lane === 'watching').map(row => row.symbol), ['7777', '2222']);
  assert.doesNotMatch(JSON.stringify(result), /private_price|69253|pending_references|episode_id/);
});
