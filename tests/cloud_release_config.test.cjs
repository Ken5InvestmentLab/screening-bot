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
    c => { c.vars.CLOUD_NEW_A_OWNER_PUSH_ENABLED = 'true'; },
    c => { c.vars.DISCORD_ALLOWED_ROLE_IDS = ''; },
    c => { c.assets.run_worker_first = false; },
  ]) {
    const changed = structuredClone(config); mutate(changed);
    assert.throws(() => verifyReleaseConfig(changed));
  }
});

test('personal manual release requires managed role/public key and keeps runtime secrets out of Git', async () => {
  const { verifyReleaseConfig } = await import('../weak-early-beta-gate/scripts/verify-release-config.mjs');
  const personal = structuredClone(config);
  personal.vars.CLOUD_PUSH_MODE = 'personal_test';
  personal.vars.CLOUD_PUSH_REGISTRATION_ENABLED = 'true';
  personal.vars.CLOUD_PUSH_AUDIENCE = 'authenticated';
  verifyReleaseConfig(personal);
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
    const changed = structuredClone(personal); mutate(changed);
    assert.throws(() => verifyReleaseConfig(changed));
  }
  const off = structuredClone(personal);
  off.vars.CLOUD_PUSH_MODE = 'disabled'; off.vars.CLOUD_PUSH_REGISTRATION_ENABLED = 'false';
  verifyReleaseConfig(off);
});

function ownerProfile(mode, scheduled) {
  const owner = structuredClone(config);
  owner.vars.CLOUD_PUSH_MODE = mode;
  owner.vars.CLOUD_PUSH_REGISTRATION_ENABLED = 'true';
  owner.vars.CLOUD_PUSH_AUDIENCE = 'paid';
  owner.vars.CLOUD_NEW_A_OWNER_PUSH_ENABLED = String(scheduled);
  return owner;
}

test('owner registration release is paid-only, sending OFF and has no scheduler', async () => {
  const { verifyReleaseConfig } = await import('../weak-early-beta-gate/scripts/verify-release-config.mjs');
  const owner = ownerProfile('new_a_owner_registration', false);
  verifyReleaseConfig(owner);
  for (const mutate of [
    c => { c.vars.CLOUD_PUSH_AUDIENCE = 'authenticated'; },
    c => { c.vars.CLOUD_PUSH_REGISTRATION_ENABLED = 'false'; },
    c => { delete c.vars.CLOUD_NEW_A_OWNER_PUSH_ENABLED; },
    c => { c.vars.CLOUD_NEW_A_OWNER_PUSH_ENABLED = 'true'; },
    c => { c.vars.CLOUD_PUSH_TEST_RUN_ID = 'fixture-only-forbidden'; },
    c => { c.triggers = { crons: ['0 23 * * *'] }; },
    c => { c.env.preview.vars.CLOUD_PUSH_MODE = 'new_a_owner_registration'; },
  ]) {
    const changed = structuredClone(owner); mutate(changed);
    assert.throws(() => verifyReleaseConfig(changed));
  }
});

test('scheduled owner release accepts only both New A crons and keeps fixed identity outside Git', async () => {
  const { verifyReleaseConfig } = await import('../weak-early-beta-gate/scripts/verify-release-config.mjs');
  const owner = ownerProfile('new_a_owner_scheduled', true);
  owner.triggers = { crons: ['0 23 * * *', '*/5 8-14 * * *'] };
  verifyReleaseConfig(owner);
  for (const mutate of [
    c => { c.vars.CLOUD_NEW_A_OWNER_PUSH_ENABLED = 'false'; },
    c => { c.vars.CLOUD_PUSH_SCHEDULER_ENABLED = 'true'; },
    c => { c.vars.CLOUD_VAPID_PRIVATE_KEY = 'fixture-only-forbidden'; },
    c => { c.vars.CLOUD_PUSH_TEST_DISCORD_USER_ID = '123456789012345678'; },
    c => { c.vars.CLOUD_PUSH_TEST_SUBSCRIPTION_ID = 'fixture-only-forbidden'; },
    c => { c.vars.CLOUD_OWNER_ONLY_ENABLED = 'true'; },
    c => { c.version_metadata = { binding: 'WRONG' }; },
    c => { c.main = 'src/other.ts'; },
    c => { c.triggers.crons = ['0 23 * * *']; },
    c => { c.triggers.crons = ['0 23 * * *', '0 23 * * *']; },
    c => { c.triggers.crons.push('0 8 * * *'); },
    c => { c.env.preview.triggers = structuredClone(c.triggers); },
    c => { c.env.preview.vars.CLOUD_NEW_A_OWNER_PUSH_ENABLED = 'true'; },
    c => { c.queues = { consumers: [{ queue: 'fixture-only-forbidden' }] }; },
  ]) {
    const changed = structuredClone(owner); mutate(changed);
    assert.throws(() => verifyReleaseConfig(changed));
  }
});

test('deployment does not rerun already applied production migrations', () => {
  const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/weak-early-beta-report-deploy.yml'), 'utf8');
  const scripts = JSON.parse(fs.readFileSync(path.join(__dirname, '../weak-early-beta-gate/package.json'), 'utf8')).scripts;
  assert.doesNotMatch(workflow + JSON.stringify(scripts), /d1\s+(?:migrations\s+apply|execute|time-travel\s+restore)/);
  assert.match(workflow, /test "\$GITHUB_SHA" = "\$target"/);
});

test('member viewing requires a separate production database outside the canonical preview', async () => {
  const { verifyReleaseConfig } = await import('../weak-early-beta-gate/scripts/verify-release-config.mjs');
  const member = structuredClone(config);
  member.vars.CLOUD_MEMBER_VIEW_ENABLED = 'true';
  const missing = structuredClone(member);
  missing.d1_databases = missing.d1_databases.filter(binding => binding.binding !== 'CLOUD_MEMBER_DB');
  assert.throws(() => verifyReleaseConfig(missing), /dedicated database/);
  verifyReleaseConfig(member);
  for (const change of [
    c => { c.d1_databases.at(-1).database_id = c.d1_databases[0].database_id; },
    c => { c.d1_databases.at(-1).database_name = 'tentei-cloud-member-stage-member'; },
    c => { c.d1_databases.at(-1).remote = true; },
    c => { c.d1_databases.at(-1).preview_database_id = c.d1_databases.at(-1).database_id; },
    c => { c.vars.CLOUD_MEMBER_STAGE_ORIGIN = 'https://stage.example.invalid'; },
    c => { delete c.vars.CLOUD_MEMBER_AUDIENCE; },
    c => { c.vars.CLOUD_MEMBER_AUDIENCE = 'role_only'; },
    c => { c.env.preview.vars.CLOUD_MEMBER_VIEW_ENABLED = 'true'; },
  ]) {
    const invalid = structuredClone(member);
    change(invalid);
    assert.throws(() => verifyReleaseConfig(invalid));
  }
});
