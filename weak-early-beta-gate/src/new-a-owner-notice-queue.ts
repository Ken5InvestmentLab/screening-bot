import { bankBusinessDate } from "./cloud-canonical-feed";
import { digest } from "./new-a-private";
import { dispatchNewAOwnerPush, readNewAOwnerPushReceipt, readNewAOwnerPushRecipient } from "./new-a-owner-push";
import type { OperationalBuild } from "./operational-readback";

type Notice = Parameters<typeof dispatchNewAOwnerPush>[1];
type Kind = Notice["event"]["kind"];
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
  arrival_confirmed: false;
};
type Prepared = { report: Report; notices: Notice[] };
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
const payloadMaxBytes = 16 * 1024;
// Includes the adapter's reads/claim/final source check and independent
// receipt reads. Larger plans are held as a whole pending measured capacity.
export const NEW_A_NOTICE_BATCH_LIMIT = 2;
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
const eventFields = ["event_id", "kind", "symbol", "candidate_date", "simulated_entry_date", "title",
  "description", "execution_status"];
const morningFields = ["scheduled_evaluation_date", "evaluation_endpoint", "evaluation_timing", "evaluation_price_status"];
const basisFields = ["dataset_id", "revision", "manifest_sha256", "source_version", "snapshot_sha256", "preferences_revision"];
const endpoints = new Map([["d5_close", "CLOSE"], ["d5_open", "OPEN"], ["d6_open", "OPEN"], ["a20_close", "CLOSE"]]);

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

function validEvent(value: unknown, kind: Kind, target: string) {
  if (!shape(value, kind === morning ? [...eventFields, ...morningFields] : eventFields) ||
      value.kind !== kind || !matches(value.event_id, sha) || !matches(value.symbol, /^[0-9A-Z]{4}$/) ||
      value.execution_status !== "SIMULATED_NOT_ACTUAL_TRADES" || !day(value.candidate_date) ||
      !day(value.simulated_entry_date) || value.candidate_date > value.simulated_entry_date) return false;
  if (kind === holding) return value.simulated_entry_date === target && value.title === "監視から仮想保有に移行" &&
    value.description === "保存した条件による仮想保有です。実際の取引は行われていません。";
  return value.scheduled_evaluation_date === target && value.simulated_entry_date < target &&
    value.evaluation_price_status === "NOT_YET_OBSERVED" && value.title === "確定日の朝8時（日本時間）" &&
    value.description === "今日は、設定した確定日です。その日の価格はまだ確定していません。" &&
    typeof value.evaluation_endpoint === "string" && endpoints.has(value.evaluation_endpoint) &&
    value.evaluation_timing === endpoints.get(value.evaluation_endpoint);
}

async function prepare(env: Environment, controller: Scheduled, build: OperationalBuild, now: number): Promise<Prepared> {
  let time: ReturnType<typeof slot> = null;
  const stop = (status: Report["status"], reason: string): Prepared => ({
    report: { status, reason, ...(time ?? {}), queued: 0, verified_accepted: 0, arrival_confirmed: false }, notices: [],
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
    if (!shape(plan, planFields) || plan.schema !== "NEW_A_OWNER_NOTICE_QUEUE_V1" ||
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
    if (plan.notices.some(event => !validEvent(event, kind, target_date)) ||
        new Set(plan.notices.map(event => event.event_id)).size !== plan.notices.length)
      return stop("held", "queue_event_mismatch");
    if (!plan.notices.length) return stop("suppressed", "no_notices_due");
    const notices = plan.notices.map(event => ({
      owner_binding_sha256: plan.owner_binding_sha256,
      recipient_binding_sha256: plan.recipient_binding_sha256,
      target_date,
      basis,
      event,
    } as Notice));
    return { report: { ...stop("ready", "queue_verified").report, queued: notices.length }, notices };
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
  const { report, notices } = await prepare(env, controller, build, now);
  if (report.status !== "ready") return report;
  const hold = (reason: string): Report => ({ ...report, status: "held", reason });
  try {
    const recipient = await readers.readRecipient(env);
    if (!recipient || recipient.fresh_paid_role !== true ||
        recipient.owner_binding_sha256 !== notices[0].owner_binding_sha256 ||
        recipient.recipient_binding_sha256 !== notices[0].recipient_binding_sha256)
      return hold("owner_recipient_unverified");
    for (const notice of notices) {
      const attempt = await readers.dispatch(env, notice);
      // A duplicate or ambiguous attempt is reconciled by read only. It
      // cannot lead to a second provider request for the same event.
      if (!["accepted", "suppressed", "unknown"].includes(attempt.status)) return hold("delivery_held");
      const receipt = await readers.readReceipt(env, notice);
      if (receipt.status !== "accepted") return hold("delivery_readback_unconfirmed");
      report.verified_accepted++;
    }
    return { ...report, status: "processed", reason: "provider_acceptance_verified" };
  } catch { return hold("delivery_readback_unavailable"); }
}
