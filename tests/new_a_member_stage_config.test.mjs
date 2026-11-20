import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  createMemberStageConfig,
  stageOrigin,
} from '../weak-early-beta-gate/scripts/prepare-new-a-member-stage.mjs';

const gate = fileURLToPath(new URL('../weak-early-beta-gate/', import.meta.url));
const canonical = JSON.parse(fs.readFileSync(path.join(gate, 'wrangler.jsonc'), 'utf8'));
const outputDir = path.join(gate, '.cache', 'new-a-member-stage', 'stage-fixture');
const fixtures = {
  accountId: '1'.repeat(32),
  publicBaseUrl: stageOrigin,
  ownerDatabaseId: '11111111-1111-4111-8111-111111111111',
  memberDatabaseId: '22222222-2222-4222-8222-222222222222',
  ownerDiscordId: '100000000000000001',
};

test('stage preserves canonical Worker routes and role pins with isolated resources and notification delivery disabled', () => {
  const config = createMemberStageConfig(fixtures, canonical, outputDir);
  assert.notEqual(config.name, canonical.name);
  assert.notEqual(config.name, canonical.env.preview.name);
  assert.equal(path.resolve(outputDir, config.main), path.resolve(gate, 'src/index.ts'));
  assert.equal(path.resolve(outputDir, config.assets.directory), path.join(outputDir, 'public'));
  assert.equal(config.assets.run_worker_first, true);
  assert.equal(config.workers_dev, true);
  assert.equal(config.preview_urls, false);
  assert.equal(config.account_id, fixtures.accountId);
  assert.deepEqual(config.triggers.crons, []);
  assert.deepEqual(config.d1_databases.map(db => db.binding), ['CLOUD_DB', 'CLOUD_MEMBER_DB']);
  assert.deepEqual(config.d1_databases.map(db => db.database_id), [fixtures.ownerDatabaseId, fixtures.memberDatabaseId]);
  assert.equal(config.vars.DISCORD_GUILD_ID, canonical.vars.DISCORD_GUILD_ID);
  assert.equal(config.vars.DISCORD_ALLOWED_ROLE_IDS, canonical.vars.DISCORD_ALLOWED_ROLE_IDS);
  assert.equal(config.vars.PUBLIC_BASE_URL, stageOrigin);
  assert.equal(config.vars.CLOUD_MEMBER_STAGE_ORIGIN, stageOrigin);
  assert.equal(config.vars.CLOUD_OWNER_ONLY_ENABLED, 'true');
  assert.equal(config.vars.CLOUD_MEMBER_VIEW_ENABLED, 'true');
  assert.equal(config.vars.CLOUD_MEMBER_AUDIENCE, undefined);
  assert.equal(config.vars.CLOUD_PUSH_MODE, 'disabled');
  for (const name of ['CLOUD_PUSH_REGISTRATION_ENABLED', 'CLOUD_PUSH_SCHEDULER_ENABLED', 'CLOUD_NEW_A_OWNER_PUSH_ENABLED']) {
    assert.equal(config.vars[name], 'false');
  }
  assert.equal(Object.hasOwn(config.vars, 'DISCORD_CLIENT_SECRET'), false);
  assert.equal(Object.hasOwn(config.vars, 'SESSION_SECRET'), false);
  assert.equal(Object.hasOwn(config, 'env'), false);
  assert.equal(Object.hasOwn(config.durable_objects.bindings[0], 'script_name'), false);
  for (const { database_id, database_name } of canonical.d1_databases) {
    assert.ok(!JSON.stringify(config).includes(database_id));
    assert.ok(!JSON.stringify(config).includes(database_name));
  }
});

test('stage can explicitly verify the role-only audience on the same isolated bindings', () => {
  const config = createMemberStageConfig({ ...fixtures, audience: 'role_only' }, canonical, outputDir);
  assert.equal(config.vars.CLOUD_MEMBER_AUDIENCE, 'role_only');
  assert.equal(config.d1_databases[0].database_id, fixtures.ownerDatabaseId);
  assert.equal(config.d1_databases[1].database_id, fixtures.memberDatabaseId);
  assert.throws(() => createMemberStageConfig({ ...fixtures, audience: 'unsupported' }, canonical, outputDir),
    /supported member stage audience/);
});

test('missing, foreign or production resource values and role-pin drift fail closed', () => {
  const make = (override, source = canonical) => createMemberStageConfig({ ...fixtures, ...override }, source, outputDir);
  const production = canonical.d1_databases.find(db => db.binding === 'CLOUD_DB').database_id;
  for (const url of [
    'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev',
    stageOrigin.replace('ipo-ken5-5489', 'different-account'),
    stageOrigin.replace('https:', 'http:'),
    stageOrigin + '/auth/callback',
    stageOrigin + '?verify=1',
  ]) assert.throws(() => make({ publicBaseUrl: url }), /exact HTTPS/);
  assert.throws(() => make({ accountId: '' }), /Cloudflare account/);
  assert.throws(() => make({ ownerDiscordId: '' }), /Discord ID/);
  assert.throws(() => make({ memberDatabaseId: fixtures.ownerDatabaseId }), /distinct/);
  assert.throws(() => make({ ownerDatabaseId: production }), /canonical database/);
  assert.throws(() => make({ memberDatabaseId: production }), /canonical database/);
  assert.throws(() => make({ memberDatabaseId: '00000000-0000-0000-0000-000000000000' }), /valid/);
  const drift = structuredClone(canonical);
  drift.env.preview.vars.DISCORD_ALLOWED_ROLE_IDS = '100000000000000002';
  assert.throws(() => make({}, drift), /allowed-role pin/);
});
