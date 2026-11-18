import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from weak_early_beta.new_a.files import atomic_write, digest, encode, private_root, read
from weak_early_beta.new_a.lifecycle_notice_inputs import HOLDING, MORNING, OWNER_PROOF, LifecycleNoticeInputs
from weak_early_beta.new_a.publisher import hash_text, is_read_only_select

REPO = Path(__file__).resolve().parents[1]
DAY = "2026-11-18"
MORNING_NOW = datetime.fromisoformat("2026-11-24T23:01:00+00:00")
HOLDING_NOW = datetime.fromisoformat("2026-11-18T08:00:00+00:00")
CALENDAR = ["2026-11-16", "2026-11-17", DAY, "2026-11-19", "2026-11-20",
            "2026-11-24", "2026-11-25", "2026-11-26"]
OWNER = hash_text("cloud-member:12345678901234567")
DATASET = "a-" + "d" * 24
SHARED_DATASET = "a-" + "e" * 24


class ReadonlyFixture:
    def __init__(self, path):
        self.db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self.called = []

    def query(self, sql, values=()):
        if not is_read_only_select(sql):
            raise AssertionError("non-SELECT dispatched")
        self.called.append((sql, values))
        return [dict(row) for row in self.db.execute(sql, values)]

    def close(self):
        self.db.close()


class LifecycleNoticeInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.root = private_root(self.repo)
        self.db_path = self.repo / "fixture.sqlite"
        self.clock = MORNING_NOW
        self.source = "a" * 64

        # Copy only the exact runtime source that production planning imports.
        for filename in (
            "scripts/windows/new-a-evaluation-morning.cjs",
            "scripts/windows/new-a-lifecycle-notice-inputs.cjs",
            "weak-early-beta-gate/src/new-a-preferences.ts",
            "weak-early-beta-gate/scripts/new-a-ui-source/engine/dataset-runtime.cjs",
            "weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs",
        ):
            copy = self.repo / filename
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / filename, copy)

        self.writer = sqlite3.connect(self.db_path)
        self.addCleanup(self.writer.close)
        self.writer.executescript((REPO / "weak-early-beta-gate/schema/new-a-private.sql").read_text("utf-8"))
        self._publish("2026-11-24")
        preferences = {"initial_cash_yen": 10_000_000, "max_positions": 20,
                       "per_order_cap_yen": 500_000, "base_shares": 100,
                       "cost_percent": 0, "price_cap_yen": None, "exit_endpoint": "d6_open",
                       "year_scope": "all", "allocation": "all"}
        view = {"trial_preset": "profit", "theme": "system", "font_size": "standard", "page_size": 20}
        self.writer.executemany(
            "INSERT INTO new_a_finite_trial_preferences VALUES (?,1,?,?,?)",
            [("cloud_" + OWNER, encode(preferences), 4, DAY),
             ("new-a-view:v1:cloud_" + OWNER, encode(view), 4, DAY),
             ("cloud_" + "9" * 64, encode({**preferences, "exit_endpoint": "a20_close"}), 11, DAY)],
        )
        self.writer.commit()

        files = {}
        for key in ("seed", "calendar", "history_input", "presentation", "quotes"):
            filename = f"{key}.json"
            raw = encode(CALENDAR if key == "calendar" else {}) + "\r\n"
            path = self.root / "bootstrap" / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw.encode("utf-8"))
            files[key] = {"path": filename, "sha256": hash_text(raw)}
        atomic_write(self.root / "bootstrap/manifest.json", {
            "schema": "NEW_A_PRIVATE_BOOTSTRAP_V1", "strategy": "A_BASE", "files": files,
        })
        self.db = ReadonlyFixture(self.db_path)
        self.addCleanup(self.db.close)
        self.proof_reads = 0
        self.inputs = LifecycleNoticeInputs(self.repo, self.db, self._proof,
                                            node=shutil.which("node"), clock=lambda: self.clock)

    def _publish(self, as_of):
        dates = [day for day in CALENDAR if day <= as_of]
        scope = {"symbol": "123A", "candidate_date": dates[0], "episode_id": 1, "priority_score": 1}
        structure = {
            "episodes": [scope],
            "watches": [{**scope, "watch_status": "TRIGGERED", "trigger_date": dates[1]}],
            "intents": [{**scope, "trigger_date": dates[1]}],
            "quotes": [["123A", day, [90, 101, 89, 100, 2000, 100, 2000, 1, True]] for day in dates],
        }
        descriptors = {}
        rows = []
        for kind, values in structure.items():
            dataset = SHARED_DATASET if kind == "episodes" else DATASET
            name = f"{kind}-000.json"
            raw = encode(values)
            part = {"name": name, "sha256": hash_text(raw), "bytes": len(raw.encode()), "rows": len(values)}
            rows.append((dataset, name, raw, part["sha256"], part["bytes"]))
            if dataset != DATASET:
                part["dataset_id"] = dataset
            descriptors[kind] = [part]
        manifest = {
            "schema": "A_BROWSER_PRIVATE_INPUT_V1", "audience": "EXISTING_CLOUD_OWNER_ONLY",
            "strategy": "A_BASE", "source_version": self.source, "daily_snapshot_sha256": "b" * 64,
            "as_of": as_of, "live": True, "quotes": descriptors.pop("quotes"),
            "collections": {**descriptors, "presentation": [], "current_daily": []},
            "expected_quote_keys": len(dates),
            "quote_fields": ["open", "high", "low", "close", "volume", "actual_close", "actual_volume",
                             "split_factor", "source_usable"],
            "input_header": {"calendar": dates, "source_version": self.source,
                             "limits": {"completeThrough": as_of, "identityUnverifiedBefore": {}, "heldSymbols": {}}},
        }
        raw = encode(manifest)
        self.active_hash = digest(["NEW_A_ACTIVE_METADATA_V1", DATASET, 1, "READY",
                                   self.source, hash_text(raw), as_of])
        for dataset in (DATASET, SHARED_DATASET):
            self.writer.execute("INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?) ON CONFLICT(dataset_id) "
                                "DO UPDATE SET manifest_json=excluded.manifest_json,manifest_sha256=excluded.manifest_sha256",
                                (dataset, self.source, raw, hash_text(raw), "READY", DAY))
        self.writer.execute("INSERT OR IGNORE INTO new_a_active_pointer VALUES ('owner',?,1,?)", (DATASET, DAY))
        self.writer.executemany("INSERT OR REPLACE INTO new_a_private_parts VALUES (?,?,?,?,?)", rows)
        self.writer.commit()
        atomic_write(self.root / "latest-publication.json", {
            "schema": "NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1", "published": True, "local_d1_emulation": False,
            "active_readback_verified": True, "existing_owner_gate_verified": True,
            "dataset_id": DATASET, "revision": 1, "source_version": self.source,
            "manifest_sha256": hash_text(raw), "snapshot_sha256": manifest["daily_snapshot_sha256"], "as_of": as_of,
        })

    def _proof(self):
        self.proof_reads += 1
        return {"schema": OWNER_PROOF, "normal_owner_policy_verified": True, "d1_active_sha256": self.active_hash,
                "owner_binding_sha256": OWNER, "observed_at": self.clock.isoformat(),
                "expires_at": (self.clock + timedelta(seconds=40)).isoformat()}

    def _morning(self):
        return self.inputs.prepare(MORNING, now=self.clock, scheduled_at=MORNING_NOW - timedelta(minutes=1))

    def test_uses_exact_owner_and_original_dashboard_exit_policy(self):
        result = self._morning()
        self.assertEqual(result.owner_binding_sha256, OWNER)
        self.assertEqual(result.plan["basis"]["preferences_revision"], 4)
        self.assertEqual(len(result.plan["notices"]), 1)
        self.assertEqual(result.plan["notices"][0]["evaluation_endpoint"], "d5_open")
        binding = self.inputs.read_source(result)
        self.assertEqual(binding["plan_sha256"], digest(result.plan))
        self.assertEqual(self.proof_reads, 3)
        self.assertTrue(any(values[0] == SHARED_DATASET for _, values in self.db.called if values))

    def test_holding_uses_same_verified_part_read_and_actual_prior_watch(self):
        self._publish(DAY)
        self.clock = HOLDING_NOW
        plan = self.inputs.prepare(HOLDING, now=self.clock, target_date=DAY)
        self.assertEqual(len(plan.plan["notices"]), 1)
        self.assertEqual(plan.plan["notices"][0]["simulated_entry_date"], DAY)
        self.assertEqual(plan.plan["notices"][0]["kind"], HOLDING)

    def test_out_of_window_and_bank_holiday_never_read_owner_or_database(self):
        holiday = datetime.fromisoformat("2026-11-22T23:00:00+00:00")
        self.assertEqual(self.inputs.prepare(MORNING, now=holiday, scheduled_at=holiday).plan["status"],
                         "bank_non_business_day")
        self.assertEqual(self.inputs.prepare(MORNING, now=self.clock + timedelta(hours=1),
                                            scheduled_at=self.clock - timedelta(minutes=1)).plan["status"],
                         "outside_reminder_window")
        self.assertEqual(self.db.called, [])
        self.assertEqual(self.proof_reads, 0)

    def test_other_member_or_legacy_row_is_never_selected(self):
        self.writer.execute("DELETE FROM new_a_finite_trial_preferences WHERE member_id = ?", ("cloud_" + OWNER,))
        self.writer.commit()
        with self.assertRaisesRegex(ValueError, "saved New A preferences unavailable"):
            self._morning()

    def test_finite_recovery_receipt_does_not_claim_ordinary_publication(self):
        path = self.root / "latest-publication.json"
        atomic_write(path, {**read(path), "existing_owner_gate_verified": False,
                            "operational_gate_continuity_verified": True})
        with self.assertRaisesRegex(ValueError, "ordinary owner publication receipt differs"):
            self._morning()

    def test_part_storage_must_still_be_ready_and_verified(self):
        self.writer.execute("UPDATE new_a_private_datasets SET status='STAGING' WHERE dataset_id=?", (SHARED_DATASET,))
        self.writer.commit()
        with self.assertRaisesRegex(ValueError, "published replay part is unavailable"):
            self._morning()

    def test_d1_readback_and_owner_authority_must_match(self):
        self.inputs.read_verified_owner = lambda: {**self._proof(), "d1_active_sha256": "1" * 64}
        with self.assertRaisesRegex(ValueError, "production owner policy or D1 identity differs"):
            self._morning()

    def test_stale_owner_authority_rejected_before_selecting_preferences(self):
        expired = self.clock - timedelta(seconds=1)
        self.inputs.read_verified_owner = lambda: {**self._proof(),
            "observed_at": (expired - timedelta(seconds=40)).isoformat(), "expires_at": expired.isoformat()}
        with self.assertRaisesRegex(ValueError, "production owner readback is stale"):
            self._morning()
        self.assertEqual(len(self.db.called), 1)

    def test_owner_revision_race_during_planning_closes_the_plan(self):
        def proof():
            if self.proof_reads == 1:
                self.writer.execute("UPDATE new_a_finite_trial_preferences SET revision = 5 WHERE member_id = ?",
                                    ("cloud_" + OWNER,))
                self.writer.commit()
            return self._proof()
        self.inputs.read_verified_owner = proof
        with self.assertRaisesRegex(ValueError, "owner preferences or calendar changed"):
            self._morning()

    def test_calendar_bytes_are_pinned(self):
        path = self.root / "bootstrap/calendar.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "bootstrap bytes changed"):
            self._morning()

    def test_validation_reuses_owner_endpoint_including_view_preferences(self):
        self.writer.execute("UPDATE new_a_finite_trial_preferences SET preferences_json='{}' WHERE member_id=?",
                            ("new-a-view:v1:cloud_" + OWNER,))
        self.writer.commit()
        with self.assertRaisesRegex(ValueError, "planner rejected"):
            self._morning()

    def test_send_readback_rejects_changed_preferences_or_plan(self):
        result = self._morning()
        result.plan["notices"][0]["title"] = "Changed"
        with self.assertRaisesRegex(ValueError, "verified lifecycle plan changed"):
            self.inputs.read_source(result)
        result = self._morning()
        self.writer.execute("UPDATE new_a_finite_trial_preferences SET revision = 5 WHERE member_id = ?",
                            ("cloud_" + OWNER,))
        self.writer.commit()
        with self.assertRaisesRegex(ValueError, "saved owner preferences changed"):
            self.inputs.read_source(result)


if __name__ == "__main__":
    unittest.main()
