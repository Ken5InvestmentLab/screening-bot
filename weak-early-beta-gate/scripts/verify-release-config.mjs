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
  const preview = config.env?.preview;
  assert.equal(preview?.name, 'tentei-kyokuchi-cloud-preview');
  assert.deepEqual(preview?.d1_databases, [], 'preview must have no D1 binding');
  assert.equal(preview?.preview_urls, false);
  for (const environment of [config, ...Object.values(config.env ?? {})]) {
    assert.equal(environment.vars?.CLOUD_PUSH_REGISTRATION_ENABLED, 'false', 'push registration must stay OFF');
    assert.equal(environment.vars?.CLOUD_PUSH_MODE, 'disabled', 'push sending must stay OFF');
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
  console.log('Release configuration verified: production CLOUD_DB retained, preview has no D1, notifications OFF. No remote operation.');
}
