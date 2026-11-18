import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const productionDatabaseId = 'e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb';
const ownerRegistration = 'new_a_owner_registration';
const ownerScheduledDelivery = 'new_a_owner_scheduled';
const ownerNoticeCrons = ['*/5 8-14 * * *', '0 23 * * *'];
const runtimeOnlyVars = [
  'CLOUD_OWNER_DISCORD_ID', 'CLOUD_OWNER_ONLY_ENABLED', 'CLOUD_ROLE_INITIAL_WAIT',
  'CLOUD_VAPID_PRIVATE_KEY', 'CLOUD_PUSH_TEST_DISCORD_USER_ID', 'CLOUD_PUSH_TEST_MEMBER_ID',
  'CLOUD_PUSH_TEST_SUBSCRIPTION_ID', 'CLOUD_PUSH_TEST_RUN_ID', 'CLOUD_PUSH_ALLOWED_ORIGINS',
  'CLOUD_DISCORD_BOT_TOKEN', 'DISCORD_CLIENT_SECRET', 'SESSION_SECRET', 'WHOP_API_KEY',
];

function verifyRegistration(vars, audience) {
  assert.equal(vars.CLOUD_PUSH_REGISTRATION_ENABLED, 'true');
  assert.equal(vars.CLOUD_PUSH_MEMBERSHIP_POLICY, 'whop_managed_discord_role');
  assert.equal(vars.CLOUD_PUSH_AUDIENCE, audience, 'wrong notification audience for this release mode');
  const key = Buffer.from(vars.CLOUD_VAPID_PUBLIC_KEY ?? '', 'base64url');
  assert.equal(key.length, 65, 'valid VAPID public key required');
  assert.equal(key[0], 4);
  assert.equal(key.toString('base64url'), vars.CLOUD_VAPID_PUBLIC_KEY);
  assert.equal(vars.CLOUD_VAPID_SUBJECT, 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/');
}

export function verifyReleaseConfig(config) {
  assert.equal(config.name, 'tentei-kyokuchi-cloud', 'wrong production Worker');
  assert.equal(config.assets?.run_worker_first, true, 'assets must pass through the access gate');
  assert.equal(config.preview_urls, false, 'production version preview URLs must stay disabled');
  const db = config.d1_databases?.find(value => value.binding === 'CLOUD_DB');
  assert.equal(db?.database_name, 'tentei-cloud-settings', 'missing production settings DB');
  assert.equal(db?.database_id, productionDatabaseId, 'wrong production settings DB');
  assert.equal(db?.migrations_dir, 'migrations');
  assert.equal(db?.remote, false, 'local development must not use remote D1');
  assert.notEqual(db?.preview_database_id, productionDatabaseId, 'preview cannot reuse production D1');
  assert.equal(config.vars?.DISCORD_GUILD_ID, '1479418833352785944');
  assert.equal(config.vars?.DISCORD_ALLOWED_ROLE_IDS, '1487089073385373828');
  assert.equal(config.vars?.SESSION_TTL_SECONDS, '31536000');
  const authority = config.durable_objects?.bindings?.find(value => value.name === 'CLOUD_ROLE_AUTHORITY');
  assert.equal(authority?.class_name, 'CloudRoleAuthority');
  assert.equal(authority?.script_name, undefined, 'authority stays inside Cloud, without another Worker dependency');
  assert.ok(config.migrations?.some(value => value.tag === 'cloud-role-authority-v1' && value.new_sqlite_classes?.includes('CloudRoleAuthority')));
  const preview = config.env?.preview;
  assert.equal(preview?.name, 'tentei-kyokuchi-cloud-preview');
  assert.deepEqual(preview?.d1_databases, [], 'preview must have no D1 binding');
  assert.equal(preview?.preview_urls, false);
  const previewAuthority = preview.durable_objects?.bindings?.find(value => value.name === 'CLOUD_ROLE_AUTHORITY');
  assert.equal(previewAuthority?.class_name, 'CloudRoleAuthority');
  assert.equal(previewAuthority?.script_name, undefined, 'preview must not point to production authority');
  assert.equal(config.keep_vars, true, 'retain the existing provider wait and runtime settings');
  const mode = config.vars?.CLOUD_PUSH_MODE;
  const manual = mode === 'personal_test';
  const ownerProfile = mode === ownerRegistration || mode === ownerScheduledDelivery;
  const scheduled = mode === ownerScheduledDelivery;
  assert.ok(mode === 'disabled' || manual || ownerProfile, 'unknown production notification mode');
  if (manual || ownerProfile) verifyRegistration(config.vars, manual ? 'authenticated' : 'paid');
  if (ownerProfile) {
    assert.equal(config.main, 'src/index.ts', 'owner notices must run on the normal Cloud gate');
    assert.equal(config.version_metadata?.binding, 'CLOUD_VERSION_METADATA', 'owner notices need exact deployed release identity');
    assert.equal(config.vars.CLOUD_PUSH_SCHEDULER_ENABLED, 'false', 'legacy scheduler must stay OFF in an owner release');
    assert.equal(config.vars.CLOUD_NEW_A_OWNER_PUSH_ENABLED, scheduled ? 'true' : 'false',
      'New A delivery switch must match the explicit owner release mode');
  }
  for (const environment of [config, ...Object.values(config.env ?? {})]) {
    const production = environment === config;
    if (!production || (!manual && !ownerProfile)) {
      assert.equal(environment.vars?.CLOUD_PUSH_REGISTRATION_ENABLED, 'false', 'nonpersonal registration must stay OFF');
      assert.equal(environment.vars?.CLOUD_PUSH_MODE, 'disabled', 'nonpersonal sending must stay OFF');
    }
    for (const name of runtimeOnlyVars) {
      assert.equal(environment.vars?.[name], undefined, `${name} must remain outside checked-in vars`);
    }
    assert.notEqual(environment.vars?.CLOUD_PUSH_SCHEDULER_ENABLED, 'true', 'no legacy notification scheduler');
    if (production && scheduled) {
      const crons = environment.triggers?.crons;
      assert.ok(Array.isArray(crons), 'missing New A owner notice schedule');
      assert.deepEqual([...crons].sort(), ownerNoticeCrons, 'only the two New A owner notice schedules are permitted');
    } else {
      assert.ok([undefined, 'false'].includes(environment.vars?.CLOUD_NEW_A_OWNER_PUSH_ENABLED),
        'New A delivery must stay OFF outside its scheduled production release');
      assert.deepEqual(environment.triggers?.crons ?? [], [], 'no notification scheduler');
    }
    assert.equal(environment.queues?.consumers?.length ?? 0, 0, 'no notification consumer');
    for (const binding of environment.d1_databases ?? []) {
      if (environment !== config) assert.notEqual(binding.database_id, productionDatabaseId, 'nonproduction D1 cannot reuse production');
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const config = JSON.parse(await readFile(new URL('../wrangler.jsonc', import.meta.url), 'utf8'));
  verifyReleaseConfig(config);
  console.log('Release configuration verified: production Cloud access and D1 retained, preview has no D1 or push. Notification mode and schedules checked. No remote operation.');
}
