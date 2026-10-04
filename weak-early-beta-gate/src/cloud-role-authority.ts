import type { CloudEnv } from "./cloud-api";
import type { ReportRoleDecision } from "./shared-report-gate";
import { DurableObject } from "cloudflare:workers";

const ROLE_LIFETIME_MS = 90000;
const USER_AGENT = "DiscordBot (https://github.com/Ken5InvestmentLab/screening-bot, 1.0)";
type Verified = { status: "paid" | "free"; checkedAt: number; validUntil: number };
type Failure = { reason: string; retryAt: number; scope?: string; replyKind?: string };

// A single account/guild/policy authority is shared by all Cloud isolates/tabs.
// Storage contains decisions/deadlines only, never credentials or provider bodies.
export class CloudRoleAuthority extends DurableObject<CloudEnv> {
  private verified?: Verified;
  private failure?: Failure;
  private running?: Promise<ReportRoleDecision>;
  private ready: Promise<void>;
  constructor(ctx: DurableObjectState, env: CloudEnv) {
    super(ctx, env);
    this.ready = ctx.blockConcurrencyWhile(async () => {
      this.verified = await ctx.storage.get<Verified>("verified");
      this.failure = await ctx.storage.get<Failure>("failure");
    });
  }
  async fetch(request: Request): Promise<Response> {
    if (request.method !== "POST" || new URL(request.url).pathname !== "/check") return new Response(null, { status: 404 });
    const input = await request.json().catch(() => null) as { accessToken?: unknown; holdUntil?: unknown } | null;
    if (typeof input?.accessToken !== "string" || !input.accessToken || input.accessToken.length > 8192) return new Response(null, { status: 400 });
    await this.ready;
    const now = Date.now();
    if (typeof input.holdUntil === "number" && Number.isFinite(input.holdUntil) && input.holdUntil > now && input.holdUntil <= now + 86400000) {
      if (!this.failure || this.failure.retryAt < input.holdUntil) {
        this.failure = { reason: "discord_role_lookup_429", retryAt: input.holdUntil, scope: "user", replyKind: "json" };
        await this.ctx.storage.put("failure", this.failure);
      }
      return Response.json(this.unavailable(this.failure, "inherited_wait"));
    }
    if (this.verified && now < this.verified.validUntil) return Response.json({ ...this.verified, source: "verified" });
    if (this.failure && now < this.failure.retryAt) return Response.json(this.unavailable(this.failure, "waiting"));
    if (this.running) return Response.json({ ...await this.running, source: "joined" });
    const promise = this.lookup(input.accessToken);
    this.running = promise;
    try { return Response.json(await promise); }
    finally { if (this.running === promise) this.running = undefined; }
  }
  private unavailable(failure: Failure, source: string): ReportRoleDecision {
    return { status: "unavailable", reason: failure.reason, retryAfterSeconds: Math.max(1, Math.ceil((failure.retryAt - Date.now()) / 1000)),
      scope: failure.scope, replyKind: failure.replyKind, source };
  }
  private async lookup(accessToken: string): Promise<ReportRoleDecision> {
    const checkedAt = Date.now();
    let failure: Failure = { reason: "discord_role_network_unavailable", retryAt: 0 };
    let httpStatus: number | undefined;
    let observedAt: string | undefined;
    try {
      const response = await fetch(`${this.env.DISCORD_API_BASE ?? "https://discord.com/api"}/users/@me/guilds/${this.env.DISCORD_GUILD_ID}/member`, {
        headers: { authorization: `Bearer ${accessToken}`, "user-agent": USER_AGENT, accept: "application/json" },
        cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000),
      });
      httpStatus = response.status;
      observedAt = new Date().toISOString();
      if (response.ok) {
        const body = await response.json().catch(() => null) as { roles?: unknown } | null;
        if (Array.isArray(body?.roles) && body.roles.every(role => typeof role === "string")) {
          const allowed = (this.env.DISCORD_ALLOWED_ROLE_IDS ?? "").split(",").map(value => value.trim()).filter(Boolean);
          const decision: Verified = { status: body.roles.some(role => allowed.includes(role)) ? "paid" : "free", checkedAt, validUntil: checkedAt + ROLE_LIFETIME_MS };
          await this.ctx.storage.put("verified", decision);
          await this.ctx.storage.delete("failure");
          this.verified = decision; this.failure = undefined;
          console.log(JSON.stringify({ operation: "cloud_role_lookup", action: "upstream", observed_at: observedAt, http_status: httpStatus, result: decision.status }));
          return { ...decision, source: "upstream" };
        }
        failure.reason = "discord_role_response_invalid";
      } else if (response.status === 429) {
        let seconds = Number(response.headers.get("retry-after"));
        if (!(Number.isFinite(seconds) && seconds > 0)) {
          const body = await response.json().catch(() => null) as { retry_after?: unknown } | null;
          seconds = typeof body?.retry_after === "number" ? body.retry_after : 0;
        }
        const scope = response.headers.get("x-ratelimit-scope");
        failure = { reason: "discord_role_lookup_429", retryAt: Date.now() + (Number.isFinite(seconds) && seconds > 0 ? Math.ceil(Math.min(seconds, 86400) * 1000) : 5000),
          scope: scope && ["user", "global", "shared"].includes(scope) ? scope : undefined,
          replyKind: response.headers.get("content-type")?.includes("application/json") ? "json" : "other" };
      } else failure.reason = `discord_role_lookup_${response.status}`;
    } catch { /* Provider bodies and credentials must never reach logs. */ }
    if (failure.retryAt === 0) failure.retryAt = Date.now() + 5000;
    // No positive decision survives its original deadline or gets extended by an error.
    await this.ctx.storage.delete("verified"); this.verified = undefined;
    await this.ctx.storage.put("failure", failure); this.failure = failure;
    const decision = this.unavailable(failure, "upstream");
    console.log(JSON.stringify({ operation: "cloud_role_lookup", action: "upstream", observed_at: observedAt, http_status: httpStatus, result: "unavailable",
      reason: decision.reason, retry_at: new Date(failure.retryAt).toISOString(), retry_after_seconds: decision.retryAfterSeconds, rate_limit_scope: decision.scope, rate_limit_response: decision.replyKind }));
    return decision;
  }
}

export async function cloudReportRole(env: CloudEnv, subject: string, accessToken: string, route: string): Promise<ReportRoleDecision> {
  if (!env.CLOUD_ROLE_AUTHORITY || !env.SESSION_SECRET) return { status: "unavailable", reason: "cloud_role_authority_unavailable", retryAfterSeconds: 5 };
  try {
    const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(env.SESSION_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const policy = JSON.stringify(["cloud-role-v1", env.DISCORD_CLIENT_ID, env.DISCORD_GUILD_ID, (env.DISCORD_ALLOWED_ROLE_IDS ?? "").split(",").map(v=>v.trim()).sort(), subject]);
    const digest = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(policy)));
    const name = Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("");
    const stub = env.CLOUD_ROLE_AUTHORITY.get(env.CLOUD_ROLE_AUTHORITY.idFromName(name));
    let holdUntil: number | undefined;
    if (env.CLOUD_ROLE_INITIAL_WAIT) {
      const wait = JSON.parse(env.CLOUD_ROLE_INITIAL_WAIT) as { member_id?: string; until?: string };
      const memberDigest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`cloud-member:${subject}`)));
      const memberId = `cloud_${Array.from(memberDigest, byte => byte.toString(16).padStart(2, "0")).join("")}`;
      if (wait.member_id === memberId) {
        const deadline = Date.parse(wait.until ?? "");
        if (!Number.isFinite(deadline) || deadline > Date.now() + 86400000) throw new Error("invalid_wait_record");
        if (deadline > Date.now()) holdUntil = deadline;
      }
    }
    const response = await stub.fetch("https://cloud-role-authority.invalid/check", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ accessToken, holdUntil }) });
    if (!response.ok) throw new Error("authority_unavailable");
    const result = await response.json() as ReportRoleDecision;
    if (!["paid", "free", "unavailable"].includes(result.status)) throw new Error("authority_invalid");
    if (result.status !== "unavailable" && (!Number.isFinite(result.validUntil) || !Number.isFinite(result.checkedAt) || result.validUntil! > result.checkedAt! + ROLE_LIFETIME_MS || result.validUntil! <= Date.now())) throw new Error("authority_expired");
    console.log(JSON.stringify({ operation: "cloud_role_access", route: route.startsWith("/weak_early_beta_data_") ? "/full-data" : route,
      result: result.status, source: result.source, valid_until: result.validUntil, reason: result.reason, retry_after_seconds: result.retryAfterSeconds }));
    return result;
  } catch { return { status: "unavailable", reason: "cloud_role_authority_unavailable", retryAfterSeconds: 5 }; }
}
