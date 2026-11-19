"""Exercise the private maintainer state machine without any provider traffic."""

import datetime
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weak_early_beta.new_a import member_rollout as rollout
from weak_early_beta.new_a.files import atomic_write, digest, encode, private_root, read
from weak_early_beta.new_a.operational_admission import read_active_metadata
from weak_early_beta.new_a.publisher import LocalD1


GATE = Path(__file__).resolve().parents[1] / "weak-early-beta-gate"
SOURCE = "a" * 40
VERSION = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DEPLOYMENT = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
STAGE_VERSION = "cccccccc-cccc-cccc-cccc-cccccccccccc"
NORMAL = "https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev"
STAGE = "https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev"
CANARY = "111111111111111111"
OTHER = "222222222222222222"
MODE_COLUMN = "SELECT mode,revision,canary_nonce,canary_subject_hmac FROM new_a_member_release_policy"


class MemberRolloutTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="new-a-member-rollout-")
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        self.audit = private_root(self.repo) / "member-rollout"
        self.target = {
            "service": "tentei-kyokuchi-cloud", "binding": "CLOUD_DB",
            "database_name": "tentei-cloud-settings",
            "database_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        }
        atomic_write(self.repo / "weak-early-beta-gate/wrangler.jsonc", {
            "name": self.target["service"],
            "d1_databases": [{key: self.target[key] for key in ("binding", "database_name", "database_id")}],
        })
        self.owner_db = LocalD1(":memory:", GATE / "schema/new-a-private.sql")
        self.member_db = LocalD1(":memory:", GATE / "member-migrations/0001_new_a_member_storage.sql")
        self.addCleanup(self.owner_db.close)
        self.addCleanup(self.member_db.close)
        self.member_db.db.executescript((GATE / "member-migrations/0002_new_a_member_release_policy.sql").read_text())
        self.ready = {
            "status": "READY", "dataset_id": "a-" + "e" * 24, "revision": 4,
            "as_of": "2026-11-19", "source_version": "e" * 64,
        }
        manifest = encode({key: self.ready[key] for key in ("as_of", "source_version")})
        self.owner_db.query("INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?)", (
            self.ready["dataset_id"], self.ready["source_version"], manifest,
            hashlib.sha256(manifest.encode()).hexdigest(), "READY", self.ready["as_of"],
        ))
        self.owner_db.query("INSERT INTO new_a_active_pointer VALUES ('owner',?,?,?)", (
            self.ready["dataset_id"], self.ready["revision"], self.ready["as_of"],
        ))
        identity = json.dumps(self.ready, separators=(",", ":"))
        projection_sha = "f" * 64
        self.member_db.query("INSERT INTO private_projection_manifest VALUES (?,?,?)", (identity, projection_sha, "{}"))
        self.member_db.query("INSERT INTO private_projection_ready VALUES (1,?,?)", (identity, projection_sha))
        atomic_write(private_root(self.repo) / "latest-member-publication.json", {
            "schema": "NEW_A_MEMBER_PUBLICATION_V1", "published": True, "active_readback_verified": True,
            "worker_version_id": VERSION, "source": self.ready, "projection_sha256": projection_sha,
        })
        self.release = {
            "schema": "NEW_A_ORDINARY_RUNTIME_RELEASE_V1", "source_commit": SOURCE, "version_id": VERSION,
            "build_input_sha256": "1" * 64, "policy_sha256": "2" * 64,
            "ci_run_id": 1234, "tag": "cloud-deploy-fixture-role",
        }
        self.deployed = (rollout.ca.now() - datetime.timedelta(minutes=2)).isoformat()
        self.owner_message = {
            "message_id": "isolated-owner-request", "author_id": "isolated-owner", "room_id": "isolated-room",
            "text_sha256": digest("Proceed with the isolated fixture"),
        }
        patcher = patch.object(rollout, "ordinary_runtime_release", return_value=self.release)
        self.addCleanup(patcher.stop)
        patcher.start()
        self.phases = []

    def primary(self, message_id):
        return {
            "partial": False, "room_id": self.owner_message["room_id"],
            "message": {
                "message_id": message_id, "author_id": self.owner_message["author_id"], "author": "user",
                "channel": "chatgpt", "deleted_at": None, "sent_at": self.deployed,
                "content": {"text": "Proceed with the isolated fixture"},
            },
        }

    def maintain(self, owner, intent):
        self.assertEqual(owner["text_sha256"], self.owner_message["text_sha256"])
        self.assertTrue(intent["owner_only_routes_preserved"])
        return {
            "schema": "NEW_A_HOST_MEMBER_ROLLOUT_REVIEW_V1", "decision": "APPLY_EXACT_MEMBER_ROLLOUT",
            "action_sha256": digest(intent), "platform_signature_claimed": False,
        }

    def deployment(self, approved):
        self.assertEqual(approved, self.release)
        return {
            **self.release, "schema": "NEW_A_HOST_VERIFIED_DEPLOYMENT_V1", "target": self.target,
            "deployment_id": DEPLOYMENT, "raw_receipt_sha256": "3" * 64, "observed_at": rollout.ca.now().isoformat(),
            "deployed_at": self.deployed, "deployment_succeeded": True, "platform_signature_claimed": False,
            "normal_origin": NORMAL, "live_traffic_percent": 100,
            "active_owner_sha256": read_active_metadata(self.owner_db)[2],
        }

    def observe(self, request):
        phase = request["phase"]
        self.phases.append(phase)
        self.assertEqual(request["paths"]["document"], "/weak_early_beta_latest.html")
        self.assertEqual(request["paths"]["member_api"], "/api/cloud/new-a-view/history.json")
        self.assertEqual(request["paths"]["owner_direct"], "/api/cloud/new-a-finite/input/manifest.json")
        if phase != "stage":
            self.assertEqual(request["policy"], rollout.read_member_policy(self.member_db))
        return {
            "schema": "NEW_A_HOST_MEMBER_ROLLOUT_OBSERVATION_V1", "request_sha256": digest(request),
            "synthetic": False, "platform_signature_claimed": False, "source_commit": SOURCE,
            "origin": STAGE if phase == "stage" else NORMAL,
            "worker_version_id": STAGE_VERSION if phase == "stage" else VERSION,
            "raw_receipt_sha256": "4" * 64, "deployed_at": self.deployed, "observed_at": rollout.ca.now().isoformat(),
            "owner": {
                "session_verified": True, "owner": True, "document_status": 200, "access_api_status": 200,
                "access": {"authorized": True, "strategy": "A_BASE"},
            },
            "anonymous": {
                "cookies_sent": False, "authorization_sent": False,
                "document_status": 302, "member_api_status": 401, "owner_direct_status": 401,
            },
            "role_allowed": self.role(CANARY, True),
            "role_denied": self.role(OTHER, False),
        }

    @staticmethod
    def role(subject, allowed):
        return {
            "session_verified": True, "owner": False, "fresh_designated_role_checked": True,
            "guild_id": "1479418833352785944", "designated_role_id": "1487089073385373828",
            "has_designated_role": allowed, "subject": subject, "document_status": 200 if allowed else 403,
            "member_api_status": 200 if allowed else 403, "owner_direct_status": 403,
        }

    def apply(self, mode, *, expected=None, deploy=None, observe=None, maintain=None):
        return rollout.change_member_rollout(
            self.repo, self.owner_db, self.member_db, mode=mode, expected=expected,
            owner_message=self.owner_message, primary_reader=self.primary, owner_authority=self.owner_message,
            decision_reader=maintain or self.maintain, deployment_reader=deploy or self.deployment,
            observation_reader=observe or self.observe,
        )

    def test_canary_then_role_and_private_rollback_to_off(self):
        canary = self.apply("canary")
        self.assertEqual(self.phases, ["before", "stage", "after"])
        self.assertEqual(canary["after"], rollout.read_member_policy(self.member_db))
        self.assertIsNone(canary["before"])
        row, = self.member_db.query(MODE_COLUMN)
        expected_mac = hmac.new(
            bytes.fromhex(row["canary_nonce"]), encode([
                "new-a-member-rollout-subject-v1", SOURCE, VERSION, CANARY,
            ]).encode(), hashlib.sha256,
        ).hexdigest()
        self.assertEqual(row["canary_subject_hmac"], expected_mac)

        role = self.apply("enabled", expected=canary["after"])
        self.assertEqual(role["after"]["mode"], "enabled")
        self.assertEqual(role["after"]["revision"], 2)
        self.assertEqual(role["before"], canary["after"])
        self.assertEqual(role["rollback_mode"], "off")
        self.assertEqual(self.phases, ["before", "stage", "after", "before", "after"])

        def must_not_use_member_sessions(_):
            self.fail("safe narrowing must be available even if member sessions are broken")

        off = self.apply("off", expected=role["after"], observe=must_not_use_member_sessions)
        self.assertEqual(off["after"]["revision"], 3)
        self.assertEqual(self.member_db.query(MODE_COLUMN), [{
            "mode": "off", "revision": 3, "canary_nonce": None, "canary_subject_hmac": None,
        }])
        for path in self.audit.glob("*.json"):
            text = path.read_text()
            for private in (CANARY, OTHER, row["canary_nonce"], expected_mac):
                self.assertNotIn(private, text)

    def test_refuses_shortcut_unapproved_provider_or_unauthenticated_stage(self):
        with self.assertRaisesRegex(ValueError, "transition_denied"):
            self.apply("enabled")
        with self.assertRaisesRegex(ValueError, "normal_release_differs"):
            self.apply("canary", deploy=lambda approval: {**self.deployment(approval), "live_traffic_percent": 50})
        with self.assertRaisesRegex(ValueError, "maintainer_review_required"):
            self.apply("canary", maintain=lambda *_: {})

        def no_real_session(request):
            observed = self.observe(request)
            if request["phase"] == "stage":
                observed["role_allowed"]["session_verified"] = False
            return observed

        with self.assertRaisesRegex(ValueError, "actual_role_observation_required"):
            self.apply("canary", observe=no_real_session)
        self.assertIsNone(rollout.read_member_policy(self.member_db))
        self.assertFalse(self.audit.exists())

    def test_actual_canary_must_be_observed_and_pending_can_be_reconciled_once(self):
        def incorrect_subject(request):
            observed = self.observe(request)
            if request["phase"] == "after":
                observed["role_allowed"]["subject"] = "333333333333333333"
            return observed

        with self.assertRaisesRegex(ValueError, "canary_subject_differs"):
            self.apply("canary", observe=incorrect_subject)
        before = rollout.read_member_policy(self.member_db)
        self.assertEqual(before["mode"], "canary")
        self.assertEqual(len(list(self.audit.glob("*-intent.json"))), 1)
        self.assertEqual(len(list(self.audit.glob("*-complete.json"))), 0)
        confirmed = self.apply("canary")
        self.assertEqual(confirmed["after"], before)
        self.assertEqual(self.phases, ["before", "stage", "after", "after"])
        restored = self.apply("canary")
        self.assertEqual(restored, confirmed)
        self.assertEqual(rollout.read_member_policy(self.member_db), before)

    def test_ambiguous_mutation_is_never_retried(self):
        writes = []
        query = self.member_db.query

        def uncertain(sql, values=()):
            if sql.startswith("INSERT INTO new_a_member_release_policy"):
                writes.append(sql)
                raise RuntimeError("isolated lost acknowledgement")
            return query(sql, values)

        with patch.object(self.member_db, "query", side_effect=uncertain):
            with self.assertRaisesRegex(RuntimeError, "write_unconfirmed"):
                self.apply("canary")
            with self.assertRaisesRegex(ValueError, "pending_reconcile"):
                self.apply("canary")
        self.assertEqual(len(writes), 1)
        self.assertIsNone(rollout.read_member_policy(self.member_db))

    def test_refuses_to_record_protected_observation_after_deployment_drift(self):
        def current_deployment(approval):
            observed = self.deployment(approval)
            if "after" in self.phases:
                observed["deployment_id"] = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
            return observed

        with self.assertRaisesRegex(ValueError, "final_readback_changed"):
            self.apply("canary", deploy=current_deployment)
        self.assertEqual(rollout.read_member_policy(self.member_db)["mode"], "canary")
        self.assertEqual(len(list(self.audit.glob("*-complete.json"))), 0)
        pending, = self.audit.glob("*-intent.json")
        self.assertEqual(read(pending)["intent"]["deployment_id"], DEPLOYMENT)
