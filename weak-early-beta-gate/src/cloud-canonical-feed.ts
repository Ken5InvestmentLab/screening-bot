// PRIVATE compiler input. No browser route, external fetch, schema application,
// identity import, or member iteration is permitted by this module.
import { BANK_CALENDAR } from "./cloud-canonical-input.generated";
import { isObject } from "./cloud-membership";

export function bankBusinessDate(day: string): boolean | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return undefined;
  const date = new Date(day + "T00:00:00.000Z");
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== day ||
      day < BANK_CALENDAR.start_date || day > BANK_CALENDAR.end_date) return undefined;
  return ![0, 6].includes(date.getUTCDay()) && !(BANK_CALENDAR.closed_dates as readonly string[]).includes(day);
}
function businessAfter(day: string, count: number): string | undefined {
  let cursor = new Date(day + "T00:00:00.000Z");
  while (count > 0) {
    cursor = new Date(cursor.getTime() + 86400000);
    const next = cursor.toISOString().slice(0, 10), business = bankBusinessDate(next);
    if (business === undefined) return undefined;
    if (business) count--;
  }
  return cursor.toISOString().slice(0, 10);
}
const digest = async (text: string): Promise<string> => Array.from(new Uint8Array(
  await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))), byte => byte.toString(16).padStart(2, "0")).join("");

export async function importCanonicalInput(db: D1Database, input: unknown, nowMs = Date.now()): Promise<{ imported: number }> {
  const invalid = (): never => { throw new Error("canonical_input_invalid"); };
  if (!isObject(input) || input.schema_version !== 1 || input.adapter_version !== "cloud-ledger-v1" ||
      typeof input.source_ledger_revision !== "string" || !/^[0-9a-f]{64}$/.test(input.source_ledger_revision) ||
      typeof input.observed_at !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(input.observed_at) ||
      !Number.isFinite(Date.parse(input.observed_at)) || Date.parse(input.observed_at) > nowMs ||
      !Array.isArray(input.events) || input.events.length > 1000) return invalid();
  const observedAt = input.observed_at, revision = input.source_ledger_revision;
  const cutoffDay = new Date(Date.parse(observedAt) + 9 * 3600000).toISOString().slice(0, 10);
  const seen = new Set<string>(), statements: D1PreparedStatement[] = [];
  // Validate the whole manifest before issuing any writes.
  for (const value of input.events) {
    if (!isObject(value) || value.adapter_version !== "cloud-ledger-v1" || value.source_ledger_revision !== revision ||
        !["new_detection", "reminder"].includes(String(value.kind)) || typeof value.signal_id !== "string" ||
        !/^\d{4}-\d{2}-\d{2}\|[A-Za-z0-9.^_-]{1,32}$/.test(value.signal_id) ||
        typeof value.detection_date !== "string" || value.signal_id.split("|")[0] !== value.detection_date ||
        value.detection_date > cutoffDay || bankBusinessDate(value.detection_date) !== true ||
        (value.kind === "new_detection" && value.detection_date !== cutoffDay) || !isObject(value.endpoints)) return invalid();
    if (value.signal_price_status === "verified") {
      if (typeof value.signal_actual_close !== "number" || !Number.isFinite(value.signal_actual_close) || value.signal_actual_close <= 0) return invalid();
    } else if (value.signal_price_status !== "missing" || value.signal_actual_close !== null) return invalid();
    for (const [endpoint, days] of [["d5_close", 5], ["d6_open", 6]] as const) {
      const observation = value.endpoints[endpoint], expected = businessAfter(value.detection_date, days);
      if (!isObject(observation) || !expected || observation.date !== expected) return invalid();
      if (observation.status === "verified") {
        if (typeof observation.actual_price !== "number" || !Number.isFinite(observation.actual_price) || observation.actual_price <= 0 ||
            typeof observation.fetched_at !== "string" || !Number.isFinite(Date.parse(observation.fetched_at)) ||
            Date.parse(observation.fetched_at) > Date.parse(observedAt) || typeof observation.source !== "string" || !/^[0-9a-f]{64}$/.test(observation.source)) return invalid();
      } else if (observation.status !== "missing" || observation.actual_price !== null || observation.fetched_at !== null || observation.source !== null) return invalid();
    }
    const key = await digest(`${value.signal_id}:${value.kind}`);
    if (seen.has(key)) return invalid();
    seen.add(key);
    statements.push(db.prepare(`INSERT INTO cloud_notification_events (source_event_key, event_json, available_at, source_ledger_revision)
      VALUES (?, ?, ?, ?) ON CONFLICT(source_event_key) DO UPDATE SET event_json = excluded.event_json,
      source_ledger_revision = excluded.source_ledger_revision
      WHERE cloud_notification_events.event_json != excluded.event_json OR cloud_notification_events.source_ledger_revision != excluded.source_ledger_revision`)
      .bind(key, JSON.stringify(value), observedAt, revision));
  }
  let imported = 0;
  for (let offset = 0; offset < statements.length; offset += 20) {
    const results = await db.batch(statements.slice(offset, offset + 20));
    if (results.some(result => !result.success)) throw new Error("canonical_import_failed");
    imported += results.reduce((sum, result) => sum + (result.meta.changes ?? 0), 0);
  }
  return { imported };
}
