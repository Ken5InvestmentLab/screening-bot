# Cloud 2.0 New A notifications

- Combine pending detections and their daily summary into one message through the existing detection webhook. A verified zero-result day is silent. Treat logical outbox counts and physical Discord POST counts separately.
- Preserve earlier SENT receipts and claim pending batch members atomically. If a batch's outcome is unknown, run the authorized notification entry with `--reconcile-only` to check the existing Discord history and confirm matching receipts. Leave unknown or legacy unconfirmed delivery pending review. Verify with `py -B -m unittest tests.test_new_a_connection tests.test_new_a_delayed_recovery tests.test_new_a_operational_integration`.

## New A member projection

- The member view publishes only the exact verified owner READY generation, from the retained private bundle to the separate `CLOUD_MEMBER_DB`. Verify both D1 primaries and the approved production Worker version. Allow no member publication from isolated, stale, or finite-recovery output.
- If only member publication is held, inspect `memberPublication` and `latest-member-publication.json`, then use `python -B -m weak_early_beta.new_a.cli publish-member --remote` for the still-current generation. Do not replay owner detection, publication, or delivery. Check `python -B -m unittest tests.test_new_a_member_publisher tests.test_new_a_wrangler_response` and `node --test scripts/windows/test-new-a-runner.mjs tests/test-wrangler-query-bridge.cjs`.
