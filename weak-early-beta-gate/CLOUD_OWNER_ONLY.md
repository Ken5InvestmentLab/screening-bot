# Cloud owner-only viewing switch

Scope: Cloud Worker only. No Discord roles, memberships, D1 data, subscriptions,
notification settings, or screening data are deleted or changed.

Runtime settings (Cloudflare Worker environment, not Git):
- CLOUD_OWNER_ONLY_ENABLED=true
- CLOUD_OWNER_DISCORD_ID=<owner-confirmed Discord user ID>

Set the owner ID before enabling. keep_vars preserves runtime settings on later
normal deployments. Missing/malformed ID while enabled fails closed. An invalid
nonempty enabled value also fails closed. To restore the previous access policy,
set CLOUD_OWNER_ONLY_ENABLED=false. Do not remove or change any membership.

All requests pass the owner gate before full/free HTML, JSON, API, scripts or
images. Only login/callback/logout, the content-free auth guard script, robots,
and liveness are public. Existing role authorization remains downstream for the
owner. Identity comes from authenticated encrypted session bytes, never headers,
query parameters, a display name, or a browser-submitted ID. OAuth access-token
expiry does not discard signed identity so the owner can still refresh normally.

Existing clients: a nonowner /auth/check receives 401; older free-page guards
therefore follow login and reach a denied page. Updated guards immediately
navigate to /private on the dedicated response header. Data already downloaded
cannot be recalled; offline screenshots, exports and already-held page content
remain outside the reach of server-side access control. Hidden tabs enforce the
restriction on their next request/visibility check, not by remote erasure.

Verification: synthetic-session tests cover owner/other/anonymous for all route
classes, tampering, expired sessions, expired OAuth token refresh access,
misconfiguration, and restoring the prior public/free policy. Full production
verification additionally requires a real owner login and unauthenticated checks
after deployment; never synthesize a production session or extract browser cookies.

Deployment: use the existing dedicated cloud-deploy-* guarded workflow only once
GitHub transmission and production deployment are approved. Do not push runtime
owner ID, credentials, logs, acquired CSV, or this execution's test outputs.
