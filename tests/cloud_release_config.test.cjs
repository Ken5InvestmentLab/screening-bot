const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const config = JSON.parse(fs.readFileSync(path.join(__dirname, '../weak-early-beta-gate/wrangler.jsonc'), 'utf8'));
test('release preserves production access/D1 and excludes previews and broad delivery', async () => {
  const { verifyReleaseConfig } = await import('../weak-early-beta-gate/scripts/verify-release-config.mjs');
  verifyReleaseConfig(config);
  for (const mutate of [
    c => { c.d1_databases = []; },
    c => { c.d1_databases[0].remote = true; },
    c => { c.d1_databases[0].preview_database_id = c.d1_databases[0].database_id; },
    c => { c.env.preview.d1_databases = structuredClone(c.d1_databases); },
    c => { c.preview_urls = true; },
    c => { c.vars.CLOUD_PUSH_MODE = 'members'; },
    c => { c.vars.CLOUD_PUSH_REGISTRATION_ENABLED = c.vars.CLOUD_PUSH_REGISTRATION_ENABLED === 'true' ? 'false' : 'true'; },
    c => { c.vars.CLOUD_PUSH_SCHEDULER_ENABLED = 'true'; },
    c => { c.vars.DISCORD_ALLOWED_ROLE_IDS = ''; },
    c => { c.assets.run_worker_first = false; },
  ]) {
    const changed = structuredClone(config); mutate(changed);
    assert.throws(() => verifyReleaseConfig(changed));
  }
});

test('personal manual release requires managed role/public key and keeps runtime secrets out of Git', async () => {
  const { verifyReleaseConfig } = await import('../weak-early-beta-gate/scripts/verify-release-config.mjs');
  assert.equal(config.vars.CLOUD_PUSH_MODE, 'personal_test');
  for (const mutate of [
    c => { c.keep_vars = false; },
    c => { c.vars.CLOUD_PUSH_MEMBERSHIP_POLICY = 'whop_api'; },
    c => { c.vars.CLOUD_VAPID_PUBLIC_KEY = ''; },
    c => { c.vars.CLOUD_VAPID_SUBJECT = 'https://other.example.invalid'; },
    c => { c.vars.CLOUD_PUSH_TEST_MEMBER_ID = 'cloud_' + 'a'.repeat(64); },
    c => { c.vars.CLOUD_VAPID_PRIVATE_KEY = 'fixture-only-forbidden'; },
    c => { c.env.preview.vars.CLOUD_PUSH_MODE = 'personal_test'; },
    c => { c.triggers = {crons:['0 23 * * *']}; },
  ]) {
    const changed = structuredClone(config); mutate(changed);
    assert.throws(() => verifyReleaseConfig(changed));
  }
  const off = structuredClone(config);
  off.vars.CLOUD_PUSH_MODE = 'disabled'; off.vars.CLOUD_PUSH_REGISTRATION_ENABLED = 'false';
  verifyReleaseConfig(off);
});
test('deployment does not rerun already applied production migrations', () => {
  const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/weak-early-beta-report-deploy.yml'), 'utf8');
  const scripts = JSON.parse(fs.readFileSync(path.join(__dirname, '../weak-early-beta-gate/package.json'), 'utf8')).scripts;
  assert.doesNotMatch(workflow + JSON.stringify(scripts), /d1\s+(?:migrations\s+apply|execute|time-travel\s+restore)/);
  assert.match(workflow, /test "\$GITHUB_SHA" = "\$target"/);
});
