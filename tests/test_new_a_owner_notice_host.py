"""Synthetic owner/runtime evidence for canonical notice staging, with no real I/O services."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from weak_early_beta.new_a import owner_notice_host
from weak_early_beta.new_a.continuing_acceptance import target
from weak_early_beta.new_a.continuing_transition import RUNTIME_RELEASE_SCHEMA
from weak_early_beta.new_a.files import atomic_write, digest, encode, private_root
from weak_early_beta.new_a.owner_notice_host import DEVICE_READ, HOST_SCHEMA, RUNTIME_SCHEMA, OwnerNoticeHost, _binding_file
from weak_early_beta.new_a.publisher import is_read_only_select


class DeviceFixture:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query(self, statement, values):
        if not is_read_only_select(statement) or "subscription.endpoint," in statement:
            raise AssertionError("device proof must be read-only and omit the endpoint")
        self.calls.append(values)
        return self.rows


class OwnerNoticeHostTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        self.config = private_root(self.repo) / "owner-notice-host.json"
        self.owner = "a" * 64
        self.device = {"subscription_id": "11111111-2222-4333-8444-555555555555", "endpoint_hash": "b" * 64}
        self.recipient = digest(["NEW_A_OWNER_WEB_PUSH_DEVICE_V1", "cloud_" + self.owner,
                                 self.device["subscription_id"], self.device["endpoint_hash"]])
        atomic_write(self.config, {"schema": HOST_SCHEMA, "enabled": True, "recipient_binding_sha256": self.recipient})
        atomic_write(self.repo / "weak-early-beta-gate/wrangler.jsonc", {
            "name": "tentei-kyokuchi-cloud",
            "d1_databases": [{"binding": "CLOUD_DB", "database_name": "tentei-cloud-settings",
                              "database_id": "11111111-2222-3333-4444-555555555555"}],
        })
        self.start = datetime(2026, 11, 18, 8, 25, tzinfo=timezone.utc)
        self.now = self.start
        self.worker = {"schema": RUNTIME_RELEASE_SCHEMA, "source_commit": "d" * 40,
                       "version_id": "11111111-2222-3333-4444-555555555555"}
        self.evidence = {"schema": RUNTIME_SCHEMA, "source_commit": self.worker["source_commit"],
                         "worker_version_id": self.worker["version_id"], "normal_owner_policy_verified": True,
                         "owner_binding_sha256": self.owner, "d1_active_sha256": "e" * 64,
                         "fresh_paid_role": True, "observed_at": self.start.isoformat(),
                         "expires_at": (self.start + timedelta(seconds=30)).isoformat()}
        self.db = DeviceFixture([self.device])
        self.observations = 0
        self.host = OwnerNoticeHost(self.repo, self.recipient, "public-key", self.db,
                                    observe=self.observe, approval=lambda: self.worker, clock=lambda: self.now)

    def observe(self, release):
        self.assertEqual(release, self.worker)
        self.observations += 1
        return self.evidence

    def test_exact_source_and_recipient_proof_uses_read_only_projection(self):
        self.assertEqual(self.host.read_release(), self.worker)
        self.assertEqual(self.host.read_owner_policy(target(self.repo))["d1_active_sha256"], "e" * 64)
        receipt = self.host.read_recipient()
        self.assertEqual(receipt["recipient_binding_sha256"], self.recipient)
        self.assertTrue(receipt["fresh_paid_role"])
        self.assertEqual(self.observations, 1)
        self.assertEqual(self.db.calls[0][:2], ("cloud_" + self.owner, "public-key"))
        self.assertNotIn(self.device["subscription_id"], str(receipt))

    def test_absent_or_different_device_and_unpaid_role_remain_held(self):
        self.evidence["fresh_paid_role"] = False
        with self.assertRaisesRegex(ValueError, "entitled"):
            self.host.read_recipient()
        self.assertEqual(self.db.calls, [])
        self.evidence["fresh_paid_role"] = True
        self.db.rows = []
        with self.assertRaisesRegex(ValueError, "opted-in"):
            self.host.read_recipient()
        self.db.rows = [{**self.device, "endpoint_hash": "f" * 64}]
        with self.assertRaisesRegex(ValueError, "opted-in"):
            self.host.read_recipient()

    def test_expired_proof_and_changed_expected_recipient_never_reuse_cache(self):
        self.host.read_release()
        self.now += timedelta(seconds=30)
        with self.assertRaisesRegex(ValueError, "proof differs"):
            self.host.read_release()
        self.assertEqual(self.observations, 2)
        atomic_write(self.config, {"schema": HOST_SCHEMA, "enabled": True, "recipient_binding_sha256": "f" * 64})
        with self.assertRaisesRegex(ValueError, "binding changed"):
            self.host.read_release()
        self.assertEqual(self.observations, 2)

    def test_local_switch_and_ordinary_approval_are_required(self):
        atomic_write(self.config, {"schema": HOST_SCHEMA, "enabled": False, "recipient_binding_sha256": self.recipient})
        with self.assertRaisesRegex(ValueError, "not approved"):
            _binding_file(self.repo)
        atomic_write(self.config, {"schema": HOST_SCHEMA, "enabled": True, "recipient_binding_sha256": self.recipient})
        self.host.approval = lambda: None
        with self.assertRaisesRegex(ValueError, "ordinary approved Worker"):
            self.host.read_release()
        self.assertEqual(self.observations, 0)

    def test_immediate_dispatch_requires_the_scheduled_release(self):
        config = self.repo / ".cache/weak_early_beta/daily-runner.config.json"
        atomic_write(config, {"repoPath": str(self.repo), "nodePath": sys.executable,
                              "runtimeDir": str(config.parent / "daily_runtime")})
        worker = self.repo / "weak-early-beta-gate/wrangler.jsonc"
        document = owner_notice_host.read(worker)
        d1, lifecycle, producer = Mock(), Mock(), Mock()
        for (mode, enabled, legacy, dispatcher) in (
            ("new_a_owner_registration", "false", "false", None),
            ("new_a_owner_registration", "true", "false", None),
            ("new_a_owner_scheduled", "false", "false", None),
            ("new_a_owner_scheduled", "true", "true", None),
            ("new_a_owner_scheduled", "true", "false", owner_notice_host._dispatch_holding),
        ):
            with self.subTest(mode=mode, enabled=enabled, legacy=legacy):
                document["vars"] = {"CLOUD_PUSH_MODE": mode, "CLOUD_NEW_A_OWNER_PUSH_ENABLED": enabled,
                                    "CLOUD_PUSH_SCHEDULER_ENABLED": legacy, "CLOUD_VAPID_PUBLIC_KEY": "fixture",
                                    "CLOUD_PUSH_MEMBERSHIP_POLICY": "whop_managed_discord_role"}
                atomic_write(worker, document)
                with patch.multiple(owner_notice_host,
                                    __file__=str(self.repo / "weak_early_beta/new_a/owner_notice_host.py"),
                                    _terminal_result=Mock(), WranglerD1=d1, LifecycleNoticeInputs=lifecycle,
                                    OwnerNoticeProducer=producer):
                    owner_notice_host.after_publication(self.repo, self.repo / "result.json")
                    self.assertIs(producer.call_args.kwargs["dispatch_holding"], dispatcher)

    def test_d1_read_respects_opt_in_expiry_and_current_key_without_reading_endpoint(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        migrations = Path(__file__).resolve().parents[1] / "weak-early-beta-gate/migrations"
        for name in ("0001_cloud_preferences.sql", "0003_push_device_metadata.sql"):
            conn.executescript((migrations / name).read_text("utf-8"))
        member = "cloud_" + self.owner
        identifier = self.device["subscription_id"]
        stamp = int(self.start.timestamp() * 1000)
        conn.execute("INSERT INTO cloud_member_preferences VALUES (?,?,?)",
                     (member, encode({"notifications": {"new_detection": False, "reminder": False}}), self.start.isoformat()))
        conn.execute("INSERT INTO cloud_push_subscriptions VALUES (?,?,?,?,?,?,NULL)",
                     (identifier, member, "synthetic-endpoint", "synthetic-key", "synthetic-auth", self.start.isoformat()))
        conn.execute("INSERT INTO cloud_push_subscription_metadata VALUES (?,?,?,?,?)",
                     (identifier, self.device["endpoint_hash"], "public-key", stamp + 1000, self.start.isoformat()))
        self.assertEqual(conn.execute(DEVICE_READ, (member, "public-key", stamp)).fetchall(), [])
        conn.execute("UPDATE cloud_member_preferences SET preferences_json=? WHERE member_id=?",
                     (encode({"notifications": {"new_detection": False, "reminder": True}}), member))
        self.assertEqual(conn.execute(DEVICE_READ, (member, "wrong-key", stamp)).fetchall(), [])
        self.assertEqual(conn.execute(DEVICE_READ, (member, "public-key", stamp + 1000)).fetchall(), [])
        result = conn.execute(DEVICE_READ, (member, "public-key", stamp)).fetchall()
        self.assertEqual(result, [(identifier, self.device["endpoint_hash"])])
