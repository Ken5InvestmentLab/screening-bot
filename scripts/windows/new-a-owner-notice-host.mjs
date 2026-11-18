// Official normal-origin status and read-only owner qualification for the
// canonical post-publication notice producer. No browsing or provider POST.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadDailyConfig, verifyAcceptedWorker } from './weak-early-beta-daily-runner.mjs';
import { operationalLoader } from './new-a-operational-loader.mjs';

const HEX = /^[a-f0-9]{64}$/;
export async function observeOwnerNoticeRuntime(configFile, release, {
  loader = operationalLoader, readWorker = verifyAcceptedWorker, readConfig = loadDailyConfig,
  request = fetch, now = () => Date.now(),
} = {}) {
  const config = readConfig(configFile);
  const owner = await loader(configFile, { includeOwnerBinding: true, checkOwnerRole: true });
  if (owner.schema !== 'NEW_A_EXISTING_LOADER_METADATA_V1' || !HEX.test(owner.owner_binding_sha256) ||
      owner.policy_sha256 !== release.policy_sha256 || typeof owner.fresh_paid_role !== 'boolean' ||
      path.resolve(config.repoPath) !== process.cwd()) throw Error('accepted_owner_policy_unavailable');

  let metadata;
  const read = async (url, options) => {
    const response = await request(url, options);
    if (response.status === 200) metadata = await response.clone().json();
    return response;
  };
  const live = await readWorker(release, release.source_commit, read);
  if (live.sourceCommit !== release.source_commit || live.versionId !== release.version_id ||
      live.buildInputSha256 !== release.build_input_sha256 || !HEX.test(metadata?.d1_active_sha256)) {
    throw Error('accepted_notice_runtime_unavailable');
  }
  const at = now();
  const roleObservedAt = owner.owner_role_observed_at_ms;
  if (!Number.isSafeInteger(roleObservedAt) || roleObservedAt > at || at - roleObservedAt >= 30_000) {
    throw Error('accepted_owner_role_observation_expired');
  }
  return { schema: 'NEW_A_OWNER_NOTICE_RUNTIME_V1', source_commit: live.sourceCommit, worker_version_id: live.versionId,
    d1_active_sha256: metadata.d1_active_sha256, normal_owner_policy_verified: true,
    owner_binding_sha256: owner.owner_binding_sha256, fresh_paid_role: owner.fresh_paid_role,
    observed_at: new Date(at).toISOString(), expires_at: new Date(roleObservedAt + 30_000).toISOString() };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const raw = readFileSync(0, 'utf8');
    if (raw.length > 8192 || !process.argv[2] || process.argv.length !== 3) throw Error('invalid_host_observation');
    const value = await observeOwnerNoticeRuntime(process.argv[2], JSON.parse(raw));
    console.log(JSON.stringify(value));
  } catch {
    console.error('owner_notice_runtime_unavailable');
    process.exitCode = 1;
  }
}
