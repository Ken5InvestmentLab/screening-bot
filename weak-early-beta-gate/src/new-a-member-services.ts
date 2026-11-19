import type { MemberTier, RoleIdentity, RoleServices } from './new-a-role-facade';
import { memberFrame } from './new-a-member-frame.generated';

export type ReadyPointer = {
  status: 'READY';
  dataset_id: string;
  revision: number;
  as_of: string;
  source_version: string;
};
type Part = { source: ReadyPointer; history_pages: number; rows: unknown[] };
type MemberPart = 'history' | 'completed-history' | 'analytics' | 'chart' | 'dashboard' | 'fundamental';
export type FundamentalSelector = { date: string; symbol: string };
export type MemberAdapters = {
  identity: (request: Request) => Promise<RoleIdentity>;
  current: () => Promise<ReadyPointer | null>;
  common: (source: ReadyPointer, kind: MemberPart, index: number, fundamental?: FundamentalSelector) => Promise<Part | null>;
  personal: (subject: string, source: ReadyPointer) => Promise<unknown | null>;
  preferences: RoleServices['preferences'];
  asset: RoleServices['asset'];
};

const json = (value: unknown, status = 200) => Response.json(value, { status });
const same = (a: ReadyPointer, b: ReadyPointer | null) => !!b
  && a.status === 'READY' && b.status === 'READY'
  && a.dataset_id === b.dataset_id
  && a.revision === b.revision
  && a.as_of === b.as_of
  && a.source_version === b.source_version;
const encoder = new TextEncoder();
const generationHeader = 'x-cloud-generation';
const selectorPattern = /^([1-9]\d{0,2})\.(\d{4}-\d\d-\d\d)\.([0-9A-Z]{4})$/;

function fundamentalSelector(url: URL) {
  const parts = selectorPattern.exec(url.searchParams.get('item') ?? '');
  if (!parts || Number(parts[1]) > 200) return null;
  const instant = new Date(parts[2] + 'T00:00:00Z');
  if (!Number.isFinite(instant.valueOf()) || instant.toISOString().slice(0, 10) !== parts[2]) return null;
  return { page: parts[1], selection: { date: parts[2], symbol: parts[3] } };
}

async function signGeneration(secret: string, subject: string, tier: MemberTier, source: ReadyPointer): Promise<string> {
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  // The member can compare responses without learning private source identifiers.
  const content = JSON.stringify(['new-a-member-generation-v2', subject, tier, source.dataset_id, source.revision, source.as_of, source.source_version]);
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(content));
  return Array.from(new Uint8Array(signature), value => value.toString(16).padStart(2, '0')).join('');
}

export function memberServices(d: MemberAdapters, generationSecret: string | undefined): RoleServices {
  return {
    identity: d.identity,
    preferences: d.preferences,
    asset: d.asset,
    document: async (request, _subject, tier) => new Response(memberFrame(new URL(request.url).pathname, tier), {
      headers: {
        'content-type': 'text/html; charset=utf-8',
        'content-security-policy': "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'",
      },
    }),
    aggregate: async (request, subject, tier = 'premium') => {
      const url = new URL(request.url);
      const history = url.pathname.endsWith('/history.json');
      const chart = url.pathname.endsWith('/chart.json');
      const personal = url.pathname.endsWith('/personal.json');
      const dashboard = url.pathname.endsWith('/dashboard.json');
      const fundamental = url.pathname.endsWith('/fundamental.json');
      if (tier === 'free' && !history) return json({ error: 'role_required' }, 403);
      const item = fundamental ? fundamentalSelector(url) : null;
      const raw = item?.page ?? url.searchParams.get('page') ?? '1';
      const preset = url.searchParams.get('preset');
      const index = chart ? ['defensive', 'medium', 'return_priority'].indexOf(preset ?? '') : history || fundamental ? Number(raw) - 1 : 0;
      if (index < 0 || (!chart && !/^[1-9]\d{0,5}$/.test(raw))
        || (!history && !chart && !fundamental && url.search) || (fundamental && !item)) {
        return json({ error: 'invalid_query' }, 400);
      }
      const current = await d.current();
      if (!generationSecret || !current || current.status !== 'READY') {
        return json({ error: 'source_unavailable' }, 503);
      }
      const source = { ...current };
      const generation = await signGeneration(generationSecret, subject, tier, source);
      const expected = request.headers.get(generationHeader);
      if (fundamental && expected === null) return json({ error: 'generation_required' }, 403);
      if (expected !== null && expected !== generation) return json({ error: 'source_changed' }, 409);
      const capture = { as_of: source.as_of, generation };
      if (personal) {
        const result = await d.personal(subject, source);
        if (!same(source, await d.current())) return json({ error: 'source_changed' }, 409);
        return json({ ...capture, metrics: result, status: result ? 'ready' : 'pending_or_unresolved' });
      }
      const historyKind = tier === 'free' ? 'completed-history' : 'history';
      const kind = history ? historyKind : fundamental ? 'fundamental' : dashboard ? 'dashboard' : chart ? 'chart' : 'analytics';
      const part = item
        ? await d.common(source, kind, index, item.selection)
        : await d.common(source, kind, index);
      if (!same(source, await d.current())) return json({ error: 'source_changed' }, 409);
      if (!part || !same(source, part.source)) return json({ error: 'source_unavailable' }, 503);
      if (history && Number(raw) > part.history_pages) return json({ error: 'page_not_found' }, 404);
      if (history) {
        const rows = (part.rows as Record<string, unknown>[]).map(({ date, symbol, state, fundamental_sha256 }) => ({
          date, symbol, state,
          ...(tier === 'premium' && typeof fundamental_sha256 === 'string' ? { has_fundamental: true } : {}),
        }));
        return json({ ...capture, page: Number(raw), pages: part.history_pages, rows });
      }
      if (fundamental) {
        const report = part.rows[0] as Record<string, unknown> | undefined;
        if (!report || !item || report.date !== item.selection.date || report.symbol !== item.selection.symbol) {
          return json({ error: 'fundamental_unavailable' }, 404);
        }
        const { date, symbol, company_name, analysis_cutoff, fields } = report;
        return json({ ...capture, date, symbol, company_name, analysis_cutoff, fields });
      }
      if (dashboard) {
        const today = [], watching = [];
        for (const item of part.rows) {
          if (!item || typeof item !== 'object') return json({ error: 'source_unavailable' }, 503);
          const { date, symbol, state, lane } = item as Record<string, unknown>;
          if (typeof date !== 'string' || typeof symbol !== 'string' || typeof state !== 'string') {
            return json({ error: 'source_unavailable' }, 503);
          }
          if (lane === 'today') today.push({ date, symbol, state });
          else if (lane === 'watching') watching.push({ date, symbol, state });
          else return json({ error: 'source_unavailable' }, 503);
        }
        return json({ ...capture, today, watching });
      }
      if (chart) return json({ ...capture, preset, rows: part.rows });
      return json({ ...capture, presets: part.rows });
    },
  };
}
