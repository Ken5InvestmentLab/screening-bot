// Cloud-only policy. No network calls, credentials, or notification sender here.
export const WHOP_API_VERSION = "2026-09-29";
export type ExitEndpoint = "d5_close" | "d6_open";
export type NotificationKind = "new_detection" | "reminder" | "result";
export type Preferences = {
  max_price: number | null;
  exit_endpoint: ExitEndpoint;
  base_shares: number;
  cost_percent: number;
  notifications: Record<"new_detection" | "reminder", boolean>;
};
export const DEFAULT_PREFERENCES: Preferences = {
  max_price: 1000,
  exit_endpoint: "d6_open",
  base_shares: 100,
  cost_percent: 0,
  notifications: { new_detection: false, reminder: false },
};
export const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function validatePreferences(value: unknown, migrateStored = false): Preferences {
  if (!isObject(value) || Object.keys(value).some(k => !["max_price", "exit_endpoint", "base_shares", "cost_percent", "notifications"].includes(k))) {
    throw new Error("invalid_preferences");
  }
  const cap = value.max_price;
  const decimalPlaces = (number: number): number => {
    const [mantissa, exponent = "0"] = String(number).toLowerCase().split("e");
    return Math.max(0, (mantissa.split(".")[1] ?? "").length - Number(exponent));
  };
  // Reject excessive precision; never silently round the user's price boundary.
  if (cap !== null && (typeof cap !== "number" || !Number.isFinite(cap) || cap <= 0 ||
    decimalPlaces(cap) > 2)) {
    throw new Error("invalid_max_price");
  }
  if (value.exit_endpoint !== "d5_close" && value.exit_endpoint !== "d6_open") throw new Error("invalid_exit_endpoint");
  const shares = value.base_shares ?? 100, cost = value.cost_percent ?? 0;
  if (typeof shares !== "number" || !Number.isSafeInteger(shares) || shares < 100 || shares > 1000000 || shares % 100) throw new Error("invalid_base_shares");
  if (typeof cost !== "number" || !Number.isFinite(cost) || cost < 0 || cost > 10 || decimalPlaces(cost) > 2) throw new Error("invalid_cost_percent");
  const n = value.notifications;
  const keys = ["new_detection", "reminder"];
  if (!isObject(n) || Object.keys(n).some(k => !keys.includes(k) && !(migrateStored && k === "result" && typeof n.result === "boolean")) || keys.some(k => typeof n[k] !== "boolean")) {
    throw new Error("invalid_notifications");
  }
  return { max_price: cap as number | null, exit_endpoint: value.exit_endpoint, base_shares: shares, cost_percent: cost,
    notifications: { new_detection: n.new_detection as boolean, reminder: n.reminder as boolean } };
}

export type VerifiedMemberLink = {
  member_id: string;
  discord_user_id: string;
  whop_user_id: string;
  membership_id: string;
  payment_id: string;
  environment: string;
  verified_at: string;
  verification_method: string;
  evidence_reference: string;
  revoked_at: string | null;
};
export type MembershipPolicy = {
  account_id: string;
  product_ids: string[];
  paid_plan_ids: string[];
  one_time_plan_ids: string[];
};
export type MembershipDecision = {
  status: "paid" | "free" | "unverified" | "unavailable";
  reason: string;
  checked_at: string;
};
const timestamp = (value: unknown): number => typeof value === "string" ? Date.parse(value) : NaN;
const idOf = (value: unknown): unknown => isObject(value) ? value.id : undefined;

export function evaluateMembership(
  membership: unknown, payment: unknown, link: VerifiedMemberLink,
  policy: MembershipPolicy, nowMs = Date.now(),
): MembershipDecision {
  const decision = (status: MembershipDecision["status"], reason: string): MembershipDecision =>
    ({ status, reason, checked_at: new Date(nowMs).toISOString() });
  if (link.environment !== "live") return decision("free", "test_account");
  if (link.revoked_at) return decision("free", "link_revoked");
  if (!["dual_oauth", "verified_operator"].includes(link.verification_method) || !link.evidence_reference ||
    !Number.isFinite(timestamp(link.verified_at)) || timestamp(link.verified_at) > nowMs) {
    return decision("unverified", "identity_link_unverified");
  }
  if (!isObject(membership) || !isObject(payment)) return decision("unavailable", "invalid_provider_response");
  if (membership.id !== link.membership_id || membership.user_id !== link.whop_user_id ||
    idOf(membership.account) !== policy.account_id ||
    !policy.product_ids.includes(String(membership.product_id)) || !policy.paid_plan_ids.includes(String(membership.plan_id))) {
    return decision("free", "membership_scope_mismatch");
  }
  const oneTime = policy.one_time_plan_ids.includes(String(membership.plan_id));
  if (membership.status !== "active" && !(membership.status === "completed" && oneTime)) {
    return decision("free", "membership_not_paid_active");
  }
  const end = timestamp(membership.current_period_end);
  if (membership.current_period_end !== null && !Number.isFinite(end)) return decision("unavailable", "invalid_period_end");
  if (Number.isFinite(end) && end <= nowMs) return decision("free", "membership_expired");
  if (!oneTime && !Number.isFinite(end)) return decision("unavailable", "period_end_required");
  // A cancellation request remains eligible until its paid period actually ends.
  // A paid plan alone is insufficient: reject free grants and refunded payments.
  if (payment.id !== link.payment_id || payment.membership_id !== link.membership_id ||
    payment.account_id !== policy.account_id || idOf(payment.user) !== link.whop_user_id ||
    payment.status !== "paid" || !isObject(payment.total) || !isObject(payment.refunded_amount)) {
    return decision("free", "payment_not_verified");
  }
  const money = (value: unknown): number =>
    typeof value === "number" ? value : typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value) ? Number(value) : NaN;
  const amount = money(payment.total.amount), refunded = money(payment.refunded_amount.amount);
  if (!Number.isFinite(amount) || !Number.isFinite(refunded) || amount <= 0 || refunded < 0 || refunded >= amount ||
    !payment.total.currency || payment.total.currency !== payment.refunded_amount.currency) return decision("free", "payment_not_paid");
  const paidAt = timestamp(payment.paid_at), periodStart = timestamp(membership.current_period_start);
  if (!Number.isFinite(paidAt) || paidAt > nowMs) return decision("unavailable", "payment_time_unverified");
  if (!oneTime && (!Number.isFinite(periodStart) || periodStart > nowMs || paidAt < periodStart)) {
    return decision("unverified", "current_period_payment_required");
  }
  return decision("paid", "verified_paid_membership");
}

export type PriceObservation = {
  date: string;
  actual_price: number | null;
  status: string;
  fetched_at: string | null;
  source: string | null;
};
export type NotificationEvent = {
  signal_id: string;
  kind: NotificationKind;
  detection_date: string;
  signal_actual_close: number | null;
  signal_price_status: string;
  endpoints: Record<ExitEndpoint, PriceObservation>;
};
export type NotificationDecision = {
  status: "would_send" | "suppressed" | "held";
  reason: string;
  event_key: string;
  message: string | null;
};

export function evaluateNotification(
  event: NotificationEvent, preferences: Preferences, membership: MembershipDecision,
  nowMs = Date.now(),
): NotificationDecision {
  const endpoint = event.endpoints[preferences.exit_endpoint];
  const key = [event.signal_id, event.kind, event.kind === "new_detection" ? "detected" : preferences.exit_endpoint,
    event.kind === "new_detection" ? event.detection_date : endpoint?.date].join(":");
  const result = (status: NotificationDecision["status"], reason: string, message: string | null = null): NotificationDecision =>
    ({ status, reason, event_key: key, message });
  // Historical result candidates remain in the delivery ledger for auditing.
  // This feature has been removed; no preference can opt back into it.
  if (event.kind === "result") return result("suppressed", "result_notifications_removed");
  if (!preferences.notifications[event.kind]) return result("suppressed", "notification_off");
  if (membership.status !== "paid") return result("held", membership.reason);
  const checkedAt = timestamp(membership.checked_at);
  if (!Number.isFinite(checkedAt) || checkedAt > nowMs || nowMs - checkedAt > 30000) return result("held", "membership_check_stale");
  // The same verified detection-day real close is used by reports, CSV and alerts.
  const close = event.signal_actual_close;
  if (preferences.max_price !== null && (event.signal_price_status !== "verified" ||
    typeof close !== "number" || !Number.isFinite(close) || close <= 0)) return result("held", "signal_price_unverified");
  if (preferences.max_price !== null && close! > preferences.max_price) return result("suppressed", "over_price_limit");
  if (event.detection_date.slice(0, 4) === "2022") return result("suppressed", "excluded_research_year");
  if (event.kind === "new_detection") return result("would_send", "new_detection", "新しい検出があります。");
  if (!endpoint || !/^\d{4}-\d{2}-\d{2}$/.test(endpoint.date)) return result("held", "endpoint_date_missing");
  const jst = new Date(nowMs + 9 * 60 * 60 * 1000).toISOString();
  if (event.kind === "reminder") {
    if (jst.slice(0, 10) !== endpoint.date || jst.slice(11, 13) !== "08") return result("suppressed", "outside_reminder_window");
    return result("would_send", "confirmation_day_reminder", "今日は、設定した確定日です");
  }
  return result("suppressed", "unsupported_notification");
}
