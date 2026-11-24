# Cloud 2.0 New A

## New A fundamental workflow

- Use the user's selected, completed Premium legacy workflow pinned under
  `scripts/windows/cloud-premium-references/`. New A claims name
  `premium-legacy-1fa6d89`; use its source research, seven fields, targeted
  repair and exact full dry-run. This replaces the later machine inventory,
  capital-risk packet and long-term packet requirements for this path. Keep
  the guide's substantive source/dilution checks, Cloud identity/cutoff,
  HTML-only import and prior verified receipts. Legacy beta paths are unchanged.
- A model preflight or research failure holds only fundamentals and preserves
  the claim/drafts while the verified detection/publication sequence continues.
  Ownership, immutable input and import-integrity failures still stop the run.

## Notifications

- Combine pending detections and their daily summary into one message through the existing detection webhook. A verified zero-result day is silent. Treat logical outbox counts and physical Discord POST counts separately.
- Preserve earlier SENT receipts and claim pending batch members atomically. If a batch's outcome is unknown, run the authorized notification entry with `--reconcile-only` to check the existing Discord history and confirm matching receipts. Leave unknown or legacy unconfirmed delivery pending review. Verify with `py -B -m unittest tests.test_new_a_connection tests.test_new_a_delayed_recovery tests.test_new_a_operational_integration`.

## New A member projection

- The member view publishes only the exact verified owner READY generation, from the retained private bundle to the separate `CLOUD_MEMBER_DB`. Verify both D1 primaries and the approved production Worker version. Allow no member publication from isolated, stale, or finite-recovery output.
- If only member publication is held, inspect `memberPublication` and `latest-member-publication.json`, then use `python -B -m weak_early_beta.new_a.cli publish-member --remote` for the still-current generation. Do not replay owner detection, publication, or delivery. Check `python -B -m unittest tests.test_new_a_member_publisher tests.test_new_a_wrangler_response` and `node --test scripts/windows/test-new-a-runner.mjs tests/test-wrangler-query-bridge.cjs`.
