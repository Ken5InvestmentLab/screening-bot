import type { MemberAdapters, ReadyPointer } from './new-a-member-services';

type PartKind = 'history' | 'analytics' | 'chart';
type Row = Record<string, unknown>;
type Statement = { bind(...values: (string | number)[]): Statement; first<T>(): Promise<T | null> };
type D1Session = { prepare(sql: string): Statement };
type ProjectionDatabase = { withSession(constraint: 'first-primary'): D1Session };

const sourceKeys = ['status', 'dataset_id', 'revision', 'as_of', 'source_version'];
const presets = ['defensive', 'medium', 'return_priority'];
const states = new Set(['WATCHING', 'TRIGGERED', 'EXPIRED', 'UP_ESCAPED', 'DOWN_INVALIDATED', 'REFERENCE_ONLY']);
const rowLimits: Record<PartKind, number> = { history: 100, analytics: 3, chart: 3000 };
const maxManifestBytes = 65_536;
const maxPartBytes = 196_608;
const maxPartCount = 204;
const encoder = new TextEncoder();
const activeManifest = `SELECT r.identity, r.digest, m.json
  FROM private_projection_ready r
  JOIN private_projection_manifest m ON m.identity = r.identity AND m.digest = r.digest
  WHERE r.singleton = 1 AND r.identity = ? AND length(CAST(m.json AS BLOB)) <= ?`;
const activePart = `SELECT p.json
  FROM private_projection_part p
  JOIN private_projection_ready r ON r.identity = p.identity AND r.singleton = 1
  WHERE p.identity = ? AND r.digest = ? AND p.kind = ? AND p.idx = ?
    AND length(CAST(p.json AS BLOB)) <= ?`;
const activeMarker = 'SELECT identity, digest FROM private_projection_ready WHERE singleton = 1';

function exactKeys(value: unknown, keys: string[]): value is Row {
  return !!value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}

function day(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d\d-\d\d$/.test(value)
    && Number.isFinite(Date.parse(value + 'T00:00:00Z'))
    && new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
}

function hash(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
}

function count(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function amount(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) < 1e12;
}

function canonicalIdentity(value: unknown): string | null {
  if (!exactKeys(value, sourceKeys) || value.status !== 'READY' || typeof value.dataset_id !== 'string'
    || !/^a-[a-f0-9]{20,64}$/.test(value.dataset_id) || !count(value.revision) || value.revision === 0
    || !day(value.as_of) || !hash(value.source_version)) return null;
  return JSON.stringify({
    status: value.status,
    dataset_id: value.dataset_id,
    revision: value.revision,
    as_of: value.as_of,
    source_version: value.source_version,
  });
}

async function sha256(payload: Uint8Array): Promise<string> {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', payload)),
    byte => byte.toString(16).padStart(2, '0')).join('');
}

function requireValid(ok: unknown): asserts ok {
  if (!ok) throw new Error('invalid_member_projection');
}

function validateRows(kind: PartKind, rows: unknown[], through: string): void {
  if (kind === 'analytics') requireValid(rows.length === 3);
  let previous: string | undefined;
  const seen = new Set<string>();
  for (const [index, row] of rows.entries()) {
    if (kind === 'history') {
      requireValid(exactKeys(row, ['date', 'symbol', 'state']) && day(row.date) && row.date <= through
        && typeof row.symbol === 'string' && /^[0-9A-Z]{4}$/.test(row.symbol)
        && typeof row.state === 'string' && states.has(row.state));
      const key = row.date + '|' + row.symbol;
      requireValid((previous === undefined || previous >= row.date) && !seen.has(key));
      previous = row.date;
      seen.add(key);
    } else if (kind === 'analytics') {
      requireValid(exactKeys(row, ['preset', 'from', 'through', 'resolved', 'metrics'])
        && row.preset === presets[index] && day(row.from) && row.from <= through
        && row.through === through && typeof row.resolved === 'boolean');
      if (!row.resolved) {
        requireValid(row.metrics === null);
        continue;
      }
      const metrics = row.metrics;
      requireValid(exactKeys(metrics, ['net_profit', 'max_drawdown_pct', 'win_rate_pct', 'trade_count'])
        && amount(metrics.net_profit) && amount(metrics.max_drawdown_pct)
        && metrics.max_drawdown_pct >= -100 && metrics.max_drawdown_pct <= 0
        && count(metrics.trade_count)
        && (metrics.trade_count === 0
          ? metrics.win_rate_pct === null
          : amount(metrics.win_rate_pct) && metrics.win_rate_pct >= 0 && metrics.win_rate_pct <= 100));
    } else {
      requireValid(exactKeys(row, ['date', 'equity_yen', 'holding_count']) && day(row.date)
        && row.date <= through && (previous === undefined || previous < row.date)
        && (row.equity_yen === null
          ? row.holding_count === null
          : amount(row.equity_yen) && count(row.holding_count)));
      previous = row.date;
    }
  }
  if (kind === 'chart') requireValid(previous === through);
}

type Descriptor = { rows: number; bytes: number; sha256: string };

function manifestPart(manifest: unknown, identity: string, kind: PartKind, index: number) {
  requireValid(exactKeys(manifest, ['schema', 'audience', 'basis', 'source', 'parts'])
    && manifest.schema === 'NEW_A_SHARED_READONLY_VIEW_V1'
    && manifest.audience === 'EXISTING_DESIGNATED_DISCORD_ROLE'
    && manifest.basis === 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS'
    && canonicalIdentity(manifest.source) === identity && Array.isArray(manifest.parts)
    && manifest.parts.length <= maxPartCount);
  const next: Record<PartKind, number> = { history: 0, analytics: 0, chart: 0 };
  let wanted: Descriptor | undefined;
  for (const descriptor of manifest.parts as unknown[]) {
    requireValid(exactKeys(descriptor, ['kind', 'index', 'rows', 'bytes', 'sha256'])
      && typeof descriptor.kind === 'string' && Object.hasOwn(next, descriptor.kind)
      && count(descriptor.index) && count(descriptor.rows) && descriptor.rows > 0
      && count(descriptor.bytes) && descriptor.bytes > 0 && descriptor.bytes <= maxPartBytes
      && hash(descriptor.sha256));
    const descriptorKind = descriptor.kind as PartKind;
    requireValid(descriptor.index === next[descriptorKind]
      && descriptor.rows <= rowLimits[descriptorKind]);
    next[descriptorKind] += 1;
    if (descriptorKind === kind && descriptor.index === index) {
      wanted = { rows: descriptor.rows, bytes: descriptor.bytes, sha256: descriptor.sha256 };
    }
  }
  requireValid(next.analytics === 1 && next.chart === 3 && (wanted || kind === 'history'));
  return { wanted, historyPages: Math.max(next.history, 1) };
}

// The activation digest is the independently approved manifest hash. The canonical
// source callback must do a fresh authoritative read of the owner READY pointer.
export function createNewAMemberProjectionReader(
  db: ProjectionDatabase | undefined,
  readOfficialReady: () => Promise<ReadyPointer | null>,
): MemberAdapters['common'] {
  return async (expected, kind, index) => {
    const identity = canonicalIdentity(expected);
    if (!db || typeof db.withSession !== 'function' || !identity || !count(index)
      || !Object.hasOwn(rowLimits, kind)) return null;
    const source = JSON.parse(identity) as ReadyPointer;
    try {
      if (canonicalIdentity(await readOfficialReady()) !== identity) return null;
      const session = db.withSession('first-primary');
      const manifest = await session.prepare(activeManifest).bind(identity, maxManifestBytes)
        .first<{ identity: unknown; digest: unknown; json: unknown }>();
      requireValid(manifest && manifest.identity === identity && hash(manifest.digest)
        && typeof manifest.json === 'string');
      const manifestBytes = encoder.encode(manifest.json);
      requireValid(manifestBytes.byteLength <= maxManifestBytes && await sha256(manifestBytes) === manifest.digest);
      const { wanted, historyPages } = manifestPart(JSON.parse(manifest.json), identity, kind, index);
      let rows: unknown[] = [];
      if (wanted) {
        const part = await session.prepare(activePart).bind(identity, manifest.digest, kind, index, maxPartBytes)
          .first<{ json: unknown }>();
        requireValid(part && typeof part.json === 'string');
        const partBytes = encoder.encode(part.json);
        requireValid(partBytes.byteLength === wanted.bytes && await sha256(partBytes) === wanted.sha256);
        const decoded: unknown = JSON.parse(part.json);
        requireValid(exactKeys(decoded, ['kind', 'index', 'rows']) && decoded.kind === kind
          && decoded.index === index && Array.isArray(decoded.rows) && decoded.rows.length === wanted.rows);
        rows = decoded.rows;
        validateRows(kind, rows, source.as_of);
      }
      // A new primary session is required here: the first session's bookmark alone
      // can allow a replica that has not observed a concurrent activation.
      const marker = await db.withSession('first-primary').prepare(activeMarker)
        .first<{ identity: unknown; digest: unknown }>();
      if (!marker || marker.identity !== identity || marker.digest !== manifest.digest
        || canonicalIdentity(await readOfficialReady()) !== identity) return null;
      return { source, history_pages: historyPages, rows };
    } catch {
      return null;
    }
  };
}
