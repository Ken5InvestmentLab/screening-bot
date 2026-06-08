const SESSION_COOKIE = "__Host-report_gate_session";
const STATE_COOKIE = "__Host-report_gate_oauth_state";
const RETURN_TO_COOKIE = "__Host-report_gate_return_to";
const DISCORD_SCOPE = "identify guilds.members.read";
const ACCESS_GUARD_SCRIPT_PATH = "/auth/guard.js";
const REPORT_INTERACTIONS_SCRIPT_PATH = "/report-interactions.js";
const ROLE_CACHE_SECONDS = 90;
const ROLE_CACHE_RATE_LIMIT_GRACE_SECONDS = 600;
const REPORT_ASSET_PATH_RE = /^\/mega_validation_report(?:_[a-z0-9_]+)?\.html$/;
const ACCESS_GUARD_SCRIPT = `(() => {
  const checkIntervalMs = 120000;
  const deny = () => {
    document.documentElement.innerHTML = '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Access denied</title><style>body{font-family:system-ui,sans-serif;margin:40px;line-height:1.6;color:#182230}a{color:#2563eb}</style></head><body><h1>Access denied</h1><p>Your Discord role no longer allows access to this report.</p><p><a href="/auth/logout">Log in again</a></p></body>';
  };
  const check = async () => {
    try {
      const response = await fetch('/auth/check', {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { accept: 'application/json' },
      });
      if (response.status === 401) {
        window.location.replace('/auth/login?return_to=' + encodeURIComponent(window.location.pathname + window.location.search));
        return;
      }
      if (response.status === 403) {
        deny();
      }
    } catch {
      // Keep the current page during transient network failures; the next check will retry.
    }
  };
  window.addEventListener('pageshow', check);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      check();
    }
  });
  window.setInterval(check, checkIntervalMs);
})();`;

type WorkerEnv = Env & {
  DISCORD_CLIENT_ID?: string;
  DISCORD_CLIENT_SECRET?: string;
  PUBLIC_BASE_URL?: string;
  SESSION_SECRET?: string;
};

type SessionPayload = {
  sub: string;
  accessToken: string;
  exp: number;
  roleCheckedAt: number;
  roles: string[];
  tokenExp: number;
};

type OAuthStatePayload = {
  exp: number;
  returnTo: string;
};

type DiscordTokenResponse = {
  access_token?: string;
  expires_in?: number;
  token_type?: string;
  scope?: string;
};

type DiscordGuildMember = {
  user?: {
    id?: string;
    username?: string;
  };
  roles?: string[];
};

class AccessDeniedError extends Error {}

class DiscordRateLimitedError extends Error {}

type SecurityHeaderOptions = {
  allowReportScript?: boolean;
};

function textResponse(body: string, status = 200): Response {
  return new Response(body, {
    status,
    headers: securityHeaders({
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
    }),
  });
}

function jsonResponse(body: unknown, status = 200, init: HeadersInit = {}): Response {
  const headers = new Headers(init);
  headers.set("content-type", "application/json; charset=utf-8");
  headers.set("cache-control", "no-store");
  return new Response(JSON.stringify(body), {
    status,
    headers: securityHeaders(headers),
  });
}

function htmlResponse(title: string, message: string, status = 200, init: HeadersInit = {}): Response {
  const safeTitle = escapeHtml(title);
  const safeMessage = escapeHtml(message);
  const headers = new Headers(init);
  headers.set("content-type", "text/html; charset=utf-8");
  headers.set("cache-control", "no-store");
  return new Response(
    `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${safeTitle}</title><style>body{font-family:system-ui,sans-serif;margin:40px;line-height:1.6;color:#182230}a{color:#2563eb}</style></head><body><h1>${safeTitle}</h1><p>${safeMessage}</p><p><a href="/auth/login">Discordでログイン</a></p></body></html>`,
    {
      status,
      headers: securityHeaders(headers),
    },
  );
}

function securityHeaders(init: HeadersInit = {}, options: SecurityHeaderOptions = {}): Headers {
  const headers = new Headers(init);
  headers.set("x-content-type-options", "nosniff");
  headers.set("x-frame-options", "DENY");
  headers.set("referrer-policy", "no-referrer");
  headers.set("x-robots-tag", "noindex, nofollow, noarchive");
  const csp = [
    "default-src 'none'",
    options.allowReportScript ? "script-src 'self'" : "",
    options.allowReportScript ? "connect-src 'self'" : "",
    "style-src 'unsafe-inline'",
    "img-src data: https:",
    "base-uri 'none'",
    "frame-ancestors 'none'",
  ].filter(Boolean);
  headers.set("content-security-policy", csp.join("; "));
  return headers;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function requiredEnv(env: WorkerEnv, key: keyof WorkerEnv): string {
  const value = env[key];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Missing required environment variable: ${String(key)}`);
  }
  return value.trim();
}

function optionalEnv(env: WorkerEnv, key: keyof WorkerEnv, fallback: string): string {
  const value = env[key];
  return typeof value === "string" && value.trim() !== "" ? value.trim() : fallback;
}

function allowedRoleIds(env: WorkerEnv): string[] {
  return requiredEnv(env, "DISCORD_ALLOWED_ROLE_IDS")
    .split(",")
    .map((roleId) => roleId.trim())
    .filter(Boolean);
}

function hasAllowedRole(memberRoles: string[], allowedRoles: string[]): boolean {
  const memberRoleSet = new Set(memberRoles);
  return allowedRoles.some((roleId) => memberRoleSet.has(roleId));
}

function parseCookies(request: Request): Map<string, string> {
  const cookieHeader = request.headers.get("cookie") ?? "";
  const cookies = new Map<string, string>();
  for (const part of cookieHeader.split(";")) {
    const [rawName, ...rawValue] = part.trim().split("=");
    if (!rawName || rawValue.length === 0) {
      continue;
    }
    cookies.set(rawName, decodeURIComponent(rawValue.join("=")));
  }
  return cookies;
}

function cookie(name: string, value: string, requestUrl: URL, maxAgeSeconds: number): string {
  const secure = requestUrl.protocol === "https:" ? " Secure;" : "";
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax;${secure} Max-Age=${maxAgeSeconds}`;
}

function clearCookie(name: string, requestUrl: URL): string {
  return cookie(name, "", requestUrl, 0);
}

function safeReturnTo(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/";
  }
  if (value.startsWith("/auth/")) {
    return "/";
  }
  return value;
}

function publicBaseUrl(request: Request, env: WorkerEnv): string {
  const configured = optionalEnv(env, "PUBLIC_BASE_URL", "");
  if (configured !== "") {
    return configured.replace(/\/+$/, "");
  }
  const url = new URL(request.url);
  return url.origin;
}

function callbackUrl(request: Request, env: WorkerEnv): string {
  return `${publicBaseUrl(request, env)}/auth/callback`;
}

function discordApiBase(env: WorkerEnv): string {
  return optionalEnv(env, "DISCORD_API_BASE", "https://discord.com/api").replace(/\/+$/, "");
}

function randomToken(bytes = 32): string {
  const buffer = new Uint8Array(bytes);
  crypto.getRandomValues(buffer);
  return base64UrlEncode(buffer);
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function base64UrlEncodeString(value: string): string {
  return base64UrlEncode(new TextEncoder().encode(value));
}

function base64UrlDecodeString(value: string): string {
  return new TextDecoder().decode(base64UrlDecode(value));
}

function base64UrlDecode(value: string): Uint8Array {
  const padded = value.replaceAll("-", "+").replaceAll("_", "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

async function signPayload(payload: string, secret: string): Promise<string> {
  const signature = await crypto.subtle.sign("HMAC", await hmacKey(secret), new TextEncoder().encode(payload));
  return base64UrlEncode(new Uint8Array(signature));
}

async function verifySignature(payload: string, signature: string, secret: string): Promise<boolean> {
  const padded = signature.replaceAll("-", "+").replaceAll("_", "/").padEnd(Math.ceil(signature.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return crypto.subtle.verify("HMAC", await hmacKey(secret), bytes, new TextEncoder().encode(payload));
}

async function aesKey(secret: string): Promise<CryptoKey> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret));
  return crypto.subtle.importKey("raw", digest, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

async function createSession(payload: SessionPayload, secret: string): Promise<string> {
  const iv = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    await aesKey(secret),
    new TextEncoder().encode(JSON.stringify(payload)),
  );
  return `v2.${base64UrlEncode(iv)}.${base64UrlEncode(new Uint8Array(ciphertext))}`;
}

async function createOAuthState(returnTo: string, secret: string): Promise<string> {
  const payload = base64UrlEncodeString(
    JSON.stringify({
      exp: Math.floor(Date.now() / 1000) + 600,
      returnTo,
    } satisfies OAuthStatePayload),
  );
  const signature = await signPayload(payload, secret);
  return `${payload}.${signature}`;
}

async function readOAuthState(state: string | null, secret: string): Promise<OAuthStatePayload | null> {
  if (!state) {
    return null;
  }

  const [payload, signature] = state.split(".");
  if (!payload || !signature || !(await verifySignature(payload, signature, secret))) {
    return null;
  }

  try {
    const parsed = JSON.parse(base64UrlDecodeString(payload)) as Partial<OAuthStatePayload>;
    if (typeof parsed.exp !== "number" || typeof parsed.returnTo !== "string") {
      return null;
    }
    if (parsed.exp <= Math.floor(Date.now() / 1000)) {
      return null;
    }
    return {
      exp: parsed.exp,
      returnTo: safeReturnTo(parsed.returnTo),
    };
  } catch {
    return null;
  }
}

async function readSession(request: Request, env: WorkerEnv): Promise<SessionPayload | null> {
  const session = parseCookies(request).get(SESSION_COOKIE);
  if (!session) {
    return null;
  }

  const [version, encodedIv, encodedCiphertext] = session.split(".");
  if (version !== "v2" || !encodedIv || !encodedCiphertext) {
    return null;
  }

  const sessionSecret = requiredEnv(env, "SESSION_SECRET");

  try {
    const plaintext = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: base64UrlDecode(encodedIv) },
      await aesKey(sessionSecret),
      base64UrlDecode(encodedCiphertext),
    );
    const parsed = JSON.parse(new TextDecoder().decode(plaintext)) as Partial<SessionPayload>;
    if (
      typeof parsed.sub !== "string" ||
      typeof parsed.accessToken !== "string" ||
      typeof parsed.exp !== "number" ||
      typeof parsed.tokenExp !== "number"
    ) {
      return null;
    }
    const now = Math.floor(Date.now() / 1000);
    if (parsed.exp <= now || parsed.tokenExp <= now) {
      return null;
    }
    return {
      sub: parsed.sub,
      accessToken: parsed.accessToken,
      exp: parsed.exp,
      roleCheckedAt: typeof parsed.roleCheckedAt === "number" ? parsed.roleCheckedAt : 0,
      roles: Array.isArray(parsed.roles) ? parsed.roles.filter((role): role is string => typeof role === "string") : [],
      tokenExp: parsed.tokenExp,
    };
  } catch {
    return null;
  }
}

type AuthorizationCheck = {
  authorized: boolean;
  refreshedSession?: SessionPayload;
};

async function checkSessionAuthorization(session: SessionPayload, env: WorkerEnv): Promise<AuthorizationCheck> {
  const now = Math.floor(Date.now() / 1000);
  const hasFreshRoles =
    session.roles.length > 0 && session.roleCheckedAt > 0 && now - session.roleCheckedAt <= ROLE_CACHE_SECONDS;
  if (hasFreshRoles) {
    return { authorized: hasAllowedRole(session.roles, allowedRoleIds(env)) };
  }

  try {
    const member = await fetchGuildMember(session.accessToken, env);
    const roles = member.roles ?? [];
    return {
      authorized: hasAllowedRole(roles, allowedRoleIds(env)),
      refreshedSession: {
        ...session,
        roleCheckedAt: now,
        roles,
      },
    };
  } catch (error) {
    if (error instanceof AccessDeniedError) {
      return { authorized: false };
    }
    if (
      error instanceof DiscordRateLimitedError &&
      session.roles.length > 0 &&
      session.roleCheckedAt > 0 &&
      now - session.roleCheckedAt <= ROLE_CACHE_RATE_LIMIT_GRACE_SECONDS
    ) {
      return { authorized: hasAllowedRole(session.roles, allowedRoleIds(env)) };
    }
    throw error;
  }
}

async function encryptedSessionCookie(request: Request, env: WorkerEnv, session: SessionPayload): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const maxAge = Math.max(0, session.exp - now);
  return cookie(SESSION_COOKIE, await createSession(session, requiredEnv(env, "SESSION_SECRET")), new URL(request.url), maxAge);
}

function accessDeniedResponse(request: Request): Response {
  const url = new URL(request.url);
  const headers = new Headers();
  headers.append("set-cookie", clearCookie(SESSION_COOKIE, url));
  return htmlResponse("Access denied", "Your Discord account does not have the required role.", 403, headers);
}

type AuthorizationResult =
  | { allowed: true; refreshedSession?: SessionPayload }
  | { allowed: false; response: Response };

async function requireAuthorized(request: Request, env: WorkerEnv): Promise<AuthorizationResult> {
  const session = await readSession(request, env);
  if (session) {
    const check = await checkSessionAuthorization(session, env);
    if (check.authorized) {
      return { allowed: true, refreshedSession: check.refreshedSession };
    }
    return { allowed: false, response: accessDeniedResponse(request) };
  }

  const url = new URL(request.url);
  const loginUrl = new URL("/auth/login", url.origin);
  loginUrl.searchParams.set("return_to", safeReturnTo(`${url.pathname}${url.search}`));
  return { allowed: false, response: Response.redirect(loginUrl.toString(), 302) };
}

async function login(request: Request, env: WorkerEnv): Promise<Response> {
  requiredEnv(env, "DISCORD_CLIENT_ID");
  requiredEnv(env, "DISCORD_CLIENT_SECRET");
  requiredEnv(env, "DISCORD_GUILD_ID");
  requiredEnv(env, "DISCORD_ALLOWED_ROLE_IDS");
  requiredEnv(env, "SESSION_SECRET");

  const url = new URL(request.url);
  const returnTo = safeReturnTo(url.searchParams.get("return_to"));
  const state = await createOAuthState(returnTo, requiredEnv(env, "SESSION_SECRET"));
  const authorizeUrl = new URL("https://discord.com/oauth2/authorize");
  authorizeUrl.searchParams.set("client_id", requiredEnv(env, "DISCORD_CLIENT_ID"));
  authorizeUrl.searchParams.set("redirect_uri", callbackUrl(request, env));
  authorizeUrl.searchParams.set("response_type", "code");
  authorizeUrl.searchParams.set("scope", DISCORD_SCOPE);
  authorizeUrl.searchParams.set("state", state);

  const headers = new Headers();
  headers.append("set-cookie", clearCookie(STATE_COOKIE, url));
  headers.append("set-cookie", clearCookie(RETURN_TO_COOKIE, url));
  headers.set("location", authorizeUrl.toString());
  headers.set("cache-control", "no-store");
  return new Response(null, { status: 302, headers });
}

async function callback(request: Request, env: WorkerEnv): Promise<Response> {
  const url = new URL(request.url);
  const actualState = url.searchParams.get("state");
  const code = url.searchParams.get("code");
  const state = await readOAuthState(actualState, requiredEnv(env, "SESSION_SECRET"));

  if (url.searchParams.has("error")) {
    return htmlResponse("Login cancelled", "Discord authorization was not completed.", 401);
  }
  if (!code || !state) {
    return htmlResponse("Invalid login state", "Please start the Discord login again.", 400);
  }

  const token = await exchangeCodeForToken(code, request, env);
  const member = await fetchGuildMember(token.accessToken, env);
  const roles = member.roles ?? [];
  if (!hasAllowedRole(roles, allowedRoleIds(env))) {
    return htmlResponse("Access denied", "Your Discord account does not have the required role.", 403);
  }

  const userId = member.user?.id;
  if (!userId) {
    return htmlResponse("Access denied", "Discord did not return a user id for this guild member.", 403);
  }

  const configuredTtl = Number.parseInt(optionalEnv(env, "SESSION_TTL_SECONDS", "21600"), 10);
  const ttl = Number.isFinite(configuredTtl) && configuredTtl > 0 ? configuredTtl : 21600;
  const now = Math.floor(Date.now() / 1000);
  const exp = now + ttl;
  const tokenExp = now + token.expiresIn;
  const session = await createSession(
    { sub: userId, accessToken: token.accessToken, exp, roleCheckedAt: now, roles, tokenExp },
    requiredEnv(env, "SESSION_SECRET"),
  );
  const returnTo = state.returnTo;

  const headers = new Headers();
  headers.append("set-cookie", cookie(SESSION_COOKIE, session, url, ttl));
  headers.append("set-cookie", clearCookie(STATE_COOKIE, url));
  headers.append("set-cookie", clearCookie(RETURN_TO_COOKIE, url));
  headers.set("location", returnTo);
  headers.set("cache-control", "no-store");
  return new Response(null, { status: 302, headers });
}

async function exchangeCodeForToken(
  code: string,
  request: Request,
  env: WorkerEnv,
): Promise<{ accessToken: string; expiresIn: number }> {
  const body = new URLSearchParams({
    client_id: requiredEnv(env, "DISCORD_CLIENT_ID"),
    client_secret: requiredEnv(env, "DISCORD_CLIENT_SECRET"),
    grant_type: "authorization_code",
    code,
    redirect_uri: callbackUrl(request, env),
  });

  const response = await fetch(`${discordApiBase(env)}/oauth2/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!response.ok) {
    const errorBody = (await response.text()).slice(0, 500);
    throw new Error(`Discord token exchange failed: ${response.status} ${errorBody}`);
  }

  const token = (await response.json()) as DiscordTokenResponse;
  if (!token.access_token) {
    throw new Error("Discord token response did not include access_token");
  }
  const expiresIn = typeof token.expires_in === "number" && token.expires_in > 0 ? token.expires_in : 3600;
  return { accessToken: token.access_token, expiresIn };
}

async function fetchGuildMember(accessToken: string, env: WorkerEnv): Promise<DiscordGuildMember> {
  const guildId = requiredEnv(env, "DISCORD_GUILD_ID");
  const response = await fetch(`${discordApiBase(env)}/users/@me/guilds/${guildId}/member`, {
    headers: { authorization: `Bearer ${accessToken}` },
  });

  if (response.status === 429) {
    throw new DiscordRateLimitedError("Discord guild member lookup was rate limited");
  }
  if ([401, 403, 404].includes(response.status)) {
    throw new AccessDeniedError("Discord guild member lookup did not authorize this user");
  }
  if (!response.ok) {
    throw new Error(`Discord guild member lookup failed: ${response.status}`);
  }
  return (await response.json()) as DiscordGuildMember;
}

function reportAssetPath(env: WorkerEnv): string {
  const path = optionalEnv(env, "REPORT_ASSET_PATH", "/mega_validation_report_latest.html");
  return path.startsWith("/") ? path : `/${path}`;
}

function isReportAssetPath(pathname: string, env: WorkerEnv): boolean {
  return pathname === reportAssetPath(env) || REPORT_ASSET_PATH_RE.test(pathname);
}

function injectAccessGuard(html: string): string {
  if (html.includes(ACCESS_GUARD_SCRIPT_PATH)) {
    return html;
  }

  const scriptTag = `<script src="${ACCESS_GUARD_SCRIPT_PATH}" defer></script>`;
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${scriptTag}</body>`);
  }
  return `${html}${scriptTag}`;
}

async function serveReport(request: Request, env: WorkerEnv, assetPath = reportAssetPath(env)): Promise<Response> {
  const authorization = await requireAuthorized(request, env);
  if (!authorization.allowed) {
    return authorization.response;
  }

  const assetUrl = new URL(assetPath, "https://assets.local");
  const assetResponse = await env.ASSETS.fetch(assetUrl.toString());
  if (!assetResponse.ok || !assetResponse.body) {
    return textResponse("Report asset not found", 404);
  }

  const html = injectAccessGuard(await assetResponse.text());
  const headers = securityHeaders(
    {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "private, no-store",
    },
    { allowReportScript: true },
  );
  if (authorization.refreshedSession) {
    headers.append("set-cookie", await encryptedSessionCookie(request, env, authorization.refreshedSession));
  }
  return new Response(html, {
    status: assetResponse.status,
    headers,
  });
}

async function serveReportScript(env: WorkerEnv): Promise<Response> {
  const assetUrl = new URL(REPORT_INTERACTIONS_SCRIPT_PATH, "https://assets.local");
  const assetResponse = await env.ASSETS.fetch(assetUrl.toString());
  if (!assetResponse.ok || !assetResponse.body) {
    return textResponse("Report script not found", 404);
  }
  return new Response(assetResponse.body, {
    status: assetResponse.status,
    headers: securityHeaders({
      "content-type": "application/javascript; charset=utf-8",
      "cache-control": "public, max-age=300",
    }),
  });
}

async function authCheck(request: Request, env: WorkerEnv): Promise<Response> {
  const session = await readSession(request, env);
  const url = new URL(request.url);
  if (!session) {
    const headers = new Headers();
    headers.append("set-cookie", clearCookie(SESSION_COOKIE, url));
    return jsonResponse({ ok: false, reason: "login_required" }, 401, headers);
  }

  const check = await checkSessionAuthorization(session, env);
  if (!check.authorized) {
    const headers = new Headers();
    headers.append("set-cookie", clearCookie(SESSION_COOKIE, url));
    return jsonResponse({ ok: false, reason: "role_required" }, 403, headers);
  }

  const headers = new Headers();
  if (check.refreshedSession) {
    headers.append("set-cookie", await encryptedSessionCookie(request, env, check.refreshedSession));
  }
  return jsonResponse({ ok: true }, 200, headers);
}

function logout(request: Request): Response {
  const url = new URL(request.url);
  const headers = new Headers({
    location: "/auth/login",
    "cache-control": "no-store",
  });
  headers.append("set-cookie", clearCookie(SESSION_COOKIE, url));
  return new Response(null, { status: 302, headers });
}

async function router(request: Request, env: WorkerEnv): Promise<Response> {
  const url = new URL(request.url);
  if (url.pathname === "/healthz") {
    return textResponse("ok");
  }
  if (url.pathname === "/robots.txt") {
    return textResponse("User-agent: *\nDisallow: /\n");
  }
  if (url.pathname === "/auth/login") {
    return login(request, env);
  }
  if (url.pathname === "/auth/check") {
    return authCheck(request, env);
  }
  if (url.pathname === ACCESS_GUARD_SCRIPT_PATH) {
    return new Response(ACCESS_GUARD_SCRIPT, {
      headers: securityHeaders({
        "content-type": "application/javascript; charset=utf-8",
        "cache-control": "no-store",
      }),
    });
  }
  if (url.pathname === REPORT_INTERACTIONS_SCRIPT_PATH) {
    return serveReportScript(env);
  }
  if (url.pathname === "/auth/callback") {
    return callback(request, env);
  }
  if (url.pathname === "/auth/logout") {
    return logout(request);
  }
  if (url.pathname === "/" || url.pathname === "/report") {
    return serveReport(request, env);
  }
  if (isReportAssetPath(url.pathname, env)) {
    return serveReport(request, env, url.pathname);
  }
  return textResponse("Not found", 404);
}

export default {
  async fetch(request, env): Promise<Response> {
    try {
      return await router(request, env);
    } catch (error) {
      if (error instanceof AccessDeniedError) {
        return htmlResponse("Access denied", "Your Discord account is not allowed to view this report.", 403);
      }
      console.error(
        JSON.stringify({
          level: "error",
          message: error instanceof Error ? error.message : "unknown error",
        }),
      );
      return htmlResponse("Temporary error", "The protected report is temporarily unavailable.", 500);
    }
  },
} satisfies ExportedHandler<WorkerEnv>;
