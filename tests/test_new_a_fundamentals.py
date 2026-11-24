"""The exact New A worktree/runtime shapes, with only isolated synthetic data."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from weak_early_beta.new_a.files import atomic_write, digest, encode, file_sha, private_root, read
from weak_early_beta.new_a.fundamentals import HISTORICAL_SCHEMA, retain_verified_for_publication, stage
from weak_early_beta.new_a.cli import publish
from weak_early_beta.new_a.publisher import LocalD1, publish_bundle, verify_dataset
from weak_early_beta.historical_fundamentals import FIELD_ORDER


class NewAFundamentalTests(unittest.TestCase):
    day = "2026-11-18"
    episode = "3133|2026-11-18|test-episode"
    source = "b" * 64

    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        self.runtime = self.repo / "isolated-runtime"
        self.runtime.mkdir()
        self.root = private_root(self.repo)
        self.row = {
            "identity": self.episode, "symbol": "3133", "signalDate": self.day,
            "companyName": "テスト社", "nameStatus": "CURRENT_SOURCE_REFERENCE_NOT_HISTORICAL_NAME",
            "analysisCutoff": None, "fundamental": None,
        }
        self.event = {
            "symbol": "3133", "kind": "WATCH_STARTED", "candidate_date": self.day,
            "session": self.day, "episode_id": "test-episode", "event_id": "a" * 64,
            "observation_kind": "LIVE_OBSERVATION", "is_new_live_signal": True,
        }
        self.build(self.day, [self.event])

    def build(self, day, events, *, delayed=False):
        self.start = f"{day}T08:00:00Z"
        self.cutoff = f"{day}T08:13:42.123Z"
        (self.runtime / "daily.lock").write_text(self.start, encoding="utf-8")
        atomic_write(self.runtime / "daily-latest.json", {
            "startedAt": self.start, "date": day, "stage": "fundamental",
        })
        self.target = self.root / "runs" / day / self.source / "live"
        self.base = self.target / "bundle"
        self.base.mkdir(parents=True)
        snapshot = {
            "schema": "NEW_A_OWNER_DAILY_SNAPSHOT_V1", "strategy": "A_BASE",
            "audience": "EXISTING_CLOUD_OWNER_ONLY", "source_sha256": self.source,
            "as_of": day, "observed_at": f"{day}T08:10:00Z", "observation_kind": "LIVE_OBSERVATION",
            "events": events, "new_live_signals": sum(x["is_new_live_signal"] for x in events),
        }
        snapshot["payload_sha256"] = digest(snapshot)
        atomic_write(self.target / "snapshot.json", snapshot)
        presentation = self.base / "presentation-000.json"
        content = encode([self.row])
        presentation.write_bytes(content.encode())
        manifest = {
            "schema": "A_BROWSER_PRIVATE_INPUT_V1", "strategy": "A_BASE",
            "audience": "EXISTING_CLOUD_OWNER_ONLY", "source_version": "c" * 64,
            "input_header": {"source_version": "c" * 64}, "as_of": day,
            "daily_snapshot_sha256": snapshot["payload_sha256"], "quotes": [],
            "collections": {"episodes": [], "intents": [], "watches": [], "current_daily": [],
                            "presentation": [{"name": presentation.name, "sha256": file_sha(presentation),
                                              "rows": 1, "bytes": len(content.encode())}]},
        }
        atomic_write(self.base / "manifest.json", manifest)
        atomic_write(self.base / "receipt.json", {
            "as_of": day, "manifest_sha256": file_sha(self.base / "manifest.json"),
            "daily_snapshot_sha256": snapshot["payload_sha256"], "source_version": "c" * 64,
        })
        atomic_write(self.root / "latest-run.json", {
            "identity": "NEW_A_CLOUD_DAILY_V1", "strategy": "A_BASE", "detection_executed": True,
            "dry_run": False, "source_sha256": self.source, "latest_session": day,
            "snapshot_file": str(self.target / "snapshot.json"), "bundle_directory": str(self.base),
            "source_version": "c" * 64,
            "snapshot_sha256": snapshot["payload_sha256"], "delayed_recovery": {"test": True} if delayed else None,
        })
        self.target_day = day

    def prepare(self):
        return stage(self.repo, self.runtime, self.target_day, self.start, "prepare", self.cutoff)

    def finish(self, sha=None):
        return stage(self.repo, self.runtime, self.target_day, self.start, "finish", reports_sha256=sha)

    def report(self, alert):
        fields = {name: "確認した資料に基づくテスト本文" for name in FIELD_ORDER}
        fields["材料インパクト"] = "様子見：テスト本文"
        fields["開示リンク"] = "・[2026-11-17 テスト開示(15:30)](https://example.com/filing.pdf)"
        fields["Sources"] = "[IR](https://example.com/ir)\n[TDnet](https://example.com/tdnet)"
        return {
            "alertId": alert["alertId"], "symbolCode": alert["symbolCode"],
            "symbolName": alert["symbolName"], "signalDate": alert["signalDate"],
            "analysisCutoff": alert["analysisCutoff"], "auditStatus": "pass",
            "fields": [{"name": name, "value": value} for name, value in fields.items()],
            "disclosures": [{"title": "テスト開示", "publishedAt": "2026-11-17T15:30:00+09:00",
                             "url": "https://example.com/filing.pdf", "contentReviewed": True}],
            "sourceChecks": [{"role": "official_ir", "url": "https://example.com/ir"},
                             {"role": "irbank_or_tdnet", "url": "https://example.com/tdnet"}],
        }

    def emit_reports(self, prepared, reports):
        path = Path(prepared["reportsPath"])
        atomic_write(path, {"reports": reports})
        return file_sha(path)

    def test_exact_audited_analysis_reaches_owner_bundle_and_is_preserved_on_zero_day(self):
        prepared = self.prepare()
        self.assertEqual(prepared["claimed"], 1)
        claim = read(prepared["claimPath"])
        self.assertEqual(claim["rules"], {"model": "gpt-6.1-sol", "reasoningEffort": "xhigh", "destination": "html", "workflow": "premium-legacy-1fa6d89"})
        self.assertEqual(claim["alerts"][0]["eventId"], self.event["event_id"])
        self.assertEqual(claim["alerts"][0]["receivedAt"], "2026-11-18T08:10:00Z")
        report = self.report(claim["alerts"][0])
        sha = self.emit_reports(prepared, [report])
        base_before = file_sha(self.base / "manifest.json")
        snapshot_before = file_sha(self.target / "snapshot.json")
        result = self.finish(sha)
        self.assertEqual((result["status"], result["imported"], result["posted"]), ("COMPLETE", 1, 0))
        applied = read(self.root / "latest-run.json")
        enriched = Path(applied["bundle_directory"])
        self.assertNotEqual(enriched, self.base)
        self.assertEqual(file_sha(self.base / "manifest.json"), base_before)
        self.assertEqual(file_sha(self.target / "snapshot.json"), snapshot_before)
        presentation = read(enriched / "presentation-000.json")[0]
        self.assertEqual(presentation["fundamental"]["identity"], "2026-11-18|3133")
        self.assertEqual(presentation["analysisCutoff"], self.cutoff)
        schema = Path(__file__).resolve().parents[1] / "weak-early-beta-gate/schema/new-a-private.sql"
        db = LocalD1(self.repo / "isolated-d1.sqlite", schema)
        try:
            published = publish_bundle(db, enriched)
            self.assertTrue(published["active_readback_verified"])
            self.assertFalse(published["published"])
            _, stored_manifest = verify_dataset(db, published["dataset_id"])
            self.assertEqual(stored_manifest["daily_snapshot_sha256"], applied["snapshot_sha256"])
            self.assertEqual(stored_manifest["source_version"], applied["source_version"])
        finally:
            db.close()
        self.assertEqual(self.finish(sha), result)
        next_day = "2026-11-19"
        self.build(next_day, [])
        self.assertEqual(self.prepare()["claimed"], 0)
        self.assertEqual(self.finish()["status"], "NO_NEW_SIGNALS")
        retained = Path(read(self.root / "latest-run.json")["bundle_directory"])
        self.assertEqual(read(retained / "presentation-000.json")[0], presentation)

    def test_refuses_wrong_owner_digest_missing_reports_and_later_disclosure(self):
        prepared = self.prepare()
        claim = read(prepared["claimPath"])
        self.emit_reports(prepared, [])
        with self.assertRaisesRegex(ValueError, "after Node"):
            self.finish("f" * 64)
        with self.assertRaisesRegex(ValueError, "exactly match"):
            self.finish(file_sha(prepared["reportsPath"]))
        report = self.report(claim["alerts"][0])
        report["disclosures"][0]["publishedAt"] = "2026-11-18T08:13:42.124Z"
        with self.assertRaisesRegex(ValueError, "post-analysis-start"):
            self.finish(self.emit_reports(prepared, [report]))
        self.assertEqual(read(self.root / "latest-run.json")["bundle_directory"], str(self.base))
        self.assertFalse((self.root / "fundamentals" / "verified").exists())

    def store_historical_ledger(self, profiles):
        directory = self.root / "fundamentals" / "historical"
        staged = directory / "verified-ledger.json"
        atomic_write(staged, {
            "schema": HISTORICAL_SCHEMA, "scope": "owner-presentation",
            "frozen_snapshot_sha256": "a" * 64, "frozen_archive_index_sha256": "b" * 64,
            "frozen_owner_manifest_sha256": "c" * 64, "inventory_sha256": "d" * 64,
            "profiles": profiles,
        })
        sha = file_sha(staged)
        staged.replace(directory / (sha + ".json"))
        atomic_write(directory / "latest.json", {"sha256": sha})
        return sha

    def test_historical_report_is_bound_to_exact_episode_and_daily_input_pin(self):
        episode = "3133|2026-11-18|1"
        self.row["identity"] = episode
        self.build("2026-11-19", [])
        cutoff = self.day + "T16:15:00+09:00"
        report = {
            "identity": "2026-11-18|3133", "signalDate": self.day, "symbol": "3133",
            "analysisCutoff": cutoff, "auditStatus": "pass",
            "fields": [{"label": name, "text": "照合済み資料"} for name in FIELD_ORDER],
        }
        profile = {
            "presentation": report, "company_name": "テスト社", "cutoff": cutoff,
            "report_sha256": "1" * 64, "validation_sha256": "2" * 64, "validator_sha256": "3" * 64,
        }
        historical_sha = self.store_historical_ledger({episode: profile})
        prepared = self.prepare()
        self.assertEqual(prepared["claimed"], 0)
        self.store_historical_ledger({"3133|2026-11-18|2": profile})
        result = self.finish()
        self.assertEqual(result["historical"], {
            "ledgerSha256": historical_sha, "attached": 1, "available": 1,
            "alreadyVerified": 0, "unmatched": 0,
        })
        output = Path(read(self.root / "latest-run.json")["bundle_directory"])
        self.assertEqual(read(output / "presentation-000.json")[0]["fundamental"], report)
        self.assertEqual(self.finish(), result)
        self.build("2026-11-20", [])
        self.prepare()
        result = self.finish()
        self.assertEqual(result["historical"]["attached"], 0)
        self.assertEqual(result["historical"]["unmatched"], 1)

    def test_historical_hash_mismatch_cannot_change_owner_bundle(self):
        self.build("2026-11-19", [])
        sha = self.store_historical_ledger({})
        self.prepare()
        path = self.root / "fundamentals" / "historical" / (sha + ".json")
        path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "historical fundamental ledger changed"):
            self.finish()
        self.assertEqual(read(self.root / "latest-run.json")["bundle_directory"], str(self.base))
        (self.runtime / "daily.lock").write_text("other-owner", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lock owner"):
            self.prepare()

    def test_refuses_old_or_delayed_detection_before_claim(self):
        run_path = self.root / "latest-run.json"
        run = read(run_path)
        atomic_write(run_path, {**run, "delayed_recovery": {"fixture": True}})
        with self.assertRaisesRegex(ValueError, "same-day ordinary"):
            self.prepare()
        self.assertFalse((self.target / "fundamental-analysis").exists())

    def replace_presentation(self, folder, rows):
        manifest = read(folder / "manifest.json")
        content = encode(rows)
        part = folder / "presentation-000.json"
        part.write_text(content, encoding="utf-8")
        manifest["collections"]["presentation"] = [{
            "name": part.name, "sha256": file_sha(part), "rows": len(rows),
            "bytes": len(content.encode()),
        }]
        atomic_write(folder / "manifest.json", manifest)
        receipt = read(folder / "receipt.json")
        atomic_write(folder / "receipt.json", {**receipt, "manifest_sha256": file_sha(folder / "manifest.json")})

    def local_owner(self):
        schema = Path(__file__).resolve().parents[1] / "weak-early-beta-gate/schema/new-a-private.sql"
        db = LocalD1(self.repo / "owner.sqlite", schema)
        self.addCleanup(db.close)
        return db

    def test_publication_retains_old_analysis_when_new_research_is_held(self):
        self.row["identity"] = f"3133|{self.day}|1"
        new_day = "2026-11-19"
        new_event = {**self.event, "symbol": "9999", "session": new_day,
                     "candidate_date": new_day, "episode_id": "new-episode", "event_id": "d" * 64}
        self.build(new_day, [new_event])
        new_row = {**self.row, "identity": f"9999|{new_day}|new-episode", "symbol": "9999",
                   "signalDate": new_day, "companyName": "新しいテスト社"}
        self.replace_presentation(self.base, [self.row, new_row])
        cutoff = self.day + "T16:15:00+09:00"
        old_report = {"identity": self.day + "|3133", "signalDate": self.day, "symbol": "3133",
                      "analysisCutoff": cutoff, "auditStatus": "pass",
                      "fields": [{"label": name, "text": "以前の検証済み本文"} for name in FIELD_ORDER]}
        self.store_historical_ledger({self.row["identity"]: {
            "presentation": old_report, "company_name": "テスト社", "cutoff": cutoff,
            "report_sha256": "1" * 64, "validation_sha256": "2" * 64, "validator_sha256": "3" * 64,
        }})
        prepared = self.prepare()
        self.assertEqual(prepared["claimed"], 1)
        claim_sha = file_sha(prepared["claimPath"])
        snapshot_sha = file_sha(self.target / "snapshot.json")
        base_sha = file_sha(self.base / "manifest.json")
        (self.runtime / "daily.lock").unlink()
        before = read(self.root / "latest-run.json")
        with patch("weak_early_beta.new_a.fundamentals.stage", side_effect=AssertionError("No new research")):
            receipt = publish(self.root, self.local_owner())
        applied = read(self.root / "latest-run.json")
        output = Path(applied["bundle_directory"])
        actual = read(output / "presentation-000.json")
        self.assertEqual(actual[0]["fundamental"], old_report)
        self.assertIsNone(actual[1]["fundamental"])
        self.assertEqual(actual[1], new_row)
        self.assertEqual({k: v for k, v in actual[0].items() if k not in {"fundamental", "analysisCutoff"}},
                         {k: v for k, v in self.row.items() if k not in {"fundamental", "analysisCutoff"}})
        self.assertEqual(applied["retained_fundamentals"]["visible"], 1)
        self.assertFalse(applied["retained_fundamentals"]["newResearch"])
        self.assertEqual(receipt["snapshot_sha256"], before["snapshot_sha256"])
        self.assertEqual(file_sha(prepared["claimPath"]), claim_sha)
        self.assertEqual(file_sha(self.target / "snapshot.json"), snapshot_sha)
        self.assertEqual(file_sha(self.base / "manifest.json"), base_sha)
        self.assertFalse((self.root / "fundamentals/verified").exists())
        self.assertFalse((self.root / "notification-outbox.sqlite").exists())

    def test_successful_analysis_publication_and_republication_do_not_change_its_generation(self):
        prepared = self.prepare()
        sha = self.emit_reports(prepared, [self.report(read(prepared["claimPath"])["alerts"][0])])
        self.finish(sha)
        before = read(self.root / "latest-run.json")
        db = self.local_owner()
        initial = publish(self.root, db)
        first_run = read(self.root / "latest-run.json")
        again = publish(self.root, db)
        self.assertEqual(first_run, read(self.root / "latest-run.json"))
        self.assertEqual(first_run["bundle_directory"], before["bundle_directory"])
        self.assertEqual(first_run["source_version"], before["source_version"])
        self.assertEqual(initial["revision"], again["revision"])
        self.assertTrue(again["same_dataset_replay"])

    def test_conflicting_attached_analysis_is_not_overwritten_by_a_cache(self):
        prepared = self.prepare()
        self.finish(self.emit_reports(prepared, [self.report(read(prepared["claimPath"])["alerts"][0])]))
        run = read(self.root / "latest-run.json")
        folder = Path(run["bundle_directory"])
        rows = read(folder / "presentation-000.json")
        rows[0]["fundamental"]["fields"][0]["text"] = "矛盾する別の本文"
        self.replace_presentation(folder, rows)
        with self.assertRaisesRegex(ValueError, "overwrite other presentation evidence"):
            retain_verified_for_publication(self.root, run)
        self.assertEqual(run, read(self.root / "latest-run.json"))

    def test_invalid_retained_history_blocks_publication_without_erasing_previous_data(self):
        sha = self.store_historical_ledger({})
        (self.root / "fundamentals/historical" / (sha + ".json")).write_text("{}", encoding="utf-8")
        run = read(self.root / "latest-run.json")
        with self.assertRaisesRegex(ValueError, "historical fundamental ledger changed"):
            publish(self.root, self.local_owner())
        self.assertEqual(run, read(self.root / "latest-run.json"))
        self.assertFalse((self.root / "latest-publication.json").exists())


if __name__ == "__main__":
    unittest.main()
