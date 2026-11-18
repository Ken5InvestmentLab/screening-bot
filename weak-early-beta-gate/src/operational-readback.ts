// Public release continuity only. Never authenticates an owner or reads private parts.
// Canonical values are ASCII-only JSON arrays, UTF-8, no whitespace (Python:
// json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf8')).
export type OperationalBuild = {
  source_commit: string;
  build_input_sha256: string;
  target: { worker: string; database: string };
};
type Metadata = { id?: string; tag?: string; timestamp?: string };
type Statement = { bind(...values: (string | number | null)[]): Statement; first<T>(): Promise<T | null> };
type Environment = {
  CLOUD_VERSION_METADATA?: Metadata;
  CLOUD_DB?: { prepare(sql: string): Statement };
  CLOUD_OWNER_ONLY_ENABLED?: string; CLOUD_OWNER_DISCORD_ID?: string;
  DISCORD_GUILD_ID?: string; DISCORD_ALLOWED_ROLE_IDS?: string; DISCORD_CLIENT_ID?: string;
  DISCORD_API_BASE?: string; SESSION_TTL_SECONDS?: string;
  SESSION_SECRET?: string; DISCORD_CLIENT_SECRET?: string; CLOUD_ROLE_AUTHORITY?: unknown;
};
type Active = { dataset_id: string; revision: number; status: string; source_version: string; manifest_sha256: string; manifest_json: string; as_of: string };

const ORIGIN = 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
const HEX = /^[a-f0-9]{64}$/;
const COMMIT = /^[a-f0-9]{40}$/;
const VERSION = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const SNOWFLAKE = /^\d{17,20}$/;
const HEADERS = { 'cache-control': 'no-store, max-age=0', 'content-type': 'application/json; charset=utf-8',
  'x-content-type-options': 'nosniff', 'cross-origin-resource-policy': 'same-origin', 'pragma': 'no-cache' };
// One fixed SELECT. Neither nonce nor caller input can affect SQL, bindings or paths.
const ACTIVE_SELECT = "SELECT d.dataset_id,p.revision,d.status,d.source_version,d.manifest_sha256,d.manifest_json,json_extract(d.manifest_json,'$.as_of') AS as_of FROM new_a_active_pointer p JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id WHERE p.pointer_key='owner'";
const fail = () => new Response('{"error":"operational_readback_unavailable","owner_http_observed":false}', { status: 503, headers: HEADERS });
function required(env: Environment, key: keyof Environment): string {
  const value = env[key];
  if (typeof value !== 'string' || value.length > 1024 || !value.trim()) throw Error('policy');
  return value.trim();
}
function id(env: Environment, key: keyof Environment): string {
  const value = required(env, key); if (!SNOWFLAKE.test(value)) throw Error('policy'); return value;
}
function present(env: Environment, key: keyof Environment): boolean {
  // Presence only: secret bytes are never included in canonical values or hashes.
  return typeof env[key] === 'string' && (env[key] as string).length > 0;
}
async function textSha(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), n => n.toString(16).padStart(2, '0')).join('');
}
async function sha(value: unknown): Promise<string> { return textSha(JSON.stringify(value)); }
function policy(env: Environment): unknown[] {
  if (required(env, 'CLOUD_OWNER_ONLY_ENABLED').toLowerCase() !== 'true') throw Error('policy');
  const roles = required(env, 'DISCORD_ALLOWED_ROLE_IDS').split(',').map(s => s.trim());
  if (!roles.length || roles.length > 32 || roles.some(s => !SNOWFLAKE.test(s))) throw Error('policy');
  const api = required(env, 'DISCORD_API_BASE').replace(/\/+$/, '');
  if (api !== 'https://discord.com/api') throw Error('policy');
  const rawTtl = required(env, 'SESSION_TTL_SECONDS');
  if (!/^[1-9]\d{0,8}$/.test(rawTtl)) throw Error('policy');
  const ttl = Number(rawTtl);
  if (!Number.isSafeInteger(ttl) || ttl > 31536000) throw Error('policy');
  const authority = env.CLOUD_ROLE_AUTHORITY as { get?: unknown; idFromName?: unknown } | undefined;
  const credentials = [present(env, 'SESSION_SECRET'), present(env, 'DISCORD_CLIENT_SECRET'),
    !!authority && typeof authority.get === 'function' && typeof authority.idFromName === 'function'];
  if (credentials.some(v => !v)) throw Error('policy');
  // Fresh role selection is enforced by the unchanged owner route's
  // reportIdentity(..., true) + CloudRoleAuthority, not a mutable env flag.
  return ['NEW_A_OPERATIONAL_POLICY_V1', true, id(env, 'CLOUD_OWNER_DISCORD_ID'),
    id(env, 'DISCORD_GUILD_ID'), [...new Set(roles)].sort(), id(env, 'DISCORD_CLIENT_ID'),
    api, ttl, 'NEW_A_REPORT_IDENTITY_FRESH_ROLE_V1', credentials];
}
function validDay(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value + 'T00:00:00Z')) && new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
}
function activeIdentity(row: Active | null): unknown[] {
  if (!row || !/^a-[a-f0-9]{20,64}$/.test(row.dataset_id) || !Number.isSafeInteger(row.revision) ||
      row.revision < 1 || row.status !== 'READY' || !HEX.test(row.source_version) ||
      !HEX.test(row.manifest_sha256) || !validDay(row.as_of)) throw Error('database');
  return ['NEW_A_ACTIVE_METADATA_V1', row.dataset_id, row.revision, row.status,
    row.source_version, row.manifest_sha256, row.as_of];
}

export async function operationalReadback(request: Request, env: Environment, build: OperationalBuild): Promise<Response> {
  try {
    const url = new URL(request.url);
    if (request.method !== 'GET' || url.origin !== ORIGIN || url.pathname !== '/healthz' || url.hash ||
        !/^\?new_a_probe=[a-f0-9]{64}$/.test(url.search) || request.url.length > 256) return fail();
    // No authenticated probe, version override, preview routing or foreign origin.
    for (const name of request.headers.keys()) if (name === 'cookie' || name === 'authorization' ||
      /(?:version|preview|override)/i.test(name) || name === 'x-forwarded-host') return fail();
    if (request.headers.get('origin') && request.headers.get('origin') !== ORIGIN ||
        request.headers.get('host') && request.headers.get('host') !== url.host) return fail();
    if (!COMMIT.test(build.source_commit) || !HEX.test(build.build_input_sha256) ||
        build.target.worker !== 'tentei-kyokuchi-cloud' || build.target.database !== 'tentei-cloud-settings') return fail();
    const version = env.CLOUD_VERSION_METADATA ? { ...env.CLOUD_VERSION_METADATA } : undefined;
    if (!version || !VERSION.test(version.id ?? '') || version.tag !== build.source_commit ||
        typeof version.timestamp !== 'string' || version.timestamp.length > 40 ||
        !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/.test(version.timestamp) ||
        !Number.isFinite(Date.parse(version.timestamp)) || Date.parse(version.timestamp) > Date.now() + 60000) return fail();
    const nonce = url.search.slice('?new_a_probe='.length);
    const policyValue = policy(env);
    if (!env.CLOUD_DB) return fail();
    const row = await env.CLOUD_DB.prepare(ACTIVE_SELECT).bind().first<Active>();
    const active = activeIdentity(row);
    if (!row || typeof row.manifest_json !== 'string' || row.manifest_json.length > 1024 * 1024 ||
        await textSha(row.manifest_json) !== row.manifest_sha256) return fail();
    const manifest = JSON.parse(row.manifest_json);
    if (!manifest || Array.isArray(manifest) || manifest.schema !== 'A_BROWSER_PRIVATE_INPUT_V1' ||
        manifest.audience !== 'EXISTING_CLOUD_OWNER_ONLY' || manifest.strategy !== 'A_BASE' ||
        manifest.as_of !== row.as_of || manifest.source_version !== row.source_version) return fail();
    const policySha = await sha(policyValue), activeSha = await sha(active);
    // Snapshot version/policy again across the await; mixed local metadata closes.
    const current = env.CLOUD_VERSION_METADATA;
    if (!current || current.id !== version.id || current.tag !== version.tag || current.timestamp !== version.timestamp ||
        JSON.stringify(policy(env)) !== JSON.stringify(policyValue)) return fail();
    const identity = ['NEW_A_OPERATIONAL_CHALLENGE_V1', nonce, build.target.worker, build.target.database,
      version.id, version.tag, version.timestamp, build.source_commit, build.build_input_sha256];
    return new Response(JSON.stringify({ schema: 'NEW_A_OPERATIONAL_READBACK_V1', nonce,
      source_commit: build.source_commit, build_input_sha256: build.build_input_sha256,
      target: build.target, version: { id: version.id, tag: version.tag, timestamp: version.timestamp },
      policy_sha256: policySha, d1_active_sha256: activeSha,
      policy_challenge_sha256: await sha([...identity, 'policy', policySha]),
      d1_challenge_sha256: await sha([...identity, 'd1-active', activeSha]),
      owner_http_observed: false, authentication_probe: false, d1_writes: 0 }), { status: 200, headers: HEADERS });
  } catch { return fail(); }
}
