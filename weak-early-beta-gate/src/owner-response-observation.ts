import type { OperationalBuild } from "./operational-readback";
import type { TrustedOwnerContext } from "./new-a-cloud";

const NORMAL_ORIGIN = "https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev";
const OWNER_DOCUMENT = "/weak_early_beta_latest.html";
const OWNER_ACCESS = "/api/cloud/new-a-finite/access";
const VERSION_ID = /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const UTC_TIMESTAMP = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/;
type VersionMetadata = { id?: string; tag?: string; timestamp?: string };
const ACCESS_BODY_LIMIT = 256;
const EXPECTED_ACCESS_RESULT = { authorized: true, strategy: "A_BASE" } as const;

async function readAccessContract(response: Response): Promise<boolean> {
  const size = response.headers.get("content-length");
  if (size !== null && (!/^\d+$/.test(size) || Number(size) > ACCESS_BODY_LIMIT)) return false;
  const reader = response.clone().body?.getReader();
  if (!reader) return false;
  const buffer = new Uint8Array(ACCESS_BODY_LIMIT);
  let used = 0;
  const check = async () => {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      if (chunk.value.byteLength > ACCESS_BODY_LIMIT - used) return false;
      buffer.set(chunk.value, used);
      used += chunk.value.byteLength;
    }
    const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
    const body: unknown = JSON.parse(decoder.decode(buffer.subarray(0, used)));
    if (!body || typeof body !== "object" || Array.isArray(body)) return false;
    const data = body as Record<string, unknown>;
    return Object.keys(data).length === 2 && Object.hasOwn(data, "authorized") &&
      Object.hasOwn(data, "strategy") && data.authorized === EXPECTED_ACCESS_RESULT.authorized &&
      data.strategy === EXPECTED_ACCESS_RESULT.strategy;
  };
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const timeout = new Promise<false>(resolve => { timer = setTimeout(() => resolve(false), 100); });
    return await Promise.race([check(), timeout]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
    // The clone shares a tee with the normal response. Waiting for cancellation
    // could wait for the reader of the normal response, which has not started yet.
    void reader.cancel().catch(() => {});
  }
}

// A candidate audit event for the operator's provider-owned log stream. This
// deliberately exports no evidence via the HTTP response and makes no decision
// about continuing acceptance. A provider-observed event is necessary before a
// trusted host can use it. Local/test stdout is not production evidence.
export async function observeOwnerResponse(
  request: Request,
  response: Response,
  context: TrustedOwnerContext,
  build: OperationalBuild,
  version: VersionMetadata | undefined,
): Promise<void> {
  try {
    if (request.method !== "GET" || response.status !== 200 || !context.ownerAuthorized ||
        !context.roleAuthorized || !context.current || !context.subject) return;
    const url = new URL(request.url);
    if (url.origin !== NORMAL_ORIGIN || url.search || url.hash ||
        (url.pathname !== OWNER_DOCUMENT && url.pathname !== OWNER_ACCESS)) return;
    for (const header of request.headers.keys()) {
      if (/(?:version|preview|override)/i.test(header) || header === "x-forwarded-host" ||
          header === "authorization") return;
    }
    const contentType = url.pathname === OWNER_DOCUMENT ? "text/html" : "application/json";
    if (response.headers.get("content-type")?.split(";", 1)[0] !== contentType) return;
    if (build.target.worker !== "tentei-kyokuchi-cloud" ||
        !/^[a-f0-9]{40}$/.test(build.source_commit) ||
        !/^[a-f0-9]{64}$/.test(build.build_input_sha256) ||
        !version?.id || !VERSION_ID.test(version.id) || version.tag !== build.source_commit ||
        !version.timestamp || !UTC_TIMESTAMP.test(version.timestamp) ||
        !Number.isFinite(Date.parse(version.timestamp)) || Date.parse(version.timestamp) > Date.now()) return;
    const versionId = version.id;
    const versionTimestamp = version.timestamp;
    const checksApi = url.pathname === OWNER_ACCESS;
    if (checksApi && !(await readAccessContract(response))) return;
    if (version.id !== versionId || version.tag !== build.source_commit || version.timestamp !== versionTimestamp) return;

    // Status comes from the existing successful route. Never log response bodies,
    // cookies, account identifiers, request URLs/headers, or tokens. The only API
    // fields emitted are these two fixed literals after the strict contract check.
    console.log({
      operation: "cloud_owner_response_observed",
      schema: "NEW_A_PROTECTED_OWNER_RESPONSE_V1",
      source_commit: build.source_commit,
      build_input_sha256: build.build_input_sha256,
      worker: build.target.worker,
      version_id: versionId,
      version_timestamp: versionTimestamp,
      route: url.pathname,
      status: response.status,
      strategy: "A_BASE",
      ...(checksApi ? { verified_access_contract: EXPECTED_ACCESS_RESULT } : {}),
    });
  } catch {
    // Instrumentation is optional and must not modify the normal response.
  }
}
