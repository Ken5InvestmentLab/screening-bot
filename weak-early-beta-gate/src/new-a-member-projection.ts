import type { FundamentalSelector, MemberAdapters, ReadyPointer } from './new-a-member-services';

type PartKind = 'history' | 'analytics' | 'chart';
type ViewKind = PartKind | 'completed-history' | 'dashboard' | 'fundamental';
type Row = Record<string, unknown>;
type Statement = { bind(...values: (string | number)[]): Statement; first<T>(): Promise<T | null> };
type D1Session = { prepare(sql: string): Statement };
type ProjectionDatabase = { withSession(constraint: 'first-primary'): D1Session };

const sourceKeys = ['status', 'dataset_id', 'revision', 'as_of', 'source_version'];
const presets = ['defensive', 'medium', 'return_priority'];
const completedStates = new Set(['EXPIRED', 'UP_ESCAPED', 'DOWN_INVALIDATED', 'HOLD_ENDED']);
const states = new Set(['WATCHING', 'TRIGGERED', 'EXPIRED', 'UP_ESCAPED', 'DOWN_INVALIDATED', 'REFERENCE_ONLY',
  'DATA_GAP', 'BASIS_CHANGED', 'IDENTITY_CHANGED']);
const todayStates = new Set(['WATCH_STARTED', 'ENTRY_CANDIDATE', 'WATCH_TERMINAL', 'HOLD_STARTED', 'HOLD_ENDED']);
const rowLimits: Record<PartKind, number> = { history: 100, analytics: 3, chart: 3000 };
const maxManifestBytes = 65_536;
const maxPartBytes = 196_608;
const maxHistoryPages = 200;
const maxDashboardRows = 1000;
const fundamentalLimit = 16_384;
const fundamentalFields = ['材料インパクト', '事業概要', '足元材料', 'ファンダ要点', '注意点', '開示リンク', 'Sources'];
const analysisTimestamp = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)$/;
const viewKinds = new Set<ViewKind>(['history', 'completed-history', 'dashboard', 'analytics', 'chart', 'fundamental']);
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
const activeFundamental = `SELECT f.json
  FROM private_projection_fundamental f
  JOIN private_projection_ready r ON r.identity = f.identity AND r.singleton = 1
  WHERE f.identity = ? AND r.digest = ? AND f.sha256 = ?
    AND length(CAST(f.json AS BLOB)) <= ?`;
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

function reportText(value: unknown, limit: number): value is string {
  return typeof value === 'string' && !!value.trim() && encoder.encode(value).length <= limit;
}

function validateFundamental(report: unknown, lookup: FundamentalSelector): void {
  requireValid(exactKeys(report, ['date', 'symbol', 'company_name', 'analysis_cutoff', 'fields'])
    && report.date === lookup.date && report.symbol === lookup.symbol
    && (report.company_name === null || reportText(report.company_name, 256))
    && typeof report.analysis_cutoff === 'string' && analysisTimestamp.test(report.analysis_cutoff)
    && Number.isFinite(Date.parse(report.analysis_cutoff))
    && Array.isArray(report.fields) && report.fields.length === fundamentalFields.length
    && report.fields.every((field, index) => exactKeys(field, ['label', 'text'])
      && field.label === fundamentalFields[index] && reportText(field.text, 8192)));
}

function validateRows(kind: ViewKind, rows: unknown[], through: string, withReports: boolean): void {
  if (kind === 'analytics') requireValid(rows.length === 3);
  let previous: string | undefined;
  const seen = new Set<string>();
  for (const [index, row] of rows.entries()) {
    if (kind === 'dashboard') {
      requireValid(exactKeys(row, ['date', 'symbol', 'state', 'lane']) && day(row.date) && row.date <= through
        && typeof row.symbol === 'string' && /^[0-9A-Z]{4}$/.test(row.symbol) && typeof row.state === 'string'
        && (row.lane === 'today' && row.date === through && todayStates.has(row.state)
          || row.lane === 'watching' && row.state === 'WATCHING'));
      const key = row.date + '|' + row.symbol + '|' + row.state + '|' + row.lane;
      requireValid(!seen.has(key));
      seen.add(key);
    } else if (kind === 'history' || kind === 'completed-history') {
      const completed = kind === 'completed-history';
      const keys = completed ? ['date', 'symbol', 'state', 'completed_on'] : ['date', 'symbol', 'state'];
      const validShape = exactKeys(row, keys)
        || !completed && withReports && exactKeys(row, [...keys, 'fundamental_sha256']) && hash(row.fundamental_sha256);
      requireValid(validShape && day(row.date) && row.date <= through
        && typeof row.symbol === 'string' && /^[0-9A-Z]{4}$/.test(row.symbol)
        && typeof row.state === 'string' && (completed
          ? completedStates.has(row.state) && day(row.completed_on) && row.completed_on >= row.date && row.completed_on <= through
          : states.has(row.state)));
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

function manifestPart(manifest: unknown, identity: string, view: ViewKind, index: number) {
  const keys = ['schema', 'audience', 'basis', 'source', 'parts'];
  const legacy = exactKeys(manifest, keys) && manifest.schema === 'NEW_A_SHARED_READONLY_VIEW_V1'
    && manifest.audience === 'EXISTING_DESIGNATED_DISCORD_ROLE';
  const withReports = exactKeys(manifest, [...keys, 'history_layout', 'fundamental_reports'])
    && manifest.schema === 'NEW_A_SHARED_READONLY_VIEW_V3' && count(manifest.fundamental_reports)
    && manifest.fundamental_reports > 0 && manifest.fundamental_reports <= maxHistoryPages * rowLimits.history;
  const tiered = (withReports || exactKeys(manifest, [...keys, 'history_layout']) && manifest.schema === 'NEW_A_SHARED_READONLY_VIEW_V2')
    && manifest.audience === 'AUTHENTICATED_TIERED_DISCORD_VIEW';
  requireValid((legacy || tiered) && manifest.basis === 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS'
    && canonicalIdentity(manifest.source) === identity && Array.isArray(manifest.parts)
    && manifest.parts.length <= maxHistoryPages * (tiered ? 2 : 1) + (tiered ? 5 : 4));
  requireValid(tiered || (view !== 'completed-history' && view !== 'dashboard'));

  let premiumPages = 0;
  let completedPages = 0;
  let dashboardIndex = -1;
  if (tiered) {
    const layout = manifest.history_layout;
    requireValid(exactKeys(layout, ['premium_pages', 'completed_pages']) && count(layout.premium_pages)
      && count(layout.completed_pages) && layout.premium_pages <= maxHistoryPages
      && layout.completed_pages <= layout.premium_pages);
    premiumPages = layout.premium_pages;
    completedPages = layout.completed_pages;
    dashboardIndex = premiumPages + completedPages;
  }
  const kind = view === 'completed-history' || view === 'dashboard' || view === 'fundamental' ? 'history' : view;
  const storedIndex = view === 'completed-history' ? index + premiumPages : view === 'dashboard' ? dashboardIndex : index;
  const outsideView = view === 'fundamental' && (!withReports || index >= premiumPages)
    || tiered && (view === 'history' && index >= premiumPages
      || view === 'completed-history' && index >= completedPages || view === 'dashboard' && index !== 0);

  const next: Record<PartKind, number> = { history: 0, analytics: 0, chart: 0 };
  let wanted: Descriptor | undefined;
  for (const descriptor of manifest.parts as unknown[]) {
    requireValid(exactKeys(descriptor, ['kind', 'index', 'rows', 'bytes', 'sha256'])
      && typeof descriptor.kind === 'string' && Object.hasOwn(next, descriptor.kind)
      && count(descriptor.index) && count(descriptor.rows)
      && count(descriptor.bytes) && descriptor.bytes > 0 && descriptor.bytes <= maxPartBytes
      && hash(descriptor.sha256));
    const descriptorKind = descriptor.kind as PartKind;
    const dashboard = tiered && descriptorKind === 'history' && descriptor.index === dashboardIndex;
    requireValid(descriptor.index === next[descriptorKind]
      && (dashboard ? descriptor.rows <= maxDashboardRows : descriptor.rows > 0 && descriptor.rows <= rowLimits[descriptorKind]));
    next[descriptorKind] += 1;
    if (!outsideView && descriptorKind === kind && descriptor.index === storedIndex) {
      wanted = { rows: descriptor.rows, bytes: descriptor.bytes, sha256: descriptor.sha256 };
    }
  }
  requireValid(next.analytics === 1 && next.chart === 3 && (!tiered || next.history === dashboardIndex + 1)
    && (wanted || view === 'history' || view === 'completed-history' || view === 'fundamental'));
  const pages = view === 'completed-history' ? completedPages : tiered ? premiumPages : next.history;
  return { wanted, kind, storedIndex, historyPages: Math.max(pages, 1), withReports };
}

// The activation digest is the independently approved manifest hash. The canonical
// source callback must do a fresh authoritative read of the owner READY pointer.
export function createNewAMemberProjectionReader(
  db: ProjectionDatabase | undefined,
  readOfficialReady: () => Promise<ReadyPointer | null>,
): MemberAdapters['common'] {
  return async (expected, kind, index, lookup) => {
    const identity = canonicalIdentity(expected);
    if (!db || typeof db.withSession !== 'function' || !identity || !count(index)
      || !viewKinds.has(kind) || kind === 'fundamental' && (!lookup || !day(lookup.date)
        || !/^[0-9A-Z]{4}$/.test(lookup.symbol))) return null;
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
      const { wanted, kind: storedKind, storedIndex, historyPages, withReports } =
        manifestPart(JSON.parse(manifest.json), identity, kind, index);
      let rows: unknown[] = [];
      if (wanted) {
        const part = await session.prepare(activePart).bind(identity, manifest.digest, storedKind, storedIndex, maxPartBytes)
          .first<{ json: unknown }>();
        requireValid(part && typeof part.json === 'string');
        const partBytes = encoder.encode(part.json);
        requireValid(partBytes.byteLength === wanted.bytes && await sha256(partBytes) === wanted.sha256);
        const decoded: unknown = JSON.parse(part.json);
        requireValid(exactKeys(decoded, ['kind', 'index', 'rows']) && decoded.kind === storedKind
          && decoded.index === storedIndex && Array.isArray(decoded.rows) && decoded.rows.length === wanted.rows);
        rows = decoded.rows;
        validateRows(kind === 'fundamental' ? 'history' : kind, rows, source.as_of, withReports);
        if (kind === 'completed-history') {
          rows = (rows as Row[]).map(({ date, symbol, state }) => ({ date, symbol, state }));
        }
      }
      if (kind === 'fundamental' && lookup) {
        const digest = (rows as Row[]).find(row => row.date === lookup.date && row.symbol === lookup.symbol)?.fundamental_sha256;
        rows = [];
        if (hash(digest)) {
          const report = await session.prepare(activeFundamental).bind(identity, manifest.digest, digest, fundamentalLimit)
            .first<{ json: unknown }>();
          requireValid(report && typeof report.json === 'string');
          const bytes = encoder.encode(report.json);
          requireValid(bytes.length <= fundamentalLimit && await sha256(bytes) === digest);
          const decoded: unknown = JSON.parse(report.json);
          validateFundamental(decoded, lookup);
          rows.push(decoded);
        }
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
