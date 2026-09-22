// The OAuth/session/role implementation remains byte-identical in the synced
// shared module. This wrapper only lets the beta's mode pages use the same gate.
import sharedGate from "./shared-report-gate";

const MODE_PAGE_RE = /^\/weak_early_beta_(?:analytics|silence|dive|shadow|fusion|balance|guide)\.html$/;
const BETA_SCRIPT_RE = /^\/weak-early-beta-(?:interactions|theme-init)\.js$/;
type SharedRequest = Parameters<typeof sharedGate.fetch>[0];

export default {
  async fetch(request: SharedRequest, env: Env): Promise<Response> {
    const pathname = new URL(request.url).pathname;
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
      const modeEnv = { ...env, REPORT_ASSET_PATH: pathname } as unknown as Env;
      return sharedGate.fetch(request, modeEnv);
    }
    return sharedGate.fetch(request, env);
  },
};
