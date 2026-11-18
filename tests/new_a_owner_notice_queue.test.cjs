const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const test = require('node:test');
const { modules } = require('./helpers/cloud-worker-modules.cjs');

const schema = name => fs.readFileSync(path.resolve(__dirname, '../weak-early-beta-gate/schema/', name), 'utf8');
const hash = value => createHash('sha256').update(value).digest('hex');
const morning = 'EVALUATION_DAY_MORNING';
const holding = 'WATCH_TO_SIMULATED_HOLDING';
const day = '2026-11-19';
const uid = '11111111-2222-4333-8444-555555555555';
const dataset = 'a-' + 'a'.repeat(24);
const source = 'c'.repeat(64);
const snapshot = 'd'.repeat(64);
const owner = 'b'.repeat(64);
const recipient = 'f'.repeat(64);
const build = {
  source_commit: '1'.repeat(40),
  build_input_sha256: '2'.repeat(64),
  target: { worker: 'tentei-kyokuchi-cloud', database: 'tentei-cloud-settings' },
};

function setUp(t, kind = morning) {
  const sqlite = new DatabaseSync(':memory:');
  t.after(() => sqlite.close());
  sqlite.exec(schema('new-a-private.sql'));
  sqlite.exec(schema('new-a-owner-notice-queue.sql'));
  const reads = [];
  const d1 = { prepare(sql) {
    const statement = sqlite.prepare(sql);
    return { bind(...values) {
      reads.push(values);
      return { first: async () => statement.get(...values) ?? null };
    } };
  } };
  const env = { CLOUD_NEW_A_OWNER_PUSH_ENABLED: 'true', CLOUD_DB: d1,
    CLOUD_VERSION_METADATA: { id: uid, tag: build.source_commit } };
  const dailyAsOf = kind === morning ? '2026-11-18' : day;
  const manifest = JSON.stringify({ as_of: dailyAsOf, live: true,
    input_header: { limits: { nextPlannedSession: kind === morning ? day : '2026-11-20' } } });
  const basis = { dataset_id: dataset, revision: 1, manifest_sha256: hash(manifest), source_version: source,
    snapshot_sha256: snapshot, preferences_revision: 2, ...(kind === morning ? { calendar_sha256: 'a'.repeat(64) } : {}) };
  sqlite.prepare('INSERT INTO new_a_private_datasets VALUES(?,?,?,?,?,?)')
    .run(dataset, source, manifest, basis.manifest_sha256, 'READY', 'fixture');
  sqlite.prepare('INSERT INTO new_a_active_pointer VALUES(?,?,?,?)').run('owner', dataset, 1, 'fixture');
  const publication = {
    schema: 'NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1', as_of: dailyAsOf, dataset_id: dataset, revision: 1,
    manifest_sha256: hash(manifest), source_version: source, snapshot_sha256: snapshot, published: true,
    active_readback_verified: true, existing_owner_gate_verified: true, local_d1_emulation: false,
  };
  function event(i = 1) {
    return { event_id: String(i).repeat(64), kind, symbol: '123A', candidate_date: '2026-11-12',
      simulated_entry_date: kind === morning ? '2026-11-13' : day, execution_status: 'SIMULATED_NOT_ACTUAL_TRADES',
      ...(kind === morning ? { title: '確定日の朝8時（日本時間）',
        description: '今日は、設定した確定日です。その日の価格はまだ確定していません。', scheduled_evaluation_date: day,
        evaluation_endpoint: 'd5_open', evaluation_timing: 'OPEN', evaluation_price_status: 'NOT_YET_OBSERVED',
      } : { title: '監視から仮想保有に移行', description: '保存した条件による仮想保有です。実際の取引は行われていません。' }),
    };
  }
  const payload = { schema: 'NEW_A_OWNER_NOTICE_QUEUE_V1', target_date: day, kind,
    source_commit: build.source_commit, worker_version_id: uid, build_input_sha256: build.build_input_sha256,
    source_run_sha256: '3'.repeat(64), publication_receipt_sha256: '4'.repeat(64), owner_binding_sha256: owner,
    recipient_binding_sha256: recipient, model_basis: 'SAVED_SCOPE', basis, publication, notices: [event()],
  };
  function stage(input = payload, suppliedSha = null) {
    const raw = JSON.stringify(input);
    sqlite.prepare('INSERT INTO new_a_owner_notice_queue VALUES(?,?,?,?)')
      .run(day, kind, raw, suppliedSha ?? hash(raw));
  }
  const clock = { now: Date.parse(day + (kind === morning ? 'T08:00:00+09:00' : 'T17:05:00+09:00')) };
  const q = modules({ clock, fetchMock: async () => { throw Error('fixture has no external fetch'); } })
    .load('./new-a-owner-notice-queue');
  const controller = { cron: kind === morning ? q.NEW_A_MORNING_CRON : q.NEW_A_HOLDING_CRON,
    scheduledTime: clock.now };
  const calls = [];
  const readers = {
    readRecipient: async () => {
      calls.push('recipient');
      return { owner_binding_sha256: owner, recipient_binding_sha256: recipient, fresh_paid_role: true };
    },
    dispatch: async (unused, value) => {
      calls.push('dispatch-' + value.event.event_id[0]);
      assert.equal(value.owner_binding_sha256, owner);
      assert.equal(value.recipient_binding_sha256, recipient);
      assert.equal(value.basis.manifest_sha256, hash(manifest));
      return { status: 'accepted' };
    },
    readReceipt: async (unused, value) => {
      calls.push('receipt-' + value.event.event_id[0]);
      return { status: 'accepted' };
    },
  };
  return { sqlite, clock, controller, env, q, reads, calls, readers, event, payload, stage,
    check: (configured = env, scheduled = controller) => q.checkNewAOwnerNoticeQueue(configured, scheduled, build, clock.now),
    run: (selected = readers, configured = env) => q.runNewAOwnerNoticeQueue(configured, controller, build, clock.now, selected) };
}

test('disabled and wrongly scheduled queues do not query D1 or the recipient', async t => {
  const f = setUp(t);
  f.stage();
  assert.equal((await f.run(f.readers, { ...f.env, CLOUD_NEW_A_OWNER_PUSH_ENABLED: undefined })).status, 'disabled');
  assert.equal((await f.check(f.env, { ...f.controller, scheduledTime: f.clock.now - 60_000 })).reason, 'outside_notice_slot');
  assert.equal((await f.check({ ...f.env, CLOUD_VERSION_METADATA: { id: uid, tag: '9'.repeat(40) } })).reason,
    'normal_release_unverified');
  assert.deepEqual(f.reads, []);
  assert.deepEqual(f.calls, []);
});

test('missing and zero-event plans do not look up a recipient', async t => {
  const f = setUp(t);
  assert.equal((await f.run()).reason, 'no_queued_plan');
  f.stage({ ...f.payload, notices: [] });
  assert.equal((await f.run()).reason, 'no_notices_due');
  assert.deepEqual(f.reads, [[day, morning], [day, morning]]);
  assert.deepEqual(f.calls, []);
});

test('morning preflight exposes only aggregate status and binds the active next market session', async t => {
  const f = setUp(t);
  f.stage();
  const observation = await f.check();
  assert.equal(observation.status, 'ready');
  assert.equal(observation.queued, 1);
  assert.equal(observation.target_date, day);
  assert.equal(observation.arrival_confirmed, false);
  for (const value of [owner, recipient, '123A', dataset]) assert(!JSON.stringify(observation).includes(value));
  assert.deepEqual(f.calls, []);
  f.sqlite.prepare("UPDATE new_a_private_datasets SET manifest_json=json_set(manifest_json,'$.input_header.limits.nextPlannedSession',?)")
    .run('2026-11-20');
  assert.equal((await f.run()).reason, 'active_publication_mismatch');
  assert.deepEqual(f.calls, []);
});

test('queue digest, exact release and full event shape fail closed before querying a recipient', async t => {
  for (const [mutate, suppliedSha, expected] of [
    [p => p, '0'.repeat(64), 'queue_integrity_mismatch'],
    [p => ({ ...p, worker_version_id: '99999999-2222-4333-8444-555555555555' }), null, 'queue_contract_mismatch'],
    [p => ({ ...p, model_basis: ['SAVED_SCOPE'] }), null, 'queue_contract_mismatch'],
    [p => ({ ...p, notices: p.notices.map(event => ({ ...event, observed_price: 100 })) }), null, 'queue_event_mismatch'],
    [p => ({ ...p, notices: [p.notices[0], p.notices[0]] }), null, 'queue_event_mismatch'],
  ]) {
    const f = setUp(t);
    f.stage(mutate(f.payload), suppliedSha);
    assert.equal((await f.run()).reason, expected);
    assert.deepEqual(f.calls, []);
  }
});

test('oversized batches and stale ordinary publication do not enter the provider path', async t => {
  const over = setUp(t);
  over.stage({ ...over.payload, notices: [over.event(1), over.event(2), over.event(3)] });
  assert.equal((await over.run()).reason, 'batch_exceeds_delivery_budget');
  assert.deepEqual(over.calls, []);
  const stale = setUp(t, holding);
  stale.stage();
  stale.sqlite.prepare("UPDATE new_a_active_pointer SET revision=2 WHERE pointer_key='owner'").run();
  assert.equal((await stale.run()).reason, 'active_publication_mismatch');
  assert.deepEqual(stale.calls, []);
});

test('holding dispatch checks exact recipient and serializes independent acceptance receipts', async t => {
  const f = setUp(t, holding);
  f.stage({ ...f.payload, notices: [f.event(1), f.event(2)] });
  const changed = { ...f.readers, readRecipient: async () => {
    f.calls.push('different-recipient');
    return { owner_binding_sha256: owner, recipient_binding_sha256: '0'.repeat(64), fresh_paid_role: true };
  } };
  assert.equal((await f.run(changed)).reason, 'owner_recipient_unverified');
  const ready = await f.run();
  assert.equal(ready.status, 'processed');
  assert.equal(ready.verified_accepted, 2);
  assert.equal(ready.arrival_confirmed, false);
  assert.deepEqual(f.calls, ['different-recipient', 'recipient', 'dispatch-1', 'receipt-1', 'dispatch-2', 'receipt-2']);
});

test('ambiguous delivery checks the existing receipt and stops further events if unconfirmed', async t => {
  const f = setUp(t);
  f.stage({ ...f.payload, notices: [f.event(1), f.event(2)] });
  const first = { ...f.readers,
    dispatch: async () => { f.calls.push('dispatch-unknown'); return { status: 'unknown' }; },
    readReceipt: async () => { f.calls.push('receipt-unknown'); return { status: 'preparing' }; },
  };
  const hold = await f.run(first);
  assert.equal(hold.status, 'held');
  assert.equal(hold.reason, 'delivery_readback_unconfirmed');
  assert.equal(hold.verified_accepted, 0);
  assert.deepEqual(f.calls, ['recipient', 'dispatch-unknown', 'receipt-unknown']);
});
