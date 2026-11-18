// Worker-internal adapter for events from the verified New A owner planner.
// The caller supplies no endpoint, credentials, message text, or untrusted route data.
import { cloudMemberId, currentMembership } from "./cloud-api";
import { bankBusinessDate } from "./cloud-canonical-feed";
import { validatePreferences } from "./cloud-membership";
import { readBackgroundDiscordRole, type BackgroundPushEnv } from "./cloud-push-dispatch";
import { allowedEndpoint, sendPersonalPush, type PushSubscription, type encryptPushPayload } from "./cloud-web-push";
import { digest, validateManifest } from "./new-a-private";
import { readTrial } from "./new-a-preferences";

type Environment = BackgroundPushEnv & { CLOUD_NEW_A_OWNER_PUSH_ENABLED?: string };
type Kind = "WATCH_TO_SIMULATED_HOLDING" | "EVALUATION_DAY_MORNING";
type Basis = {
  dataset_id: string; revision: number; manifest_sha256: string; source_version: string;
  snapshot_sha256: string; preferences_revision: number; calendar_sha256?: string;
};
type Notice = {
  owner_binding_sha256: string; recipient_binding_sha256: string; target_date: string;
  basis: Basis; kind: Kind; event_count: number; batch_sha256: string;
};
type Owner = { subject: string; member: string; subscription: string };
type Device = PushSubscription & { endpoint_hash: string; vapid_public_key: string; expires_at_ms: number | null };
type ReceiptStatus = "preparing" | "held" | "accepted" | "rejected" | "unknown" | "expired";
type Outcome = { status: ReceiptStatus | "disabled" | "suppressed"; reason: string; arrival_confirmed: false };
type DeviceProof = { binding: string; device: Device };
const SHA = /^[a-f0-9]{64}$/;
const SNOWFLAKE = /^\d{17,20}$/;
const UUID_V4 = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
const MORNING = "EVALUATION_DAY_MORNING";
const HOLDING = "WATCH_TO_SIMULATED_HOLDING";
const JST_MS = 9 * 60 * 60 * 1000;
export const NEW_A_NOTICE_BATCH_LIMIT = 1000;
const roleMaxAgeMs = 30_000;
const outcome = (status: Outcome["status"], reason: string): Outcome => ({ status, reason, arrival_confirmed: false });

async function configuredOwner(env: Environment): Promise<Owner | null> {
  const subject = env.CLOUD_OWNER_DISCORD_ID?.trim();
  const member = env.CLOUD_PUSH_TEST_MEMBER_ID;
  const subscription = env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID;
  if (env.CLOUD_OWNER_ONLY_ENABLED?.trim().toLowerCase() !== "true" || String(env.CLOUD_PUSH_MODE) !== "personal_test" ||
      env.CLOUD_PUSH_MEMBERSHIP_POLICY !== "whop_managed_discord_role" || !env.CLOUD_DB ||
      !subject || !SNOWFLAKE.test(subject) || subject !== env.CLOUD_PUSH_TEST_DISCORD_USER_ID ||
      !member || member !== await cloudMemberId(subject) || !subscription || !UUID_V4.test(subscription)) return null;
  return { subject, member, subscription };
}

async function selectedDevice(env: Environment, owner: Owner, requireActive = true): Promise<DeviceProof | null> {
  const device = await env.CLOUD_DB!.prepare(`SELECT s.endpoint,s.p256dh,s.auth,m.endpoint_hash,m.vapid_public_key,m.expires_at_ms
    FROM cloud_push_subscriptions s JOIN cloud_push_subscription_metadata m ON m.subscription_id=s.subscription_id
    WHERE s.member_id=? AND s.subscription_id=? AND (?=0 OR s.revoked_at IS NULL)`)
    .bind(owner.member, owner.subscription, requireActive ? 1 : 0).first<Device>();
  if (!device || !SHA.test(device.endpoint_hash) || device.endpoint_hash !== await digest(device.endpoint)) return null;
  if (requireActive) {
    if (!env.CLOUD_VAPID_PUBLIC_KEY || device.vapid_public_key !== env.CLOUD_VAPID_PUBLIC_KEY ||
        (device.expires_at_ms !== null && (!Number.isSafeInteger(device.expires_at_ms) || device.expires_at_ms <= Date.now()))) return null;
    allowedEndpoint(device.endpoint, env);
  }
  const binding = await digest(JSON.stringify(["NEW_A_OWNER_WEB_PUSH_DEVICE_V1", owner.member, owner.subscription, device.endpoint_hash]));
  return { binding, device };
}

async function freshPaidRole(env: Environment, owner: Owner): Promise<number | null> {
  const checkedAt = Date.now();
  const identity = await readBackgroundDiscordRole(env, owner.subject);
  if (identity.subject !== owner.subject || identity.discord_authorized !== true) return null;
  const paid = await currentMembership(env, owner.subject, true);
  return paid.status === "paid" ? checkedAt : null;
}

function validDate(value: string): boolean {
  const ms = Date.parse(value + "T00:00:00Z");
  return /^\d{4}-\d\d-\d\d$/.test(value) && Number.isFinite(ms) && new Date(ms).toISOString().slice(0, 10) === value;
}

function validBatch(notice: Notice): boolean {
  return validDate(notice.target_date) && [MORNING, HOLDING].includes(notice.kind) &&
    SHA.test(notice.batch_sha256) && Number.isSafeInteger(notice.event_count) &&
    notice.event_count >= 1 && notice.event_count <= NEW_A_NOTICE_BATCH_LIMIT;
}

function matchesWindow(notice: Notice, now: number): boolean {
  const { target_date: day, kind } = notice;
  const jst = new Date(now + JST_MS).toISOString();
  if (!validBatch(notice) || jst.slice(0, 10) !== day || bankBusinessDate(day) !== true) return false;
  return kind === MORNING ? jst.slice(11, 13) === "08" && SHA.test(notice.basis.calendar_sha256 ?? "")
    : jst.slice(11, 13) >= "17";
}

async function matchesSource(db: D1Database, owner: Owner, notice: Notice): Promise<boolean> {
  const { basis, kind, target_date: day } = notice;
  if (!/^a-[a-f0-9]{24}$/.test(basis.dataset_id) || !SHA.test(basis.manifest_sha256) ||
      !SHA.test(basis.source_version) || !SHA.test(basis.snapshot_sha256) ||
      !Number.isSafeInteger(basis.revision) || basis.revision < 1 ||
      !Number.isSafeInteger(basis.preferences_revision) || basis.preferences_revision < 1) return false;
  const row = await db.prepare(`SELECT d.manifest_json,d.manifest_sha256,d.source_version,d.dataset_id,p.revision,q.payload_sha256
    FROM new_a_active_pointer p JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id
    JOIN new_a_owner_notice_queue q ON q.target_date=? AND q.kind=?
    WHERE p.pointer_key='owner' AND d.status='READY'`).bind(day, kind).first<{
      manifest_json: string; manifest_sha256: string; source_version: string; dataset_id: string; revision: number;
      payload_sha256: string;
    }>();
  if (!row || row.dataset_id !== basis.dataset_id || row.revision !== basis.revision ||
      row.manifest_sha256 !== basis.manifest_sha256 || row.source_version !== basis.source_version ||
      row.payload_sha256 !== notice.batch_sha256 ||
      await digest(row.manifest_json) !== row.manifest_sha256) return false;
  const manifest = validateManifest(JSON.parse(row.manifest_json));
  if (manifest.strategy !== "A_BASE" || manifest.source_version !== row.source_version ||
      manifest.daily_snapshot_sha256 !== basis.snapshot_sha256 || typeof manifest.as_of !== "string" ||
      !validDate(manifest.as_of) || (kind === HOLDING ? manifest.as_of !== day || manifest.live !== true : manifest.as_of >= day)) return false;
  const trial = await readTrial(db, owner.member);
  if (!trial.has_saved_finite_preferences || trial.revision !== basis.preferences_revision) return false;
  const savedPush = await db.prepare("SELECT preferences_json FROM cloud_member_preferences WHERE member_id=?")
    .bind(owner.member).first<{ preferences_json: string }>();
  if (!savedPush) return false;
  const optIn = validatePreferences(JSON.parse(savedPush.preferences_json), true).notifications;
  // These are the existing owner notification switches for the two classes.
  return kind === MORNING ? optIn.reminder : optIn.new_detection;
}

const eventKey = (notice: Notice) => `new-a-owner-v2:${notice.kind}:${notice.target_date}`;
const receiptPrefix = (notice: Notice) => `batch:${notice.batch_sha256}:`;
const priorReceiptFilter = "(event_key=? OR (event_key GLOB ? AND updated_at>=? AND updated_at<?))";

function receiptKeys(notice: Notice): [string, string, string, string] {
  const start = Date.parse(notice.target_date + "T00:00:00+09:00");
  return [eventKey(notice), `new-a-owner-v1:${notice.kind}:*`, new Date(start).toISOString(),
    new Date(start + 24 * 60 * 60 * 1000).toISOString()];
}

export async function readNewAOwnerPushRecipient(env: Environment): Promise<{
  owner_binding_sha256: string; recipient_binding_sha256: string; fresh_paid_role: true;
} | null> {
  try {
    if (env.CLOUD_NEW_A_OWNER_PUSH_ENABLED !== "true") return null;
    const owner = await configuredOwner(env);
    if (!owner) return null;
    const checkedAt = await freshPaidRole(env, owner);
    const selected = await selectedDevice(env, owner);
    if (checkedAt === null || Date.now() - checkedAt > roleMaxAgeMs || !selected) return null;
    return { owner_binding_sha256: owner.member.slice("cloud_".length),
      recipient_binding_sha256: selected.binding, fresh_paid_role: true };
  } catch { return null; }
}

/** Read the exact provider outcome recorded locally. There is no provider arrival query. */
export async function readNewAOwnerPushReceipt(env: Environment, notice: Notice): Promise<Outcome> {
  try {
    const owner = await configuredOwner(env);
    if (!owner || notice.owner_binding_sha256 !== owner.member.slice("cloud_".length) ||
        !validBatch(notice)) return outcome("held", "owner_binding_required");
    const selected = await selectedDevice(env, owner, false);
    if (!selected || selected.binding !== notice.recipient_binding_sha256) return outcome("held", "recipient_binding_required");
    const row = await env.CLOUD_DB!.prepare("SELECT status,reason FROM cloud_push_dispatch_receipts WHERE member_id=? AND subscription_id=? AND event_key=?")
      .bind(owner.member, owner.subscription, eventKey(notice)).first<{ status: ReceiptStatus; reason: string }>();
    const prefix = receiptPrefix(notice);
    if (!row) return outcome("unknown", "no_exact_receipt");
    if (!row.reason.startsWith(prefix)) return outcome("unknown", "receipt_batch_mismatch");
    return outcome(row.status, row.reason.slice(prefix.length));
  } catch { return outcome("unknown", "receipt_read_failed"); }
}

/** Provider acceptance is claimed once for the immutable batch on the JST slot. */
export async function dispatchNewAOwnerPush(env: Environment, notice: Notice,
  transport: typeof fetch = fetch, fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<Outcome> {
  let reservationAttempted = false;
  try {
    if (env.CLOUD_NEW_A_OWNER_PUSH_ENABLED !== "true") return outcome("disabled", "new_a_owner_push_disabled");
    const owner = await configuredOwner(env);
    if (!owner || notice.owner_binding_sha256 !== owner.member.slice("cloud_".length)) return outcome("held", "owner_binding_required");
    if (!matchesWindow(notice, Date.now())) return outcome("held", "current_notice_window_required");
    const db = env.CLOUD_DB!, key = eventKey(notice), prefix = receiptPrefix(notice), keys = receiptKeys(notice);
    const duplicate = await db.prepare(`SELECT 1 FROM cloud_push_dispatch_receipts WHERE member_id=? AND ${priorReceiptFilter} LIMIT 1`)
      .bind(owner.member, ...keys).first();
    if (duplicate) return outcome("suppressed", "existing_notice_receipt");
    const checkedAt = await freshPaidRole(env, owner);
    if (checkedAt === null) return outcome("held", "fresh_paid_role_required");
    const device = await selectedDevice(env, owner);
    if (!device || device.binding !== notice.recipient_binding_sha256) return outcome("held", "recipient_binding_required");
    if (!await matchesSource(db, owner, notice)) return outcome("held", "current_source_and_opt_in_required");
    reservationAttempted = true;
    const claim = await db.prepare(`INSERT OR IGNORE INTO cloud_push_dispatch_receipts
      (member_id,subscription_id,event_key,status,reason,updated_at)
      SELECT ?,?,?,'preparing',?,? WHERE NOT EXISTS
      (SELECT 1 FROM cloud_push_dispatch_receipts WHERE member_id=? AND ${priorReceiptFilter})`)
      .bind(owner.member, owner.subscription, key, prefix + "reserved", new Date().toISOString(), owner.member, ...keys).run();
    if (!claim.success) return outcome("unknown", "reservation_unconfirmed");
    if (claim.meta.changes !== 1) return outcome("suppressed", "existing_notice_receipt");
    const morning = notice.kind === MORNING;
    const payload = JSON.stringify({ version: 1, kind: morning ? "reminder" : "new_detection", tag: key,
      body: morning ? `本日の評価予定は${notice.event_count}件です。価格はまだ確定していません。` :
        `監視から仮想保有に移行した銘柄は${notice.event_count}件です。保存した条件による試算です。` });
    let finalHeld = false;
    const guardedTransport: typeof fetch = async (input, init) => {
      // Match the accepted endpoint/keys and private source again after encryption
      // so concurrent opt-out, endpoint rotation or publication holds this send.
      try {
        const current = await selectedDevice(env, owner);
        const sourceCurrent = await matchesSource(db, owner, notice);
        const now = Date.now();
        if (!current || current.binding !== device.binding || current.device.p256dh !== device.device.p256dh ||
            current.device.auth !== device.device.auth || !sourceCurrent || now < checkedAt ||
            now - checkedAt > roleMaxAgeMs || !matchesWindow(notice, now)) throw Error("qualification_changed");
      } catch {
        finalHeld = true;
        return new Response(null, { status: 412 });
      }
      return transport(input, init);
    };
    const result = await sendPersonalPush(env, owner.member, owner.subscription, device.device, payload, guardedTransport, fixture);
    const received = finalHeld ? { status: "held" as const, reason: "final_qualification_changed" } : result;
    const status: ReceiptStatus = received.status === "disabled" ? "held" : received.status;
    const saved = await db.prepare(`UPDATE cloud_push_dispatch_receipts SET status=?,reason=?,updated_at=?
      WHERE member_id=? AND subscription_id=? AND event_key=? AND status='preparing' AND reason=?`)
      .bind(status, prefix + received.reason, new Date().toISOString(), owner.member, owner.subscription, key, prefix + "reserved").run();
    return saved.success && saved.meta.changes === 1 ?
      outcome(status, received.reason) : outcome("unknown", "receipt_save_unconfirmed");
  } catch { return reservationAttempted ? outcome("unknown", "reserved_outcome_unconfirmed") : outcome("held", "new_a_owner_push_unavailable"); }
}
