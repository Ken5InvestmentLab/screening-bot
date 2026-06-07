const SESSION_COOKIE = "__Host-report_gate_session";
const STATE_COOKIE = "__Host-report_gate_oauth_state";
const RETURN_TO_COOKIE = "__Host-report_gate_return_to";
const DISCORD_SCOPE = "identify guilds.members.read";

type WorkerEnv = Env & {
  DISCORD_CLIENT_ID?: string;
  DISCORD_CLIENT_SECRET?: string;
  PUBLIC_BASE_URL?: string;
  SESSION_SECRET?: string;
};

type SessionPayload = {
  sub: string;
  roles: string[];
  exp: number;
};

type DiscordTokenResponse = {
  access_token?: string;
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

function textResponse(body: string, status = 200): Response {
  return new Response(body, {
    status,
    headers: securityHeaders({
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
    }),
  });
}

function htmlResponse(title: string, message: string, status = 200): Response {
  const safeTitle = escapeHtml(title);
  const safeMessage = escapeHtml(message);
  return new Response(
    `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${safeTitle}</title><style>body{font-family:system-ui,sans-serif;margin:40px;line-height:1.6;color:#182230}a{color:#2563eb}</style></head><body><h1>${safeTitle}</h1><p>${safeMessage}</p><p><a href="/auth/login">Discordでログイン</a></p></body></html>`,
    {
      status,
      headers: securityHeaders({
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
      }),
    },
  );
}

function securityHeaders(init: HeadersInit = {}): Headers {
  const headers = new Headers(init);
  headers.set("x-content-type-options", "nosniff");
  headers.set("x-frame-options", "DENY");
  headers.set("referrer-policy", "no-referrer");
  headers.set("x-robots-tag", "noindex, nofollow, noarchive");
  headers.set(
    "content-security-policy",
    "default-src 'none'; style-src 'unsafe-inline'; img-src data: https:; base-uri 'none'; frame-ancestors 'none'",
  );
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
  const padded = value.replaceAll("-", "+").replaceAll("_", "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new TextDecoder().decode(bytes);
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

async function createSession(payload: SessionPayload, secret: string): Promise<string> {
  const encodedPayload = base64UrlEncodeString(JSON.stringify(payload));
  const signature = await signPayload(encodedPayload, secret);
  return `${encodedPayload}.${signature}`;
}

async function readSession(request: Request, env: WorkerEnv): Promise<SessionPayload | null> {
  const session = parseCookies(request).get(SESSION_COOKIE);
  if (!session) {
    return null;
  }

  const [payload, signature] = session.split(".");
  if (!payload || !signature) {
    return null;
  }

  const sessionSecret = requiredEnv(env, "SESSION_SECRET");
  if (!(await verifySignature(payload, signature, sessionSecret))) {
    return null;
  }

  try {
    const parsed = JSON.parse(base64UrlDecodeString(payload)) as Partial<SessionPayload>;
    if (typeof parsed.sub !== "string" || !Array.isArray(parsed.roles) || typeof parsed.exp !== "number") {
      return null;
    }
    if (parsed.exp <= Math.floor(Date.now() / 1000)) {
      return null;
    }
    return {
      sub: parsed.sub,
      roles: parsed.roles.filter((role): role is string => typeof role === "string"),
      exp: parsed.exp,
    };
  } catch {
    return null;
  }
}

async function requireAuthorized(request: Request, env: WorkerEnv): Promise<Response | null> {
  const session = await readSession(request, env);
  if (session && hasAllowedRole(session.roles, allowedRoleIds(env))) {
    return null;
  }

  const url = new URL(request.url);
  const loginUrl = new URL("/auth/login", url.origin);
  loginUrl.searchParams.set("return_to", safeReturnTo(`${url.pathname}${url.search}`));
  return Response.redirect(loginUrl.toString(), 302);
}

async function login(request: Request, env: WorkerEnv): Promise<Response> {
  requiredEnv(env, "DISCORD_CLIENT_ID");
  requiredEnv(env, "DISCORD_CLIENT_SECRET");
  requiredEnv(env, "DISCORD_GUILD_ID");
  requiredEnv(env, "DISCORD_ALLOWED_ROLE_IDS");
  requiredEnv(env, "SESSION_SECRET");

  const url = new URL(request.url);
  const state = randomToken();
  const returnTo = safeReturnTo(url.searchParams.get("return_to"));
  const authorizeUrl = new URL("https://discord.com/oauth2/authorize");
  authorizeUrl.searchParams.set("client_id", requiredEnv(env, "DISCORD_CLIENT_ID"));
  authorizeUrl.searchParams.set("redirect_uri", callbackUrl(request, env));
  authorizeUrl.searchParams.set("response_type", "code");
  authorizeUrl.searchParams.set("scope", DISCORD_SCOPE);
  authorizeUrl.searchParams.set("state", state);

  const headers = new Headers();
  headers.append("set-cookie", cookie(STATE_COOKIE, state, url, 600));
  headers.append("set-cookie", cookie(RETURN_TO_COOKIE, returnTo, url, 600));
  headers.set("location", authorizeUrl.toString());
  headers.set("cache-control", "no-store");
  return new Response(null, { status: 302, headers });
}

async function callback(request: Request, env: WorkerEnv): Promise<Response> {
  const url = new URL(request.url);
  const cookies = parseCookies(request);
  const expectedState = cookies.get(STATE_COOKIE);
  const actualState = url.searchParams.get("state");
  const code = url.searchParams.get("code");

  if (url.searchParams.has("error")) {
    return htmlResponse("Login cancelled", "Discord authorization was not completed.", 401);
  }
  if (!code || !expectedState || actualState !== expectedState) {
    return htmlResponse("Invalid login state", "Please start the Discord login again.", 400);
  }

  const token = await exchangeCodeForToken(code, request, env);
  const member = await fetchGuildMember(token, env);
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
  const exp = Math.floor(Date.now() / 1000) + ttl;
  const session = await createSession({ sub: userId, roles, exp }, requiredEnv(env, "SESSION_SECRET"));
  const returnTo = safeReturnTo(cookies.get(RETURN_TO_COOKIE) ?? "/");

  const headers = new Headers();
  headers.append("set-cookie", cookie(SESSION_COOKIE, session, url, ttl));
  headers.append("set-cookie", clearCookie(STATE_COOKIE, url));
  headers.append("set-cookie", clearCookie(RETURN_TO_COOKIE, url));
  headers.set("location", returnTo);
  headers.set("cache-control", "no-store");
  return new Response(null, { status: 302, headers });
}

async function exchangeCodeForToken(code: string, request: Request, env: WorkerEnv): Promise<string> {
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
    throw new Error(`Discord token exchange failed: ${response.status}`);
  }

  const token = (await response.json()) as DiscordTokenResponse;
  if (!token.access_token) {
    throw new Error("Discord token response did not include access_token");
  }
  return token.access_token;
}

async function fetchGuildMember(accessToken: string, env: WorkerEnv): Promise<DiscordGuildMember> {
  const guildId = requiredEnv(env, "DISCORD_GUILD_ID");
  const response = await fetch(`${discordApiBase(env)}/users/@me/guilds/${guildId}/member`, {
    headers: { authorization: `Bearer ${accessToken}` },
  });

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

async function serveReport(request: Request, env: WorkerEnv): Promise<Response> {
  const unauthorized = await requireAuthorized(request, env);
  if (unauthorized) {
    return unauthorized;
  }

  const assetUrl = new URL(reportAssetPath(env), "https://assets.local");
  const assetResponse = await env.ASSETS.fetch(assetUrl.toString());
  if (!assetResponse.ok || !assetResponse.body) {
    return textResponse("Report asset not found", 404);
  }

  const headers = securityHeaders(assetResponse.headers);
  headers.set("content-type", "text/html; charset=utf-8");
  headers.set("cache-control", "private, no-store");
  return new Response(assetResponse.body, {
    status: assetResponse.status,
    headers,
  });
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
  if (url.pathname === "/auth/callback") {
    return callback(request, env);
  }
  if (url.pathname === "/auth/logout") {
    return logout(request);
  }
  if (url.pathname === "/" || url.pathname === "/report" || url.pathname === reportAssetPath(env)) {
    return serveReport(request, env);
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
