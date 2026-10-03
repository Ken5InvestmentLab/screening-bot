# Cloud membership and push preparation

This revision is **dry-run only**. It contains no push sender, scheduled handler,
email collection, email sender, or public subscription-registration endpoint.
No database, Whop app, webhook, credential, VAPID key, or deployment was created.
The existing Discord notifications in `weak_early_beta/notify.py` are unchanged.

## API contract

All routes require the existing encrypted Discord session. Only `/auth/check`
refreshes tokens. JSON is `private, no-store`; mutation requests require an exact
same-origin `Origin` header. The server derives an internal member ID from the
authenticated Discord subject; clients cannot choose another member's ID.

- `GET /api/cloud/preferences`: `{ok, preferences, membership, delivery_mode:
  "dry_run", persistence:"server"}`. `preferences` contains `max_price` (default
  `1000`; positive finite number, at most two decimal places; `null` means no cap),
  `exit_endpoint` (`d5_close` or `d6_open`), and `notifications` with
  `new_detection`, `reminder`, `result` booleans, all false initially.
- `PUT /api/cloud/preferences`: the preferences object itself is the JSON body.
  Unknown properties are rejected. Any true notification flag requires a live
  paid membership check. Authenticated users can still turn everything off after
  expiry. Failed persistence never reports success.
- `DELETE /api/cloud/push-subscriptions`: atomically turns all flags off and
  revokes every saved device subscription for this member, including after expiry.
- `POST /api/cloud/notifications/dry-run`: body `{}` only. Reads trusted server
  candidates and returns reasons/countable outcomes without identifiers, prices
  or message text. `sent` is always zero. No browser-provided candidate is accepted.
  Each call processes at most 20 rows, returning `scan.processed`, `page_limit`,
  `has_more` and `cycle_complete`. Repeat while `has_more` is true to finish the
  current cycle; the next call after completion starts a new reevaluation cycle.
  Scan positions and source keys are server-side only and never returned.

Missing D1 returns `503 storage_unavailable`. Unlinked users and missing Whop
configuration receive only the generated free HTML, even with a Discord paid role.
Raw JSON/CSV asset routes are not exposed. `/auth/check` repeats the Cloud check so
the existing page guard also removes protected content after loss of eligibility.
Mega does not supply the additional hook and retains its existing behavior.

## Identity and entitlement setup still required

After separately approving production setup, bind an existing/new D1 database as
`CLOUD_DB` and apply `migrations/0001_cloud_preferences.sql`, then
`migrations/0002_notification_scan_progress.sql`. The second migration adds only
per-member scan progress and a candidate-order index; it preserves existing event
and delivery records. Both migrations are idempotent and tested in local SQLite.
The current Wrangler
configuration deliberately has no production binding or invented database ID.
Local SQL/fixture checks can run without creating cloud resources.

Configure `WHOP_API_KEY`, `WHOP_ACCOUNT_ID`, comma-separated `WHOP_PRODUCT_IDS` and
`WHOP_PAID_PLAN_IDS`; use `WHOP_ONE_TIME_PLAN_IDS` only for approved paid lifetime
plans. Keep credentials in Worker secrets, never public assets or source control.
The read-only provider calls are pinned to REST `Api-Version-Date: 2026-09-29`.
Do not mix the current `user_id`, `account.id`, `current_period_end` fields with
legacy API field names. See [membership](https://docs.whop.com/api-reference/beta/memberships/retrieve-membership)
and [payments](https://docs.whop.com/api-reference/beta/payments/list-payments).

No Whop-link registration route is implemented. Provision `cloud_member_links`
only after independently verifying both identities, using `cloudMemberId` for its
member key. Required evidence includes Discord ID, Whop user ID, membership ID,
initial payment ID, verification method/reference/time, and environment `live`.
Never infer the link from email, display name, a Discord role, or client input.
A future self-service flow must bind the current Discord session to Whop OAuth
2.1 PKCE/state/nonce and verify `userinfo.sub`; only `openid` is needed for identity.
[Official OAuth contract](https://docs.whop.com/developer/guides/oauth).

Eligibility requires matching owner/account/product/paid plan, active membership,
an unexpired period, and a current-period positive paid payment that is not fully
refunded. The provider follows renewal payments; the original link evidence is
not rewritten. Completed memberships qualify only on allowed one-time plans.
Trial, free, test, expired, past_due, unknown and unverified identities fail closed.
An active cancellation-at-period-end remains valid until period end. API errors,
429 and timeouts hold notifications; Discord's role-cache grace is not used as
Whop eligibility. No positive Whop response is cached across requests.

Conservatively, payments before the returned period start are held for review;
this may need an explicit policy for prepaid renewals before production use.
Live Whop credentials and real account fixtures have not been exercised here.

## Canonical candidates and delivery receipts

`scripts/build-notification-events.py --ledger <private-ledger.csv> --output
<private-output.json> --as-of <timezone-aware-ISO>` reads the ledger without
modifying it or connecting to a provider/database. It excludes reconstructions,
2022 and future detection dates. Signal prices and D6 prices use the exact receipt
verifiers from `weak_early_beta.endpoint_receipts`. D5 uses frozen actual economics
plus the new `d5_price_observed_at`; old D5 rows without that acquisition time stay
unconfirmed. `updated_at` is never repurposed as an acquisition timestamp.

The same `bank_calendar` supplies +5/+6 dates, including holidays and year changes.
Conflicting stored dates stop export. The private DTO maps status `verified`,
observation time and source SHA-256 into the Worker. Events must identify adapter
`cloud-ledger-v1` and match the server row's source-ledger SHA-256. Upload/import of
these private candidates to D1 is a remaining integration step, not a public API.

At 08:00 JST the selected-day reminder says the price is not yet final. Result
notifications require a verified positive real price, source digest and a valid
observation time after the relevant market event. D5 close uses 15:30 JST since
2024-11-05 (15:00 earlier), D6 open uses 09:00 JST. No D6 P/L is guessed from D5.
Price caps use the verified detection-day actual close, inclusive of the boundary;
unlimited bypasses the cap, as in the report. Missing prices never become zero.

Detections are aggregated by signal date + stock across modes; inconsistent
overlapping receipts stop export. The delivery key is member + unique stock
detection + notification kind + endpoint + session.
Changing a price cap does not create another key. The unique SQL key and guarded
upsert prevent simultaneous repeat eligibility. Held events can be reevaluated;
dry-run-eligible events deduplicate. Dry-run does not mark delivery as sent.
Candidate scans seek forward by `(available_at, source_event_key)` with a fixed
cutoff for each cycle. A persisted per-member cursor prevents the newest 100 rows
from starving the rest; the 21st fetched row is only lookahead for the 20-row page.
The cursor advances after successful receipt writes using a version comparison,
so concurrent or delayed requests cannot rewind or skip a page. Interrupted
requests retry the same page safely through the delivery unique-key guard.
At cycle end the cursor wraps: held/suppressed candidates can be reevaluated after
eligibility, preference, time or price-evidence changes. Newly imported backdated
rows are reached by the next cycle. Malformed private candidates are held and do
not prevent the cursor from reaching later rows. No unbounded request scan or
client-controlled cursor is exposed.
A future sender must use a separate attempt/dispatch state, repeat a fresh
entitlement check immediately before each attempt, honor unsubscribe, and disable
dead push endpoints. It must never mistake existing dry-run records for sent ones.

## Webhook and push deployment remains disabled

The schema reserves webhook IDs for deduplication, but there is no webhook handler.
Before enabling one, pin v1 and the same dated schema, verify the raw body signature
and timestamp, persist unique `webhook-id`, then reconcile current API state.
`membership.updated` covers status and period-end cancellation changes. Delivery
is duplicated and unordered; never restore access from an older event.
[Webhook specification](https://docs.whop.com/developer/guides/webhooks),
[membership.updated](https://docs.whop.com/api-reference/beta/memberships/membership-updated).

Browser push still needs an approved VAPID setup, service worker, explicit browser
opt-in and validated subscription registration. Whop push would instead need its
experience and notification permission. Neither is enabled by this revision.
There is no setting or environment flag that turns dry-run into actual sending.
