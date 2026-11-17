# Accepted candidate handoff — isolated implementation, not a production switch

## Why the current release stops

The current `cloud-deploy-*` workflow publishes first, then probes public
`/healthz`. It neither obtains owner document/API observations nor applies
`continuing_acceptance`. Updating the daily checkout separately invalidates its
source-bound acceptance. This is a correct rejection, not a stale hash to edit.

There is already a formal fix for an observed code-only upgrade:
`continuing_acceptance.issue()` and `apply(previous_acceptance=...)`. They require
the actual primary, owner/anonymous/direct observations, unchanged authentication
hashes and target, finite management authority, normal preflight, locks, a CAS
baseline, immutable predecessor audit, backup and completed application readback.
Those validators are unchanged by this candidate.

## What the new module does

`weak_early_beta.new_a.release_acceptance` prepares an **independently stored
candidate** and never updates the operating checkout. Default `dry_run=True`
does not issue or apply anything, even in the candidate.

1. Validate the operating copy's real, completed current acceptance. Already
   mismatched or revoked operating state is refused, not repaired by relabelling.
2. Require separate non-overlapping directories, a distinct exact candidate SHA,
   the same Worker/DB and authentication hashes, and a byte-identical private
   activation plus retained predecessor audit in the candidate. No credential or
   daily DB copying is required or implemented.
3. Read independently verified deployment metadata and actual host observations.
   Bind source, target, provider version, deployment time, raw receipt hashes,
   owner identity, document/API 200 and the authorized A_BASE response. Preserve
   anonymous/direct requirements and explicitly unmeasured nonowner status.
4. Review the actual primary and exact continuing scope. A message is not a
   server response. No generic JSON approval-file CLI or platform-signature claim
   is introduced. Readers are trusted host integrations, not self-authenticating
   dictionaries; local hashes alone prove no identity or network status.
5. Only explicit non-dry-run preparation invokes the **existing** issue/apply in
   the candidate. Serialize preparations and preserve failed/interrupted attempt
   records. Revalidate the candidate, deployment identity and operating baseline.
6. Produce immutable `ready.json`. `verify_ready()` rechecks the stored receipt,
   normal formal application, finite handoff deadline, unchanged current baseline
   and exact provider version. It never promotes, deploys or launches anything.

A same-version fresh provider observation may have a later observation time and
new transport receipt hash. A different version cannot pass. An application
failure can leave a candidate-only audit or partial application; preserve it and
reconcile explicitly. Do not retry by deleting its `started.json`/grant/claim.
The operating copy remains byte-identical throughout preparation.

## Production feasibility and the boundary that remains

There is **no demonstrated current path** to exercise an unpublished candidate's
normal owner API against this exact production target. Existing preview uses a
separate environment, no production D1 and separate role authority; it is not a
production owner-acceptance observation. Initial inactive upload/prearm also
requires inactive daily state, so it cannot be reused for this active service.

The above preparer can verify an already legitimately observed deployed version
before a **local runtime handoff**. It does **not** solve the earlier Worker
traffic switch. Requiring actual evidence is deliberate: without a supported
pre-traffic observation or verified equivalent, a candidate must not be newly
published just to manufacture proof and risk an unaccepted operating version.
No such publication is performed by this module or this work.

The existing schedule/config also points to a fixed checkout; it has no atomic
accepted-release pointer. The runner additionally requires the latest research
remote HEAD. Keeping the old local files alone therefore does not prove daily
operation can continue after an unrelated remote branch advance. The tests
prove byte preservation and the actual old **acceptance validator**, not a full
scheduled-day run or transactional Git/Cloudflare promotion.

Before adoption, choose and authorize a normal deployment integration that can
(a) obtain exact-target candidate proof before traffic, or provide an explicitly
approved post-publication recovery/rollback contract, and (b) atomically select a
fully accepted runtime without dropping the existing latest-HEAD, preflight or
lock protections. The helper deliberately contains no production switch adapter;
there is no fallback that edits the old hash, accepts any SHA, fabricates a 200,
uses another browser route, or disables a check. The existing broken current
315673ae/25628e2e pair still needs genuine current-source observations and the
existing formal source-upgrade procedure; this module does not bypass it.

## Browser-independent evidence

Source/config show existing observability enabled. Existing role logs alone are
insufficient: `cloud_role_lookup.http_status` is upstream Discord, and
`cloud_role_access` lacks final Cloud HTTP status and source identity. No existing
authorized historical-log reader or full server receipt satisfying owner identity,
same target/version, document/API 200 and normal response was found in the local
runbook/scripts. Provider retention/permissions remain unverified. Public health,
CI success, UI screenshots and owner statements cannot substitute.

A future already-authorized server observation reader could be injected only
after its provenance and full required fields are established. The module does
not request new permissions, extract CI secrets, start a live tail, invent such a
reader or retry the stopped browser. No extra owner screen check is requested.

## Validation and rollback

All new tests use temporary directories, fictional data and mocked trusted host
readers, exercising the real formal issue/apply and predecessor audit validators.
No synthetic test result is a production acceptance receipt. Cases include old
SHA, wrong DB, changed authentication source, missing/synthetic/altered receipt,
cross-site denial, missing identity/body, wrong version, predeployment observation,
CI-health-only evidence, scope/channel/expiry, concurrent preparation/deployment,
interrupted apply, stale/tampered candidate and already mismatched current state.

Local rollback: retain the diff/commit and remove only this isolated candidate
from adoption consideration. No production restore is needed because no existing
operating file, acceptance, deployment, schedule, DB, notification or credential
was changed. Failed candidate audits must be retained; a ready candidate is not
an instruction to replace any live folder or record.
