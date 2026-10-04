// Explicit adapter for the documented nested v1 response. No shape guessing,
// account-wide payment scan, credential provisioning, or identity inference.
import { evaluateMembership, isObject, type MembershipDecision, type MembershipPolicy, type VerifiedMemberLink } from "./cloud-membership";

const id = (value: unknown, prefix: string): string => {
  if (!isObject(value) || typeof value.id !== "string" || !new RegExp(`^${prefix}_[A-Za-z0-9]+$`).test(value.id)) throw new Error("invalid_provider_shape");
  return value.id;
};
const period = (value: unknown): string | null => {
  if (value === null) return null;
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) throw new Error("invalid_provider_shape");
  return value;
};
export function evaluateNestedMembership(membership: unknown, payment: unknown,
  link: VerifiedMemberLink, policy: MembershipPolicy, nowMs = Date.now()): MembershipDecision {
  const hold = (reason: string): MembershipDecision => ({ status: "unavailable", reason, checked_at: new Date(nowMs).toISOString() });
  try {
    if (!isObject(membership) || !isObject(payment)) return hold("invalid_provider_response");
    // Refuse mixed old/new contracts rather than choosing a favourable alias.
    if (["account", "user_id", "product_id", "plan_id", "current_period_start", "current_period_end"].some(k => k in membership) ||
        ["account_id", "membership_id"].some(k => k in payment)) return hold("ambiguous_provider_schema");
    const company = id(membership.company, "biz"), user = id(membership.user, "user");
    const product = id(membership.product, "prod"), plan = id(membership.plan, "plan");
    if (typeof membership.id !== "string" || typeof membership.status !== "string" || typeof membership.cancel_at_period_end !== "boolean" ||
        typeof membership.payment_collection_paused !== "boolean") return hold("invalid_provider_response");
    if (membership.payment_collection_paused) return hold("payment_collection_paused");
    if (id(payment.company, "biz") !== company || id(payment.user, "user") !== user ||
        id(payment.membership, "mem") !== membership.id || id(payment.product, "prod") !== product || id(payment.plan, "plan") !== plan) return hold("payment_scope_mismatch");
    if (typeof membership.currency !== "string" || !/^[a-z]{3,8}$/.test(membership.currency) || payment.currency !== membership.currency ||
        typeof payment.total !== "number" || !Number.isFinite(payment.total) || typeof payment.refunded_amount !== "number" || !Number.isFinite(payment.refunded_amount)) return hold("invalid_payment_amount");
    // Partial refunds/disputes require an approved policy; never silently pass.
    if (payment.substatus !== "succeeded" || payment.refunded_amount !== 0) return hold("payment_refund_or_dispute_requires_review");
    return evaluateMembership({ id: membership.id, user_id: user, account: { id: company }, product_id: product, plan_id: plan,
      status: membership.status, current_period_start: period(membership.renewal_period_start), current_period_end: period(membership.renewal_period_end) },
      { id: payment.id, membership_id: membership.id, account_id: company, user: { id: user }, status: payment.status,
        total: { amount: payment.total, currency: payment.currency }, refunded_amount: { amount: payment.refunded_amount, currency: payment.currency }, paid_at: period(payment.paid_at) },
      link, policy, nowMs);
  } catch { return hold("invalid_provider_response"); }
}
