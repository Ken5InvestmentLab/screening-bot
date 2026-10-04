# Cloud release readiness after v06 wording approval

The user approved publication after the two display changes: shorter D5/D6
labels and compact allocation quantities. Those changes are completed in the
review branch. This document records the separate access/setup release gate.
No production publish, merge, tag or deployment has been performed.

## Current review artifact cannot be deployed unchanged

The original Cloud base `0dc12cb5d8a6acd226a830d3e83ebc84e368986e` uses the existing
Discord OAuth/session/role gate. The review wrapper now supplies
`REPORT_ACCESS_CHECK` on every protected page and auth check. In `src/index.ts`
the hook accepts only `currentMembership(...).status === "paid"`; full bundles
also require both the Discord authorization and that fresh Whop decision.

`src/cloud-api.ts:39` returns `membership_not_configured` unless `CLOUD_DB`,
`WHOP_API_KEY`, account, product and paid-plan IDs exist. A missing verified
server-side Discord/Whop link returns `identity_link_required`. The checked-in
`wrangler.jsonc` deliberately contains no D1 binding or Whop policy IDs. A deploy
from this configuration without the missing setup routes existing Discord paid
role holders to free content, or denies full JSON. D1-dependent preferences
return503 without storage. This would fail the required preservation of existing
paid access; the full review Worker is therefore blocked from publication.

Production's deployed SHA, secrets/bindings and authenticated paid/free state
were not obtained. The source-base comparison is not proof that production is
running that exact source. No credentials, cookies or entitlement bypass was
used to infer it, and no unsupported claim of live configuration is made.

## Concrete setup needing separate approval

1. Identify the Cloud Worker/account and the exact existing/new D1 database;
   approve a `CLOUD_DB` binding and the two idempotent SQL migrations
   `migrations/0001_cloud_preferences.sql` and
   `migrations/0002_notification_scan_progress.sql`. Back up existing relevant
   state before any migration. No database or binding was created here.
2. Approve use/configuration of an appropriately scoped Whop credential for the
   named account, allowed product and paid-plan IDs; specify permitted one-time
   plans if needed. Store credentials only as Worker secrets. No key was read,
   generated or configured here; the pinned read contract needs live validation.
3. Verify exact Discord and Whop ownership plus membership/payment evidence for
   the existing paid cohort before populating `cloud_member_links`. No email,
   display-name or role-only inference is valid. A self-service link flow is not
   implemented. Any OAuth/link flow or authentication permission changes require
   their own explicit scope/approval and testing, not general publication consent.
4. Confirm existing paid, free, expired and period-end-cancellation fixtures on
   the actual configuration, including API failure and revocation. Test full
   pages, free pages, auth/check and settings persistence before Cloud replacement.
   Recheck the exact deployed source, prepare a rollback to that version, then
   publish only the Cloud target and verify the resulting version and rendering.

These steps must not touch main/Mega or production Discord configuration. An
approved release must use a reviewed Cloud commit, not an arbitrary branch/tag.

## Safe scope while setup is missing

The current authorized local preview, private review ZIP and draft PR remain
available with tested data/UI. They do not change existing live access.

A separate assets-only release could preserve the exact deployed OAuth/role
Worker and replace only the full/free HTML, three public scripts and assets.
It would not establish direct Whop eligibility or server-bound preferences.
Consequently this is a distinct partial-release scope, not permission to disable
the review's stricter hook or silently claim the full membership feature is live.
It needs an identified deployed version, an explicit scope decision, a reviewed
asset-serving adapter for all three scripts and an authenticated access check.
No such production subset was deployed or substituted here.

## Notifications remain unavailable

The settings UI states that delivery is in preparation and will not send, even
if preferences are saved. It distinguishes eligibility/browser permission and
preparation. Notification defaults are OFF; no permission prompt, registration,
service worker or sender is present. Morning copy says today is the confirmation
day and does not claim an actual open/close is known.

VAPID/subscription/service-worker/sender setup is independent of publishing
analytics and can stay blocked/off. Enabling it later requires separately
approved key/configuration work and explicit per-member opt-in, fresh paid
eligibility immediately before delivery, held provider errors and tested dedupe.
This publication approval creates no email collection, send, payment agreement,
new product/legal registration assertion or sales promise.

See `CLOUD_MEMBERSHIP_SETUP.md` for existing tested contracts and remaining live
integration work. Mock tests and Wrangler dry-run are not live-access proof.
