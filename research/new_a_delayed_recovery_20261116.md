# One stopped New A session: formal delayed recovery

This entry is limited to the stopped 2026-11-16 New A run which began at
2026-11-16T13:28:10.435Z. Admission is on the actual 2026-11-17 JST day only.
It does not change the 17:00 schedule, strategy, trading rules, owner gate,
notification destinations, or the ordinary next-day route. Actual observations
remain Nov17; the target session remains Nov16. Delayed target signals are
separate from realtime LIVE signals and from ineligible historical catchup.

The host issues a private contract only after independently reading the owner's
primary instruction, stop evidence, complete existing-channel histories, D1
pointer and target-day absence, retained request receipts, and stable prior
source/quality hashes. These are local operator attestations, not product or
platform signatures. Authenticated-nonowner rejection remains unmeasured/false.

Only the normal task entry consumes the host-issued record and a finite,
new-source-bound continuing-acceptance application. It holds task-entry.lock,
claims the original receipt once globally, preserves its exact bytes and lock,
archives that exact stale lock, and runs the unchanged normal launch preflight.
The source upgrade retains active/external flags, target and authentication pins
and requires the completed predecessor application chain and fresh acceptance
observations on the new release. Failure restores the original lock when its
ownership is still certain; immutable claims are never automatically erased.
The old 19:28 preflight receipt is not altered or reused.

The existing daily runner then owns its normal lock. Its executing context binds
PID creation time, real start time, source HEAD, target, claim and archived bytes.
A verified replay copy preserves the original 47 raw receipts/packets. Normal
source validation, no-network-fallback replay rules and exact target freshness
are mandatory. No date or cache status is relabelled. Small phase logs identify
normalization/revision calls without reading or logging arguments or prices.

Invocation (paths contain references, never credentials):

    node scripts/windows/weak-early-beta-task-entry.mjs <existing-config> cloud-2 --start --delayed-recovery <host-issued-private-record> --acceptance-application <host-issued-private-application>

There is no generic approval-issuing CLI. Direct --as-of or a flag alone cannot
create an executing context. The network guard still uses the real execution
day. Ordinary Nov17 admission has no delayed-reference requirement.

Publication uses the existing publisher with exact old revision/dataset checks,
atomic READY/pointer CAS and verified readback. Notification admission checks the
same resulting pointer, source and snapshot, and uses the existing outbox and
existing destinations. Uncertain sends are never reset or automatically retried.
Zero detections retain the existing rule of no signal or summary message.

Rollback and uncertain outcomes:
- Before external effects, retain all claim/application/stop receipts. Restore
  the prior code through the ordinary branch/tag release only, and restore the
  exact previous activation bytes only after CAS/lock/PID checks under normal
  arbitration. The historical application chain must match the restored HEAD.
- A spawned/unknown process, changed pointer, data write, or uncertain notification
  requires readback and formal reconciliation. Do not clear claims/locks, reset
  outbox state, replay a completed date, or resend notifications as rollback.
- Existing publisher rollback requires its own explicit target and revision
  checks; it is not automatically invoked by this recovery entry.

Private approval texts, host measurements, SQL, retained prices, credentials,
activation records and operation receipts stay outside Git and public assets.
