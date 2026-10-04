import { isObject, type MembershipDecision } from "./cloud-membership";
import { personalPreparationConfigured, registrationConfigured, validateSubscription, type PushConfig } from "./cloud-web-push";
type Environment = PushConfig & { CLOUD_DB?: D1Database };
type Dependencies = { memberId: string; roleAuthorized: boolean; membership: () => Promise<MembershipDecision> };
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: {
  "cache-control": "private, no-store", vary: "Cookie", "x-content-type-options": "nosniff",
  "content-security-policy": "default-src 'none'; frame-ancestors 'none'", "x-robots-tag": "noindex, nofollow, noarchive",
} });
export async function endpointHash(endpoint: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(endpoint));
  return Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, "0")).join("");
}
export async function pushApi(request: Request, env: Environment, context: Dependencies): Promise<Response> {
  const db = env.CLOUD_DB;
  if (!db) return json({ ok: false, reason: "storage_unavailable" }, 503);
  const path = new URL(request.url).pathname;
  // A separately approved personal-test configuration must not open device
  // registration for other paid members. Revocation remains available to owners.
  const personalMemberAllowed = env.CLOUD_PUSH_MODE !== "personal_test" ||
    (!!env.CLOUD_PUSH_TEST_MEMBER_ID && context.memberId === env.CLOUD_PUSH_TEST_MEMBER_ID);
  if (path === "/api/cloud/push-config") {
    const membership = context.roleAuthorized ? await context.membership() : { status: "free", reason: "discord_role_required" };
    const ready = personalMemberAllowed && registrationConfigured(env) && membership.status === "paid";
    const preparation = personalMemberAllowed && personalPreparationConfigured(env) && membership.status === "paid";
    const rows = await db.prepare(`SELECT s.subscription_id, m.endpoint_hash FROM cloud_push_subscriptions s
      JOIN cloud_push_subscription_metadata m ON m.subscription_id = s.subscription_id
      WHERE s.member_id = ? AND s.revoked_at IS NULL ORDER BY s.opted_in_at DESC LIMIT 50`)
      .bind(context.memberId).all<{ subscription_id: string; endpoint_hash: string }>();
    if (!rows.success) throw new Error("subscription_read_failed");
    const testReady = ready && env.CLOUD_PUSH_MODE === "personal_test" && /^[A-Za-z0-9_-]{16,64}$/.test(env.CLOUD_PUSH_TEST_RUN_ID ?? "") &&
      (rows.results ?? []).some(device => device.subscription_id === env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID);
    return json({ ok: true, registration_available: ready, preparation_available: preparation, delivery_available: false,
      personal_test_available: testReady, ...(testReady ? { personal_test_subscription_id: env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID } : {}),
      reason: ready ? "device_registration_only" : "push_unavailable", membership,
      ...(ready || preparation ? { public_key: env.CLOUD_VAPID_PUBLIC_KEY,
        allowed_origins: (env.CLOUD_PUSH_ALLOWED_ORIGINS ?? "").split(",").map(value => value.trim()).filter(Boolean) } : {}), devices: rows.results ?? [] });
  }
  let input: unknown;
  try {
    if (!(request.headers.get("content-type") ?? "").startsWith("application/json")) throw new Error("json_required");
    const text = await request.text(); if (text.length > 4096) throw new Error("request_too_large");
    input = JSON.parse(text);
  } catch { return json({ ok: false, reason: "invalid_request" }, 400); }
  if (path === "/api/cloud/push-subscriptions/device") {
    if (!isObject(input) || Object.keys(input).join(",") !== "subscription_id" || typeof input.subscription_id !== "string" || !/^[0-9a-f-]{36}$/.test(input.subscription_id)) return json({ ok: false, reason: "invalid_request" }, 400);
    const owned = await db.prepare("SELECT revoked_at FROM cloud_push_subscriptions WHERE member_id = ? AND subscription_id = ?")
      .bind(context.memberId, input.subscription_id).first<{ revoked_at: string | null }>();
    if (!owned) return json({ ok: false, reason: "device_unavailable" }, 404);
    if (owned.revoked_at) return json({ ok: true, device_revoked: true, delivery_available: false });
    // Revocation is permitted after expiry and always scoped to the session ID.
    const result = await db.prepare("UPDATE cloud_push_subscriptions SET revoked_at = ? WHERE member_id = ? AND subscription_id = ? AND revoked_at IS NULL")
      .bind(new Date().toISOString(), context.memberId, input.subscription_id).run();
    if (!result.success || result.meta.changes !== 1) throw new Error("revocation_failed");
    return json({ ok: true, device_revoked: true, delivery_available: false });
  }
  if (!registrationConfigured(env)) return json({ ok: false, reason: "registration_disabled" }, 503);
  if (!personalMemberAllowed) return json({ ok: false, reason: "personal_test_member_required" }, 403);
  if (!context.roleAuthorized || (await context.membership()).status !== "paid") return json({ ok: false, reason: "paid_membership_required" }, 403);
  if (!isObject(input) || Object.keys(input).sort().join(",") !== "opt_in,subscription" || input.opt_in !== true) return json({ ok: false, reason: "explicit_opt_in_required" }, 400);
  let subscription;
  try { subscription = await validateSubscription(input.subscription, env); }
  catch { return json({ ok: false, reason: "invalid_subscription" }, 400); }
  const existing = await db.prepare("SELECT subscription_id, member_id FROM cloud_push_subscriptions WHERE endpoint = ?")
    .bind(subscription.endpoint).first<{ subscription_id: string; member_id: string }>();
  // Never move a browser subscription from another Discord account.
  if (existing && existing.member_id !== context.memberId) return json({ ok: false, reason: "subscription_unavailable" }, 409);
  const id = existing?.subscription_id ?? crypto.randomUUID();
  const now = new Date().toISOString();
  const results = await db.batch([
    db.prepare(`INSERT INTO cloud_push_subscriptions (subscription_id, member_id, endpoint, p256dh, auth, opted_in_at, revoked_at)
      VALUES (?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(subscription_id) DO UPDATE SET p256dh = excluded.p256dh,
      auth = excluded.auth, opted_in_at = excluded.opted_in_at, revoked_at = NULL
      WHERE cloud_push_subscriptions.member_id = excluded.member_id AND cloud_push_subscriptions.endpoint = excluded.endpoint`)
      .bind(id, context.memberId, subscription.endpoint, subscription.p256dh, subscription.auth, now),
    db.prepare(`INSERT INTO cloud_push_subscription_metadata (subscription_id, endpoint_hash, vapid_public_key, expires_at_ms, registered_at)
      VALUES (?, ?, ?, ?, ?) ON CONFLICT(subscription_id) DO UPDATE SET endpoint_hash = excluded.endpoint_hash,
      vapid_public_key = excluded.vapid_public_key, expires_at_ms = excluded.expires_at_ms, registered_at = excluded.registered_at`)
      .bind(id, await endpointHash(subscription.endpoint), env.CLOUD_VAPID_PUBLIC_KEY,
        isObject(input.subscription) ? input.subscription.expirationTime ?? null : null, now),
  ]);
  if (results.some(row => !row.success) || results[0].meta.changes !== 1) throw new Error("subscription_save_failed");
  // No preference flag is enabled by device registration.
  return json({ ok: true, subscription_id: id, delivery_available: false, reason: "device_registration_only" });
}
