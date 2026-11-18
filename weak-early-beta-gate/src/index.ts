import {isNewAPath,newACloudRoute,protectedReply,newAEarlyRefusal,isCompatibilityAsset,compatibilityCodeResponse} from "./new-a-cloud";
// The OAuth/session/role implementation remains byte-identical in the synced
// shared module. This wrapper only lets the beta's mode pages use the same gate.
import sharedGate, { reportIdentity } from "./shared-report-gate";
import { cloudApi, type CloudEnv } from "./cloud-api";
import { runScheduledPersonalNotifications, type ScheduleEnv } from "./cloud-push-scheduler";
import { ownerOnlyGate } from "./cloud-owner-only";
import { cloudReportRole } from "./cloud-role-authority";
import { operationalReadback } from "./operational-readback";
import { operationalBuild } from "./operational-build.generated";
import { observeOwnerResponse } from "./owner-response-observation";
import { dispatchStagedHoldingNotice, HOLDING_NOTICE_DISPATCH_PATH, NEW_A_HOLDING_CRON, NEW_A_MORNING_CRON, runNewAOwnerNoticeQueue } from "./new-a-owner-notice-queue";
export { CloudRoleAuthority } from "./cloud-role-authority";

const MODE_PAGE_RE = /^\/weak_early_beta_(?:analytics|silence|dive|shadow|fusion|balance|guide)\.html$/;
const BETA_SCRIPT_RE = /^\/weak-early-beta-(?:interactions|theme-init|scenarios|push|service-worker)\.js$/;
const BUNDLE_RE = /^\/weak_early_beta_data_(full|free)_(latest|analytics|silence|dive|shadow|fusion|balance|guide)_([a-f0-9]{16})_(\d{4})\.json$/;
type SharedRequest = Parameters<typeof sharedGate.fetch>[0];
type CloudScheduleEnv = ScheduleEnv & Parameters<typeof runNewAOwnerNoticeQueue>[0];

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
  async scheduled(controller: ScheduledController, env: CloudScheduleEnv): Promise<void> {
    if (env.CLOUD_NEW_A_OWNER_PUSH_ENABLED === "true" &&
        (controller.cron === NEW_A_MORNING_CRON || controller.cron === NEW_A_HOLDING_CRON)) {
      const result = String(env.CLOUD_PUSH_SCHEDULER_ENABLED) === "true"
        ? { status: "held", reason: "conflicting_legacy_schedule" }
        : await runNewAOwnerNoticeQueue(env, controller, operationalBuild);
      console.log(JSON.stringify({ operation: "cloud_new_a_owner_schedule", ...result }));
      return;
    }
    const result = await runScheduledPersonalNotifications(controller, env);
    console.log(JSON.stringify({ operation: "cloud_personal_schedule", ...result }));
  },
  async fetch(request: SharedRequest, env: CloudEnv): Promise<Response> {
    const pathname = new URL(request.url).pathname;
    if (pathname === HOLDING_NOTICE_DISPATCH_PATH) return dispatchStagedHoldingNotice(request, env, operationalBuild);
    const denied = await ownerOnlyGate(request, env);
    if (denied) return denied;
    if (pathname === '/healthz' && new URL(request.url).searchParams.has('new_a_probe')) return operationalReadback(request, env, operationalBuild);
    // Existing ownerOnlyGate has already run. Reuse the existing fresh-role identity.
    // Preserve existing push-only script updates after the unchanged owner gate.
    if (isCompatibilityAsset(pathname)) return compatibilityCodeResponse(request, env);
    if (isNewAPath(pathname)) {
      if (env.CLOUD_OWNER_ONLY_ENABLED?.trim().toLowerCase() !== "true") return protectedReply(request, 503, {error:"owner_mode_required"});
      const earlyRefusal = newAEarlyRefusal(request); if (earlyRefusal) return earlyRefusal;
      try {
        const identity = await reportIdentity(request, { ...env, REPORT_ROLE_LOOKUP: (subject, token) => cloudReportRole(env, subject, token, pathname) }, true);
        if (identity.reason === "refresh_required") {
          if (pathname.startsWith("/api/") || pathname.startsWith("/new-a-assets/")) return protectedReply(request, 401, {error:"refresh_required"});
          return protectedReply(request, 200, '<!doctype html><html lang="ja" data-auth-recovery><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Discord認証確認</title><script src="/auth/guard.js" defer></script></head><body>Discord認証を確認しています。</body></html>', false);
        }
        if (identity.reason || !identity.subject) return protectedReply(request, identity.reason === "login_required" ? 401 : 503, {error:"authentication_unavailable"});
        const ownerContext = {
          ownerAuthorized: identity.subject === env.CLOUD_OWNER_DISCORD_ID?.trim(),
          roleAuthorized: identity.discord_authorized === true,
          current: true,
          subject: identity.subject,
        };
        const response = await newACloudRoute(request, env, ownerContext);
        await observeOwnerResponse(request, response, ownerContext, operationalBuild, env.CLOUD_VERSION_METADATA);
        return response;
      } catch { return protectedReply(request, 503, {error:"authentication_unavailable"}); }
    }
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
