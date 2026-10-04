# Cloud release readiness after Discord-policy approval

The integrated notification-OFF candidate, fresh test results, tag release and
64bee25d rollback procedure are in [CLOUD_NOTIFY_OFF_RELEASE.md](CLOUD_NOTIFY_OFF_RELEASE.md).

For the latest D1 creation, local binding verification, observed production
configuration and pending approvals, see [CLOUD_D1_RELEASE_PREP.md](CLOUD_D1_RELEASE_PREP.md).
The earlier CLI/public-read limitations below do not imply Edge Browser Use is
unavailable. Approved D1 schema/binding are now applied in Production only;
binding-only Dashboard version is64bee25d. Edge login still renders the old report.
The new preparation code remains unpublished and push remains OFF.

The user approved keeping existing Discord OAuth + configured role and storing
settings by Discord ID. The review wrapper now preserves that report/auth-check/
full-bundle contract without requiring another login or Whop reauthentication.
Server synchronization needs an approved D1 binding; notification opt-in and
delivery remain independently fail-closed and disabled.

The authoritative migration, source contract, read-only production check results,
unverified Whop role-duration guarantee, provider schema discrepancy, concrete
approval items and no-send implementation limits are in
[CLOUD_DISCORD_PUSH_READINESS.md](CLOUD_DISCORD_PUSH_READINESS.md).

At the original handoff, Wrangler was unauthenticated and public reads returned
403. Later authorized Edge checks verified deployed version64bee25d, D1 binding,
preview isolation and existing encrypted Secret names without opening their values.
The candidate's code and new server-save API remain unpublished. Paid cohort and
role-duration guarantees remain unverified. Local tests are not actual-arrival
evidence. Publication approval does not imply permission to issue new credentials,
install secrets, change billing or send notifications.
