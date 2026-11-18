# Isolated V2 / accepted-handoff connection

This patch connects existing isolated APIs. It supplies no real host/provider
adapter, observes no production response and changes no production acceptance,
traffic, schedule, credentials, permissions, D1 data or notification.

`release_acceptance` now binds trusted dependency/Worker readers to each actual
repository and carries them through baseline/unchanged, candidate dry-run and
issue, finite apply, ready readback and handoff binding. V2 dry-run checks the
distinct owner decision/schema/identity digest and original raw HTTP reader.
V1 defaults and exact-source behavior are retained. No file/env/CLI factory
turns assertions into these trusted readers.

An accepted V2 anchor and current runtime HEAD are separate. The operating
baseline is fully validated against current readers and receipt lineage. Only
then is its original anchor used to verify the historical predecessor audit in
the candidate. An old V1 record for another HEAD is still rejected; historical
validation is not an alternative to current operating validation.

`runtime_binding` supplies a typed proof only after full current V2 validation.
The JS `acceptedLaunchPreflight` can use that proof to check the actual receipt-
advanced HEAD with ordinary preflight and latest-remote-HEAD checks while keeping
the accepted anchor immutable. It rejects a V1 boolean/partial proof for V2,
identity/target/repository changes and races. It starts nothing.

## Explicit unresolved transaction boundary

AH V2 initial acceptance requires a genuinely observed normal production URL,
single 100% deployment and exact actual Worker version/deployment/artifact. The
existing JS release transaction accepts only private pretraffic proof. These
are distinct evidence types and are not interchangeable.

In the private-probe case, Python V2 preparation rejects at
`execution_identity.checked_worker` before issuing/applying an acceptance. If a
V2 handoff binding reaches JS, it rejects explicitly with
`V2_NORMAL_PROOF_PRETRAFFIC_CONTRACT_UNAVAILABLE` before staging or selection.
The original accepted pair and its records are preserved. No V2 successful
pretraffic fixture or new two-phase proof contract is invented here.

The Python `ALREADY_DEPLOYED_VERSION` path is a separate API. Its existing
candidate issue/finite-apply/ready calls can be wired and exercised with mocked
genuine-normal-response reader shapes. That local API-wiring test is not proof
of a pretraffic deployment or an atomic real provider/runtime selection. Its V2
binding remains unacceptable to the pretraffic JS transaction.

The tests retain the existing V1 selection success, definitive failure,
concurrency, partial/unknown outcome and lease-preservation cases. They also
exercise a fully validated existing V2 runtime across receipt-only commits, not
a fabricated new V2 pretraffic promotion.

## What remains

Actual trusted effective-loader metadata and current normal responding
Worker/artifact readers are still unimplemented/unavailable here. Existing
blocked observations must not be retried or bypassed. A concrete formal method
must reconcile the candidate-proof and normal-proof phases before this JS
transaction can promote V2. This patch does not assert that a new two-phase
contract is the only possible formal solution.

A new daily provider version/deployment remains a new-acceptance boundary, even
for identical source/artifact. Existing distinct-source application and
selection requirements remain unchanged; same-source reacceptance is not
silently enabled. Ordinary runtime launch/publish/notify CLIs have no installed
trusted V2 adapter and stay closed without one. No Nov17 recovery is performed.

All experiments use temporary Git repositories and synthetic readers. Restore
the isolated candidate by reverting its local integration commit; preserve AH,
AA and operational source refs and their previous audit records. No production
rollback is implemented or performed.
