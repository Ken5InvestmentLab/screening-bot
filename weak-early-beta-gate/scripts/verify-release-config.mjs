import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const productionDatabaseId = 'e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb';
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
  const personal = config.vars?.CLOUD_PUSH_MODE === 'personal_test';
  if (personal) {
    assert.equal(config.keep_vars, true, 'retain operator-fixed member/device/provider runtime settings');
    assert.equal(config.vars.CLOUD_PUSH_REGISTRATION_ENABLED, 'true');
    assert.equal(config.vars.CLOUD_PUSH_MEMBERSHIP_POLICY, 'whop_managed_discord_role');
    assert.equal(config.vars.CLOUD_PUSH_AUDIENCE, 'authenticated', 'generic notifications are approved for logged-in free and paid users');
    const key = Buffer.from(config.vars.CLOUD_VAPID_PUBLIC_KEY ?? '', 'base64url');
    assert.equal(key.length, 65, 'valid VAPID public key required');
    assert.equal(key[0], 4);
    assert.equal(key.toString('base64url'), config.vars.CLOUD_VAPID_PUBLIC_KEY);
    assert.equal(config.vars.CLOUD_VAPID_SUBJECT, 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/');
    // Identity/device/provider are confirmed in the Dashboard; never published
    // into the repository. Runtime has no recipient fallback if they are absent.
    for (const name of ['CLOUD_VAPID_PRIVATE_KEY', 'CLOUD_PUSH_TEST_MEMBER_ID', 'CLOUD_PUSH_TEST_SUBSCRIPTION_ID',
      'CLOUD_PUSH_TEST_RUN_ID', 'CLOUD_PUSH_ALLOWED_ORIGINS', 'CLOUD_DISCORD_BOT_TOKEN', 'WHOP_API_KEY', 'CLOUD_ROLE_INITIAL_WAIT']) {
      assert.equal(config.vars[name], undefined, `${name} must remain outside checked-in vars`);
    }
  }
  for (const environment of [config, ...Object.values(config.env ?? {})]) {
    if (environment !== config || !personal) {
      assert.equal(environment.vars?.CLOUD_PUSH_REGISTRATION_ENABLED, 'false', 'nonpersonal registration must stay OFF');
      assert.equal(environment.vars?.CLOUD_PUSH_MODE, 'disabled', 'nonpersonal sending must stay OFF');
    }
    assert.equal(environment.vars?.CLOUD_ROLE_INITIAL_WAIT, undefined, 'owner wait metadata must stay outside Git');
    assert.notEqual(environment.vars?.CLOUD_PUSH_SCHEDULER_ENABLED, 'true', 'scheduled delivery must stay OFF in this manual-test release');
    assert.equal(environment.triggers?.crons?.length ?? 0, 0, 'no notification scheduler');
    assert.equal(environment.queues?.consumers?.length ?? 0, 0, 'no notification consumer');
    for (const binding of environment.d1_databases ?? []) {
      if (environment !== config) assert.notEqual(binding.database_id, productionDatabaseId, 'nonproduction D1 cannot reuse production');
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const config = JSON.parse(await readFile(new URL('../wrangler.jsonc', import.meta.url), 'utf8'));
  verifyReleaseConfig(config);
  console.log('Release configuration verified: production CLOUD_DB retained, preview has no D1/push, only explicitly fixed personal manual delivery is permitted, scheduler OFF. No remote operation.');
}
