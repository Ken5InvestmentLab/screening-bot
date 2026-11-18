# Cloud 2.0 New A notifications

- Combine pending detections and their daily summary into one message through the existing detection webhook. A verified zero-result day is silent. Treat logical outbox counts and physical Discord POST counts separately.
- Preserve earlier SENT receipts and claim pending batch members atomically. If a batch's outcome is unknown, run the authorized notification entry with `--reconcile-only` to check the existing Discord history and confirm matching receipts. Leave unknown or legacy unconfirmed delivery pending review. Verify with `py -B -m unittest tests.test_new_a_connection tests.test_new_a_delayed_recovery tests.test_new_a_operational_integration`.
