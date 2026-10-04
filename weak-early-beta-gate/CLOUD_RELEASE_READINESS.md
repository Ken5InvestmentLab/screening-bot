# Cloud release readiness after Discord-policy approval

The user approved keeping existing Discord OAuth + configured role and storing
settings by Discord ID. The review wrapper now preserves that report/auth-check/
full-bundle contract without requiring another login or Whop reauthentication.
Server synchronization needs an approved D1 binding; notification opt-in and
delivery remain independently fail-closed and disabled.

The authoritative migration, source contract, read-only production check results,
unverified Whop role-duration guarantee, provider schema discrepancy, concrete
approval items and no-send implementation limits are in
[CLOUD_DISCORD_PUSH_READINESS.md](CLOUD_DISCORD_PUSH_READINESS.md).

Existing Wrangler is unauthenticated; all attempted public Cloud reads returned
403. Deployed version, bindings, secrets and paid cohort were not verified. No
bypass, new credential, permission change, DB resource, merge, tag or deployment
was performed. Current local previews and mock tests are not live-access or
actual-arrival evidence. Publication approval does not imply permission to issue
new credentials, install secrets, change billing or send notifications.
