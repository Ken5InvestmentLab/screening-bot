import { reportIdentity, reportSessionIdentity } from "./shared-report-gate";
import { pushApi } from "./cloud-push";
import { dispatchPersonalDeviceTest } from "./cloud-push-dispatch";
import { evaluateNestedMembership } from "./cloud-whop-adapter";
import { isNewAOwnerPushMode, type PushConfig } from "./cloud-web-push";
import {
  DEFAULT_PREFERENCES, WHOP_API_VERSION, evaluateMembership, evaluateNotification,
  isObject, validatePreferences, notificationEligible,
  type MembershipDecision, type MembershipPolicy, type NotificationEvent,
  type Preferences, type VerifiedMemberLink,
} from "./cloud-membership";

export type CloudEnv = Env & PushConfig & {
  CLOUD_OWNER_ONLY_ENABLED?: string;
  CLOUD_OWNER_DISCORD_ID?: string;
  CLOUD_DB?: D1Database;
  CLOUD_ROLE_AUTHORITY?: DurableObjectNamespace;
  WHOP_API_KEY?: string;
  WHOP_ACCOUNT_ID?: string;
  WHOP_PRODUCT_IDS?: string;
  WHOP_PAID_PLAN_IDS?: string;
  WHOP_ONE_TIME_PLAN_IDS?: string;
  WHOP_RESPONSE_SCHEMA?: string;
  CLOUD_PUSH_MEMBERSHIP_POLICY?: string;
  CLOUD_PUSH_AUDIENCE?: string;
  SESSION_SECRET?: string;
  DISCORD_CLIENT_ID?: string;
  CLOUD_ROLE_INITIAL_WAIT?: string;
};
const list = (value?: string): string[] => (value ?? "").split(",").map(x => x.trim()).filter(Boolean);
// Bound each request's database work. A persistent per-member cursor visits the
// remaining candidates on subsequent calls; held/suppressed rows return next cycle.
const DRY_RUN_PAGE_SIZE = 20;
type ScanProgress = {
  after_available_at: string;
  after_source_event_key: string;
  cycle_cutoff_at: string;
  version: number;
};
type CandidateRow = {
  source_event_key: string;
  event_json: string;
  source_ledger_revision: string;
  available_at: string;
};
export async function cloudMemberId(discordSubject: string): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`cloud-member:${discordSubject}`));
  return `cloud_${Array.from(new Uint8Array(hash), n => n.toString(16).padStart(2, "0")).join("")}`;
}

export async function currentMembership(env: CloudEnv, subject: string, freshRoleAuthorized?: boolean): Promise<MembershipDecision> {
  const unavailable = (reason: string): MembershipDecision => ({ status: "unavailable", reason, checked_at: new Date().toISOString() });
  // Explicitly approved alternative policy. This is never an error fallback from
  // Whop: fresh Discord authorization is the selected source of paid eligibility.
  if (env.CLOUD_PUSH_MEMBERSHIP_POLICY === "whop_managed_discord_role") {
    if (!subject || freshRoleAuthorized === undefined) return unavailable("fresh_managed_role_required");
    return { status: freshRoleAuthorized ? "paid" : "free", reason: freshRoleAuthorized ? "verified_whop_managed_discord_role" : "managed_role_revoked",
      checked_at: new Date().toISOString() };
  }
  if (env.CLOUD_PUSH_MEMBERSHIP_POLICY && env.CLOUD_PUSH_MEMBERSHIP_POLICY !== "whop_api") return unavailable("unsupported_membership_policy");
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
    const policy: MembershipPolicy = {
      account_id: env.WHOP_ACCOUNT_ID, product_ids: list(env.WHOP_PRODUCT_IDS),
      paid_plan_ids: list(env.WHOP_PAID_PLAN_IDS), one_time_plan_ids: list(env.WHOP_ONE_TIME_PLAN_IDS),
    };
    if (env.WHOP_RESPONSE_SCHEMA === "nested_v1") {
      // Personal-test minimum: only this operator-verified payment is read.
      // A renewal needs updated evidence; no undocumented membership/user filter
      // or account-wide scan is permitted by this adapter.
      return evaluateNestedMembership(membership, await read(`payments/${link.payment_id}`), link, policy);
    }
    if (env.WHOP_RESPONSE_SCHEMA && env.WHOP_RESPONSE_SCHEMA !== "legacy_fixture") return unavailable("unsupported_provider_schema");
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
  return row ? validatePreferences(JSON.parse(row.preferences_json), true) : validatePreferences(DEFAULT_PREFERENCES);
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
    "/api/cloud/push-subscriptions": ["POST"],
    "/api/cloud/push-config": ["GET"],
    "/api/cloud/push-subscriptions/device": ["DELETE"],
    "/api/cloud/notifications/dry-run": ["POST"],
    "/api/cloud/notifications/personal-test": ["POST"],
  };
  if (!methods[path]) return json({ ok: false, reason: "not_found" }, 404);
  if (!methods[path].includes(request.method)) return json({ ok: false, reason: "method_not_allowed" }, 405);
  if (request.method !== "GET" && request.headers.get("origin") !== new URL(request.url).origin) {
    return json({ ok: false, reason: "same_origin_required" }, 403);
  }
  try {
    const managedRoles = env.CLOUD_PUSH_MEMBERSHIP_POLICY === "whop_managed_discord_role";
    const identity = path === "/api/cloud/notifications/personal-test" || managedRoles
      ? await reportSessionIdentity(request, env) : await reportIdentity(request, env);
    if (!identity.subject) return json({ ok: false, reason: identity.reason }, identity.reason === "temporarily_unavailable" ? 503 : 401);
    const ownerMode = isNewAOwnerPushMode(env.CLOUD_PUSH_MODE);
    const ownerVerified = env.CLOUD_OWNER_ONLY_ENABLED?.trim().toLowerCase() === "true" &&
      /^[0-9]{17,20}$/.test(identity.subject) && identity.subject === env.CLOUD_OWNER_DISCORD_ID?.trim();
    if (ownerMode && (!ownerVerified || !managedRoles || String(env.CLOUD_PUSH_AUDIENCE) !== "paid"))
      return json({ ok: false, reason: "owner_notification_policy_required" }, 403);
    if (ownerMode && path.startsWith("/api/cloud/notifications/"))
      return json({ ok: false, reason: "legacy_notification_path_disabled" }, 403);
    if (!env.CLOUD_DB) return json({ ok: false, reason: "storage_unavailable", delivery_mode: "dry_run" }, 503);
    const memberId = await cloudMemberId(identity.subject);
    const freshMembership = (fresh: Awaited<ReturnType<typeof reportIdentity>>) => {
      if (fresh.subject !== identity.subject) return { status: "unavailable" as const,
        reason: fresh.reason === "login_required" || fresh.reason === "refresh_required" || fresh.reason?.startsWith("discord_role_") ? fresh.reason : "fresh_managed_role_unavailable",
        checked_at: new Date().toISOString() };
      return currentMembership(env, identity.subject!, fresh.discord_authorized);
    };
    if (path === "/api/cloud/notifications/personal-test") {
      let input: unknown;
      try { input = await requestJson(request); } catch { return json({ ok: false, reason: "invalid_request" }, 400); }
      if (!isObject(input) || Object.keys(input).length) return json({ ok: false, reason: "empty_body_required" }, 400);
      const result = await dispatchPersonalDeviceTest(request, env);
      return json({ ok: true, ...result, arrival_confirmed: false });
    }
    if (path === "/api/cloud/push-config" || path === "/api/cloud/push-subscriptions/device" ||
      (path === "/api/cloud/push-subscriptions" && request.method === "POST")) {
      const freshIdentity = request.method === "POST" || (path === "/api/cloud/push-config" && env.CLOUD_PUSH_MEMBERSHIP_POLICY === "whop_managed_discord_role") ? await reportIdentity(request, env, true) : identity;
      return pushApi(request, env, { memberId, ownerVerified, roleAuthorized: freshIdentity.discord_authorized,
        membership: () => Promise.resolve(freshMembership(freshIdentity)) });
    }
    const preferences = await preferencesFor(env.CLOUD_DB, memberId);
    let membership = identity.discord_authorized
      ? await currentMembership(env, identity.subject)
      : { status: "free" as const, reason: "discord_role_required", checked_at: new Date().toISOString() };
    const omitNotificationStatus = request.method === "GET" && path === "/api/cloud/preferences" && new URL(request.url).searchParams.get("notification_status") === "omit";
    if (omitNotificationStatus) {
      // Hidden notification UI only needs the signed owner's saved settings.
      // This opt-out never grants report access or notification qualification.
      membership = { status: "unavailable", reason: "notification_status_not_requested", checked_at: new Date().toISOString() };
    } else if (request.method === "GET" && managedRoles) {
      const fresh = await reportIdentity(request, env, true);
      membership = await freshMembership(fresh);
    }
    if (path === "/api/cloud/preferences") {
      if (request.method === "GET") return json({ ok: true, preferences, membership, notification_eligible: notificationEligible(membership, env.CLOUD_PUSH_AUDIENCE), delivery_mode: "dry_run", persistence: "server" });
      let next: Preferences;
      try {
        const input = await requestJson(request);
        // Hidden notification controls omit this field. Preserve the owner's
        // authoritative opt-ins rather than resetting them from a UI default.
        next = validatePreferences(isObject(input) && !Object.hasOwn(input, "notifications")
          ? { ...input, notifications: preferences.notifications } : input);
      }
      catch { return json({ ok: false, reason: "invalid_preferences" }, 400); }
      // Saving display/trial settings must not re-enable an already saved opt-in
      // or depend on a role lookup. Delivery still always performs a fresh check.
      const enabling = (Object.keys(next.notifications) as (keyof Preferences["notifications"])[])
        .some(kind => next.notifications[kind] && !preferences.notifications[kind]);
      if (enabling && managedRoles) {
        const fresh = await reportIdentity(request, env, true);
        membership = await freshMembership(fresh);
      }
      if (enabling && !notificationEligible(membership, env.CLOUD_PUSH_AUDIENCE)) return json({ ok: false, reason: "notification_qualification_required", membership }, 403);
      const saved = await preferenceStatement(env.CLOUD_DB, memberId, next).run();
      if (!saved.success) throw new Error("preference_save_failed");
      return json({ ok: true, preferences: next, membership, notification_eligible: notificationEligible(membership, env.CLOUD_PUSH_AUDIENCE), delivery_mode: "dry_run", persistence: "server" });
    }
    // Candidates are trusted server-produced canonical observations. This route
    // never accepts a browser-supplied signal, price, identity, or recipient.
    let input: unknown;
    try { input = await requestJson(request); } catch { return json({ ok: false, reason: "invalid_request" }, 400); }
    if (!isObject(input) || Object.keys(input).length) return json({ ok: false, reason: "empty_body_required" }, 400);
    if (managedRoles) membership = await freshMembership(await reportIdentity(request, env, true));
    const now = Date.now();
    const nowIso = new Date(now).toISOString();
    const initialized = await env.CLOUD_DB.prepare(`INSERT OR IGNORE INTO cloud_notification_scan_progress
      (member_id, updated_at) VALUES (?, ?)`).bind(memberId, nowIso).run();
    if (!initialized.success) throw new Error("scan_progress_save_failed");
    const progress = await env.CLOUD_DB.prepare(`SELECT after_available_at, after_source_event_key,
      cycle_cutoff_at, version FROM cloud_notification_scan_progress WHERE member_id = ?`)
      .bind(memberId).first<ScanProgress>();
    if (!progress || !Number.isSafeInteger(progress.version) || progress.version < 0) throw new Error("scan_progress_missing");
    const cutoff = progress.cycle_cutoff_at || nowIso;
    const rows = await env.CLOUD_DB.prepare(
      `SELECT source_event_key, event_json, source_ledger_revision, available_at
       FROM cloud_notification_events WHERE available_at <= ?
       AND (available_at, source_event_key) > (?, ?)
       ORDER BY available_at ASC, source_event_key ASC LIMIT 21`,
    ).bind(cutoff, progress.after_available_at, progress.after_source_event_key).all<CandidateRow>();
    if (!rows.success) throw new Error("candidate_read_failed");
    const candidates = (rows.results ?? []).slice(0, DRY_RUN_PAGE_SIZE);
    const hasMore = (rows.results ?? []).length > DRY_RUN_PAGE_SIZE;
    const results: { status: string; reason: string }[] = [];
    for (const row of candidates) {
      let parsed: unknown;
      try { parsed = JSON.parse(row.event_json); }
      catch {
        results.push({ status: "held", reason: "canonical_event_evidence_required" });
        continue;
      }
      if (!isObject(parsed) || parsed.adapter_version !== "cloud-ledger-v1" ||
        !/^[0-9a-f]{64}$/.test(row.source_ledger_revision) || parsed.source_ledger_revision !== row.source_ledger_revision) {
        results.push({ status: "held", reason: "canonical_event_evidence_required" });
        continue;
      }
      const event = parsed as NotificationEvent;
      let decision: ReturnType<typeof evaluateNotification>;
      try { decision = evaluateNotification(event, preferences, membership, now, env.CLOUD_PUSH_AUDIENCE); }
      catch {
        // One malformed private candidate must not strand every following page.
        results.push({ status: "held", reason: "invalid_candidate_data" });
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
    const last = candidates.at(-1);
    // Advance only after all delivery writes succeeded. Concurrent callers may
    // inspect the same page, but the delivery guard prevents duplicate eligibility
    // and this version comparison prevents a late request from moving us backward.
    const advanced = await env.CLOUD_DB.prepare(`UPDATE cloud_notification_scan_progress
      SET after_available_at = ?, after_source_event_key = ?, cycle_cutoff_at = ?,
      updated_at = ?, version = version + 1 WHERE member_id = ? AND version = ?`)
      .bind(hasMore && last ? last.available_at : "", hasMore && last ? last.source_event_key : "",
        hasMore ? cutoff : "", nowIso, memberId, progress.version).run();
    if (!advanced.success) throw new Error("scan_progress_save_failed");
    // No event IDs, company names, prices, or messages are returned by dry-run.
    return json({ ok: true, delivery_mode: "dry_run", sent: 0, results,
      scan: { processed: candidates.length, page_limit: DRY_RUN_PAGE_SIZE, has_more: hasMore, cycle_complete: !hasMore } });
  } catch {
    return json({ ok: false, reason: "temporarily_unavailable", delivery_mode: "dry_run" }, 503);
  }
}
