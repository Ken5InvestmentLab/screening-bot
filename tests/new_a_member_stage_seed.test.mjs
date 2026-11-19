import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  createSyntheticStageSeed,
  verifyStageSeedTarget,
} from '../weak-early-beta-gate/scripts/prepare-new-a-member-stage-seed.mjs';
import workerModules from './helpers/cloud-worker-modules.cjs';

const modules = workerModules.modules();
const { createNewAMemberCurrentReader } = modules.load('new-a-member-current');
const { createNewAMemberProjectionReader } = modules.load('new-a-member-projection');
const { validateManifest, readPrivatePart } = modules.load('new-a-private');
const projectionSql = db => ({
  withSession(constraint) {
    assert.equal(constraint, 'first-primary');
    return statementBinding(db);
  },
});
const statementBinding = db => ({
  prepare(sql) {
    const statement = db.prepare(sql);
    const first = async (...bindings) => statement.get(...bindings) ?? null;
    return {
      first,
      bind(...bindings) {
        return { first: () => first(...bindings) };
      },
    };
  },
});
const digest = value => createHash('sha256').update(value).digest('hex');
function open(t) {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  t.after(() => db.close());
  return db;
}

test('separate stage databases load the same immutable READY owner and member projection', async t => {
  const seed = await createSyntheticStageSeed();
  const owner = open(t);
  const member = open(t);
  owner.exec(seed.ownerSql);
  member.exec(seed.memberSql);

  const row = owner.prepare('SELECT * FROM new_a_private_datasets').get();
  assert.equal(row.manifest_sha256, digest(row.manifest_json));
  assert.equal(row.dataset_id, 'a-' + row.manifest_sha256.slice(0, 24));
  const manifest = validateManifest(JSON.parse(row.manifest_json));
  assert.equal(manifest.live, false);
  for (const desc of [...Object.values(manifest.collections).flat(), ...manifest.quotes]) {
    const text = await readPrivatePart(statementBinding(owner), row.dataset_id, desc.name);
    assert.equal(digest(text), desc.sha256);
    assert.equal(Buffer.byteLength(text), desc.bytes);
    assert.equal(JSON.parse(text).length, desc.rows);
  }

  const current = createNewAMemberCurrentReader(projectionSql(owner));
  const source = await current();
  assert.deepEqual(JSON.parse(JSON.stringify(source)), seed.source);
  const shared = createNewAMemberProjectionReader(projectionSql(member), current);
  const history = await shared(source, 'history', 0);
  assert.deepEqual(JSON.parse(JSON.stringify(history.rows)), [
    { date: seed.source.as_of, symbol: '0000', state: 'WATCHING' },
    { date: '2026-11-18', symbol: '0001', state: 'EXPIRED' },
  ]);
  const completed = await shared(source, 'completed-history', 0);
  assert.deepEqual(JSON.parse(JSON.stringify(completed.rows)),
    [{ date: '2026-11-18', symbol: '0001', state: 'EXPIRED' }]);
  assert.equal(completed.history_pages, 1);
  const dashboard = await shared(source, 'dashboard', 0);
  assert.deepEqual(JSON.parse(JSON.stringify(dashboard.rows)), [
    { date: seed.source.as_of, symbol: '0000', state: 'WATCH_STARTED', lane: 'today' },
    { date: seed.source.as_of, symbol: '0000', state: 'WATCHING', lane: 'watching' },
  ]);
  assert.equal((await shared(source, 'analytics', 0)).rows.length, 3);
  for (let index = 0; index < 3; index++) assert.equal((await shared(source, 'chart', index)).rows.length, 1);
  assert.equal(member.prepare('SELECT count(*) n FROM new_a_member_settings').get().n, 0);
  assert.equal(member.prepare('SELECT count(*) n FROM new_a_member_results').get().n, 0);
  owner.exec("UPDATE new_a_active_pointer SET revision = 2 WHERE pointer_key = 'owner'");
  assert.equal(await shared(source, 'history', 0), null);
});

test('each seed refuses a preinitialized database before creating any tables', async t => {
  const seed = await createSyntheticStageSeed();
  for (const sql of [seed.ownerSql, seed.memberSql]) {
    const db = open(t);
    db.exec("CREATE TABLE existing_data (id TEXT NOT NULL); INSERT INTO existing_data VALUES ('retained');");
    assert.throws(() => db.exec(sql), /malformed JSON/i);
    assert.equal(db.prepare('SELECT count(*) n FROM sqlite_schema WHERE type = ?').get('table').n, 1);
    assert.equal(db.prepare('SELECT id FROM existing_data').get().id, 'retained');
  }
});

test('the normal Wrangler configuration is not an allowed seed target', async () => {
  const gate = fileURLToPath(new URL('../weak-early-beta-gate/', import.meta.url));
  await assert.rejects(verifyStageSeedTarget(path.join(gate, 'wrangler.jsonc')), /generated, ignored/);
});
