"""Stage-only tests using a local SQLite database and synthetic verification."""
from datetime import datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from weak_early_beta.new_a.continuing_transition import RUNTIME_RELEASE_SCHEMA
from weak_early_beta.new_a.files import atomic_write, digest, private_root
from weak_early_beta.new_a.owner_notice_queue import stage_notice_queue
from weak_early_beta.new_a.planned_notice_delivery import AUDIENCE, HOLDING, MORNING
from weak_early_beta.new_a.publisher import LocalD1


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "weak-early-beta-gate/schema/new-a-private.sql"


class OwnerNoticeQueueTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        self.db = LocalD1(self.repo / "queue.db", SCHEMA_PATH)
        self.addCleanup(self.db.close)
        self.db.db.executescript(SCHEMA_PATH.with_name("new-a-owner-notice-queue.sql").read_text("utf-8"))
        self.owner = "1" * 64
        self.recipient = "2" * 64
        self.day = "2026-11-25"
        self.now = datetime.fromisoformat(self.day + "T17:15:00+09:00")
        self.release = {
            "schema": RUNTIME_RELEASE_SCHEMA, "worker": "tentei-kyokuchi-cloud",
            "database": "tentei-cloud-settings", "source_commit": "b" * 40,
            "version_id": "11111111-2222-3333-4444-555555555555",
            "activation_sha256": "a" * 64, "build_input_sha256": "b" * 64,
        }
        self.basis = {"dataset_id": "a-" + "c" * 24, "revision": 3, "preferences_revision": 2,
                      "manifest_sha256": "3" * 64, "source_version": "4" * 64, "snapshot_sha256": "5" * 64}
        self.event = {
            "event_id": "e" * 64, "kind": HOLDING, "symbol": "123A", "candidate_date": "2026-11-24",
            "simulated_entry_date": self.day, "execution_status": "SIMULATED_NOT_ACTUAL_TRADES",
            "title": "監視から仮想保有に移行", "description": "保存した条件による仮想保有です。実際の取引は行われていません。",
        }
        self.plan = {"status": "planned", "target_date": self.day, "basis": self.basis,
                     "model_basis": "SAVED_SCOPE", "notices": [self.event]}
        self.run = self.repo / ".cache/weak_early_beta/daily_runtime/daily-fixture/result.json"
        self.write_receipts(as_of=self.day)
        self.db.query("INSERT INTO new_a_private_datasets VALUES (?,?,?,?,'READY',?)",
                      (self.basis["dataset_id"], self.basis["source_version"], "{}", self.basis["manifest_sha256"], self.day))
        self.db.query("INSERT INTO new_a_active_pointer VALUES ('owner',?,?,?)",
                      (self.basis["dataset_id"], self.basis["revision"], self.day))
        self.db.query("INSERT INTO new_a_finite_trial_preferences VALUES (?,1,?,?,?)",
                      ("cloud_" + self.owner, "{}", self.basis["preferences_revision"], self.day))

    def write_receipts(self, *, as_of, publish_overrides=None):
        private = private_root(self.repo)
        public_fields = {k: self.basis[k] for k in ("dataset_id", "revision", "manifest_sha256", "source_version", "snapshot_sha256")}
        atomic_write(private / "latest-publication.json", {
            **public_fields, "schema": "NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1", "as_of": as_of,
            "published": True, "active_readback_verified": True, "existing_owner_gate_verified": True,
            "local_d1_emulation": False, **(publish_overrides or {}),
        })
        atomic_write(self.run, {
            "ok": True, "date": as_of, "latestSession": as_of, "startCommit": self.release["source_commit"],
            "completedAt": as_of + "T08:10:00Z",
            "new_a": {**public_fields, "owner_publication_verified": True},
            "deployment": {"reusedApprovedCodeOnly": True, "approvedWorkerReadback": {
                "versionId": self.release["version_id"], "sourceCommit": self.release["source_commit"],
                "buildInputSha256": self.release["build_input_sha256"],
            }},
        })

    def source(self):
        return {
            "schema": "NEW_A_OWNER_NOTICE_SOURCE_V1", "current": True, "owner_binding_sha256": self.owner,
            "plan_sha256": digest(self.plan), "basis": self.basis, "observed_at": self.now.isoformat(),
        }

    def device(self):
        return {
            "schema": "NEW_A_OWNER_NOTICE_RECIPIENT_V1", "audience": AUDIENCE,
            "enabled": True, "owner_verified": True, "fresh_paid_role": True, "owner_binding_sha256": self.owner,
            "recipient_binding_sha256": self.recipient, "observed_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=1)).isoformat(),
        }

    def stage(self, kind=HOLDING, **options):
        args = dict(kind=kind, owner=self.owner, read_source=self.source, read_release=lambda: self.release,
                    read_recipient=self.device, now=lambda: self.now)
        return stage_notice_queue(self.db, self.repo, self.run, self.plan, **{**args, **options})

    def rows(self):
        return self.db.query("SELECT target_date,kind,payload_json,payload_sha256 FROM new_a_owner_notice_queue")

    def test_idempotent_staging_retains_exact_row_and_refuses_a_different_plan(self):
        first = self.stage()
        self.assertEqual(first, self.stage())
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["payload_sha256"], first["payload_sha256"])
        self.event["event_id"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "staging conflict"):
            self.stage()
        self.assertEqual(self.rows()[0]["payload_sha256"], first["payload_sha256"])

    def test_database_pointer_or_preference_race_blocks_the_write(self):
        def changed():
            self.db.query("UPDATE new_a_finite_trial_preferences SET revision=3")
            return self.source()
        with self.assertRaisesRegex(ValueError, "source race"):
            self.stage(read_source=changed)
        self.assertEqual(self.rows(), [])

    def test_finite_publication_or_over_budget_is_held(self):
        self.write_receipts(as_of=self.day, publish_overrides={"operational_gate_continuity_verified": True})
        with self.assertRaisesRegex(ValueError, "ordinary published"):
            self.stage()
        self.plan["notices"] = [{**self.event, "event_id": f"{i:064x}"} for i in range(1001)]
        with self.assertRaisesRegex(ValueError, "source bound"):
            self.stage()
        self.assertEqual(self.rows(), [])

    def test_thousand_events_fit_the_d1_statement_and_staged_payload(self):
        self.plan["notices"] = [{**self.event, "event_id": f"{i:064x}", "symbol": f"{i:04d}"} for i in range(1000)]
        result = self.stage()
        self.assertEqual(result["staged"], 1000)
        row = self.rows()[0]
        self.assertLess(len(row["payload_json"].encode("utf-8")), 85_000)
        document = json.loads(row["payload_json"])
        self.assertEqual(document["schema"], "NEW_A_OWNER_NOTICE_QUEUE_V2")
        self.assertEqual(len(document["notices"]), 1000)
        self.assertEqual(document["notices"][0], ["A" * 43, "0000", 20261124, 20261125, None])

    def test_morning_requires_real_local_time_and_previous_publication(self):
        self.plan["basis"]["calendar_sha256"] = "6" * 64
        self.event.update(kind=MORNING, candidate_date="2026-11-17", simulated_entry_date="2026-11-18", scheduled_evaluation_date=self.day,
                          evaluation_endpoint="d5_open", evaluation_timing="OPEN", evaluation_price_status="NOT_YET_OBSERVED",
                          title="確定日の朝8時（日本時間）", description="今日は、設定した確定日です。その日の価格はまだ確定していません。")
        with self.assertRaisesRegex(ValueError, "08:00 JST"):
            self.stage(MORNING)
        self.now = datetime.fromisoformat(self.day + "T08:00:00+09:00")
        self.write_receipts(as_of="2026-11-24")
        self.assertEqual(self.stage(MORNING)["staged"], 1)

    def test_future_morning_can_be_staged_from_its_actual_preceding_evening(self):
        due = datetime.fromisoformat(self.day + "T08:00:00+09:00")
        self.now = datetime.fromisoformat("2026-11-24T17:15:00+09:00")
        self.write_receipts(as_of="2026-11-24")
        self.plan.update(preparation_mode="AFTER_ORDINARY_PUBLICATION", scheduled_for="2026-11-24T23:00:00.000Z")
        self.plan["basis"]["calendar_sha256"] = "6" * 64
        self.event.update(kind=MORNING, candidate_date="2026-11-17", simulated_entry_date="2026-11-18",
                          scheduled_evaluation_date=self.day, evaluation_endpoint="d5_open", evaluation_timing="OPEN",
                          evaluation_price_status="NOT_YET_OBSERVED", title="確定日の朝8時（日本時間）",
                          description="今日は、設定した確定日です。その日の価格はまだ確定していません。")
        with self.assertRaisesRegex(ValueError, "preparation mode"):
            self.stage(MORNING)
        self.assertEqual(self.stage(MORNING, advance=True, scheduled_at=due)["staged"], 1)
        self.assertEqual(json.loads(self.rows()[0]["payload_json"])["notices"][0][4], 1)
