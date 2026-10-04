import { CANONICAL_MANIFEST } from "./cloud-canonical-input.generated";
import { bankBusinessDate, importCanonicalInput } from "./cloud-canonical-feed";
import { runPersonalNotificationBatch } from "./cloud-push-runner";
import type { BackgroundPushEnv } from "./cloud-push-dispatch";

export const MORNING_CRON = "0 23 * * *"; // UTC, next calendar day 08:00 JST.
export type ScheduleEnv = BackgroundPushEnv & { CLOUD_PUSH_SCHEDULER_ENABLED?: string; CLOUD_PUSH_NEW_DETECTION_CRON?: string };
type ScheduleDependencies = { importInput: typeof importCanonicalInput; runBatch: typeof runPersonalNotificationBatch };
const defaults: ScheduleDependencies = { importInput: importCanonicalInput, runBatch: runPersonalNotificationBatch };

export async function runScheduledPersonalNotifications(controller: { cron: string; scheduledTime: number }, env: ScheduleEnv,
  nowMs = Date.now(), dependencies: ScheduleDependencies = defaults): Promise<Record<string, string | number | boolean>> {
  if (String(env.CLOUD_PUSH_SCHEDULER_ENABLED) !== "true" || String(env.CLOUD_PUSH_MODE) !== "personal_test" ||
      env.CLOUD_PUSH_MEMBERSHIP_POLICY !== "whop_managed_discord_role" || !env.CLOUD_DB || !env.CLOUD_DISCORD_BOT_TOKEN ||
      !env.CLOUD_PUSH_TEST_DISCORD_USER_ID || !env.CLOUD_PUSH_TEST_MEMBER_ID || !env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID)
    return { status: "disabled", reason: "personal_scheduler_not_configured" };
  if (!Number.isFinite(controller.scheduledTime) || !Number.isFinite(nowMs) || controller.scheduledTime > nowMs)
    return { status: "held", reason: "invalid_schedule_time" };
  const scheduledJst = new Date(controller.scheduledTime + 9 * 3600000).toISOString();
  const actualJst = new Date(nowMs + 9 * 3600000).toISOString();
  if (scheduledJst.slice(0, 10) !== actualJst.slice(0, 10)) return { status: "suppressed", reason: "late_previous_day_schedule" };
  const business = bankBusinessDate(actualJst.slice(0, 10));
  if (business === undefined) return { status: "held", reason: "calendar_range_unavailable" };
  if (!business) return { status: "suppressed", reason: "bank_non_business_day" };
  let kind: "reminder" | "new_detection";
  if (controller.cron === MORNING_CRON) {
    if (scheduledJst.slice(11, 16) !== "08:00" || actualJst.slice(11, 13) !== "08")
      return { status: "suppressed", reason: "outside_reminder_window" };
    kind = "reminder";
  } else if (env.CLOUD_PUSH_NEW_DETECTION_CRON && env.CLOUD_PUSH_NEW_DETECTION_CRON !== MORNING_CRON && controller.cron === env.CLOUD_PUSH_NEW_DETECTION_CRON) {
    // Cadence is deliberately unspecified, never inferred from the report job.
    kind = "new_detection";
  } else return { status: "disabled", reason: "unapproved_cron" };
  try {
    const input = await dependencies.importInput(env.CLOUD_DB, CANONICAL_MANIFEST, nowMs);
    const total = { processed: 0, accepted: 0, held: 0, suppressed: 0, failed: 0 };
    let more = false, pages = 0;
    do {
      const page = await dependencies.runBatch(env, undefined, undefined, kind);
      for (const key of Object.keys(total) as (keyof typeof total)[]) total[key] += page[key];
      more = page.more;
      pages++;
    } while (more && pages < 50);
    // Aggregate-only monitoring. No subject, event, endpoint, or message logging.
    return { status: "processed", kind, imported: input.imported, ...total, pages, more, arrival_confirmed: false };
  } catch { return { status: "held", reason: "canonical_import_or_scan_failed" }; }
}
