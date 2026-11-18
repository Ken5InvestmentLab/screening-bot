const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {DatabaseSync} = require('node:sqlite');
const test = require('node:test');
const {modules} = require('./helpers/cloud-worker-modules.cjs');

const owner = '100000000000000001';
const other = '100000000000000002';
const target = '2026-11-19';
const base = '2026-11-18';
const dataset = 'a-' + '1'.repeat(24);
const source = '2'.repeat(64);
const provenance = '3'.repeat(64);
const tradeAt = target + 'T09:02:14.126789+09:00';
const sha = value => createHash('sha256').update(value).digest('hex');
const schema = name => fs.readFileSync(path.join(__dirname, '../weak-early-beta-gate/schema', name), 'utf8');
const copy = value => JSON.parse(JSON.stringify(value));

async function fixture(t) {
 const sql = new DatabaseSync(':memory:');
 t.after(() => sql.close());
 sql.exec(schema('new-a-private.sql'));
 sql.exec(schema('new-a-opening-observation.sql'));
 const clock = {now: Date.parse(target + 'T09:04:00+09:00')};
 const {load} = modules({clock});
 const service = load('./new-a-opening-observation');
 const {cloudMemberId} = load('./cloud-api');
 const member = await cloudMemberId(owner);
 const {DEFAULTS} = load('./new-a-preferences');
 const queries = [];
 let interceptWrite;
 const db = {prepare(query) {
  queries.push(query);
  return {bind(...args) {
   return {first: async () => {
    if (query.includes('ON CONFLICT')) interceptWrite?.();
    return sql.prepare(query).get(...args) ?? null;
   }};
  }};
 }};
 const manifest = (asOf = base, next = target, live = true) => JSON.stringify({
  schema: 'A_BROWSER_PRIVATE_INPUT_V1', audience: 'EXISTING_CLOUD_OWNER_ONLY',
  source_version: source,
  input_header: {source_version: source, limits: {completeThrough: asOf, nextPlannedSession: next}},
  quotes: [], collections: {episodes: [{name: 'episodes-000.json', sha256: '4'.repeat(64), bytes: 2, rows: 0}],
   intents: [], watches: [], current_daily: [], presentation: []},
  as_of: asOf, live,
 });
 const publish = (id, revision, raw = manifest()) => {
  sql.prepare('INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?)')
   .run(id, source, raw, sha(raw), 'READY', clock.now.toString());
  sql.prepare(`INSERT INTO new_a_active_pointer VALUES ('owner',?,?,?)
   ON CONFLICT(pointer_key) DO UPDATE SET dataset_id=excluded.dataset_id,revision=excluded.revision`)
   .run(id, revision, clock.now.toString());
 };
 publish(dataset, 5);
 const prefs = (revision = 3, who = member) =>
  sql.prepare(`INSERT INTO new_a_finite_trial_preferences VALUES (?,1,?,?,?)
   ON CONFLICT(member_id) DO UPDATE SET preferences_json=excluded.preferences_json,revision=excluded.revision`)
   .run(who, JSON.stringify(DEFAULTS), revision, clock.now.toString());
 prefs();
 const row = {symbol: '123A', candidate_date: '2026-11-12', episode_id: 17, status: 'FIRST_TRADE_VERIFIED',
  trade_at: tradeAt, actual_price_yen: 199.1};
 const waiting = {symbol: '9876', candidate_date: base, episode_id: 7, status: 'AWAITING_FIRST_TRADE'};
 const input = {target_date: target, dataset_id: dataset, pointer_revision: 5, manifest_sha256: sha(manifest()),
  preferences_revision: 3, expected_revision: 0, source_receipt_sha256: provenance, rows: [row, waiting]};
 const save = (selection = input, time = clock.now, who = member) =>
  service.saveOpeningObservation(db, who, selection, time);
 const route = load('./new-a-cloud').newACloudRoute;
 const context = {ownerAuthorized: true, roleAuthorized: true, current: true, subject: owner};
 const env = {CLOUD_DB: db, CLOUD_OWNER_DISCORD_ID: owner};
 const read = (init, auth = context, configured = env, search = '') =>
  route(new Request('https://synthetic.invalid' + service.OPENING_OBSERVATION_PATH + search, init), configured, auth);
 return {sql, db, input, row, waiting, save, read, publish, manifest, prefs, queries, clock, service, context, env, member,
  intercept: callback => { interceptWrite = callback; }};
}

test('opening read is only available to the fixed authenticated owner, even without posted rows', async t => {
 const f = await fixture(t);
 assert.equal((await f.read(undefined, {...f.context, ownerAuthorized: false})).status, 401);
 assert.equal((await f.read(undefined, {...f.context, subject: other})).status, 403);
 assert.equal((await f.read(undefined, {...f.context, roleAuthorized: false})).status, 403);
 assert.equal((await f.read(undefined, {...f.context, current: false})).status, 503);
 assert.equal((await f.read({headers: {origin: 'https://other.invalid'}})).status, 403);
 assert.equal((await f.read({headers: {'sec-fetch-site': 'cross-site'}})).status, 403);
 for (const method of ['POST','PUT','DELETE','OPTIONS'])
  assert.equal((await f.read({method})).status, 405);
 assert.equal((await f.read(undefined, f.context, f.env, '?owner=other')).status, 404);
 assert.equal(f.queries.length, 0);
 const reply = await f.read();
 assert.equal(reply.headers.get('cache-control'), 'private, no-store, max-age=0');
 assert.equal(reply.headers.get('vary'), 'Cookie');
 assert.deepEqual(await reply.json(), {state: 'empty', target_date: target});
 assert.doesNotMatch(f.queries[0], /LEFT JOIN new_a_opening_observations/);
 const head = await f.read({method: 'HEAD'});
 assert.equal(head.status, 200);
 assert.equal(await head.text(), '');
 assert.equal(f.sql.prepare('SELECT count(*) AS count FROM new_a_opening_observations').get().count, 0);
});

test('operator CAS stores a sealed snapshot and the reader projects only safe row fields', async t => {
 const f = await fixture(t);
 assert.deepEqual(copy(await f.save()), {revision: 1});
 const response = await f.read();
 const body = await response.json();
 assert.equal(response.status, 200);
 const {episode_id: _private, ...row} = f.row;
 const {episode_id: _waiting, ...waiting} = f.waiting;
 assert.deepEqual(body, {state: 'ready', target_date: target, updated_at: new Date(f.clock.now).toISOString(),
  revision: 1, rows: [row, waiting]});
 const stored = f.sql.prepare('SELECT * FROM new_a_opening_observations').get();
 assert.equal(stored.source_receipt_sha256, provenance);
 assert.equal(sha(stored.rows_json), stored.rows_sha256);
 assert.equal(stored.member_id, f.member);
 assert.equal(JSON.parse(stored.rows_json)[0].episode_id, f.row.episode_id);
 assert.equal(await f.save(), null);
 f.clock.now += 60_000;
 const next = {...f.input, expected_revision: 1, rows: [{...f.row, status: 'PROVISIONAL_ELIGIBLE'}, f.waiting]};
 assert.deepEqual(copy(await f.save(next)), {revision: 2});
 assert.equal(await f.save({...next, expected_revision: 2}, f.clock.now - 60_000), null);
 const head = await f.read({method: 'HEAD'});
 assert.equal(head.status, 200);
 assert.equal(await head.text(), '');
 assert.equal((await (await f.read()).json()).rows[0].status, 'PROVISIONAL_ELIGIBLE');
});

test('scope invalidates old target, pointer, unset or changed preferences, and already-published results', async t => {
 const f = await fixture(t);
 await f.save();
 const assertEmpty = async (day = target) => {
  assert.deepEqual(await (await f.read()).json(), {state: 'empty', target_date: day});
 };
 f.clock.now = Date.parse('2026-11-20T00:01:00+09:00');
 await assertEmpty('2026-11-20');
 f.clock.now = Date.parse(target + 'T09:04:00+09:00');
 const otherMember = 'cloud_' + '9'.repeat(64);
 f.prefs(3, otherMember);
 assert.deepEqual(copy(await f.service.readOpeningObservation(f.db, otherMember)), {state: 'empty', target_date: target});
 f.prefs(4);
 await assertEmpty();
 assert.equal(await f.save({...f.input, expected_revision: 1}), null);
 f.sql.prepare('DELETE FROM new_a_finite_trial_preferences WHERE member_id=?').run(f.member);
 await assertEmpty();
 f.prefs(3);
 f.sql.prepare('UPDATE new_a_active_pointer SET revision=6').run();
 await assertEmpty();
 assert.equal(await f.save({...f.input, expected_revision: 1}), null);
 const newDataset = 'a-' + 'a'.repeat(24);
 const finished = f.manifest(target, '2026-11-20');
 f.publish(newDataset, 7, finished);
 assert.equal(await f.save({...f.input, dataset_id: newDataset, pointer_revision: 7, manifest_sha256: sha(finished)}), null);
 await assertEmpty();
 assert.equal(f.sql.prepare('SELECT count(*) AS count FROM new_a_opening_observations').get().count, 1);
});

test('operator write atomically fails if preferences, pointer or revision change during validation', async t => {
 const f = await fixture(t);
 f.intercept(() => f.prefs(4));
 assert.equal(await f.save(), null);
 f.prefs(3);
 f.intercept(() => f.sql.prepare('UPDATE new_a_active_pointer SET revision=6').run());
 assert.equal(await f.save(), null);
 f.sql.prepare('UPDATE new_a_active_pointer SET revision=5').run();
 f.intercept(undefined);
 const results = await Promise.all([f.save(),f.save()]);
 assert.equal(results.filter(Boolean).length, 1);
 assert.equal(results.filter(value => value === null).length, 1);
 assert.equal((await (await f.read()).json()).revision, 1);
});

test('saved view is validated and checked in the same CAS as the base trial', async t => {
 const f = await fixture(t);
 const view = {trial_preset: 'balanced', theme: 'light', font_size: 'standard', page_size: 50};
 const member = 'new-a-view:v1:' + f.member;
 f.sql.prepare('INSERT INTO new_a_finite_trial_preferences VALUES (?,1,?,2,?)')
  .run(member, JSON.stringify(view), 'fixture');
 f.intercept(() => f.sql.prepare('UPDATE new_a_finite_trial_preferences SET revision=3 WHERE member_id=?').run(member));
 assert.equal(await f.save(), null);
 f.intercept(undefined);
 const extra = {...f.waiting, symbol: 'AB12'};
 assert.deepEqual(copy(await f.save({...f.input, rows: [f.row, extra]})), {revision: 1});
 const body = await (await f.read()).json();
 assert.equal(body.rows[1].symbol, extra.symbol);
 assert(!JSON.stringify(body).includes('trial_preset'));
 f.sql.prepare('UPDATE new_a_finite_trial_preferences SET preferences_json=? WHERE member_id=?').run('{}', member);
 assert.equal((await f.read()).status, 503);
});

test('invalid trade clocks, non-regular price fields and corrupted persistence fail closed', async t => {
 const f = await fixture(t);
 const invalid = [
  {...f.row, trade_at: target + 'T08:59:59+09:00'},
  {...f.row, trade_at: target + 'T11:30:01+09:00'},
  {...f.row, trade_at: target + 'T12:30:00+09:00'},
  {...f.row, trade_at: target + 'T09:05:00+09:00'},
  {...f.row, trade_at: base + 'T09:02:00+09:00'},
  {...f.row, actual_price_yen: '199.1'},
  {...f.row, actual_price_yen: 100.10000000001},
  {...f.waiting, status: 'PROVISIONAL_ELIGIBLE'},
  {...f.row, status: 'AWAITING_FIRST_TRADE'},
  {...f.row, candidate_date: target},
  {...f.row, raw_order: 'not_for_display'},
 ];
 for (const row of invalid) await assert.rejects(f.save({...f.input, rows: [row]}), /opening_/);
 await assert.rejects(f.save({...f.input, rows: [f.row, {...f.row, episode_id: 18}]}), /opening_row_duplicate/);
 await assert.rejects(f.save({...f.input, source_receipt_sha256: 'unsealed'}), /opening_input/);
 await f.save();
 const bad = JSON.stringify([{...f.row, raw_order: 'not_for_display'}]);
 f.sql.prepare('UPDATE new_a_opening_observations SET rows_json=?').run(bad);
 assert.equal((await f.read()).status, 503);
 f.sql.prepare('UPDATE new_a_opening_observations SET rows_sha256=?').run(sha(bad));
 const reply = await f.read();
 assert.equal(reply.status, 503);
 assert.deepEqual(await reply.json(), {error: 'new_a_service_unavailable'});
});
