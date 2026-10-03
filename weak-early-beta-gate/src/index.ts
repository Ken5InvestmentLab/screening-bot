// The OAuth/session/role implementation remains byte-identical in the synced
// shared module. This wrapper only lets the beta's mode pages use the same gate.
import sharedGate from "./shared-report-gate";
import { cloudApi, currentMembership, type CloudEnv } from "./cloud-api";

const MODE_PAGE_RE = /^\/weak_early_beta_(?:analytics|silence|dive|shadow|fusion|balance|guide)\.html$/;
const BETA_SCRIPT_RE = /^\/weak-early-beta-(?:interactions|theme-init)\.js$/;
type SharedRequest = Parameters<typeof sharedGate.fetch>[0];

export default {
  async fetch(request: SharedRequest, env: CloudEnv): Promise<Response> {
    const pathname = new URL(request.url).pathname;
    if (pathname.startsWith("/api/cloud/")) return cloudApi(request, env);
    // A Discord role alone never unlocks Cloud's unreleased identifiers.
    // Missing configuration, unlinked users and provider failures all use free.
    const protectedEnv = {
      ...env,
      REPORT_ACCESS_CHECK: async (subject: string) => (await currentMembership(env, subject)).status === "paid",
      REPORT_ACCESS_DENIED_MESSAGE: "有効なWhop有料会員との連携を確認できません。会員資格を確認してからもう一度開いてください。",
    };
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
          "cache-control": "public, max-age=300",
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
