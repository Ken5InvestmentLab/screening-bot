# Cloud membership and push preparation

Delivery remains disabled. Subscription registration/UI, push-only service worker,
RFC web-push sender and an unwired personal dispatch helper now exist. No actual
push, keys, credentials, DB resource, production binding or deployment was made.
Discord login/role access and Discord-ID settings follow the approved contract in
[CLOUD_DISCORD_PUSH_READINESS.md](CLOUD_DISCORD_PUSH_READINESS.md). That document
also records an unresolved provider schema discrepancy; these membership fixtures
are not proof of live paid qualification. Existing Discord notifications are unchanged.

## API contract

All routes require the existing encrypted Discord session. Only `/auth/check`
refreshes tokens. JSON is `private, no-store`; mutation requests require an exact
same-origin `Origin` header. The server derives an internal member ID from the
authenticated Discord subject; clients cannot choose another member's ID.

- `GET /api/cloud/preferences`: `{ok, preferences, membership, delivery_mode:
  "dry_run", persistence:"server"}`. `preferences` contains `max_price` (default
  `1000`; positive finite number, at most two decimal places; `null` means no cap),
  `exit_endpoint` (`d5_close` or `d6_open`), `base_shares` (default `100`,
  multiples of 100 from 100 to 1,000,000), `cost_percent` (default `0`,
  0–10 with at most two decimal places, applied to both buy and sell notionals),
  and `notifications` with `new_detection`, `reminder` booleans, both false initially.
  Stored legacy preferences gain the new defaults and drop `result`. New writes
  containing `result` are rejected; historical result candidates are suppressed
  regardless of a previously saved opt-in.
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

Missing D1 returns `503 storage_unavailable` for settings; it does not remove
existing Discord role-based report access. Full pages, full lazy bundles and
`/auth/check` keep their configured-role contract. Whop checks apply independently
to notification opt-in/registration/delivery, with no additional user login.
Free report identities still require actually verified D6 opening receipts.

## Identity and entitlement setup still required

After separately approving production setup, bind an existing/new D1 database as
`CLOUD_DB` and apply `migrations/0001_cloud_preferences.sql`, then
`migrations/0002_notification_scan_progress.sql` and
`migrations/0003_push_device_metadata.sql`. The second migration adds only
per-member scan progress and a candidate-order index; it preserves existing event
and delivery records. All three migrations are idempotent and tested in local SQLite.
The current Wrangler
configuration deliberately has no production binding or invented database ID.
Local SQL/fixture checks can run without creating cloud resources.

Configure `WHOP_API_KEY`, `WHOP_ACCOUNT_ID`, comma-separated `WHOP_PRODUCT_IDS` and
`WHOP_PAID_PLAN_IDS`; use `WHOP_ONE_TIME_PLAN_IDS` only for approved paid lifetime
plans. Keep credentials in Worker secrets, never public assets or source control.
The provider is pinned to `Api-Version-Date: 2026-09-29`, but exact-version live
responses/filters/read scopes are not verified. Current public docs show different
nested ID/period/payment formats than these fixtures. Validate and review a strict
adapter before enabling notification registration or delivery. See the readiness
document for the precise discrepancy and approval requirements.

Provision notification-only `cloud_member_links` from verified operator evidence
of existing exact Discord/Whop IDs, membership/payment, method/reference/time and
live environment. Never infer identity from email/display name or a client field.
No new Cloud account, Whop login or repeated Whop OAuth is required of users.

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

At 08:00 JST the selected-day reminder says the price is not yet final. The
adapter produces only new-detection and reminder candidates; it never produces
result notifications. D5 close receipts use 15:30 JST since 2024-11-05 (15:00
earlier), D6 open uses 09:00 JST. No D6 P/L is guessed from D5.
Price caps use the verified detection-day actual close, inclusive of the boundary;
unlimited bypasses the cap, as in the report. Missing prices never become zero.
The adapter and report share the reviewed forward-close view for 4052 on
2026-09-30 (1,149 yen). Its receipt was observed on 2026-10-04; an earlier
`--as-of` cannot claim that later observation. Canonical ledger bytes and their
source revision are preserved. Future daily runs record signal-close receipts
through `attach_forward_rows` and `refresh_forward_endpoints`, independently of
frozen D5 economics; this snapshot is not a substitute for ongoing daily capture.

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

Browser push registration, opt-out, service worker and personal-only sender now
exist locally, all disabled by default. Approved live VAPID/provider settings,
membership response verification, exact personal device and separate send approval
remain required. There is no public test-send route, scheduled handler or broad
member delivery mode. Dry-run API never invokes the sender.
