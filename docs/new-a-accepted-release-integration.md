# Isolated accepted-release integration

This extends local candidate 461984ad. It is a mock deployment integration, not
an installed production controller. No CI workflow, task definition, live data,
acceptance record, access policy or destination is modified by this work.

## Existing independent commit points

- `.github/workflows/weak-early-beta-report-deploy.yml` accepts the latest
  research SHA, runs guarded deployment, and checks public `/healthz`. It does
  not apply the personal PC's private continuing acceptance.
- `weak-early-beta-gate/scripts/deploy-with-provider-recovery.mjs::main()` runs
  `wrangler deploy`, which can change live traffic before the later health and
  artifact steps finish. A successful assets/script publication is not owner
  acceptance. Its recovery guard correctly refuses ambiguous-publication retry.
- `scripts/windows/weak-early-beta-jpx-checkout.mjs::prepareJpxCheckout()` can
  independently fast-forward the local research checkout. The private activation
  is not a tracked Git file and is not switched by that merge.
- `continuing_acceptance.validate_record()` correctly requires the current SHA.
  Its `apply()` transaction controls activation, locks, backup and its own audit;
  it is not a transaction with GitHub, Worker traffic and local Git HEAD.
- `weak-early-beta-daily-runner.mjs::requireRemoteHead()` separately requires
  latest remote HEAD. Retaining an old accepted checkout is not permission to
  run it against a newer research ref. The new tests explicitly preserve this
  rejection. Pair preservation and uninterrupted daily availability differ.

Thus a successful Worker deploy or checkout merge can leave a source/acceptance
mismatch. Editing the old source pin would hide the failure rather than fix it.

## Implemented connection and test boundaries

`release_acceptance.py` now distinguishes two honest evidence types:

1. Existing actually deployed-version evidence (backward compatible).
2. **Explicit private pretraffic probe** evidence: uploaded-only, 0% live traffic,
   deployment_succeeded=false, unchanged access policy, no public preview, and
   existing owner authorization with the actual protected normal response.

The second is a contract for a missing trusted host capability, not a claim that
this provider path exists. It cannot be obtained by changing the first schema
or marking an old owner observation as a new version. The host still supplies
genuine primary and independent raw observation readers. No new permissive CLI,
credential, signature or synthetic production receipt is installed.

After the existing formal issue/apply validates an isolated candidate,
`handoff_binding()` emits a minimal version/target/acceptance/activation/preparation
binding. This is an operator binding, explicitly not a platform signature.

`scripts/new-a-accepted-release.mjs` connects this binding to the **real existing
guardedDeploy function** and an explicit pair-selection adapter:

1. Acquire a common release lease and validate the known accepted current pair.
2. Require the exact private candidate proof before any CI stage operation.
3. Invoke guardedDeploy with its existing HEAD/source/provider/retry behavior.
   Recheck the proof and old pair before every stage attempt and after staging.
4. CAS-select the entire source + Worker version + acceptance + activation pair.
   Do not independently advance a runtime SHA or reuse an old acceptance hash.
5. Read the selected pair **and the authoritative terminal selection record**.
   A lost acknowledgement with confirmed COMMITTED is not repeated. Confirmed
   NOT_COMMITTED preserves the old pair. Old/new contents alone do not establish
   a terminal result; UNKNOWN preserves the lease and requires reconciliation.
6. Before a runner could start, acceptedLaunchPreflight revalidates the pair,
   invokes the existing normal launchPreflight and requireRemoteHead, checks
   canonical physical paths, then rereads the pair and release barrier.
   It never starts a process, writes D1 or sends anything.

The JS tests use private temporary atomic pair files and a fictional stage-only
adapter. The Python integration test obtains a binding using the **actual formal
acceptance functions** with synthetic trusted readers, then passes it through the
real JS coordinator and CI provider guard. Actual launchPreflight and
requireRemoteHead are exercised with private fixture files/mocked Git commands.

Failures before selection retain the old accepted pair. A committed but lost
acknowledgement is read back once. Unexpected live mutation or an unknown result
is a protected stop with a retained lease, not a claim that the old Worker is
still live and not permission to roll back or deploy again.

## One operational prerequisite: the formal acceptance/promotion bridge

The required real adapter is **a private exact-version acceptance and promotion
bridge**: it must prove the normal protected candidate response with existing
legitimate authorization before live traffic, and provide serialized, audited
selection/readback of the accepted Worker/runtime pair. This unified bridge is
not available in the current runbook/tools and is intentionally not fabricated.

In particular, current `wrangler deploy` is traffic-changing and MUST NOT be used
as the stage-only callback. Existing preview is a different environment and may
not share production D1. Initial inactive prearm does not apply to an active
service. Existing role logs, public health, CI success, owner statements and
screenshots do not supply the required exact-version protected-response proof.
Current Cloudflare + fixed Windows checkout do not share the atomic backend used
by the simulation. The real bridge must implement its equivalent protected
barrier/reconciliation contract; the mock file CAS is not evidence of that.

Without this bridge, the coordinator rejects before deployment and cannot be
adopted as a working production path. No new token, permission or public preview
has been requested. No browser retry is attempted or requested from the owner.
Normal CI entry points are unchanged; the new module has no production factory,
JSON-file approval fallback or command-line execution path.

## Preservation and local rollback

The original 461984ad commit and its 250/250 result remain preserved separately.
This integration is a separate branch/diff. Not adopting the new files restores
the prior isolated candidate; production requires no rollback because it was
never changed. Retain all preparation/selection failure records and leases in
any future real implementation; never clear them to authorize another attempt.
