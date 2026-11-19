import type { OperationalBuild } from './operational-readback';
import type { MemberTier } from './new-a-role-facade';

type WorkerVersion = { id?: string; tag?: string };
type PolicyRow = {
  revision: number;
  mode: string;
  source_commit: string;
  worker_version_id: string;
  canary_nonce: string | null;
  canary_subject_hmac: string | null;
  canary_free_subject_hmac: string | null;
};

const readPolicy = 'SELECT revision, mode, source_commit, worker_version_id, canary_nonce, canary_subject_hmac, canary_free_subject_hmac'
  + ' FROM new_a_member_release_policy WHERE singleton = 1';
const commit = /^[a-f0-9]{40}$/;
const version = /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const hex256 = /^[a-f0-9]{64}$/;
const encoder = new TextEncoder();

function decodeHex64(value: string): Uint8Array<ArrayBuffer> {
  return Uint8Array.from({ length: 32 }, (_, i) => parseInt(value.slice(i * 2, i * 2 + 2), 16));
}

export async function memberReleaseAllows(
  db: Pick<D1Database, 'withSession'> | undefined,
  build: OperationalBuild,
  metadata: WorkerVersion | undefined,
  subject: string,
  tier: MemberTier = 'premium',
): Promise<boolean> {
  const source = build.source_commit;
  const workerVersion = metadata?.id;
  if (!db || !workerVersion || !version.test(workerVersion) || metadata?.tag !== source
    || build.target.worker !== 'tentei-kyokuchi-cloud' || !commit.test(source) || !/^\d{17,20}$/.test(subject)) return false;

  try {
    // A fresh first-primary query on every authorization sees off and new policy revisions.
    const row = await db.withSession('first-primary').prepare(readPolicy).first<PolicyRow>();
    if (!row || !Number.isSafeInteger(row.revision) || row.revision < 1 || row.source_commit !== source
      || row.worker_version_id !== workerVersion) return false;
    if (row.mode === 'enabled') return row.canary_nonce === null && row.canary_subject_hmac === null
      && row.canary_free_subject_hmac === null;
    if (row.mode !== 'canary' || typeof row.canary_nonce !== 'string' || !hex256.test(row.canary_nonce)
      || typeof row.canary_subject_hmac !== 'string' || !hex256.test(row.canary_subject_hmac)
      || typeof row.canary_free_subject_hmac !== 'string' || !hex256.test(row.canary_free_subject_hmac)
      || row.canary_subject_hmac === row.canary_free_subject_hmac) return false;

    const key = await crypto.subtle.importKey('raw', decodeHex64(row.canary_nonce), { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']);
    const message = encoder.encode(JSON.stringify(['new-a-member-rollout-subject-v1', source, workerVersion, subject]));
    const target = tier === 'free' ? row.canary_free_subject_hmac : row.canary_subject_hmac;
    return await crypto.subtle.verify('HMAC', key, decodeHex64(target), message);
  } catch {
    return false;
  }
}
