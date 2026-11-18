import { bankBusinessDate } from "./cloud-canonical-feed";
import { digest } from "./new-a-private";
import { dispatchNewAOwnerPush, NEW_A_NOTICE_BATCH_LIMIT, readNewAOwnerPushReceipt, readNewAOwnerPushRecipient } from "./new-a-owner-push";
import type { OperationalBuild } from "./operational-readback";

type Notice = Parameters<typeof dispatchNewAOwnerPush>[1];
type Kind = Notice["kind"];
type Environment = Parameters<typeof dispatchNewAOwnerPush>[0] & {
  CLOUD_VERSION_METADATA?: { id?: string; tag?: string };
};
type Scheduled = { cron: string; scheduledTime: number };
type Reader = {
  readRecipient: typeof readNewAOwnerPushRecipient;
  dispatch: typeof dispatchNewAOwnerPush;
  readReceipt: typeof readNewAOwnerPushReceipt;
};
type Report = {
  status: "disabled" | "suppressed" | "held" | "ready" | "processed";
  reason: string;
  target_date?: string;
  kind?: Kind;
  queued: number;
  verified_accepted: number;
  verified_accepted_pushes: number;
  arrival_confirmed: false;
};
type Prepared = { report: Report; notice?: Notice };
type QueueRow = {
  payload_json: string;
  payload_sha256: string;
  active_dataset_id: string | null;
  active_revision: number | null;
  active_status: string | null;
  active_manifest_sha256: string | null;
  active_source_version: string | null;
  active_as_of: string | null;
  active_next_session: string | null;
  active_live: number | null;
};

const morning = "EVALUATION_DAY_MORNING";
const holding = "WATCH_TO_SIMULATED_HOLDING";
export const NEW_A_MORNING_CRON = "0 23 * * *";
export const NEW_A_HOLDING_CRON = "*/5 8-14 * * *";
const payloadMaxBytes = 88 * 1024;
const JST = 9 * 60 * 60 * 1000;
const sha = /^[a-f0-9]{64}$/;
const commit = /^[a-f0-9]{40}$/;
const version = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const defaults: Reader = {
  readRecipient: readNewAOwnerPushRecipient,
  dispatch: dispatchNewAOwnerPush,
  readReceipt: readNewAOwnerPushReceipt,
};
const planFields = ["schema", "target_date", "kind", "source_commit", "worker_version_id",
  "build_input_sha256", "source_run_sha256", "publication_receipt_sha256", "owner_binding_sha256",
  "recipient_binding_sha256", "model_basis", "basis", "publication", "notices"];
const publicationFields = ["schema", "as_of", "dataset_id", "revision", "manifest_sha256", "source_version",
  "snapshot_sha256", "published", "active_readback_verified", "existing_owner_gate_verified", "local_d1_emulation"];
const basisFields = ["dataset_id", "revision", "manifest_sha256", "source_version", "snapshot_sha256", "preferences_revision"];
const eventId = /^[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]$/;
const monthDays = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
function shape(value: unknown, fields: string[]): value is Record<string, unknown> {
  return object(value) && Object.keys(value).length === fields.length && fields.every(name => Object.hasOwn(value, name));
}
function matches(value: unknown, pattern: RegExp): value is string {
  return typeof value === "string" && pattern.test(value);
}
function day(value: unknown): value is string {
  return matches(value, /^\d{4}-\d{2}-\d{2}$/) && Number.isFinite(Date.parse(value + "T00:00:00Z")) &&
    new Date(value + "T00:00:00Z").toISOString().slice(0, 10) === value;
}
function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function slot(controller: Scheduled, now: number): { target_date: string; kind: Kind } | null {
  if (!Number.isSafeInteger(now) || !Number.isSafeInteger(controller.scheduledTime) ||
      controller.scheduledTime > now || controller.scheduledTime % 60_000 !== 0) return null;
  const scheduled = new Date(controller.scheduledTime + JST).toISOString();
  const actual = new Date(now + JST).toISOString();
  const target_date = actual.slice(0, 10);
  if (scheduled.slice(0, 10) !== target_date) return null;
  if (controller.cron === NEW_A_MORNING_CRON && scheduled.slice(11, 16) === "08:00" && actual.slice(11, 13) === "08")
    return { target_date, kind: morning };
  if (controller.cron === NEW_A_HOLDING_CRON && scheduled.slice(11, 13) >= "17" &&
      Number(scheduled.slice(14, 16)) % 5 === 0) return { target_date, kind: holding };
  return null;
}

function wireDay(value: unknown): value is number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 10000101 || value > 99991231) return false;
  const year = Math.floor(value / 10000);
  const month = Math.floor(value / 100) % 100;
  const date = value % 100;
  const leapDay = month === 2 && year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  return month >= 1 && month <= 12 && date >= 1 && date <= monthDays[month - 1] + Number(leapDay);
}

function validEvents(values: unknown[], kind: Kind, target: string): boolean {
  const targetDate = Number(target.replaceAll("-", ""));
  const ids = new Set<string>();
  for (const value of values) {
    if (!Array.isArray(value) || value.length !== 5) return false;
    // V2 orders the fields as SHA-256 base64url, symbol, two YYYYMMDD dates, endpoint.
    // Morning endpoint codes 0..3 mean d5_close, d5_open, d6_open, a20_close.
    const [id, symbol, candidate, entry, endpoint] = value;
    if (!matches(id, eventId) || ids.has(id) || !matches(symbol, /^[0-9A-Z]{4}$/) ||
        !wireDay(candidate) || !wireDay(entry) || candidate > entry ||
        (kind === holding ? entry !== targetDate || endpoint !== null
          : entry >= targetDate || typeof endpoint !== "number" || !Number.isInteger(endpoint) || endpoint < 0 || endpoint > 3))
      return false;
    ids.add(id);
  }
  return true;
}

async function prepare(env: Environment, controller: Scheduled, build: OperationalBuild, now: number): Promise<Prepared> {
  let time: ReturnType<typeof slot> = null;
  const stop = (status: Report["status"], reason: string): Prepared => ({
    report: { status, reason, ...(time ?? {}), queued: 0, verified_accepted: 0, verified_accepted_pushes: 0, arrival_confirmed: false },
  });
  if (env.CLOUD_NEW_A_OWNER_PUSH_ENABLED !== "true") return stop("disabled", "owner_notice_disabled");
  try {
    time = slot(controller, now);
    if (!time) return stop("suppressed", "outside_notice_slot");
    const { kind, target_date } = time;
    const business = bankBusinessDate(target_date);
    if (business === undefined) return stop("held", "bank_calendar_unavailable");
    if (!business) return stop("suppressed", "bank_non_business_day");
    const metadata = env.CLOUD_VERSION_METADATA;
    if (!env.CLOUD_DB || build.target.worker !== "tentei-kyokuchi-cloud" || build.target.database !== "tentei-cloud-settings" ||
        !commit.test(build.source_commit) || !sha.test(build.build_input_sha256) ||
        !matches(metadata?.id, version) || metadata?.tag !== build.source_commit)
      return stop("held", "normal_release_unverified");
    const row = await env.CLOUD_DB.prepare(
      "SELECT q.payload_json,q.payload_sha256,p.dataset_id AS active_dataset_id,p.revision AS active_revision," +
      "d.status AS active_status,d.manifest_sha256 AS active_manifest_sha256,d.source_version AS active_source_version," +
      "json_extract(d.manifest_json,'$.as_of') AS active_as_of," +
      "json_extract(d.manifest_json,'$.input_header.limits.nextPlannedSession') AS active_next_session," +
      "json_extract(d.manifest_json,'$.live') AS active_live " +
      "FROM new_a_owner_notice_queue q LEFT JOIN new_a_active_pointer p ON p.pointer_key='owner' " +
      "LEFT JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id WHERE q.target_date=? AND q.kind=?",
    ).bind(target_date, kind).first<QueueRow>();
    if (!row) return stop("suppressed", "no_queued_plan");
    if (typeof row.payload_json !== "string" || row.payload_json.length > payloadMaxBytes ||
        new TextEncoder().encode(row.payload_json).length > payloadMaxBytes || !matches(row.payload_sha256, sha) ||
        await digest(row.payload_json) !== row.payload_sha256) return stop("held", "queue_integrity_mismatch");
    const plan: unknown = JSON.parse(row.payload_json);
    if (!shape(plan, planFields) || plan.schema !== "NEW_A_OWNER_NOTICE_QUEUE_V2" ||
        plan.kind !== kind || plan.target_date !== target_date || plan.source_commit !== build.source_commit ||
        plan.worker_version_id !== metadata.id || plan.build_input_sha256 !== build.build_input_sha256 ||
        ![plan.source_run_sha256, plan.publication_receipt_sha256, plan.owner_binding_sha256,
          plan.recipient_binding_sha256].every(value => matches(value, sha)) ||
        (plan.model_basis !== "SAVED_SCOPE" && plan.model_basis !== "LATEST_YEAR_STANDALONE") || !Array.isArray(plan.notices))
      return stop("held", "queue_contract_mismatch");
    if (plan.notices.length > NEW_A_NOTICE_BATCH_LIMIT) return stop("held", "batch_exceeds_delivery_budget");
    const { basis, publication } = plan;
    if (!shape(basis, kind === morning ? [...basisFields, "calendar_sha256"] : basisFields) ||
        !matches(basis.dataset_id, /^a-[a-f0-9]{24}$/) || !positive(basis.revision) || !positive(basis.preferences_revision) ||
        ![basis.manifest_sha256, basis.source_version, basis.snapshot_sha256].every(value => matches(value, sha)) ||
        (kind === morning && !matches(basis.calendar_sha256, sha)) ||
        !shape(publication, publicationFields) || publication.schema !== "NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1" ||
        publication.published !== true || publication.active_readback_verified !== true ||
        publication.existing_owner_gate_verified !== true || publication.local_d1_emulation !== false ||
        !["dataset_id", "revision", "manifest_sha256", "source_version", "snapshot_sha256"]
          .every(field => publication[field] === basis[field]) ||
        row.active_status !== "READY" || row.active_dataset_id !== basis.dataset_id || row.active_revision !== basis.revision ||
        row.active_manifest_sha256 !== basis.manifest_sha256 || row.active_source_version !== basis.source_version ||
        !day(publication.as_of) || row.active_as_of !== publication.as_of ||
        (kind === morning ? publication.as_of >= target_date || row.active_next_session !== target_date
          : publication.as_of !== target_date || row.active_live !== 1))
      return stop("held", "active_publication_mismatch");
    if (!validEvents(plan.notices, kind, target_date))
      return stop("held", "queue_event_mismatch");
    if (!plan.notices.length) return stop("suppressed", "no_notices_due");
    const notice = {
      owner_binding_sha256: plan.owner_binding_sha256,
      recipient_binding_sha256: plan.recipient_binding_sha256,
      target_date,
      basis,
      kind,
      event_count: plan.notices.length,
      batch_sha256: row.payload_sha256,
    } as Notice;
    return { report: { ...stop("ready", "queue_verified").report, queued: notice.event_count }, notice };
  } catch { return stop("held", "queue_preflight_unavailable"); }
}

/** Read-only and aggregate-only. This does not check or send to a provider. */
export async function checkNewAOwnerNoticeQueue(env: Environment, controller: Scheduled,
  build: OperationalBuild, now = Date.now()): Promise<Report> {
  return (await prepare(env, controller, build, now)).report;
}

/** Internal bounded consumer for explicitly enabled New A schedule slots. */
export async function runNewAOwnerNoticeQueue(env: Environment, controller: Scheduled,
  build: OperationalBuild, now = Date.now(), readers = defaults): Promise<Report> {
  const { report, notice } = await prepare(env, controller, build, now);
  if (report.status !== "ready" || !notice) return report;
  const hold = (reason: string): Report => ({ ...report, status: "held", reason });
  try {
    const recipient = await readers.readRecipient(env);
    if (!recipient || recipient.fresh_paid_role !== true ||
        recipient.owner_binding_sha256 !== notice.owner_binding_sha256 ||
        recipient.recipient_binding_sha256 !== notice.recipient_binding_sha256)
      return hold("owner_recipient_unverified");
    const attempt = await readers.dispatch(env, notice);
    // A duplicate or ambiguous attempt is reconciled by read only. It
    // cannot lead to a second provider request for this owner's slot.
    if (!["accepted", "suppressed", "unknown"].includes(attempt.status)) return hold("delivery_held");
    const receipt = await readers.readReceipt(env, notice);
    if (receipt.status !== "accepted") return hold("delivery_readback_unconfirmed");
    return { ...report, status: "processed", reason: "provider_acceptance_verified",
      verified_accepted: notice.event_count, verified_accepted_pushes: 1 };
  } catch { return hold("delivery_readback_unavailable"); }
}
