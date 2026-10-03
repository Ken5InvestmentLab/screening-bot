import { reportIdentity } from "./shared-report-gate";
import {
  DEFAULT_PREFERENCES, WHOP_API_VERSION, evaluateMembership, evaluateNotification,
  isObject, validatePreferences,
  type MembershipDecision, type MembershipPolicy, type NotificationEvent,
  type Preferences, type VerifiedMemberLink,
} from "./cloud-membership";

export type CloudEnv = Env & {
  CLOUD_DB?: D1Database;
  WHOP_API_KEY?: string;
  WHOP_ACCOUNT_ID?: string;
  WHOP_PRODUCT_IDS?: string;
  WHOP_PAID_PLAN_IDS?: string;
  WHOP_ONE_TIME_PLAN_IDS?: string;
  SESSION_SECRET?: string;
};
const list = (value?: string): string[] => (value ?? "").split(",").map(x => x.trim()).filter(Boolean);
export async function cloudMemberId(discordSubject: string): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`cloud-member:${discordSubject}`));
  return `cloud_${Array.from(new Uint8Array(hash), n => n.toString(16).padStart(2, "0")).join("")}`;
}

export async function currentMembership(env: CloudEnv, subject: string): Promise<MembershipDecision> {
  const unavailable = (reason: string): MembershipDecision => ({ status: "unavailable", reason, checked_at: new Date().toISOString() });
  if (!env.CLOUD_DB || !env.WHOP_API_KEY || !env.WHOP_ACCOUNT_ID || !list(env.WHOP_PRODUCT_IDS).length || !list(env.WHOP_PAID_PLAN_IDS).length) {
    return unavailable("membership_not_configured");
  }
  try {
    const memberId = await cloudMemberId(subject);
    const link = await env.CLOUD_DB.prepare(
      "SELECT * FROM cloud_member_links WHERE member_id = ? AND discord_user_id = ?",
    ).bind(memberId, subject).first<VerifiedMemberLink>();
    if (!link) return { status: "unverified", reason: "identity_link_required", checked_at: new Date().toISOString() };
    if (link.environment !== "live" || link.revoked_at) return { status: "free", reason: link.revoked_at ? "link_revoked" : "test_account", checked_at: new Date().toISOString() };
    // IDs come only from a verified server-side link, never a browser field.
    if (!/^mem_[A-Za-z0-9]+$/.test(link.membership_id) || !/^pay_[A-Za-z0-9]+$/.test(link.payment_id)) return unavailable("invalid_identity_link");
    const read = async (resource: string): Promise<unknown> => {
      const response = await fetch(`https://api.whop.com/api/v1/${resource}`, {
        headers: { authorization: `Bearer ${env.WHOP_API_KEY}`, "Api-Version-Date": WHOP_API_VERSION },
        redirect: "error", signal: AbortSignal.timeout(8000), cache: "no-store",
      });
      if (!response.ok) throw new Error("membership_lookup_failed");
      return response.json();
    };
    const membership = await read(`memberships/${link.membership_id}`);
    if (!isObject(membership)) return unavailable("invalid_provider_response");
    // Follow renewals instead of pinning eligibility to the first payment in the
    // identity-link evidence. Scope every query and recheck returned ownership.
    const paymentQuery = new URLSearchParams({
      account_id: env.WHOP_ACCOUNT_ID, membership_id: link.membership_id,
      user_id: link.whop_user_id, status: "paid", order: "paid_at", direction: "desc", first: "100",
    });
    const payments = await read(`payments?${paymentQuery}`);
    if (!isObject(payments) || !Array.isArray(payments.data)) return unavailable("invalid_provider_response");
    const paid = payments.data.find((row: unknown) => isObject(row) && row.membership_id === link.membership_id &&
      row.account_id === env.WHOP_ACCOUNT_ID && isObject(row.user) && row.user.id === link.whop_user_id &&
      row.status === "paid" && typeof row.id === "string" && /^pay_[A-Za-z0-9]+$/.test(row.id));
    if (!isObject(paid)) return { status: "unverified", reason: "current_period_payment_required", checked_at: new Date().toISOString() };
    const payment = await read(`payments/${paid.id}`);
    const policy: MembershipPolicy = {
      account_id: env.WHOP_ACCOUNT_ID, product_ids: list(env.WHOP_PRODUCT_IDS),
      paid_plan_ids: list(env.WHOP_PAID_PLAN_IDS), one_time_plan_ids: list(env.WHOP_ONE_TIME_PLAN_IDS),
    };
    return evaluateMembership(membership, payment, { ...link, payment_id: String(paid.id) }, policy);
  } catch {
    // No role-cache grace, previous positive result, or provider-error body leaks.
    return unavailable("membership_verification_unavailable");
  }
}

function json(body: unknown, status = 200): Response {
  return Response.json(body, { status, headers: {
    "cache-control": "private, no-store", "x-content-type-options": "nosniff",
    "x-robots-tag": "noindex, nofollow, noarchive", "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "vary": "Cookie",
  } });
}
async function preferencesFor(db: D1Database, memberId: string): Promise<Preferences> {
  const row = await db.prepare("SELECT preferences_json FROM cloud_member_preferences WHERE member_id = ?")
    .bind(memberId).first<{ preferences_json: string }>();
  return row ? validatePreferences(JSON.parse(row.preferences_json)) : validatePreferences(DEFAULT_PREFERENCES);
}
function preferenceStatement(db: D1Database, memberId: string, preferences: Preferences): D1PreparedStatement {
  return db.prepare(`INSERT INTO cloud_member_preferences (member_id, preferences_json, updated_at)
    VALUES (?, ?, ?) ON CONFLICT(member_id) DO UPDATE SET
    preferences_json = excluded.preferences_json, updated_at = excluded.updated_at`)
    .bind(memberId, JSON.stringify(preferences), new Date().toISOString());
}
async function requestJson(request: Request): Promise<unknown> {
  if (!(request.headers.get("content-type") ?? "").startsWith("application/json")) throw new Error("json_required");
  const text = await request.text();
  if (text.length > 4096) throw new Error("request_too_large");
  return JSON.parse(text);
}

export async function cloudApi(request: Request, env: CloudEnv): Promise<Response> {
  const path = new URL(request.url).pathname;
  const methods: Record<string, string[]> = {
    "/api/cloud/preferences": ["GET", "PUT"],
    "/api/cloud/push-subscriptions": ["DELETE"],
    "/api/cloud/notifications/dry-run": ["POST"],
  };
  if (!methods[path]) return json({ ok: false, reason: "not_found" }, 404);
  if (!methods[path].includes(request.method)) return json({ ok: false, reason: "method_not_allowed" }, 405);
  if (request.method !== "GET" && request.headers.get("origin") !== new URL(request.url).origin) {
    return json({ ok: false, reason: "same_origin_required" }, 403);
  }
  try {
    const identity = await reportIdentity(request, env);
    if (!identity.subject) return json({ ok: false, reason: identity.reason }, identity.reason === "temporarily_unavailable" ? 503 : 401);
    if (!env.CLOUD_DB) return json({ ok: false, reason: "storage_unavailable", delivery_mode: "dry_run" }, 503);
    const memberId = await cloudMemberId(identity.subject);
    const preferences = await preferencesFor(env.CLOUD_DB, memberId);
    const membership = identity.discord_authorized
      ? await currentMembership(env, identity.subject)
      : { status: "free" as const, reason: "discord_role_required", checked_at: new Date().toISOString() };
    if (path === "/api/cloud/preferences") {
      if (request.method === "GET") return json({ ok: true, preferences, membership, delivery_mode: "dry_run", persistence: "server" });
      let next: Preferences;
      try { next = validatePreferences(await requestJson(request)); }
      catch { return json({ ok: false, reason: "invalid_preferences" }, 400); }
      const enabling = Object.values(next.notifications).some(Boolean);
      if (enabling && membership.status !== "paid") return json({ ok: false, reason: "paid_membership_required", membership }, 403);
      const saved = await preferenceStatement(env.CLOUD_DB, memberId, next).run();
      if (!saved.success) throw new Error("preference_save_failed");
      return json({ ok: true, preferences: next, membership, delivery_mode: "dry_run", persistence: "server" });
    }
    if (path === "/api/cloud/push-subscriptions") {
      const next = { ...preferences, notifications: { new_detection: false, reminder: false, result: false } };
      const saved = await env.CLOUD_DB.batch([
        preferenceStatement(env.CLOUD_DB, memberId, next),
        env.CLOUD_DB.prepare("UPDATE cloud_push_subscriptions SET revoked_at = ? WHERE member_id = ? AND revoked_at IS NULL")
          .bind(new Date().toISOString(), memberId),
      ]);
      if (saved.some(row => !row.success)) throw new Error("unsubscribe_failed");
      return json({ ok: true, preferences: next, delivery_mode: "dry_run", unsubscribed: true });
    }
    // Candidates are trusted server-produced canonical observations. This route
    // never accepts a browser-supplied signal, price, identity, or recipient.
    let input: unknown;
    try { input = await requestJson(request); } catch { return json({ ok: false, reason: "invalid_request" }, 400); }
    if (!isObject(input) || Object.keys(input).length) return json({ ok: false, reason: "empty_body_required" }, 400);
    const now = Date.now();
    const rows = await env.CLOUD_DB.prepare(
      "SELECT event_json, source_ledger_revision FROM cloud_notification_events WHERE available_at <= ? ORDER BY available_at DESC LIMIT 100",
    ).bind(new Date(now).toISOString()).all<{ event_json: string; source_ledger_revision: string }>();
    const results: { status: string; reason: string }[] = [];
    for (const row of rows.results ?? []) {
      const parsed: unknown = JSON.parse(row.event_json);
      if (!isObject(parsed) || parsed.adapter_version !== "cloud-ledger-v1" ||
        !/^[0-9a-f]{64}$/.test(row.source_ledger_revision) || parsed.source_ledger_revision !== row.source_ledger_revision) {
        results.push({ status: "held", reason: "canonical_event_evidence_required" });
        continue;
      }
      const event = parsed as NotificationEvent;
      const decision = evaluateNotification(event, preferences, membership, now);
      const existing = await env.CLOUD_DB.prepare(
        "SELECT status FROM cloud_notification_deliveries WHERE member_id = ? AND event_key = ?",
      ).bind(memberId, decision.event_key).first<{ status: string }>();
      if (existing?.status === "dry_run_eligible" || existing?.status === "sent") {
        results.push({ status: "suppressed", reason: "duplicate_event" });
        continue;
      }
      const state = decision.status === "would_send" ? "dry_run_eligible" : decision.status;
      const receipt = await env.CLOUD_DB.prepare(`INSERT INTO cloud_notification_deliveries
        (member_id, event_key, status, reason, checked_at, membership_checked_at, attempts)
        VALUES (?, ?, ?, ?, ?, ?, 1) ON CONFLICT(member_id, event_key) DO UPDATE SET
        status = excluded.status, reason = excluded.reason, checked_at = excluded.checked_at,
        membership_checked_at = excluded.membership_checked_at, attempts = attempts + 1
        WHERE cloud_notification_deliveries.status NOT IN ('dry_run_eligible', 'sent')`)
        .bind(memberId, decision.event_key, state, decision.reason, new Date(now).toISOString(), membership.checked_at).run();
      if (!receipt.success) throw new Error("delivery_receipt_save_failed");
      results.push(receipt.meta.changes === 0 ? { status: "suppressed", reason: "duplicate_event" } : { status: decision.status, reason: decision.reason });
    }
    // No event IDs, company names, prices, or messages are returned by dry-run.
    return json({ ok: true, delivery_mode: "dry_run", sent: 0, results });
  } catch {
    return json({ ok: false, reason: "temporarily_unavailable", delivery_mode: "dry_run" }, 503);
  }
}
