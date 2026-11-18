"""Verify recovery closure reconciles terminal and independent receipts."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from weak_early_beta.new_a import finite_completion as completion


class FiniteCompletionTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.reference = {"path": "historical-record.json", "sha256": "a" * 64}
        self.record = {
            "target_date": "2026-11-17", "execution_date": "2026-11-18",
            "source_commit": "f" * 40, "issued_at": "2026-11-18T04:23:00Z",
            "not_after": "2026-11-18T10:23:00Z",
            "ci": {"version_id": "version", "run_id": 112},
        }
        self.local = {
            "target_date": "2026-11-17", "actual_execution_date": "2026-11-18",
            "run_started_at_jst": "2026-11-18T13:28:22.559+09:00",
            "run_completed_at_jst": "2026-11-18T14:43:42.157+09:00",
            "source_commit": self.record["source_commit"], "worker_version": "version",
            "ci_run_id": 112, "root_pid": 2018,
            "dataset_id": "dataset", "source_version": "b" * 64,
            "daily_snapshot_sha256": "c" * 64, "manifest_sha256": "d" * 64,
            "operational_gate_continuity_verified": True, "existing_owner_gate_verified": False,
            "owner_http_observed": False, "outbox_remaining_signal": 0, "outbox_remaining_summary": 0,
        }
        self.evidence = {
            "schema": "NEW_A_NOV17_INDEPENDENT_FINAL_READBACK_V1",
            "passed": True, "stage": "external_readback", "read_only": True,
            "production_changes": False, "posts_performed": False,
            "observed_at_jst": "2026-11-18T14:45:23.666+09:00", "local": self.local,
            "d1": {
                "passed": True, "select_only": True, "ready": True, "as_of": "2026-11-17",
                "same_target_dataset_count": 1, "current_display_snapshot_matches": True,
                "current_d1_challenge_matches_public_worker": True,
            },
            "discord": {
                "passed": True, "get_only": True, "expected_delivery_count": 2,
                "messages": [
                    {"message_id": str(1000000000000000001 + i), "event_id": str(i),
                     "arrived_at_jst": "2026-11-18T14:42:00.000+09:00", "kind": kind,
                     "payload_footer_and_delayed_run_verified": True}
                    for i, kind in enumerate(("signal", "summary"))
                ],
            },
        }
        sent = {
            "date": "2026-11-17", "snapshot_sha256": "c" * 64, "dry_run": False,
            "signal_notifications": 1, "completion_notifications": 1, "external_sends": 2,
        }
        self.run = {
            "identity": "WEAK_EARLY_CLOUD_DAILY_V1", "ok": True, "stage": "notification",
            "observationKind": "DELAYED_SCHEDULED_OBSERVATION",
            "date": "2026-11-17", "latestSession": "2026-11-17",
            "executionDate": "2026-11-18", "startCommit": self.record["source_commit"],
            "startedAt": "2026-11-18T04:28:22.559Z", "completedAt": "2026-11-18T05:43:42.157Z",
            "pid": 2018, "originalRunId": "original",
            "nativeAdmissionContinuation": {"original_run_id": "original"},
            "deployment": {"headSha": self.record["source_commit"], "versionId": "version",
                           "run": {"databaseId": 112}, "reusedPredeployedCodeOnly": True},
            "new_a": {
                "strategy": "A_BASE", "operational_publication_verified": True,
                "owner_publication_verified": False, "owner_http_observed": False,
                "dataset_id": "dataset", "snapshot_sha256": "c" * 64, "source_version": "b" * 64,
            },
            "notifications": sent,
            "notificationReconciliation": {
                **sent, "dry_run": True, "signal_notifications": 0,
                "completion_notifications": 0, "external_sends": 0,
            },
        }

    def verify(self):
        independent = self.repo / "independent.json"
        original = self.repo / ".cache/weak_early_beta/daily_runtime/daily-2026-11-18T04-28-22-559Z/result.json"

        def read(path):
            path = Path(path)
            self.assertIn(path, (independent, original))
            return (self.evidence, "1" * 64) if path == independent else (self.run, "2" * 64)

        with patch.object(completion, "_read", side_effect=read):
            return completion.verified_completion(self.repo, self.reference, self.record, independent)

    def test_closure_uses_dated_terminal_receipt_and_matches_independent_delivery(self):
        result = self.verify()
        self.assertTrue(result["publication_verified"] and result["notification_reconciled"])
        self.assertEqual(result["finite_admission"], self.reference)
        self.assertEqual(result["target_date"], "2026-11-17")
        self.assertEqual(result["execution_date"], "2026-11-18")
        self.assertEqual(result["receipt_hashes"]["terminal_runner"], "2" * 64)

    def test_refuses_disagreement_or_incomplete_delivery(self):
        original = deepcopy(self.run)
        for update, reason in [
            ({"ok": False}, "terminal runner identity"),
            ({"date": "2026-11-18"}, "terminal runner identity"),
            ({"new_a": {**original["new_a"], "dataset_id": "other"}}, "publication"),
            ({"notificationReconciliation": {**original["notificationReconciliation"],
                                               "signal_notifications": 1}}, "notification"),
        ]:
            with self.subTest(update=update), self.assertRaisesRegex(ValueError, reason):
                self.run = {**original, **update}
                self.verify()

    def test_refuses_duplicate_discord_message_ids(self):
        messages = self.evidence["discord"]["messages"]
        messages[1]["message_id"] = messages[0]["message_id"]
        with self.assertRaisesRegex(ValueError, "notification"):
            self.verify()
