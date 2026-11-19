"""Private local holds only. No provider, Git remote, scheduler or Worker writes."""

import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weak_early_beta.new_a import release_maintenance as guard
from weak_early_beta.new_a.files import atomic_write, digest, file_sha, private_root, read


OLD = "a" * 40
NEW = "b" * 40
OLD_VERSION = "11111111-1111-1111-1111-111111111111"
NEW_VERSION = "22222222-2222-2222-2222-222222222222"
OLD_DEPLOYMENT = "33333333-3333-3333-3333-333333333333"
NEW_DEPLOYMENT = "44444444-4444-4444-4444-444444444444"


class ReleaseMaintenanceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="new-a-release-maintenance-")
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        base = self.repo / ".cache/weak_early_beta"
        runtime = base / "daily_runtime"
        self.locks = [runtime / "task-entry.lock", runtime / "daily.lock", base / "exit-reminder-runner.lock"]
        self.target = {
            "service": "tentei-kyokuchi-cloud", "binding": "CLOUD_DB",
            "database_name": "tentei-cloud-settings", "database_id": "test-owner-d1-id",
        }
        atomic_write(base / "daily-runner.config.json", {
            "repoPath": str(self.repo), "runtimeDir": str(runtime),
        })
        atomic_write(self.repo / "weak-early-beta-gate/wrangler.jsonc", {
            "name": self.target["service"],
            "d1_databases": [{key: self.target[key] for key in ("binding", "database_name", "database_id")}],
        })
        self.subject = {
            "message_id": "fixture-msg", "author_id": "fixture-owner", "room_id": "fixture-room",
            "text_sha256": digest("approve this isolated fixture"),
        }
        self.now = guard.ca.now()
        self.not_after = (self.now + datetime.timedelta(minutes=15)).isoformat()
        self.current = self.observation(OLD, OLD_VERSION, OLD_DEPLOYMENT)

    def observation(self, source, version, deployment):
        return {
            "schema": "NEW_A_HOST_OBSERVED_RELEASE_PAIR_V1", "repository": str(self.repo), "source_commit": source,
            "git": {"repository": str(self.repo), "branch": "research/weak-early-beta",
                    "clean": True, "local_head": source, "remote_head": source},
            "target": self.target, "activation_sha256": digest(["activation", source]),
            "acceptance_sha256": digest(["acceptance", source]), "policy_sha256": "c" * 64,
            "build_input_sha256": "d" * 64, "provider_sha256": "e" * 64,
            "version_id": version, "deployment_id": deployment, "ci_run_id": 7,
            "tag": "cloud-deploy-" + source[:6], "observed_at": self.now.isoformat(),
        }

    def pair(self, repo):
        self.assertEqual(repo, self.repo)
        return self.current

    def primary(self, message_id):
        return {
            "partial": False, "room_id": self.subject["room_id"],
            "message": {
                "author": "user", "author_id": self.subject["author_id"], "channel": "chatgpt",
                "message_id": message_id, "deleted_at": None, "sent_at": self.now.isoformat(),
                "content": {"text": "approve this isolated fixture"},
            },
        }

    def decide(self, _, intent):
        self.assertEqual(intent["old"]["source_commit"], OLD)
        self.assertEqual(intent["candidate_source"], NEW)
        return {
            "schema": "NEW_A_HOST_RELEASE_MAINTENANCE_REVIEW_V1", "operation_sha256": digest(intent),
            "authorized": True, "platform_signature_claimed": False,
        }

    def begin(self, *, decide=None, pair=None):
        return guard.begin_release(
            self.repo, NEW, not_after=self.not_after, owner_message=self.subject, primary_reader=self.primary,
            owner_authority=self.subject, decision_reader=decide or self.decide,
            pair_reader=pair or self.pair, idle_reader=lambda _: True,
        )

    def admit(self, operation):
        return guard.admit_release(self.repo, operation, pair_reader=self.pair, idle_reader=lambda _: True)

    def finish(self, operation, *, reader=None):
        return guard.finish_release(
            self.repo, operation, pair_reader=self.pair, idle_reader=lambda _: True, terminal_reader=reader,
        )

    @staticmethod
    def terminal(status):
        return lambda operation, pair: {
            "schema": "NEW_A_HOST_RELEASE_TERMINAL_V1", "operation_sha256": operation,
            "observed_pair_sha256": digest(pair), "outcome": status, "platform_signature_claimed": False,
            "synthetic": False, "raw_receipt_sha256": "f" * 64,
        }

    def test_holds_existing_three_locks_until_exact_candidate_and_terminal_proof(self):
        op = self.begin()["operation_sha256"]
        guard.verify_release_hold(self.repo, op, admitted=False)
        self.assertEqual([path.read_text() for path in self.locks], ["new-a-release:" + op] * 3)
        admission = self.admit(op)
        self.assertEqual(admission["candidate_source"], NEW)
        self.assertEqual(guard.verify_release_hold(self.repo, op), "new-a-release:" + op)
        with self.assertRaisesRegex(ValueError, "already_consumed"):
            self.admit(op)
        with guard.admitted_release_hold(self.repo, op) as token:
            self.assertEqual(token, "new-a-release:" + op)
            with self.assertRaisesRegex(ValueError, "transition_already_held"):
                self.finish(op)
        self.current = self.observation(NEW, NEW_VERSION, NEW_DEPLOYMENT)
        result = self.finish(op, reader=self.terminal("candidate-selected"))
        self.assertEqual(result["outcome"], "candidate-selected")
        self.assertEqual(result["starts"], 0)
        self.assertEqual(self.finish(op), result)
        self.assertFalse(any(path.exists() for path in self.locks))
        record = read(private_root(self.repo) / "release-maintenance" / op / "terminal.json")
        self.assertEqual(record["pair"]["version_id"], NEW_VERSION)

    def test_refuses_changed_git_and_unreviewed_baseline_before_holding(self):
        self.current["git"]["remote_head"] = NEW
        with self.assertRaisesRegex(ValueError, "git_pair_differs"):
            self.begin()
        self.current["git"]["remote_head"] = OLD
        with self.assertRaisesRegex(ValueError, "maintainer_review_required"):
            self.begin(decide=lambda *_: {})
        self.assertFalse(any(path.exists() for path in self.locks))

    def test_does_not_clear_existing_runner_lock_during_failed_acquisition(self):
        self.locks[1].parent.mkdir(parents=True)
        self.locks[1].write_text("existing-daily")
        with self.assertRaises(FileExistsError):
            self.begin()
        self.assertFalse(self.locks[0].exists())
        self.assertEqual(self.locks[1].read_text(), "existing-daily")
        self.assertFalse(self.locks[2].exists())

    def test_old_pair_observed_without_terminal_record_is_still_ambiguous_after_admission(self):
        op = self.begin()["operation_sha256"]
        self.admit(op)
        with self.assertRaisesRegex(ValueError, "terminal_host_reader_required"):
            self.finish(op)
        self.assertTrue(all(path.exists() for path in self.locks))
        self.assertEqual(self.finish(op, reader=self.terminal("old-unchanged"))["outcome"], "old-unchanged")

    def test_expiry_blocks_new_steps_but_allows_exact_restored_pair_to_clear(self):
        op = self.begin()["operation_sha256"]
        self.admit(op)
        self.current["deployment_id"] = NEW_DEPLOYMENT
        late = self.now + datetime.timedelta(hours=2)
        with patch.object(guard.ca, "now", return_value=late):
            with self.assertRaisesRegex(ValueError, "active_hold_required"):
                guard.verify_release_hold(self.repo, op)
            with self.assertRaisesRegex(ValueError, "old_pair_changed"):
                self.finish(op, reader=self.terminal("old-unchanged"))
            self.assertTrue(all(path.exists() for path in self.locks))
            self.assertEqual(self.finish(op, reader=self.terminal("old-restored"))["outcome"], "old-restored")
        self.assertFalse(any(path.exists() for path in self.locks))

    def test_mixed_new_runtime_with_old_acceptance_cannot_release(self):
        op = self.begin()["operation_sha256"]
        self.admit(op)
        old_approval = self.current["acceptance_sha256"]
        self.current = self.observation(NEW, NEW_VERSION, NEW_DEPLOYMENT)
        self.current["acceptance_sha256"] = old_approval
        with self.assertRaisesRegex(ValueError, "candidate_pair_not_approved"):
            self.finish(op, reader=self.terminal("candidate-selected"))
        self.assertTrue(all(path.exists() for path in self.locks))

    def test_unadmitted_window_can_only_resume_original_exact_pair(self):
        op = self.begin()["operation_sha256"]
        self.current = self.observation(NEW, NEW_VERSION, NEW_DEPLOYMENT)
        with self.assertRaisesRegex(ValueError, "unadmitted_old_pair_changed"):
            self.finish(op)
        self.assertTrue(all(path.exists() for path in self.locks))
        self.current = self.observation(OLD, OLD_VERSION, OLD_DEPLOYMENT)
        self.assertEqual(self.finish(op)["outcome"], "old-unchanged")

    def test_transition_file_is_reusable_without_unlocking_a_live_writer(self):
        transition = private_root(self.repo) / "isolated-transition"
        with guard._serialize(transition):
            with self.assertRaisesRegex(ValueError, "transition_already_held"):
                with guard._serialize(transition):
                    self.fail("only one local transition can write receipts")
        with guard._serialize(transition):
            self.assertTrue((transition / "transition.lock").is_file())

    def test_reconciles_partially_released_hold_from_immutable_terminal_record(self):
        op = self.begin()["operation_sha256"]
        self.admit(op)
        self.current = self.observation(NEW, NEW_VERSION, NEW_DEPLOYMENT)
        original_drop = guard._drop_own

        def interrupted_drop(paths, owner):
            original_drop(paths[-1:], owner)
            raise RuntimeError("fixture stopped during local unlock")

        with patch.object(guard, "_drop_own", side_effect=interrupted_drop):
            with self.assertRaisesRegex(RuntimeError, "local unlock"):
                self.finish(op, reader=self.terminal("candidate-selected"))
        self.assertTrue(self.locks[0].exists())
        self.assertFalse(self.locks[2].exists())
        self.assertEqual(self.finish(op, reader=self.terminal("candidate-selected"))["outcome"], "candidate-selected")
        self.assertFalse(any(path.exists() for path in self.locks))

    def test_pair_assembler_reuses_approved_activation_and_exact_provider_traffic(self):
        activation = private_root(self.repo) / "activation.json"
        atomic_write(activation, {"owner_acceptance": {"continuing_acceptance": {"sha256": "1" * 64}}})
        release = {
            **{key: self.current[key] for key in guard._RELEASE}, "activation_sha256": file_sha(activation),
            "schema": guard.RUNTIME_RELEASE_SCHEMA,
        }
        provider = {
            **release, "schema": "NEW_A_HOST_VERIFIED_DEPLOYMENT_V1", "target": self.target,
            "deployment_id": OLD_DEPLOYMENT, "observed_at": self.now.isoformat(),
            "deployed_at": (self.now - datetime.timedelta(minutes=5)).isoformat(),
            "normal_origin": guard._ORIGIN, "live_traffic_percent": 100,
            "active_owner_sha256": "2" * 64, "raw_receipt_sha256": "3" * 64,
            "deployment_succeeded": True, "platform_signature_claimed": False,
        }
        with patch.object(guard, "ordinary_runtime_release", return_value=release):
            observed = guard.observe_release_pair(
                self.repo, git_reader=lambda _: self.current["git"], deployment_reader=lambda *_: provider,
            )
            self.assertEqual(observed["activation_sha256"], file_sha(activation))
            self.assertEqual(observed["acceptance_sha256"], "1" * 64)
            provider["live_traffic_percent"] = 50
            with self.assertRaisesRegex(ValueError, "normal_provider_differs"):
                guard.observe_release_pair(
                    self.repo, git_reader=lambda _: self.current["git"], deployment_reader=lambda *_: provider,
                )
