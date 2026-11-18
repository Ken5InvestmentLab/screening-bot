// Standard CI deployment -> actual normal-origin response. No session or override.
import fs from 'node:fs';
import { randomBytes } from 'node:crypto';
import { setTimeout as sleep } from 'node:timers/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ORIGIN = 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
const SHA = /^[a-f0-9]{64}$/;
const COMMIT = /^[a-f0-9]{40}$/;
const VERSION = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const OBSERVATION_DELAYS = [0, 2000, 4000, 8000, 12000];

export async function verifyOperationalLive(receipt, head, {
  fetchImpl = fetch, wait = sleep, nonce = () => randomBytes(32).toString('hex'),
} = {}) {
  if (receipt.ok !== true || !COMMIT.test(head) || receipt.headSha !== head ||
      !VERSION.test(receipt.versionId) || receipt.operationalBuild?.source_commit !== head ||
      !SHA.test(receipt.operationalBuild.build_input_sha256)) {
    throw Error('Exact successful CI release unavailable');
  }
  for (const delay of OBSERVATION_DELAYS) {
    if (delay) await wait(delay);
    const freshness = nonce();
    const url = ORIGIN + '/healthz?new_a_probe=' + freshness;
    const response = await fetchImpl(url, { redirect: 'error', headers: { 'Cache-Control': 'no-cache' },
      signal: AbortSignal.timeout(15000) });
    if (response.status !== 200 || response.url !== url ||
        !response.headers.get('cache-control')?.includes('no-store')) {
      throw Error('Normal operational response unavailable');
    }
    const actual = await response.json();
    if (actual.schema !== 'NEW_A_OPERATIONAL_READBACK_V1' || actual.nonce !== freshness ||
        !COMMIT.test(actual.source_commit) || !VERSION.test(actual.version?.id) ||
        actual.version?.tag !== actual.source_commit || !SHA.test(actual.build_input_sha256) ||
        actual.owner_http_observed !== false || actual.authentication_probe !== false || actual.d1_writes !== 0) {
      throw Error('Normal operational response integrity mismatch');
    }
    // A well-formed response from another version can arrive before Cloudflare
    // propagates the new deployment. Observe again without issuing another deploy.
    if (actual.version.id !== receipt.versionId) continue;
    if (actual.source_commit !== head || actual.build_input_sha256 !== receipt.operationalBuild.build_input_sha256) {
      throw Error('Expected Worker reported a different source or build');
    }
    return { identity: 'NEW_A_CI_NORMAL_VERSION_READBACK_V1', source_commit: head,
      version_id: receipt.versionId, build_input_sha256: actual.build_input_sha256,
      owner_http_observed: false, management_deployment_observed: false };
  }
  throw Error('Normal origin did not serve the deployed Worker version in time');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const receipt = JSON.parse(fs.readFileSync('../.cache/weak_early_beta/cloud-deploy-recovery.json', 'utf8'));
  console.log(JSON.stringify(await verifyOperationalLive(receipt, process.env.GITHUB_SHA)));
}
