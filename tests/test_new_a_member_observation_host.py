from pathlib import Path
import tempfile
import unittest

from weak_early_beta.new_a import member_observation_host as host
from weak_early_beta.new_a import member_rollout
from weak_early_beta.new_a.publisher import LocalD1


SOURCE = "a" * 40
BUILD = "b" * 64
STAGE_VERSION = "10000000-0000-4000-8000-000000000019"
NORMAL_VERSION = "20000000-0000-4000-8000-000000000019"
ALLOWED = "10000000000000001"
DENIED = "20000000000000002"


class MemberObservationHostTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        migrations = Path(__file__).resolve().parents[1] / "weak-early-beta-gate/member-migrations"
        migration = migrations / "0003_new_a_member_response_observations.sql"
        self.db = LocalD1(Path(temporary.name) / "isolated.sqlite", migration)
        for file in ("0002_new_a_member_release_policy.sql", "0004_new_a_member_access_tiers.sql"):
            self.db.db.executescript((migrations / file).read_text(encoding="utf-8"))
        self.addCleanup(self.db.close)
        self.live = {
            "origin": host._STAGE, "source_commit": SOURCE, "build_input_sha256": BUILD,
            "version_id": STAGE_VERSION, "live_traffic_percent": 100,
            "platform_signature_claimed": False, "raw_receipt_sha256": "c" * 64,
            "deployed_at": "2026-01-01T00:00:00Z",
        }

    def open(self):
        self.window = host.open_member_window(
            self.db, origin=host._STAGE, deployment_reader=lambda: self.live, allowed=ALLOWED, denied=DENIED,
        )

    def seed(self):
        scope = host.read_window(self.db)
        for role in ("allowed", "denied"):
            for key in ("document", "member_api", "premium_dashboard", "owner_direct"):
                state = role if key != "owner_direct" else "not_checked"
                status = 403 if key == "owner_direct" or (role == "denied" and key == "premium_dashboard") else 200
                self.db.query(
                    "INSERT INTO new_a_member_response_observation_v2 VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (*(scope[key] for key in host.WINDOW_FIELDS[:5]), scope[role + "_subject_hmac"],
                     host._PROTECTED_PATHS[key], status, state, scope["opens_at_ms"]),
                )

    def read(self, *, allowed=ALLOWED, denied=DENIED):
        return host.read_member_window(
            self.db, origin=host._STAGE, deployment_reader=lambda: self.live,
            window_id=self.window, allowed=allowed, denied=denied,
        )

    def test_stage_host_readback_passes_real_rollout_consumer(self):
        self.open()
        self.seed()
        self.assertNotIn(ALLOWED, str(host.read_window(self.db)))
        self.assertEqual(self.read()["role_allowed"]["document_status"], 200)
        self.assertEqual(self.read()["role_denied"]["member_api_status"], 200)
        self.assertEqual(self.read()["role_denied"]["premium_dashboard_status"], 403)
        normal = {**self.live, "version_id": NORMAL_VERSION}
        accounts, receipt = member_rollout._observe(
            lambda request: host.member_rollout_observation(
                request, deployment_reader=lambda: self.live, member_db=self.db,
                window_id=self.window, accounts=(ALLOWED, DENIED),
            ),
            {"phase": "stage", "source_commit": SOURCE, "worker_version_id": NORMAL_VERSION,
             "effective_mode": "enabled"}, live=normal, stage=True,
        )
        self.assertEqual(accounts, (ALLOWED, DENIED))
        self.assertEqual(len(receipt), 64)

    def test_conflicting_window_and_incomplete_paths_refuse(self):
        self.open()
        with self.assertRaisesRegex(ValueError, "active member observation"):
            self.open()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.read()

    def test_swapped_accounts_or_changed_live_version_refuse(self):
        self.open()
        self.seed()
        with self.assertRaisesRegex(ValueError, "authorized selection"):
            self.read(allowed=DENIED, denied=ALLOWED)
        self.live = {**self.live, "version_id": NORMAL_VERSION}
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.read()

    def test_rollout_refuses_changed_deployment_during_the_capture(self):
        self.open()
        self.seed()
        other_stage = "30000000-0000-4000-8000-000000000019"
        copies = iter([self.live, {**self.live, "version_id": other_stage}])
        actual_request = {
            "schema": "NEW_A_MEMBER_ROLLOUT_OBSERVATION_REQUEST_V2",
            "phase": "stage", "source_commit": SOURCE, "worker_version_id": NORMAL_VERSION,
            "effective_mode": "enabled", "paths": host._PROTECTED_PATHS,
            "guild_id": host._GUILD, "designated_role_id": host._ROLE,
        }
        with self.assertRaisesRegex(ValueError, "changed during observation"):
            host.member_rollout_observation(
                actual_request, deployment_reader=lambda: next(copies), member_db=self.db,
                window_id=self.window, accounts=(ALLOWED, DENIED),
            )
