// The OAuth/session/role implementation remains byte-identical in the synced
// shared module. This wrapper only lets the beta's mode pages use the same gate.
import sharedGate from "./shared-report-gate";

const MODE_PAGE_RE = /^\/weak_early_beta_(?:silence|dive|shadow|fusion|balance)\.html$/;
type SharedRequest = Parameters<typeof sharedGate.fetch>[0];

export default {
  async fetch(request: SharedRequest, env: Env): Promise<Response> {
    const pathname = new URL(request.url).pathname;
    if (MODE_PAGE_RE.test(pathname)) {
      const modeEnv = { ...env, REPORT_ASSET_PATH: pathname } as unknown as Env;
      return sharedGate.fetch(request, modeEnv);
    }
    return sharedGate.fetch(request, env);
  },
};
