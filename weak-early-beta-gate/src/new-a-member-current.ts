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
const publishedReady = 'SELECT r.identity, r.digest, m.json FROM private_projection_ready r'
  + ' JOIN private_projection_manifest m ON m.identity = r.identity AND m.digest = r.digest'
  + ' WHERE r.singleton = 1 AND length(CAST(m.json AS BLOB)) <= ?';
const archivedReady = 'SELECT dataset_id, status, source_version, manifest_json, manifest_sha256'
  + " FROM new_a_private_datasets WHERE dataset_id = ? AND status = 'READY'"
  + ' AND length(CAST(manifest_json AS BLOB)) <= ?';
const memberMarker = 'SELECT identity, digest FROM private_projection_ready WHERE singleton = 1';
const sourceKeys = ['status', 'dataset_id', 'revision', 'as_of', 'source_version'];
const maxProjectionBytes = 65_536;

function identity(value: unknown): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== sourceKeys.length || !sourceKeys.every(key => Object.hasOwn(row, key))
    || row.status !== 'READY' || typeof row.dataset_id !== 'string' || !DATASET_ID.test(row.dataset_id)
    || typeof row.revision !== 'number' || !Number.isSafeInteger(row.revision) || row.revision < 1
    || !isJstDay(row.as_of) || typeof row.source_version !== 'string' || !sha256.test(row.source_version)) return null;
  return JSON.stringify({ status: row.status, dataset_id: row.dataset_id, revision: row.revision,
    as_of: row.as_of, source_version: row.source_version });
}

async function verifiedOwner(row: ActiveRow | null): Promise<ReadyPointer | null> {
  if (!row || row.status !== 'READY' || typeof row.dataset_id !== 'string' || !DATASET_ID.test(row.dataset_id)
    || typeof row.revision !== 'number' || !Number.isSafeInteger(row.revision) || row.revision < 1
    || typeof row.source_version !== 'string' || !sha256.test(row.source_version)
    || typeof row.manifest_json !== 'string' || row.manifest_json.length > maxManifestBytes
    || typeof row.manifest_sha256 !== 'string' || !sha256.test(row.manifest_sha256)
    || await digest(row.manifest_json) !== row.manifest_sha256) return null;
  const manifest = validateManifest(JSON.parse(row.manifest_json));
  if (manifest.strategy !== 'A_BASE' || manifest.source_version !== row.source_version || !isJstDay(manifest.as_of)) return null;
  return { status: 'READY', dataset_id: row.dataset_id, revision: row.revision,
    as_of: manifest.as_of, source_version: row.source_version };
}

function isJstDay(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const time = Date.parse(value + 'T00:00:00Z');
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

// Each invocation uses a fresh primary read so action-time checks cannot reuse a replica bookmark.
export function createNewAMemberCurrentReader(
  db: PrimaryDatabase | undefined, member?: PrimaryDatabase,
): () => Promise<ReadyPointer | null> {
  return async () => {
    if (!db) return null;
    try {
      const row = await db.withSession('first-primary').prepare(activeReady).bind(maxManifestBytes).first<ActiveRow>();
      const official = await verifiedOwner(row);
      if (!official || member === undefined) return official;
      // The private owner can advance before member staging finishes. Continue
      // serving only the last fully published, independently verified generation.
      const published = await member.withSession('first-primary').prepare(publishedReady).bind(maxProjectionBytes)
        .first<{ identity: unknown; digest: unknown; json: unknown }>();
      if (!published || typeof published.identity !== 'string' || typeof published.digest !== 'string'
        || !sha256.test(published.digest) || typeof published.json !== 'string'
        || await digest(published.json) !== published.digest) return null;
      const source = JSON.parse(published.identity) as ReadyPointer;
      const key = identity(source);
      const manifest = JSON.parse(published.json);
      if (!key || key !== published.identity || identity(manifest?.source) !== key
        || !['NEW_A_SHARED_READONLY_VIEW_V1', 'NEW_A_SHARED_READONLY_VIEW_V2', 'NEW_A_SHARED_READONLY_VIEW_V3'].includes(manifest.schema)
        || manifest.basis !== 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS'
        || !['EXISTING_DESIGNATED_DISCORD_ROLE', 'AUTHENTICATED_TIERED_DISCORD_VIEW'].includes(manifest.audience)
        || source.revision > official.revision || source.as_of > official.as_of) return null;
      if (key !== identity(official)) {
        if (source.revision >= official.revision) return null;
        // A previous member generation remains eligible only while its exact
        // retained owner dataset is still READY and its manifest verifies.
        const prior = await db.withSession('first-primary').prepare(archivedReady)
          .bind(source.dataset_id, maxManifestBytes).first<Omit<ActiveRow, 'revision'>>();
        if (!prior || identity(await verifiedOwner({ ...prior, revision: source.revision })) !== key) return null;
      }
      const selected = await member.withSession('first-primary').prepare(memberMarker)
        .first<{ identity: unknown; digest: unknown }>();
      return selected?.identity === key && selected.digest === published.digest ? source : null;
    } catch {
      return null;
    }
  };
}
