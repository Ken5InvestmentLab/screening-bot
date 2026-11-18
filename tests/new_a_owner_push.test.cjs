const assert = require('node:assert/strict');
const { createHash, webcrypto } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const test = require('node:test');
const { modules } = require('./helpers/cloud-worker-modules.cjs');

const gate = path.resolve(__dirname, '../weak-early-beta-gate');
const subject = '123456789012345678';
const guild = '345678901234567890';
const role = '234567890123456789';
const deviceId = '11111111-1111-4111-8111-111111111111';
const endpoint = 'https://push.example.invalid/owner';
// Public RFC 8291 test vector. No credentials or live endpoints.
const publicKey = 'BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8';
const privateKey = 'yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw';
const agentKey = 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4';
const auth = 'BTBZMqHH6r4Tts7J_aSIgg';
const snapshot = 'd'.repeat(64);
const dataset = 'a-' + 'a'.repeat(24);
const source = 'c'.repeat(64);
const sha = value => createHash('sha256').update(value).digest('hex');
const date = '2026-11-19';

async function setup(t, { morning = false } = {}) {
  const clock = { now: Date.parse(date + (morning ? 'T08:00:00+09:00' : 'T17:05:00+09:00')) };
  const state = { role: true, roleReads: 0, sends: 0, afterClaim: null, failSave: false, failSend: false };
  const m = modules({ clock, fetchMock: async (url, init) => {
    assert.equal(url, `https://discord.com/api/v10/guilds/${guild}/members/${subject}`);
    assert.equal(init.redirect, 'error');
    state.roleReads += 1;
    return Response.json({ user: { id: subject }, roles: state.role ? [role] : [] });
  } });
  const adapter = m.load('./new-a-owner-push');
  const sender = m.load('./cloud-web-push');
  const api = m.load('./cloud-api');
  const member = await api.cloudMemberId(subject);
  const sqlite = new DatabaseSync(':memory:');
  t.after(() => sqlite.close());
  for (const name of fs.readdirSync(path.join(gate, 'migrations')).filter(name => name.endsWith('.sql')).sort()) {
    sqlite.exec(fs.readFileSync(path.join(gate, 'migrations', name), 'utf8'));
  }
  sqlite.exec(fs.readFileSync(path.join(gate, 'schema/new-a-private.sql'), 'utf8'));
  const db = { prepare(sql) {
    const statement = sqlite.prepare(sql);
    return {
      args: [],
      bind(...args) { this.args = args; return this; },
      async first() { return statement.get(...this.args) ?? null; },
      async run() {
        if (state.failSave && sql.includes('UPDATE cloud_push_dispatch_receipts')) throw Error('fixture receipt save fault');
        const result = statement.run(...this.args);
        if (sql.includes('INSERT OR IGNORE INTO cloud_push_dispatch_receipts')) state.afterClaim?.();
        return { success: true, meta: { changes: Number(result.changes) } };
      },
    };
  } };
  const manifestText = JSON.stringify({ schema: 'A_BROWSER_PRIVATE_INPUT_V1', strategy: 'A_BASE',
    audience: 'EXISTING_CLOUD_OWNER_ONLY', source_version: source, daily_snapshot_sha256: snapshot,
    as_of: morning ? '2026-11-18' : date, live: true, input_header: { source_version: source },
    collections: { episodes: [{ name: 'episodes-000.json', sha256: 'b'.repeat(64), bytes: 2, rows: 0 }],
      intents: [], watches: [], presentation: [], current_daily: [] }, quotes: [] });
  const manifestSha = sha(manifestText);
  sqlite.prepare('INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?)')
    .run(dataset, source, manifestText, manifestSha, 'READY', 'fixture');
  sqlite.prepare('INSERT INTO new_a_active_pointer VALUES (?,?,?,?)').run('owner', dataset, 2, 'fixture');
  sqlite.prepare('INSERT INTO new_a_finite_trial_preferences VALUES (?,?,?,?,?)')
    .run(member, 1, JSON.stringify(m.load('./new-a-preferences').DEFAULTS), 3, 'fixture');
  const preferences = { ...m.load('./cloud-membership').DEFAULT_PREFERENCES,
    notifications: { new_detection: true, reminder: true } };
  sqlite.prepare('INSERT INTO cloud_member_preferences VALUES (?,?,?)').run(member, JSON.stringify(preferences), 'fixture');
  sqlite.prepare('INSERT INTO cloud_push_subscriptions VALUES (?,?,?,?,?,?,NULL)')
    .run(deviceId, member, endpoint, agentKey, auth, 'fixture');
  sqlite.prepare('INSERT INTO cloud_push_subscription_metadata VALUES (?,?,?,NULL,?)')
    .run(deviceId, sha(endpoint), publicKey, 'fixture');
  const env = { CLOUD_DB: db, CLOUD_NEW_A_OWNER_PUSH_ENABLED: 'true', CLOUD_OWNER_ONLY_ENABLED: 'true',
    CLOUD_OWNER_DISCORD_ID: subject, CLOUD_PUSH_MODE: 'personal_test', CLOUD_PUSH_TEST_DISCORD_USER_ID: subject,
    CLOUD_PUSH_TEST_MEMBER_ID: member, CLOUD_PUSH_TEST_SUBSCRIPTION_ID: deviceId, CLOUD_DISCORD_BOT_TOKEN: 'fixture-only',
    CLOUD_PUSH_MEMBERSHIP_POLICY: 'whop_managed_discord_role', CLOUD_PUSH_AUDIENCE: 'authenticated',
    DISCORD_GUILD_ID: guild, DISCORD_ALLOWED_ROLE_IDS: role, CLOUD_PUSH_ALLOWED_ORIGINS: new URL(endpoint).origin,
    CLOUD_VAPID_PUBLIC_KEY: publicKey, CLOUD_VAPID_PRIVATE_KEY: privateKey, CLOUD_VAPID_SUBJECT: 'https://cloud.example.invalid/' };
  const event = { event_id: 'e'.repeat(64), kind: morning ? 'EVALUATION_DAY_MORNING' : 'WATCH_TO_SIMULATED_HOLDING',
    symbol: '9999', candidate_date: '2026-11-16', simulated_entry_date: morning ? '2026-11-17' : date,
    execution_status: 'SIMULATED_NOT_ACTUAL_TRADES',
    ...(morning ? { scheduled_evaluation_date: date, evaluation_price_status: 'NOT_YET_OBSERVED' } : {}) };
  const notice = { owner_binding_sha256: member.slice('cloud_'.length),
    recipient_binding_sha256: sha(JSON.stringify(['NEW_A_OWNER_WEB_PUSH_DEVICE_V1', member, deviceId, sha(endpoint)])),
    target_date: date, event, basis: { dataset_id: dataset, revision: 2, manifest_sha256: manifestSha,
      source_version: source, snapshot_sha256: snapshot, preferences_revision: 3,
      ...(morning ? { calendar_sha256: 'f'.repeat(64) } : {}) } };
  const point = sender.decode(publicKey, 65);
  const imported = await webcrypto.subtle.importKey('jwk', { kty: 'EC', crv: 'P-256', x: sender.encode(point.slice(1, 33)),
    y: sender.encode(point.slice(33)), d: privateKey }, { name: 'ECDH', namedCurve: 'P-256' }, false, ['deriveBits']);
  const cryptoFixture = { privateKey: imported, publicKey: point, salt: sender.decode('DGv6ra1nlYgDCS1FRnbzlw', 16) };
  const transport = async (url, init) => {
    state.sends += 1;
    assert.equal(url, endpoint);
    assert.equal(init.method, 'POST');
    assert.equal(init.headers['Content-Encoding'], 'aes128gcm');
    const row = sqlite.prepare('SELECT event_key,status FROM cloud_push_dispatch_receipts').get();
    assert.equal(row.status, 'preparing');
    const body = morning ? '今日は、設定した確定日です。その日の価格はまだ確定していません。' :
      '監視から仮想保有に移行しました。保存した条件による試算です。実際の取引は行われていません。';
    const expected = await sender.encryptPushPayload({ endpoint, p256dh: agentKey, auth },
      JSON.stringify({ version: 1, kind: morning ? 'reminder' : 'new_detection', tag: row.event_key, body }), cryptoFixture);
    assert.deepEqual(Buffer.from(init.body), Buffer.from(expected));
    if (state.failSend) throw Error('fixture provider connection lost');
    return new Response('', { status: 201 });
  };
  return { adapter, clock, env, notice, sqlite, state, preferences,
    send: (chosen = notice, configuration = env) => adapter.dispatchNewAOwnerPush(configuration, chosen, transport, cryptoFixture) };
}

for (const morning of [true, false]) test(`${morning ? 'morning' : 'holding'} uses exact owner, verified source, and encrypted one-time delivery`, async t => {
  const f = await setup(t, { morning });
  const recipient = await f.adapter.readNewAOwnerPushRecipient(f.env);
  assert.equal(recipient.recipient_binding_sha256, f.notice.recipient_binding_sha256);
  assert.equal(recipient.owner_binding_sha256, f.notice.owner_binding_sha256);
  assert.equal(recipient.fresh_paid_role, true);
  const attempts = await Promise.all([f.send(), f.send()]);
  assert.deepEqual(attempts.map(value => value.status).sort(), ['accepted', 'suppressed']);
  assert.equal(f.state.sends, 1);
  const receipt = await f.adapter.readNewAOwnerPushReceipt(f.env, f.notice);
  assert.equal(receipt.status, 'accepted');
  assert.equal(receipt.arrival_confirmed, false);
  assert.equal((await f.send()).status, 'suppressed');
});

test('disabled, foreign, untimely, unpaid and stale cases leave the receipt ledger untouched', async t => {
  const f = await setup(t);
  assert.equal((await f.send(f.notice, { ...f.env, CLOUD_NEW_A_OWNER_PUSH_ENABLED: 'false' })).status, 'disabled');
  assert.equal((await f.send(f.notice, { ...f.env, CLOUD_PUSH_TEST_DISCORD_USER_ID: '999999999999999999' })).reason, 'owner_binding_required');
  assert.equal((await f.send({ ...f.notice, target_date: '2026-11-18' })).reason, 'current_notice_window_required');
  assert.equal((await f.send({ ...f.notice, recipient_binding_sha256: 'f'.repeat(64) })).reason, 'recipient_binding_required');
  f.state.role = false;
  assert.equal((await f.send()).reason, 'fresh_paid_role_required');
  f.state.role = true;
  f.sqlite.exec('UPDATE new_a_active_pointer SET revision=3');
  assert.equal((await f.send()).reason, 'current_source_and_opt_in_required');
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM cloud_push_dispatch_receipts').get().n, 0);
  assert.equal(f.state.sends, 0);
});

test('owner opt-out immediately after claiming holds without calling the provider', async t => {
  const f = await setup(t, { morning: true });
  f.state.afterClaim = () => {
    const off = { ...f.preferences, notifications: { new_detection: true, reminder: false } };
    f.sqlite.prepare('UPDATE cloud_member_preferences SET preferences_json=?').run(JSON.stringify(off));
  };
  assert.equal((await f.send()).reason, 'final_qualification_changed');
  assert.equal((await f.adapter.readNewAOwnerPushReceipt(f.env, f.notice)).status, 'held');
  assert.equal(f.state.sends, 0);
});

test('an accepted provider request with lost receipt write never triggers another POST', async t => {
  const f = await setup(t);
  f.state.failSave = true;
  assert.equal((await f.send()).status, 'unknown');
  assert.equal((await f.adapter.readNewAOwnerPushReceipt(f.env, f.notice)).status, 'preparing');
  f.state.failSave = false;
  assert.equal((await f.send()).status, 'suppressed');
  assert.equal(f.state.sends, 1);
});

test('unknown provider outcome is lookup-only', async t => {
  const f = await setup(t);
  f.state.failSend = true;
  assert.equal((await f.send()).status, 'unknown');
  const receipt = await f.adapter.readNewAOwnerPushReceipt(f.env, f.notice);
  assert.equal(receipt.status, 'unknown');
  assert.equal(receipt.reason, 'delivery_outcome_unknown_no_auto_retry');
  assert.equal((await f.send()).status, 'suppressed');
  assert.equal(f.state.sends, 1);
});
