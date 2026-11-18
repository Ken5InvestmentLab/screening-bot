"""Integration of the actual planner and queue using an isolated D1 fixture."""
from datetime import datetime, timedelta
import json
import unittest

from tests import test_new_a_lifecycle_notice_inputs as fixtures
from weak_early_beta.new_a.continuing_transition import RUNTIME_RELEASE_SCHEMA
from weak_early_beta.new_a.files import atomic_write, digest, encode, read
from weak_early_beta.new_a.owner_notice_producer import OwnerNoticeProducer
from weak_early_beta.new_a.planned_notice_delivery import AUDIENCE, HOLDING, MORNING
from weak_early_beta.new_a.publisher import LocalD1, hash_text


class OwnerNoticeProducerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LifecycleNoticeInputTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.repo = self.fixture.repo
        schema = fixtures.REPO / "weak-early-beta-gate/schema"
        self.queue = LocalD1(self.fixture.db_path, schema / "new-a-owner-notice-queue.sql")
        self.addCleanup(self.queue.close)
        self.release = {
            "schema": RUNTIME_RELEASE_SCHEMA, "worker": "tentei-kyokuchi-cloud",
            "database": "tentei-cloud-settings", "source_commit": "a" * 40,
            "version_id": "11111111-2222-3333-4444-555555555555",
            "activation_sha256": "c" * 64, "build_input_sha256": "d" * 64,
        }
        self.recipient_reads = 0
        self.producer = OwnerNoticeProducer(
            self.repo, self.fixture.inputs, self.queue, read_release=lambda: self.release,
            read_recipient=self._recipient, clock=lambda: self.fixture.clock,
        )

    def _recipient(self):
        self.recipient_reads += 1
        now = self.fixture.clock
        return {
            "schema": "NEW_A_OWNER_NOTICE_RECIPIENT_V1", "audience": AUDIENCE,
            "enabled": True, "owner_verified": True, "fresh_paid_role": True,
            "owner_binding_sha256": fixtures.OWNER, "recipient_binding_sha256": "e" * 64,
            "observed_at": now.isoformat(), "expires_at": (now + timedelta(minutes=1)).isoformat(),
        }

    def _run(self, date, **overrides):
        self.fixture._publish(date)
        publication_path = self.fixture.root / "latest-publication.json"
        publication = read(publication_path)
        dataset = self.queue.query("SELECT manifest_json FROM new_a_private_datasets WHERE dataset_id=?",
                                   (fixtures.DATASET,))[0]
        manifest = json.loads(dataset["manifest_json"])
        manifest["input_header"]["limits"]["nextPlannedSession"] = fixtures.CALENDAR[fixtures.CALENDAR.index(date) + 1]
        manifest_raw = encode(manifest)
        publication["manifest_sha256"] = hash_text(manifest_raw)
        self.queue.query("UPDATE new_a_private_datasets SET manifest_json=?,manifest_sha256=? WHERE dataset_id=?",
                         (manifest_raw, publication["manifest_sha256"], fixtures.DATASET))
        self.fixture.active_hash = digest([
            "NEW_A_ACTIVE_METADATA_V1", fixtures.DATASET, publication["revision"], "READY",
            publication["source_version"], publication["manifest_sha256"], date,
        ])
        atomic_write(publication_path, publication)
        started_at = date + "T08:00:00.000Z"
        run = {"identity": "WEAK_EARLY_CLOUD_DAILY_V1", "startedAt": started_at,
               "completedAt": date + "T08:20:00.000Z", "date": date, "latestSession": date,
               "ok": True, "startCommit": self.release["source_commit"],
               "new_a": {"owner_publication_verified": True,
                         **{key: publication[key] for key in ("dataset_id", "source_version", "snapshot_sha256")}},
               "deployment": {"reusedApprovedCodeOnly": True, "approvedWorkerReadback": {
                   "sourceCommit": self.release["source_commit"], "versionId": self.release["version_id"],
                   "buildInputSha256": self.release["build_input_sha256"]}}, **overrides}
        runtime = self.repo / ".cache/weak_early_beta/daily_runtime"
        path = runtime / ("daily-" + started_at.replace(":", "-").replace(".", "-")) / "result.json"
        atomic_write(path, run)
        return path

    def _rows(self):
        return self.queue.query("SELECT kind,target_date,payload_json FROM new_a_owner_notice_queue ORDER BY target_date")

    def test_after_publication_stages_real_same_session_holding_before_consumer(self):
        path = self._run(fixtures.DAY)
        self.fixture.clock = fixtures.HOLDING_NOW + timedelta(minutes=30)
        first = self.producer.after_publication(path)
        second = self.producer.after_publication(path)
        self.assertEqual(first, second)
        self.assertEqual(first["holding"]["staged"], 1)
        self.assertEqual(first["morning"]["target_date"], "2026-11-19")
        self.assertEqual(first["morning"]["staged"], 0)
        rows = self._rows()
        self.assertEqual([(r["kind"], r["target_date"]) for r in rows], [(HOLDING, fixtures.DAY)])
        payload = json.loads(rows[0]["payload_json"])
        self.assertEqual(payload["publication"]["as_of"], fixtures.DAY)
        self.assertEqual(len(payload["notices"]), 1)

    def test_previous_jpx_publication_can_stage_exact_08_slot_in_advance_and_verify_at_08(self):
        path = self._run("2026-11-24")
        self.fixture.clock = datetime.fromisoformat("2026-11-24T08:30:00+00:00")
        result = self.producer.after_publication(path)
        self.assertEqual(result["holding"]["staged"], 0)
        self.assertEqual(result["morning"]["staged"], 1)
        rows = self._rows()
        self.assertEqual([(r["kind"], r["target_date"]) for r in rows], [(MORNING, "2026-11-25")])
        payload = json.loads(rows[0]["payload_json"])
        self.assertEqual(payload["publication"]["as_of"], "2026-11-24")
        self.assertEqual(len(payload["notices"]), 1)
        self.fixture.clock = fixtures.MORNING_NOW
        staged = self.producer.at_morning(path, scheduled_at=fixtures.MORNING_NOW - timedelta(minutes=1))
        self.assertEqual(staged["payload_sha256"], result["morning"]["payload_sha256"])
        self.assertEqual(self._rows(), rows)

    def test_weekend_and_bank_holiday_gap_uses_the_next_pinned_jpx_session(self):
        path = self._run("2026-11-20")
        self.fixture.clock = datetime.fromisoformat("2026-11-20T08:30:00+00:00")
        result = self.producer.after_publication(path)
        self.assertEqual(result["morning"]["target_date"], "2026-11-24")
        self.assertEqual(result["morning"]["staged"], 0)
        self.assertEqual(self.recipient_reads, 0)

    def test_morning_rejects_stale_source_or_bad_schedule_before_device_lookup(self):
        path = self._run("2026-11-20")
        schedule = fixtures.MORNING_NOW - timedelta(minutes=1)
        with self.assertRaisesRegex(ValueError, "preceding JPX publication"):
            self.producer.at_morning(path, schedule)
        with self.assertRaisesRegex(ValueError, "08:00"):
            self.producer.at_morning(path, fixtures.MORNING_NOW)
        self.assertEqual(self.fixture.proof_reads, 0)
        self.assertEqual(self.recipient_reads, 0)
        self.assertEqual(self._rows(), [])

    def test_no_staging_from_incomplete_or_delayed_ordinary_receipt(self):
        for overrides in ({"ok": False}, {"observationKind": "DELAYED_SCHEDULED_OBSERVATION"}):
            path = self._run(fixtures.DAY, **overrides)
            self.fixture.clock = fixtures.HOLDING_NOW + timedelta(minutes=30)
            with self.assertRaisesRegex(ValueError, "completed ordinary publication"):
                self.producer.after_publication(path)
        self.assertEqual(self.fixture.proof_reads, 0)
        self.assertEqual(self.recipient_reads, 0)
        self.assertEqual(self._rows(), [])
