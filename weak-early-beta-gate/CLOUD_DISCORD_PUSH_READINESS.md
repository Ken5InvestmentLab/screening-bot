# Discord access, synchronized settings and personal push preparation

2026-10-04 followup. This document supersedes the Whop-for-every-report proposal
in earlier review documents. Nothing here is deployed or sent.

## Approved account contract

Keep existing Discord OAuth and `DISCORD_ALLOWED_ROLE_IDS` for report access;
there is no Cloud account, Whop login or extra consent/login screen. The session's
verified Discord `sub` is hashed as `SHA256("cloud-member:" + sub)` to form the
existing server preference key. Names, email and client-supplied IDs are never
used. Any configured-role account retains its full pages, `/auth/check` and full
lazy bundles, even when Whop settings or a membership link are missing. A logged
out or role-less user retains the existing denied/free behavior. Free artifacts
still expose only identities with an actually verified D6 opening receipt.

The source contract reads Discord `/users/@me/guilds/{guild}/member` using the
existing OAuth token. Normal reports retain the 90-second role cache and up to
600-second 429 grace. Added optional `reportIdentity(..., true)` obtains fresh
roles and accepts neither cache nor grace. It does not refresh tokens or write
cookies; `/auth/check` continues to serialize token refresh. All old callers use
the original behavior. This shared-source export was regenerated through sync,
not patched into a generated copy; main was not changed.

GET/PUT preferences use the current session, private/no-store responses and
same-origin mutation checks. Changing price cap, D5/D6, share count and costs with
both notifications OFF requires D1, not Whop credentials or a new login. Another
device using the same Discord ID reads those same settings. Existing display-only
theme/font/row choices remain device preferences. Without D1, the API returns
503; browser fallback is not described as server synchronization.

## Paid role versus proven paid duration

Source inspection proves role access; it does NOT prove that the deployed role is
granted only to paid Whop plans or removed at expiration/refund/revocation. Live
Whop app-to-product-to-role mapping, manual grants, trial/free/test grants,
end-of-period cancellation versus immediate removal, bot permissions and measured
removal lag all need an authorized read-only check. A fresh Discord role alone
cannot prove payment while that chain is unverified.

Therefore registration/opt-in and internal delivery currently additionally use
the existing fail-closed Whop payment checker. Missing link/config, expired/test,
provider429/error and uncertainty hold delivery. Link migration must consume
existing exact Discord-to-Whop identifiers from verified operator evidence or
existing authenticated integration receipts. Do not ask users to create another
account or repeat Whop OAuth, and do not infer links from email/display name.
`dual_oauth` remains a legacy schema value, not a new login requirement.

An important provider blocker was found during this followup: current official
[membership documentation](https://docs.whop.com/api-reference/memberships/retrieve-membership)
shows nested company/user/product/plan and `renewal_period_*`, while the earlier
2026-09-29 fixture adapter expects account/user_id/product_id/plan_id and
`current_period_*`. Official [payment documentation](https://docs.whop.com/api-reference/payments/retrieve-payment)
also shows nested company/membership and numeric amounts, whereas the fixture uses
account_id/membership_id and amount/currency objects. The pinned provider response,
query filters and required read scopes have NOT been validated against production.
Do not enable registration/delivery until sanitized exact-version responses are
tested and an unambiguous adapter is reviewed. Existing role access/settings do
not depend on this unresolved adapter. No live paid eligibility is claimed.

## Production reads actually attempted

Existing Wrangler `whoami`: unauthenticated, no token/secret value printed.
Unauthenticated GET to the Cloud Worker `/auth/check`, interactions/scenarios
scripts and preferences: all403. No cookies/credentials/user-agent substitution,
alternate authenticated route, login or retry to bypass refusal was attempted.
There is no exposed Cloudflare/Whop read connector in this executor. Deployed
version, bindings, secret names/values and actual paid cohort remain unverified.
Checked-in Wrangler has no D1 binding; that is source evidence, not a statement
that the live Worker has no database. Private sanitized QA receipts are outside
the published bundle. Public documentation reads do not access customer records.

## Local implementation now present

- `/api/cloud/push-config`: private own-device hashes/opaque IDs and public VAPID
  key only when registration is configured and paid qualification is proven.
- POST subscriptions: explicit opt-in, fresh Discord role, Whop check, exact HTTPS
  provider-origin allowlist, validated P256/auth, endpoint owner lock, atomic
  subscription/metadata writes. This never turns notification choices ON.
- DELETE one device scopes revocation to current session even after expiry;
  existing DELETE all turns both member notification choices OFF.
- Browser registers/subscribes only on its explicit button, rolls a newly created
  browser subscription back on server failure, and uses no localStorage. Loading
  pages performs only config/read-existing-registration operations.
- Push-only service worker has no fetch/offline/cache handler; fixed same-origin
  click destination; opaque notification tag; no signal identifier in lock-screen
  payload. Only generic new detection and 08JST confirmation-day copy is supported.
  Historical result notification candidates remain suppressed as in v06.
- RFC8291 AES128GCM and RFC8292 VAPID ES256 sender, provider redirect refusal,
  bounded TTL/timeout, provider acceptance distinguished from actual arrival.
- Internal `dispatchPersonalCandidate` has NO public API, cron or scheduler entry.
  It reads trusted canonical candidates and exact chosen member/device, rechecks
  fresh Discord role, Whop, preferences and active device before send, reserves a
  unique event/device receipt, and never auto-retries preparing/accepted/unknown
  outcomes. A held reservation also needs operator review before replay.
- `0003_push_device_metadata.sql` creates new tables idempotently; it does not
  rewrite dry-run receipts, existing membership links, prefs or frozen economics.

All flags are absent/off in checked-in Wrangler. `CLOUD_PUSH_MODE=personal_test`
only supports one exact server member and subscription; there is no broad-member
mode. An approved key pair/HTTPS subject and exact provider-origin allowlist are
required. Browser config always reports `delivery_available:false`. No test-send
button or scheduled delivery is wired before the user's real device is identified.
Fixed published RFC test keys are isolated fixtures; tests prohibit key generation
and use mocked transport. No production key pair, credentials, DB or push was made.
Standards: [RFC8291](https://www.rfc-editor.org/rfc/rfc8291),
[RFC8292](https://www.rfc-editor.org/rfc/rfc8292),
[RFC8030](https://www.rfc-editor.org/rfc/rfc8030).

## Concrete approvals/setup for the parent

1. Authorize a read-only connection to the named existing Cloudflare account/Worker
   and existing Whop/Discord integration. Check deployed version/rollback, binding
   names and exact role/product/paid-plan mapping; never print credential values.
2. Select an EXISTING approved D1 if available, approve only this Cloud Worker's
   `CLOUD_DB` binding and migrations0001–0003 after backup/local validation. If no
   database exists, new-resource/free-or-paid terms require a separate decision;
   do not create a billed database or change main/other Worker bindings.
3. Deploy report/preferences with unchanged Discord client/guild/roles/session
   secret/scopes. First compare old/new access for existing paid-role, ordinary
   role, no-role, expired-role, logout and provider-error fixtures. Count existing
   paid cohort preservation before switching, keep rollback version. No member
   links required for viewing or notification-OFF settings. No reset of defaults,
   preferences, membership periods or identity migration on browser login.
4. For push only, approve use of existing narrowly scoped provider reads and exact
   verified operator links; validate actual versioned response shapes before any
   activation. New credential issuance/read-scope changes remain separately
   blocked. If verified existing role integration is chosen as authoritative paid
   proof instead, review that policy and revocation guarantees explicitly; no
   silent fallback from failed Whop calls to a cached role.
5. Approve use/provisioning of VAPID pair, HTTPS subject, device-specific provider
   origins and a single member/subscription test-mode configuration. Key generation
   and production secret registration are separate operations, not implied by UI
   implementation approval. Never put private keys/endpoints/auth tokens in Slack.
6. Parent is collecting personal device/OS/browser/install/permission details.
   After explicit opt-in, approve two labeled personal tests (new-detection and
   confirmation-day); create no fabricated stock event. Verify payment/role again
   immediately before dispatch, no other members. Record provider receipt and
   user's actual arrival separately, then disable mode/revoke that device.

Remaining implementation before general service: approved background identity
checking (current helper uses user's OAuth session), trusted canonical event job
integration, 08JST scheduler execution/holiday contract, reviewed retry/lease and
reconciliation operations, webhook invalidation/versioned provider adapter and
monitoring. No unsupported promise of unattended delivery after the tab closes.
No merge/deploy/cloud-deploy tag or real-arrival test was performed.
