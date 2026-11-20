import type { MemberResponseObserver } from './new-a-member-observation';

export type RoleEnv = {
  CLOUD_OWNER_ONLY_ENABLED?: string;
  CLOUD_MEMBER_VIEW_ENABLED?: string;
  CLOUD_MEMBER_AUDIENCE?: string;
  CLOUD_MEMBER_STAGE_ORIGIN?: string;
  PUBLIC_BASE_URL?: string;
  DISCORD_GUILD_ID?: string;
  DISCORD_ALLOWED_ROLE_IDS?: string;
  SESSION_SECRET?: string;
};

export type RoleIdentity = {
  subject?: string;
  reason?: string;
  discord_authorized?: boolean;
};

export type MemberTier = 'premium' | 'free';
export type MemberAudience = 'tiered' | 'role_only';

export type RoleServices = {
  identity: (request: Request) => Promise<RoleIdentity>;
  document: (request: Request, subject: string, tier: MemberTier) => Promise<Response>;
  aggregate: (request: Request, subject: string, tier: MemberTier) => Promise<Response>;
  preferences: (request: Request, subject: string) => Promise<Response>;
  asset: (request: Request) => Promise<Response>;
};

const productionOrigin = 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';
const isolatedStageOrigin = 'https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev';
const documents = new Set([
  '/', '/report', '/index.html',
  '/weak_early_beta_latest.html', '/weak_early_beta_analytics.html', '/weak_early_beta_settings.html',
]);
const historyPath = '/api/cloud/new-a-view/history.json';
const fundamentalPath = '/api/cloud/new-a-view/fundamental.json';
const aggregates = new Map([
  [historyPath, 'page'],
  [fundamentalPath, 'item'],
  ['/api/cloud/new-a-view/dashboard.json', null],
  ['/api/cloud/new-a-view/analytics.json', null],
  ['/api/cloud/new-a-view/chart.json', 'preset'],
  ['/api/cloud/new-a-view/personal.json', null],
]);
const preferencesPath = '/api/cloud/new-a-view/preferences';
const sessionPath = '/api/cloud/new-a-view/session';
const memberSessionHeader = 'x-cloud-member-session';
const memberAccessHeader = 'x-cloud-member-access';
const assets = new Set([
  '/new-a-assets/member-loader.js',
  '/new-a-assets/member-presentation.js',
  '/new-a-assets/member-settings.js',
  '/new-a-assets/report-assets/cloud-logo-light.png',
  '/new-a-assets/report-assets/cloud-logo-dark.png',
]);
for (const brand of ['discord', 'coconala', 'x']) {
  for (const shade of ['dark', 'light']) assets.add('/new-a-assets/report-assets/' + brand + '-' + shade + '.png');
}
const privateHeaders = {
  'cache-control': 'private, no-store',
  vary: 'Cookie',
  'x-content-type-options': 'nosniff',
  'cross-origin-resource-policy': 'same-origin',
};

function reject(request: Request, status: number, error: string): Response {
  return new Response(request.method === 'HEAD' ? null : JSON.stringify({ error }), {
    status,
    headers: { ...privateHeaders, 'content-type': 'application/json; charset=utf-8' },
  });
}

function roleRequiredPage(request: Request): Response {
  const document = `<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Premiumアクセス権 | 天底極致 Cloud 2.0</title>
<style>
:root{color-scheme:dark;background:#121b2d;color:#edf1fa;font:16px system-ui,sans-serif}
main{max-width:480px;margin:clamp(24px,10vh,96px) auto;padding:24px}
a{display:inline-block;padding:12px 16px;border:1px solid #7a93d4;border-radius:12px;background:#284779;color:#fff;text-decoration:none;font-weight:700}
</style></head><body><main><h1>Premium会員限定</h1><p>当日の動きや監視銘柄は、Premiumアクセス権の取得後に閲覧できます。</p>
<a href="/purchase">Premiumアクセス権を購入する</a></main></body></html>`;
  return new Response(request.method === 'HEAD' ? null : document, {
    status: 403,
    headers: { ...privateHeaders, 'content-type': 'text/html; charset=utf-8',
      'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'" },
  });
}

export function memberOrigin(url: URL, env: RoleEnv): 'production' | 'stage' | null {
  const stage = env.CLOUD_MEMBER_STAGE_ORIGIN;
  if (stage === undefined) return url.origin === productionOrigin ? 'production' : null;
  return stage === isolatedStageOrigin && url.origin === isolatedStageOrigin && env.PUBLIC_BASE_URL === isolatedStageOrigin
    ? 'stage' : null;
}

export function memberAudience(env: RoleEnv, origin: 'production' | 'stage'): MemberAudience | null {
  const audience = env.CLOUD_MEMBER_AUDIENCE;
  if (audience === 'role_only') return audience;
  if (origin === 'stage' && (audience === 'tiered' || audience === undefined)) return 'tiered';
  return null;
}

export function hasMemberRoleConfiguration(env: RoleEnv): boolean {
  return env.CLOUD_OWNER_ONLY_ENABLED === 'true' && env.DISCORD_GUILD_ID === '1479418833352785944'
    && env.DISCORD_ALLOWED_ROLE_IDS === '1487089073385373828';
}

async function memberSessionTag(secret: string, subject: string, tier: MemberTier): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const message = encoder.encode(JSON.stringify(['new-a-member-session-v2', subject, tier]));
  const tag = await crypto.subtle.sign('HMAC', key, message);
  return Array.from(new Uint8Array(tag), value => value.toString(16).padStart(2, '0')).join('');
}

export async function roleFacade(
  request: Request, env: RoleEnv, ownerDenial: Response | null, services: RoleServices | undefined,
  productionAllowed?: (subject: string, tier: MemberTier) => Promise<boolean>,
  observe?: MemberResponseObserver,
): Promise<Response | null> {
  if (!ownerDenial || env.CLOUD_MEMBER_VIEW_ENABLED !== 'true') return ownerDenial;
  const url = new URL(request.url);
  const { pathname } = url;
  const document = documents.has(pathname);
  const aggregate = aggregates.has(pathname);
  const preferences = pathname === preferencesPath;
  const session = pathname === sessionPath;
  const asset = assets.has(pathname);
  if (!document && !aggregate && !preferences && !session && !asset) return ownerDenial;
  if (ownerDenial.status !== 403) return ownerDenial;

  if (!hasMemberRoleConfiguration(env) || !services) {
    return reject(request, 503, 'member_service_unavailable');
  }
  const methods = preferences ? ['GET', 'HEAD', 'PUT'] : ['GET', 'HEAD'];
  if (!methods.includes(request.method)) return reject(request, 405, 'method_not_allowed');
  const releaseOrigin = memberOrigin(url, env);
  const host = request.headers.get('host');
  if (!releaseOrigin || (host && host !== url.host)) return reject(request, 403, 'origin_not_allowed');
  const audience = memberAudience(env, releaseOrigin);
  if (!audience) return ownerDenial;

  const origin = request.headers.get('origin');
  const topLevelDocument = document && request.headers.get('sec-fetch-mode') === 'navigate'
    && request.headers.get('sec-fetch-dest') === 'document';
  if ((origin && origin !== url.origin) || (request.headers.get('sec-fetch-site') === 'cross-site' && !topLevelDocument)) {
    return reject(request, 403, 'cross_site');
  }
  if (!aggregate && url.search) return reject(request, 404, 'query_not_allowed');
  if (aggregate) {
    const key = aggregates.get(pathname);
    const keys = [...url.searchParams.keys()];
    if (keys.length > 1 || keys.some(value => value !== key)) return reject(request, 400, 'query_not_allowed');
  }

  try {
    const identity = await services.identity(request);
    if (!identity.subject || identity.reason) {
      const loginRequired = identity.reason === 'login_required' || identity.reason === 'refresh_required';
      if (loginRequired && topLevelDocument && request.method === 'GET') {
        const location = '/auth/login?return_to=' + encodeURIComponent(pathname);
        return new Response(null, { status: 302, headers: { ...privateHeaders, location } });
      }
      return reject(request, loginRequired ? 401 : 503, 'authentication_unavailable');
    }
    const subject = identity.subject;
    if (typeof subject !== 'string' || !/^\d{17,20}$/.test(subject) || typeof identity.discord_authorized !== 'boolean') {
      return reject(request, 503, 'authentication_unavailable');
    }
    const tier: MemberTier = identity.discord_authorized ? 'premium' : 'free';
    const role = tier === 'premium' ? 'allowed' : 'denied';
    if (releaseOrigin === 'production' && await productionAllowed?.(subject, tier) !== true) return ownerDenial;
    if (tier === 'free' && (audience === 'role_only' || preferences || (aggregate && pathname !== historyPath))) {
      const response = document ? roleRequiredPage(request) : reject(request, 403, 'role_required');
      observe?.(response, subject, role);
      return response;
    }
    const expectedSession = aggregate || preferences ? request.headers.get(memberSessionHeader) : null;
    if (pathname === fundamentalPath && expectedSession === null) return reject(request, 403, 'member_session_required');
    if (session || expectedSession !== null) {
      if (!env.SESSION_SECRET) return reject(request, 503, 'member_service_unavailable');
      const tag = await memberSessionTag(env.SESSION_SECRET, subject, tier);
      if (session) return new Response(null, {
        status: 204, headers: { ...privateHeaders, [memberSessionHeader]: tag, [memberAccessHeader]: tier },
      });
      if (expectedSession !== tag) return reject(request, 403, 'member_session_changed');
    }
    const handler = document ? services.document : preferences ? services.preferences
      : aggregate ? services.aggregate : services.asset;
    const response = await handler(request, subject, tier);
    const headers = new Headers(response.headers);
    for (const [key, value] of Object.entries(privateHeaders)) headers.set(key, value);
    headers.set(memberAccessHeader, tier);
    const finalResponse = new Response(request.method === 'HEAD' ? null : response.body, { status: response.status, headers });
    observe?.(finalResponse, subject, role);
    return finalResponse;
  } catch {
    return reject(request, 503, 'member_service_unavailable');
  }
}
