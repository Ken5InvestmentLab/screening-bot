// Internal helper only: no HTTP endpoint, scheduler or cron invokes this module.
import { reportIdentity } from "./shared-report-gate";
import { cloudMemberId, currentMembership, type CloudEnv } from "./cloud-api";
import { evaluateNotification, isObject, validatePreferences, DEFAULT_PREFERENCES, type NotificationEvent } from "./cloud-membership";
import { sendPersonalPush, type SendResult, type PushSubscription, type encryptPushPayload } from "./cloud-web-push";
type Device = PushSubscription & { member_id: string; subscription_id: string; revoked_at: string | null; vapid_public_key: string; expires_at_ms: number | null };
export async function dispatchPersonalCandidate(request: Request, env: CloudEnv, sourceEventKey: string,
  transport: typeof fetch = fetch, fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<SendResult | { status: "held" | "suppressed"; reason: string }> {
  const db = env.CLOUD_DB;
  if (!db || env.CLOUD_PUSH_MODE !== "personal_test" || !env.CLOUD_PUSH_TEST_MEMBER_ID || !env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID) return { status: "disabled", reason: "personal_test_not_enabled" };
  const identity = await reportIdentity(request, env, true);
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
  } catch { return { status: "held", reason: "canonical_event_required" }; }
  const check = async () => {
    const row = await db.prepare("SELECT preferences_json FROM cloud_member_preferences WHERE member_id = ?").bind(memberId).first<{ preferences_json: string }>();
    const prefs = validatePreferences(row ? JSON.parse(row.preferences_json) : DEFAULT_PREFERENCES, true);
    const member = await currentMembership(env, identity.subject!);
    return evaluateNotification(event, prefs, member, Date.now());
  };
  const decision = await check();
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
  // Repeat both identity/role and payment/opt-in checks immediately before send.
  const fresh = await reportIdentity(request, env, true);
  if (!fresh.discord_authorized || fresh.subject !== identity.subject) return finish({ status: "held", reason: "fresh_discord_role_required" });
  const second = await check();
  if (second.status !== "would_send") return finish({ status: "held", reason: second.reason });
  const device = await db.prepare(`SELECT s.*, m.vapid_public_key, m.expires_at_ms FROM cloud_push_subscriptions s JOIN
    cloud_push_subscription_metadata m ON m.subscription_id = s.subscription_id
    WHERE s.member_id = ? AND s.subscription_id = ? AND s.revoked_at IS NULL`)
    .bind(memberId, env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID).first<Device>();
  if (!device || device.vapid_public_key !== env.CLOUD_VAPID_PUBLIC_KEY || (device.expires_at_ms !== null && device.expires_at_ms <= Date.now())) return finish({ status: "held", reason: "active_approved_device_required" });
  const payload = JSON.stringify({ version: 1, kind: event.kind, body: `【本人端末テスト】${second.message}`, tag: decision.event_key });
  const result = await sendPersonalPush(env, memberId, device.subscription_id, device, payload, transport, fixture);
  if (result.status === "expired") {
    const revoked = await db.prepare("UPDATE cloud_push_subscriptions SET revoked_at = ? WHERE member_id = ? AND subscription_id = ? AND revoked_at IS NULL")
      .bind(new Date().toISOString(), memberId, device.subscription_id).run();
    if (!revoked.success) throw new Error("expired_device_revocation_failed");
  }
  // Disabled cannot follow reservation unless a configuration changed mid-call.
  return finish(result.status === "disabled" ? { status: "held", reason: result.reason } : result);
}
