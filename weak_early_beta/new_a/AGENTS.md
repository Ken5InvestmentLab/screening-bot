# Cloud 2.0 New A

## New A fundamental workflow

- Use the selected Premium source pinned by `COPY_MANIFEST.json` under
  `scripts/windows/cloud-premium-references/`. The executed worker, shared
  guide, examples and reviewed issuer inventory are exact copies. New A's
  `premium-legacy-1fa6d89` claim name retains the contract lineage; use the
  recorded selected source for research, seven fields, targeted
  repair and exact full dry-run. This replaces the later machine inventory,
  capital-risk packet and long-term packet requirements for this path. Keep
  the guide's substantive source/dilution checks, Cloud identity/cutoff,
  HTML-only import and prior verified receipts. Legacy beta paths are unchanged.
- A model preflight or research failure holds only fundamentals and preserves
  the claim/drafts while the verified detection/publication sequence continues.
  Ownership, immutable input and import-integrity failures still stop the run.
- Missing research is not issuer dilution risk. Do not add generic unverified
  dilution language or choose a mixed impact label solely because research is
  incomplete. Verify actual issued instruments; report known amounts with their
  observation dates and distinguish issued value, carrying value and outstanding
  principal. Keep unresolved research internal and continue it without inventing
  either a risk or its absence.
- Premium parity includes the installed user's normal execution settings.
  Do not discard user configuration or silently substitute a runtime. Verify
  local input/output before research; a denied probe holds the claim.
- Recover a retained claim from a completed daily only through
  `scripts/windows/new-a-completed-fundamental-recovery.mjs --date YYYY-MM-DD`.
  It uses a separate lease bound to the selected approved source, completed
  receipt, producer and original claim/cutoff. Never forge a daily lock,
  change the original completion, rerun detection or resend notifications.
- Ordinary publication always retains hash-verified historical and forward
  analyses for the exact presentation episodes, independently of new research.
  Re-publishing an already completed snapshot may restore this presentation
  cache; keep its detection snapshot and SENT outbox unchanged, and do not
  rerun research or notifications. An identical attached report is a no-op;
  conflicting existing analysis must fail instead of being overwritten.
- An editorial correction to an already published analysis uses the explicit
  `correct-fundamentals` command with exact reviewed bytes. Retain its original
  seven-field report, cutoff, source links and immutable analysis receipts in
  the append-only correction ledger. Only impact and notes prose may change.
  The ordinary publication rebuilds presentation parts with that ledger; it
  must preserve the snapshot, price parts and SENT notifications. Removing an
  unsupported research-gap warning never establishes absence of dilution.

## Notifications

- Combine pending detections and their daily summary into one message through the existing detection webhook. A verified zero-result day is silent. Treat logical outbox counts and physical Discord POST counts separately.
- Preserve earlier SENT receipts and claim pending batch members atomically. If a batch's outcome is unknown, run the authorized notification entry with `--reconcile-only` to check the existing Discord history and confirm matching receipts. Leave unknown or legacy unconfirmed delivery pending review. Verify with `py -B -m unittest tests.test_new_a_connection tests.test_new_a_delayed_recovery tests.test_new_a_operational_integration`.

## New A member projection

- The member view publishes only the exact verified owner READY generation, from the retained private bundle to the separate `CLOUD_MEMBER_DB`. Verify both D1 primaries and the approved production Worker version. Allow no member publication from isolated, stale, or finite-recovery output.
- If only member publication is held, inspect `memberPublication` and `latest-member-publication.json`, then use `python -B -m weak_early_beta.new_a.cli publish-member --remote` for the still-current generation. Do not replay owner detection, publication, or delivery. Check `python -B -m unittest tests.test_new_a_member_publisher tests.test_new_a_wrangler_response` and `node --test scripts/windows/test-new-a-runner.mjs tests/test-wrangler-query-bridge.cjs`.
- For the exact Wrangler file-upload InternalError that occurs before ingestion, reconcile the owner READY identity, member marker and immutable manifest before retrying that same member staging group once. Authentication, unknown outcomes, changed generations and activation writes never use this retry.
