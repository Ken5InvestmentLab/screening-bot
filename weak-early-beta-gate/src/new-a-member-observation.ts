import type { OperationalBuild } from './operational-readback';

export const OBSERVED_OWNER_MANIFEST = '/api/cloud/new-a-finite/input/manifest.json';
const documentPath = '/weak_early_beta_latest.html';
const historyPath = '/api/cloud/new-a-view/history.json';
const productionOrigin = 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
const stageOrigin = 'https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev';
const maxWindowMs = 15 * 60_000;
const hex256 = /^[a-f0-9]{64}$/;
const uuid = /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const encoder = new TextEncoder();

type RoleResult = 'allowed' | 'denied' | 'not_checked';
type Subject = string | (() => Promise<string | undefined>);
type Window = {
  window_id: string;
  opens_at_ms: number;
  closes_at_ms: number;
  subject_key: string;
  allowed_subject_hmac: string;
  denied_subject_hmac: string;
};
type Version = { id?: string; tag?: string; timestamp?: string };
type Authority = {
  db?: Pick<D1Database, 'withSession'>;
  ctx?: Pick<ExecutionContext, 'waitUntil'>;
  version?: Version;
  scope: 'production' | 'stage';
  owner?: string;
};
export type MemberResponseObserver = (response: Response, subject: Subject, role: RoleResult) => void;

const windowWhere = 'singleton = 1 AND origin = ? AND source_commit = ? AND build_input_sha256 = ? AND worker_version_id = ?';
const selectWindow = 'SELECT window_id, opens_at_ms, closes_at_ms, subject_key, allowed_subject_hmac, denied_subject_hmac'
  + ` FROM new_a_member_observation_window_v1 WHERE ${windowWhere} AND opens_at_ms <= ? AND closes_at_ms > ?`;
const insertObservation = `INSERT INTO new_a_member_response_observation_v1
 (window_id, origin, source_commit, build_input_sha256, worker_version_id, subject_hmac, route, status, role_result, observed_at_ms)
 SELECT window_id, origin, source_commit, build_input_sha256, worker_version_id, ?, ?, ?, ?, ?
 FROM new_a_member_observation_window_v1 WHERE ${windowWhere} AND window_id = ?
 AND opens_at_ms = ? AND closes_at_ms = ? AND subject_key = ? AND allowed_subject_hmac = ? AND denied_subject_hmac = ?
 AND opens_at_ms <= ? AND closes_at_ms > ?
 ON CONFLICT(window_id, subject_hmac, route) DO NOTHING`;

function responseMatches(path: string, response: Response, role: RoleResult): boolean {
  if (path === OBSERVED_OWNER_MANIFEST) {
    return role === 'not_checked' && response.status === 403 && response.headers.get('x-cloud-private') === 'true';
  }
  if (role === 'denied') return response.status === 403;
  const type = response.headers.get('content-type')?.split(';', 1)[0];
  return role === 'allowed' && response.status === 200
    && type === (path === documentPath ? 'text/html' : 'application/json');
}

export function memberResponseObserver(
  request: Request, build: OperationalBuild, authority: Authority,
): MemberResponseObserver | undefined {
  const { db, ctx, version, scope, owner } = authority;
  const url = new URL(request.url);
  if (!ctx || !db || !owner || !/^\d{17,20}$/.test(owner) || request.method !== 'GET' || url.search || url.hash
    || url.origin !== (scope === 'stage' ? stageOrigin : productionOrigin)
    || (url.pathname !== documentPath && url.pathname !== historyPath && url.pathname !== OBSERVED_OWNER_MANIFEST)) return;
  if ([...request.headers.keys()].some(header => /(?:version|preview|override)/i.test(header)
    || header === 'x-forwarded-host' || header === 'authorization')) return;
  const host = request.headers.get('host');
  if (host && host !== url.host) return;

  const buildSha = build.build_input_sha256;
  const source = build.source_commit;
  const versionId = version?.id;
  const versionAt = Date.parse(version?.timestamp ?? '');
  if (build.target.worker !== 'tentei-kyokuchi-cloud' || !/^[a-f0-9]{40}$/.test(source) || !hex256.test(buildSha)
    || !versionId || !uuid.test(versionId) || version?.tag !== source || !Number.isFinite(versionAt)) return;
  const target = [url.origin, source, buildSha, versionId];

  return (response, subject, role) => {
    if (!responseMatches(url.pathname, response, role)) return;
    const status = response.status;
    const observed = Date.now();
    const task = Promise.resolve().then(async () => {
      const session = db.withSession('first-primary');
      const window = await session.prepare(selectWindow).bind(...target, observed, observed).first<Window>();
      if (!window || !Number.isSafeInteger(window.opens_at_ms) || !Number.isSafeInteger(window.closes_at_ms)
        || versionAt > window.opens_at_ms || window.opens_at_ms > observed || window.closes_at_ms <= observed
        || window.closes_at_ms - window.opens_at_ms > maxWindowMs
        || ![window.window_id, window.subject_key, window.allowed_subject_hmac, window.denied_subject_hmac]
          .every(value => typeof value === 'string' && hex256.test(value))
        || window.allowed_subject_hmac === window.denied_subject_hmac) return;
      const verified = typeof subject === 'string' ? subject : await subject();
      if (!verified || verified === owner || !/^\d{17,20}$/.test(verified)) return;
      const bytes = Uint8Array.from({ length: 32 }, (_, i) => parseInt(window.subject_key.slice(i * 2, i * 2 + 2), 16));
      const key = await crypto.subtle.importKey('raw', bytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      const message = encoder.encode(JSON.stringify(['new-a-member-observation-subject-v1', window.window_id, ...target, verified]));
      const tag = [...new Uint8Array(await crypto.subtle.sign('HMAC', key, message))]
        .map(byte => byte.toString(16).padStart(2, '0')).join('');
      if (tag !== window.allowed_subject_hmac && tag !== window.denied_subject_hmac) return;
      await session.prepare(insertObservation).bind(tag, url.pathname, status, role, observed, ...target, window.window_id,
        window.opens_at_ms, window.closes_at_ms, window.subject_key, window.allowed_subject_hmac, window.denied_subject_hmac,
        observed, Date.now()).run();
    }).catch(() => {});
    try { ctx.waitUntil(task); } catch { /* Observation never changes the response. */ }
  };
}
