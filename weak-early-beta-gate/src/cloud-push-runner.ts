// Single-device batch. Activation/wiring is separate from this internal runner.
// Shared scan schema, separate cursor namespace; never iterate over members.
import { dispatchBackgroundPersonalCandidate, type BackgroundPushEnv } from "./cloud-push-dispatch";
import type { encryptPushPayload } from "./cloud-web-push";

export async function runPersonalNotificationBatch(env: BackgroundPushEnv, transport: typeof fetch = fetch,
  fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<{ processed: number; accepted: number; held: number; suppressed: number; failed: number; more: boolean }> {
  const counts = { processed: 0, accepted: 0, held: 0, suppressed: 0, failed: 0, more: false };
  if (!env.CLOUD_DB || String(env.CLOUD_PUSH_MODE) !== "personal_test" || !env.CLOUD_PUSH_TEST_MEMBER_ID || !env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID) return counts;
  const db = env.CLOUD_DB, now = new Date().toISOString();
  // Isolated from the current-session dry-run cursor, using only fixed server IDs.
  const cursor = `personal-push:${env.CLOUD_PUSH_TEST_MEMBER_ID}:${env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID}`;
  const init = await db.prepare(`INSERT OR IGNORE INTO cloud_notification_scan_progress (member_id, updated_at) VALUES (?, ?)`).bind(cursor, now).run();
  if (!init.success) throw new Error("scan_progress_save_failed");
  const progress = await db.prepare(`SELECT after_available_at, after_source_event_key, cycle_cutoff_at, version FROM cloud_notification_scan_progress WHERE member_id = ?`)
    .bind(cursor).first<{ after_available_at: string; after_source_event_key: string; cycle_cutoff_at: string; version: number }>();
  if (!progress || !Number.isSafeInteger(progress.version) || progress.version < 0) throw new Error("scan_progress_missing");
  const cutoff = progress.cycle_cutoff_at || now;
  const rows = await db.prepare(`SELECT source_event_key, available_at FROM cloud_notification_events WHERE available_at <= ?
    AND (available_at, source_event_key) > (?, ?) ORDER BY available_at, source_event_key LIMIT 21`)
    .bind(cutoff, progress.after_available_at, progress.after_source_event_key).all<{ source_event_key: string; available_at: string }>();
  if (!rows.success) throw new Error("candidate_read_failed");
  counts.more = (rows.results ?? []).length > 20;
  const page = (rows.results ?? []).slice(0, 20);
  for (const row of page) {
    counts.processed++;
    try {
      const result = await dispatchBackgroundPersonalCandidate(env, row.source_event_key, transport, fixture);
      if (result.status === "accepted") counts.accepted++;
      else if (result.status === "held") counts.held++;
      else if (result.status === "suppressed" || result.status === "disabled") counts.suppressed++;
      else counts.failed++;
    } catch { counts.failed++; }
  }
  const last = page.at(-1);
  const advanced = await db.prepare(`UPDATE cloud_notification_scan_progress SET after_available_at = ?, after_source_event_key = ?,
    cycle_cutoff_at = ?, updated_at = ?, version = version + 1 WHERE member_id = ? AND version = ?`)
    .bind(counts.more && last ? last.available_at : "", counts.more && last ? last.source_event_key : "", counts.more ? cutoff : "", now, cursor, progress.version).run();
  if (!advanced.success) throw new Error("scan_progress_save_failed");
  // All preparing/unknown/accepted/rejected receipts still prohibit auto-resend.
  // Only aggregate counts leave this internal runner; provider acceptance != arrival.
  return counts;
}
