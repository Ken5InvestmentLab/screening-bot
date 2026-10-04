// Canonical dispatch is internal. The HTTP route invokes only the fixed-device
// test below, with no browser-supplied event, recipient, or message.
import { reportIdentity, reportSessionIdentity } from "./shared-report-gate";
import { cloudMemberId, currentMembership, type CloudEnv } from "./cloud-api";
import { evaluateNotification, isObject, validatePreferences, DEFAULT_PREFERENCES, type NotificationEvent } from "./cloud-membership";
import { sendPersonalPush, type SendResult, type PushSubscription, type encryptPushPayload } from "./cloud-web-push";
type Device = PushSubscription & { member_id: string; subscription_id: string; revoked_at: string | null; vapid_public_key: string; expires_at_ms: number | null };
type Identity = { subject?: string; discord_authorized: boolean };
export async function dispatchPersonalDeviceTest(request: Request, env: CloudEnv,
  transport: typeof fetch = fetch, fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<SendResult | { status: "held" | "suppressed"; reason: string }> {
  const db = env.CLOUD_DB;
  if (!db || String(env.CLOUD_PUSH_MODE) !== "personal_test" || !env.CLOUD_PUSH_TEST_MEMBER_ID || !env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID ||
      !/^[A-Za-z0-9_-]{16,64}$/.test(env.CLOUD_PUSH_TEST_RUN_ID ?? "")) return { status: "disabled", reason: "personal_test_not_enabled" };
  const identity = await reportSessionIdentity(request, env);
  if (!identity.subject) return { status: "held", reason: "authenticated_session_required" };
  const memberId = await cloudMemberId(identity.subject);
  if (memberId !== env.CLOUD_PUSH_TEST_MEMBER_ID) return { status: "disabled", reason: "personal_test_member_required" };
  const optedIn = async () => {
    const row = await db.prepare("SELECT preferences_json FROM cloud_member_preferences WHERE member_id = ?").bind(memberId).first<{ preferences_json: string }>();
    const prefs = validatePreferences(row ? JSON.parse(row.preferences_json) : DEFAULT_PREFERENCES, true);
    return Object.values(prefs.notifications).some(Boolean);
  };
  try { if (!await optedIn()) return { status: "held", reason: "notification_opt_in_required" }; }
  catch { return { status: "held", reason: "notification_preferences_unavailable" }; }
  const eventKey = `personal-device-test:${env.CLOUD_PUSH_TEST_RUN_ID}`;
  const receipt = await db.prepare(`INSERT OR IGNORE INTO cloud_push_dispatch_receipts
    (member_id, subscription_id, event_key, status, reason, updated_at) VALUES (?, ?, ?, 'preparing', 'reserved', ?)`)
    .bind(memberId, env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID, eventKey, new Date().toISOString()).run();
  if (!receipt.success) throw new Error("reservation_failed");
  if (receipt.meta.changes !== 1) return { status: "suppressed", reason: "duplicate_or_uncertain_delivery" };
  const finish = async (result: SendResult | { status: "held"; reason: string }) => {
    const saved = await db.prepare("UPDATE cloud_push_dispatch_receipts SET status = ?, reason = ?, updated_at = ? WHERE member_id = ? AND subscription_id = ? AND event_key = ?")
      .bind(result.status, result.reason, new Date().toISOString(), memberId, env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID, eventKey).run();
    if (!saved.success) throw new Error("receipt_save_failed");
    return result;
  };
  // Exactly one fresh role lookup in this HTTP operation. Neither the signed
  // identity nor cached roles authorize sending. Look up after reservation and
  // re-read opt-in before transport; failures remain non-retryable receipts.
  try {
    const fresh = await reportIdentity(request, env, true);
    if (fresh.reason === "temporarily_unavailable")
      return finish({ status: "held", reason: "fresh_discord_role_unavailable" });
    if (fresh.subject !== identity.subject || !fresh.discord_authorized)
      return finish({ status: "held", reason: "fresh_discord_role_required" });
    if ((await currentMembership(env, identity.subject!, true)).status !== "paid")
      return finish({ status: "held", reason: "fresh_paid_membership_required" });
    if (!await optedIn()) return finish({ status: "held", reason: "notification_opt_in_required" });
  } catch { return finish({ status: "held", reason: "final_qualification_unavailable" }); }
  const device = await db.prepare(`SELECT s.*, m.vapid_public_key, m.expires_at_ms FROM cloud_push_subscriptions s JOIN
    cloud_push_subscription_metadata m ON m.subscription_id = s.subscription_id
    WHERE s.member_id = ? AND s.subscription_id = ? AND s.revoked_at IS NULL`)
    .bind(memberId, env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID).first<Device>();
  if (!device || device.vapid_public_key !== env.CLOUD_VAPID_PUBLIC_KEY || (device.expires_at_ms !== null && device.expires_at_ms <= Date.now()))
    return finish({ status: "held", reason: "active_approved_device_required" });
  const payload = JSON.stringify({ version: 1, kind: "reminder", body: "【本人端末テスト】天底極致Cloudからの通知です。", tag: eventKey });
  const result = await sendPersonalPush(env, memberId, device.subscription_id, device, payload, transport, fixture);
  if (result.status === "expired") {
    const revoked = await db.prepare("UPDATE cloud_push_subscriptions SET revoked_at = ? WHERE member_id = ? AND subscription_id = ? AND revoked_at IS NULL")
      .bind(new Date().toISOString(), memberId, device.subscription_id).run();
    if (!revoked.success) throw new Error("expired_device_revocation_failed");
  }
  return finish(result.status === "disabled" ? { status: "held", reason: result.reason } : result);
}
export async function dispatchPersonalCandidate(request: Request, env: CloudEnv, sourceEventKey: string,
  transport: typeof fetch = fetch, fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<SendResult | { status: "held" | "suppressed"; reason: string }> {
  return dispatchWithIdentity(env, sourceEventKey, () => reportIdentity(request, env, true), transport, fixture);
}

// Dormant server path: production activation requires configured fixed IDs.
// Never invoked by HTTP, a cron, or a queue. No user token is stored for this path.
export type BackgroundPushEnv = CloudEnv & { CLOUD_DISCORD_BOT_TOKEN?: string; CLOUD_PUSH_TEST_DISCORD_USER_ID?: string };
export async function dispatchBackgroundPersonalCandidate(env: BackgroundPushEnv, sourceEventKey: string,
  transport: typeof fetch = fetch, fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<SendResult | { status: "held" | "suppressed"; reason: string }> {
  const denied = (): Identity => ({ discord_authorized: false });
  return dispatchWithIdentity(env, sourceEventKey, async () => {
    if (!env.CLOUD_DB || !env.CLOUD_DISCORD_BOT_TOKEN) return denied();
    // The approved managed-role policy needs only an exact Discord identity;
    // it does not fabricate a Discord-to-Whop database link.
    if (env.CLOUD_PUSH_MEMBERSHIP_POLICY !== "whop_managed_discord_role" && env.WHOP_RESPONSE_SCHEMA !== "nested_v1") return denied();
    let subject: string | undefined;
    if (env.CLOUD_PUSH_MEMBERSHIP_POLICY === "whop_managed_discord_role") {
      subject = env.CLOUD_PUSH_TEST_DISCORD_USER_ID;
    } else {
      const link = await env.CLOUD_DB.prepare("SELECT * FROM cloud_member_links WHERE member_id = ?")
        .bind(env.CLOUD_PUSH_TEST_MEMBER_ID).first<{ discord_user_id: string; environment: string; revoked_at: string | null; verification_method: string; verified_at: string; evidence_reference: string }>();
      const now = Date.now();
      if (!link || link.environment !== "live" || link.revoked_at || link.verification_method !== "verified_operator" ||
          !link.evidence_reference || !Number.isFinite(Date.parse(link.verified_at)) || Date.parse(link.verified_at) > now) return denied();
      subject = link.discord_user_id;
    }
    if (!subject || !/^\d{17,20}$/.test(subject) || await cloudMemberId(subject) !== env.CLOUD_PUSH_TEST_MEMBER_ID ||
        !/^\d{17,20}$/.test(String(env.DISCORD_GUILD_ID))) return denied();
    const roles = String(env.DISCORD_ALLOWED_ROLE_IDS ?? "").split(",").map(x => x.trim()).filter(Boolean);
    if (!roles.length || roles.some(role => !/^\d{17,20}$/.test(role))) return denied();
    try {
      const response = await fetch(`https://discord.com/api/v10/guilds/${env.DISCORD_GUILD_ID}/members/${subject}`, {
        headers: { Authorization: `Bot ${env.CLOUD_DISCORD_BOT_TOKEN}` }, redirect: "error", cache: "no-store", signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) return denied();
      const member: unknown = await response.json();
      if (!isObject(member) || !isObject(member.user) || member.user.id !== subject || !Array.isArray(member.roles) ||
          member.roles.some(role => typeof role !== "string")) return denied();
      return { subject, discord_authorized: roles.some(role => (member.roles as string[]).includes(role)) };
    } catch { return denied(); }
  }, transport, fixture);
}

async function dispatchWithIdentity(env: CloudEnv, sourceEventKey: string, identityRead: () => Promise<Identity>,
  transport: typeof fetch, fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<SendResult | { status: "held" | "suppressed"; reason: string }> {
  const db = env.CLOUD_DB;
  // Release vars generate the literal "disabled" type; this unused helper also
  // checks any separately approved runtime configuration without enabling it.
  if (!db || String(env.CLOUD_PUSH_MODE) !== "personal_test" || !env.CLOUD_PUSH_TEST_MEMBER_ID || !env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID) return { status: "disabled", reason: "personal_test_not_enabled" };
  const identity = await identityRead();
  if (!identity.subject || !identity.discord_authorized) return { status: "held", reason: "fresh_discord_role_required" };
  const memberId = await cloudMemberId(identity.subject);
  if (memberId !== env.CLOUD_PUSH_TEST_MEMBER_ID) return { status: "disabled", reason: "personal_test_member_required" };
  const candidate = await db.prepare("SELECT event_json, source_ledger_revision FROM cloud_notification_events WHERE source_event_key = ? AND available_at <= ?")
    .bind(sourceEventKey, new Date().toISOString()).first<{ event_json: string; source_ledger_revision: string }>();
  if (!candidate) return { status: "held", reason: "canonical_event_required" };
  let event: NotificationEvent;
  try {
    const parsed: unknown = JSON.parse(candidate.event_json);
    if (!isObject(parsed) || parsed.adapter_version !== "cloud-ledger-v1" || !/^[0-9a-f]{64}$/.test(candidate.source_ledger_revision) || parsed.source_ledger_revision !== candidate.source_ledger_revision) throw new Error("invalid_event");
    event = parsed as NotificationEvent;
    // Persisted prior-day candidates must not become new alerts on a later run.
    const jstDay = new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
    if (!["new_detection", "reminder", "result"].includes(event.kind) || typeof event.signal_id !== "string" || !event.signal_id ||
        !isObject(event.endpoints) || !isObject(event.endpoints.d5_close) || !isObject(event.endpoints.d6_open) ||
        typeof event.detection_date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(event.detection_date) ||
        !Number.isFinite(Date.parse(event.detection_date)) || event.detection_date > jstDay) throw new Error("invalid_event");
    if (event.kind === "new_detection" && event.detection_date !== jstDay) return { status: "suppressed", reason: "outside_detection_day" };
  } catch { return { status: "held", reason: "canonical_event_required" }; }
  const check = async (roleAuthorized: boolean) => {
    const row = await db.prepare("SELECT preferences_json FROM cloud_member_preferences WHERE member_id = ?").bind(memberId).first<{ preferences_json: string }>();
    const prefs = validatePreferences(row ? JSON.parse(row.preferences_json) : DEFAULT_PREFERENCES, true);
    const member = await currentMembership(env, identity.subject!, roleAuthorized);
    return evaluateNotification(event, prefs, member, Date.now());
  };
  let decision;
  try { decision = await check(identity.discord_authorized); }
  catch { return { status: "held", reason: "invalid_candidate_or_preferences" }; }
  if (decision.status !== "would_send") return { status: decision.status, reason: decision.reason };
  // Atomic reservation. Preparing/unknown/accepted cannot be retried: delivery
  // may already have happened even if the HTTP response/process was lost.
  const receipt = await db.prepare(`INSERT OR IGNORE INTO cloud_push_dispatch_receipts
    (member_id, subscription_id, event_key, status, reason, updated_at) VALUES (?, ?, ?, 'preparing', 'reserved', ?)`)
    .bind(memberId, env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID, decision.event_key, new Date().toISOString()).run();
  if (!receipt.success) throw new Error("reservation_failed");
  if (receipt.meta.changes !== 1) return { status: "suppressed", reason: "duplicate_or_uncertain_delivery" };
  const finish = async (result: SendResult | { status: "held"; reason: string }) => {
    const saved = await db.prepare("UPDATE cloud_push_dispatch_receipts SET status = ?, reason = ?, updated_at = ? WHERE member_id = ? AND subscription_id = ? AND event_key = ?")
      .bind(result.status, result.reason, new Date().toISOString(), memberId, env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID, decision.event_key).run();
    if (!saved.success) throw new Error("receipt_save_failed");
    return result;
  };
  // Repeat identity/role, selected membership policy, and opt-in before send.
  const fresh = await identityRead();
  if (!fresh.discord_authorized || fresh.subject !== identity.subject) return finish({ status: "held", reason: "fresh_discord_role_required" });
  let second;
  try { second = await check(fresh.discord_authorized); }
  catch { return finish({ status: "held", reason: "invalid_candidate_or_preferences" }); }
  if (second.status !== "would_send") return finish({ status: "held", reason: second.reason });
  const device = await db.prepare(`SELECT s.*, m.vapid_public_key, m.expires_at_ms FROM cloud_push_subscriptions s JOIN
    cloud_push_subscription_metadata m ON m.subscription_id = s.subscription_id
    WHERE s.member_id = ? AND s.subscription_id = ? AND s.revoked_at IS NULL`)
    .bind(memberId, env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID).first<Device>();
  if (!device || device.vapid_public_key !== env.CLOUD_VAPID_PUBLIC_KEY || (device.expires_at_ms !== null && device.expires_at_ms <= Date.now())) return finish({ status: "held", reason: "active_approved_device_required" });
  const payload = JSON.stringify({ version: 1, kind: event.kind, body: event.kind === "reminder" ? second.message : `【本人端末テスト】${second.message}`, tag: decision.event_key });
  const result = await sendPersonalPush(env, memberId, device.subscription_id, device, payload, transport, fixture);
  if (result.status === "expired") {
    const revoked = await db.prepare("UPDATE cloud_push_subscriptions SET revoked_at = ? WHERE member_id = ? AND subscription_id = ? AND revoked_at IS NULL")
      .bind(new Date().toISOString(), memberId, device.subscription_id).run();
    if (!revoked.success) throw new Error("expired_device_revocation_failed");
  }
  // Disabled cannot follow reservation unless a configuration changed mid-call.
  return finish(result.status === "disabled" ? { status: "held", reason: result.reason } : result);
}
