import type { RoleIdentity, RoleServices } from './new-a-role-facade';
import { memberFrame } from './new-a-member-frame.generated';

export type ReadyPointer = {
  status: 'READY';
  dataset_id: string;
  revision: number;
  as_of: string;
  source_version: string;
};
type Part = { source: ReadyPointer; history_pages: number; rows: unknown[] };
export type MemberAdapters = {
  identity: (request: Request) => Promise<RoleIdentity>;
  current: () => Promise<ReadyPointer | null>;
  common: (source: ReadyPointer, kind: 'history' | 'analytics' | 'chart', index: number) => Promise<Part | null>;
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

async function signGeneration(secret: string, subject: string, source: ReadyPointer): Promise<string> {
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  // The member can compare responses without learning private source identifiers.
  const content = JSON.stringify(['new-a-member-generation-v1', subject, source.dataset_id, source.revision, source.as_of, source.source_version]);
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(content));
  return Array.from(new Uint8Array(signature), value => value.toString(16).padStart(2, '0')).join('');
}

export function memberServices(d: MemberAdapters, generationSecret: string | undefined): RoleServices {
  return {
    identity: d.identity,
    preferences: d.preferences,
    asset: d.asset,
    document: async request => new Response(memberFrame(new URL(request.url).pathname), {
      headers: {
        'content-type': 'text/html; charset=utf-8',
        'content-security-policy': "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'",
      },
    }),
    aggregate: async (request, subject) => {
      const url = new URL(request.url);
      const history = url.pathname.endsWith('/history.json');
      const chart = url.pathname.endsWith('/chart.json');
      const personal = url.pathname.endsWith('/personal.json');
      const raw = url.searchParams.get('page') ?? '1';
      const preset = url.searchParams.get('preset');
      const index = chart ? ['defensive', 'medium', 'return_priority'].indexOf(preset ?? '') : history ? Number(raw) - 1 : 0;
      if (index < 0 || (!chart && !/^[1-9]\d{0,5}$/.test(raw)) || (!history && !chart && url.search)) {
        return json({ error: 'invalid_query' }, 400);
      }
      const current = await d.current();
      if (!generationSecret || !current || current.status !== 'READY') {
        return json({ error: 'source_unavailable' }, 503);
      }
      const source = { ...current };
      const generation = await signGeneration(generationSecret, subject, source);
      const expected = request.headers.get(generationHeader);
      if (expected !== null && expected !== generation) return json({ error: 'source_changed' }, 409);
      const capture = { as_of: source.as_of, generation };
      if (personal) {
        const result = await d.personal(subject, source);
        if (!same(source, await d.current())) return json({ error: 'source_changed' }, 409);
        return json({ ...capture, metrics: result, status: result ? 'ready' : 'pending_or_unresolved' });
      }
      const part = await d.common(source, history ? 'history' : chart ? 'chart' : 'analytics', index);
      if (!same(source, await d.current())) return json({ error: 'source_changed' }, 409);
      if (!part || !same(source, part.source)) return json({ error: 'source_unavailable' }, 503);
      if (history && Number(raw) > part.history_pages) return json({ error: 'page_not_found' }, 404);
      if (history) return json({ ...capture, page: Number(raw), pages: part.history_pages, rows: part.rows });
      if (chart) return json({ ...capture, preset, rows: part.rows });
      return json({ ...capture, presets: part.rows });
    },
  };
}
