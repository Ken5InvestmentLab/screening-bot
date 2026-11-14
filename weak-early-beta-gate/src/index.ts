import { newACloudRoute } from "./new-a-cloud";
// The OAuth/session/role implementation remains byte-identical in the synced
// shared module. This wrapper only lets the beta's mode pages use the same gate.
import sharedGate, { reportIdentity } from "./shared-report-gate";
import { cloudApi, type CloudEnv } from "./cloud-api";
import { runScheduledPersonalNotifications, type ScheduleEnv } from "./cloud-push-scheduler";
import { ownerOnlyGate } from "./cloud-owner-only";
import { cloudReportRole } from "./cloud-role-authority";
export { CloudRoleAuthority } from "./cloud-role-authority";

const MODE_PAGE_RE = /^\/weak_early_beta_(?:analytics|silence|dive|shadow|fusion|balance|guide)\.html$/;
const BETA_SCRIPT_RE = /^\/weak-early-beta-(?:interactions|theme-init|scenarios|push|service-worker)\.js$/;
const BUNDLE_RE = /^\/weak_early_beta_data_(full|free)_(latest|analytics|silence|dive|shadow|fusion|balance|guide)_([a-f0-9]{16})_(\d{4})\.json$/;
type SharedRequest = Parameters<typeof sharedGate.fetch>[0];

async function bundleResponse(request: Request, env: CloudEnv, audience: string): Promise<Response> {
  const headers = { "content-type": "application/json; charset=utf-8", "cache-control": "private, no-store",
    vary: "Cookie", "x-content-type-options": "nosniff", "cross-origin-resource-policy": "same-origin" };
  const reject = (status: number) => new Response(JSON.stringify({ error: "bundle_unavailable" }), { status, headers });
  if (request.method !== "GET" && request.method !== "HEAD") return reject(405);
  if (request.headers.get("sec-fetch-site") === "cross-site" || (request.headers.get("origin") && request.headers.get("origin") !== new URL(request.url).origin)) return reject(403);
  try {
    if (audience === "full") {
      const identity = await reportIdentity(request, { ...env, REPORT_ROLE_LOOKUP: (subject, token) => cloudReportRole(env, subject, token, "/full-data") }, true);
      if (!identity.subject) return reject(identity.reason === "login_required" || identity.reason === "refresh_required" ? 401 : 503);
      if (!identity.discord_authorized) return reject(403);
    }
    const asset = await env.ASSETS.fetch(new URL(new URL(request.url).pathname, "https://assets.local").toString());
    if (!asset.ok) return reject(404);
    return new Response(request.method === "HEAD" ? null : asset.body, { status: 200, headers });
  } catch (_error) { return reject(503); }
}

export default {
  async scheduled(controller: ScheduledController, env: ScheduleEnv): Promise<void> {
    const result = await runScheduledPersonalNotifications(controller, env);
    console.log(JSON.stringify({ operation: "cloud_personal_schedule", ...result }));
  },
  async fetch(request: SharedRequest, env: CloudEnv): Promise<Response> {
    const denied = await ownerOnlyGate(request, env);
    if (denied) return denied;
    const newAResponse = await newACloudRoute(request, env);
    if (newAResponse) return newAResponse;
    const pathname = new URL(request.url).pathname;
    const bundle = BUNDLE_RE.exec(pathname);
    if (bundle) return bundleResponse(request, env, bundle[1]);
    if (pathname.startsWith("/weak_early_beta_data_")) return new Response("Not found", { status: 404, headers: { "cache-control": "private, no-store" } });
    if (pathname.startsWith("/api/cloud/")) return cloudApi(request, env);
    // Keep existing Discord OAuth + configured-role access. Payment verification
    // remains independent for notifications, without another user login.
    // First-time visitors go straight to existing Discord OAuth, without a
    // purchase interstitial. Valid free sessions receive prefiltered free HTML.
    // Full assets and full lazy bundles retain the existing Discord role gate.
    const protectedEnv = { ...env, REPORT_PUBLIC_FREE: "true", REPORT_LOGIN_REQUIRED: "true", REPORT_REQUIRE_FRESH_ROLE: "true",
      REPORT_ROLE_LOOKUP: (subject: string, token: string) => cloudReportRole(env, subject, token, pathname) };
    if (BETA_SCRIPT_RE.test(pathname)) {
      const assetResponse = await env.ASSETS.fetch(
        new URL(pathname, "https://assets.local").toString(),
      );
      if (!assetResponse.ok || !assetResponse.body) {
        return new Response("Not found", { status: 404 });
      }
      return new Response(assetResponse.body, {
        status: assetResponse.status,
        headers: {
          "content-type": "application/javascript; charset=utf-8",
          "cache-control": pathname.endsWith("service-worker.js") ? "no-store" : "public, max-age=300",
          "x-content-type-options": "nosniff",
        },
      });
    }
    if (MODE_PAGE_RE.test(pathname)) {
      const modeEnv = { ...protectedEnv, REPORT_ASSET_PATH: pathname } as unknown as Env;
      return sharedGate.fetch(request, modeEnv);
    }
    return sharedGate.fetch(request, protectedEnv);
  },
};
