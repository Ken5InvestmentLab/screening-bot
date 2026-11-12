import { reportVerifiedSessionSubject } from "./shared-report-gate";
import type { CloudEnv } from "./cloud-api";

const PUBLIC_PATHS = new Set(["/auth/login", "/auth/callback", "/auth/logout", "/auth/guard.js", "/healthz", "/robots.txt"]);
const headers = { "cache-control": "private, no-store", vary: "Cookie", "x-content-type-options": "nosniff", "x-cloud-private": "true" };
function privateResponse(status: number, json = false): Response {
  if (json) return Response.json({ authorized: false, reason: "owner_only" }, { status, headers });
  return new Response('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>非公開中</title><body><h1>現在非公開です</h1><p>所有者本人のみ閲覧できます。</p><a href="/auth/logout">別のDiscordアカウントでログイン</a></body></html>', { status, headers: { ...headers, "content-type": "text/html; charset=utf-8" } });
}

export async function ownerOnlyGate(request: Request, env: CloudEnv): Promise<Response | null> {
  // Missing/off preserves historical policy; misspelled nonempty mode fails shut.
  const mode = env.CLOUD_OWNER_ONLY_ENABLED?.trim().toLowerCase();
  if (!mode || mode === "false") return null;
  const path = new URL(request.url).pathname;
  if (PUBLIC_PATHS.has(path)) return null;
  const json = path === "/auth/check" || path.startsWith("/api/") || path.endsWith(".json");
  const owner = env.CLOUD_OWNER_DISCORD_ID?.trim();
  if (mode !== "true" || !owner || !/^\d{17,20}$/.test(owner)) return privateResponse(503, json);
  let subject: string | undefined;
  try { subject = await reportVerifiedSessionSubject(request, env); }
  catch { return privateResponse(503, json); }
  if (subject === owner) return null;
  if (subject) {
    // Older guards ignore free-page 403s, but 401 sends them through login to
    // the now-denied document. Updated guards handle x-cloud-private directly.
    return privateResponse(path === "/auth/check" ? 401 : 403, json);
  }
  if (path === "/private") return privateResponse(403);
  if (json || !["GET", "HEAD"].includes(request.method)) return privateResponse(401, true);
  const url = new URL(request.url);
  return new Response(null, { status: 302, headers: { ...headers, location: "/auth/login?return_to=" + encodeURIComponent(url.pathname + url.search) } });
}
