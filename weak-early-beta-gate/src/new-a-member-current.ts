import { DATASET_ID, digest, validateManifest } from './new-a-private';
import type { ReadyPointer } from './new-a-member-services';

type PrimaryDatabase = Pick<D1Database, 'withSession'>;
type ActiveRow = {
  dataset_id: unknown;
  revision: unknown;
  status: unknown;
  source_version: unknown;
  manifest_json: unknown;
  manifest_sha256: unknown;
};
const maxManifestBytes = 1024 * 1024;
const sha256 = /^[a-f0-9]{64}$/;
const activeReady = 'SELECT d.dataset_id, p.revision, d.status, d.source_version, d.manifest_json, d.manifest_sha256'
  + ' FROM new_a_active_pointer p JOIN new_a_private_datasets d ON d.dataset_id = p.dataset_id'
  + " WHERE p.pointer_key = 'owner' AND d.status = 'READY'"
  + ' AND length(CAST(d.manifest_json AS BLOB)) <= ?';

function isJstDay(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const time = Date.parse(value + 'T00:00:00Z');
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

// Each invocation uses a fresh primary read so action-time checks cannot reuse a replica bookmark.
export function createNewAMemberCurrentReader(db: PrimaryDatabase | undefined): () => Promise<ReadyPointer | null> {
  return async () => {
    if (!db) return null;
    try {
      const row = await db.withSession('first-primary').prepare(activeReady).bind(maxManifestBytes).first<ActiveRow>();
      if (!row || row.status !== 'READY' || typeof row.dataset_id !== 'string' || !DATASET_ID.test(row.dataset_id)
        || typeof row.revision !== 'number' || !Number.isSafeInteger(row.revision) || row.revision < 1
        || typeof row.source_version !== 'string' || !sha256.test(row.source_version)
        || typeof row.manifest_json !== 'string' || row.manifest_json.length > maxManifestBytes
        || typeof row.manifest_sha256 !== 'string' || !sha256.test(row.manifest_sha256)
        || await digest(row.manifest_json) !== row.manifest_sha256) return null;

      const manifest = validateManifest(JSON.parse(row.manifest_json));
      if (manifest.strategy !== 'A_BASE' || manifest.source_version !== row.source_version || !isJstDay(manifest.as_of)) return null;
      return {
        status: 'READY',
        dataset_id: row.dataset_id,
        revision: row.revision,
        as_of: manifest.as_of,
        source_version: row.source_version,
      };
    } catch {
      return null;
    }
  };
}
