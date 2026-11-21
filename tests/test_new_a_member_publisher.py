import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from weak_early_beta.new_a import member_publication
from weak_early_beta.new_a.member_reference_publication import SCHEMA as REFERENCE_SCHEMA, VARIANTS, READY_INDEX
from weak_early_beta.new_a.files import atomic_write, file_sha, private_root, read
from weak_early_beta.new_a.member_publisher import import_member_projection, read_member_marker
from weak_early_beta.new_a.operational_admission import read_active_metadata
from weak_early_beta.new_a.publisher import LocalD1


REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "weak-early-beta-gate"
SCHEMA = GATE / "member-migrations/0001_new_a_member_storage.sql"
OWNER_SCHEMA = GATE / "schema/new-a-private.sql"
DAY = "2026-11-19"


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def source(revision):
    return {
        "status": "READY", "dataset_id": f"a-{revision:024x}", "revision": revision,
        "as_of": DAY, "source_version": f"{revision:064x}",
    }


def projection(
    folder, ready, *, alter=lambda parts: None,
    source_manifest_sha256="d" * 64, owner_readback_sha256="e" * 64, tiered=False, report=None,
):
    folder.mkdir()
    tiered = tiered or report is not None
    parts = [
        {"kind": "history", "index": 0, "rows": [{"date": DAY, "symbol": "123A", "state": "WATCHING"}]},
        {"kind": "analytics", "index": 0, "rows": [
            {"preset": preset, "from": DAY, "through": DAY, "resolved": False, "metrics": None}
            for preset in ("defensive", "medium", "return_priority")
        ]},
        *[
            {"kind": "chart", "index": index, "rows": [{"date": DAY, "equity_yen": None, "holding_count": None}]}
            for index in range(3)
        ],
    ]
    if tiered:
        parts[0]["rows"] = [{"date": "2026-11-17", "symbol": "123A", "state": "TRIGGERED"}]
        parts[1:1] = [
            {"kind": "history", "index": 1, "rows": [
                {"date": "2026-11-17", "symbol": "123A", "state": "HOLD_ENDED", "completed_on": DAY},
            ]},
            {"kind": "history", "index": 2, "rows": []},
        ]
    if report is not None:
        body = encode(report)
        report_hash = sha(body)
        (folder / f"fundamental-{report_hash}.json").write_bytes(body.encode())
        parts[0]["rows"][0]["fundamental_sha256"] = report_hash
    alter(parts)
    descriptors = []
    for part in parts:
        text = encode(part)
        kind, index = part["kind"], part["index"]
        (folder / f"{kind}-{index}.json").write_bytes(text.encode())
        descriptors.append({
            "kind": kind, "index": index, "rows": len(part["rows"]), "bytes": len(text.encode()),
            "sha256": sha(text),
        })
    manifest = encode({
        "schema": "NEW_A_SHARED_READONLY_VIEW_V" + ("3" if report is not None else "2" if tiered else "1"),
        **({"fundamental_reports": 1} if report is not None else {}),
        "audience": "AUTHENTICATED_TIERED_DISCORD_VIEW" if tiered else "EXISTING_DESIGNATED_DISCORD_ROLE",
        "basis": "SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS", "source": ready, "parts": descriptors,
        **({"history_layout": {"premium_pages": 1, "completed_pages": 1}} if tiered else {}),
    })
    (folder / "manifest.json").write_bytes(manifest.encode())
    receipt = encode({
        "schema": "NEW_A_MEMBER_PROJECTION_OFFLINE_V" + ("3" if report is not None else "2" if tiered else "1"),
        **({"fundamental_reports": 1} if report is not None else {}),
        "source": ready,
        "source_manifest_sha256": source_manifest_sha256, "owner_readback_sha256": owner_readback_sha256,
        "projection_manifest_sha256": sha(manifest), "history_rows": 1, "parts": len(parts), "activated": False,
    })
    (folder / "receipt.json").write_bytes(receipt.encode())
    return sha(receipt)


class FaultableD1:
    def __init__(self, db, *, before_marker=None):
        self.db = db
        self.before_marker = before_marker
        self.marker_writes = 0

    def query(self, sql, values=()):
        if sql.lstrip().startswith(("INSERT INTO private_projection_ready", "UPDATE private_projection_ready")):
            self.marker_writes += 1
            if self.before_marker:
                self.before_marker()
        return self.db.query(sql, values)

    def batch(self, statements):
        return self.db.batch(statements)


class MemberPublisherTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="new-a-member-publisher-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.member_path = self.root / "members.sqlite"
        self.member = LocalD1(self.member_path, SCHEMA)
        self.addCleanup(self.member.close)
        self.owner = LocalD1(self.root / "owner.sqlite", OWNER_SCHEMA)
        self.addCleanup(self.owner.close)
        self.put_owner(source(4))
        self.folder = self.root / "p4"
        self.pin = projection(self.folder, source(4))

    def put_owner(self, ready):
        manifest = encode({
            "schema": "A_BROWSER_PRIVATE_INPUT_V1", "audience": "EXISTING_CLOUD_OWNER_ONLY",
            "strategy": "A_BASE", "as_of": ready["as_of"], "source_version": ready["source_version"],
            "daily_snapshot_sha256": "a" * 64, "quotes": [],
            "collections": {key: [] for key in ("episodes", "intents", "watches", "presentation", "current_daily")},
        })
        self.owner.query(
            "INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?)",
            (ready["dataset_id"], ready["source_version"], manifest, sha(manifest), "READY", ready["as_of"]),
        )
        self.owner.query(
            """INSERT INTO new_a_active_pointer VALUES ('owner',?,?,?)
            ON CONFLICT(pointer_key) DO UPDATE SET dataset_id=excluded.dataset_id,revision=excluded.revision""",
            (ready["dataset_id"], ready["revision"], ready["as_of"]),
        )

    def read_owner(self):
        row, = self.owner.query("""
            SELECT d.status,d.dataset_id,p.revision,d.source_version,d.manifest_json
            FROM new_a_active_pointer p JOIN new_a_private_datasets d ON p.dataset_id=d.dataset_id
            WHERE p.pointer_key='owner'
        """)
        row["as_of"] = json.loads(row.pop("manifest_json"))["as_of"]
        return row

    def ingest(self, *, db=None, prepared=None, baseline=None, activate=True, read_owner=None):
        folder, pin = prepared or (self.folder, self.pin)
        return import_member_projection(
            db or self.member, folder, read_official_ready=read_owner or self.read_owner,
            receipt_sha256=pin, expected_previous=baseline, activate=activate,
        )

    def test_stage_activate_replay_and_update_only_member_marker(self):
        staged = self.ingest(activate=False)
        self.assertEqual(staged["status"], "staged")
        self.assertIsNone(read_member_marker(self.member))
        imported = self.ingest()
        old = read_member_marker(self.member)
        self.assertEqual(old, {key: imported[key] for key in ("identity", "digest")})
        self.assertEqual(imported["status"], "activated")
        self.assertEqual(self.ingest()["status"], "already_active")
        self.assertEqual(self.read_owner(), source(4))
        self.put_owner(source(5))
        next_folder = self.root / "p5"
        next_pin = projection(next_folder, source(5))
        newer = self.ingest(prepared=(next_folder, next_pin), baseline=old)
        self.assertEqual(newer["source"], source(5))
        self.assertEqual(newer["status"], "activated")
        self.assertEqual(self.member.query("SELECT COUNT(*) AS n FROM private_projection_manifest"), [{"n": 2}])
        self.assertEqual(self.read_owner(), source(5))

    def test_reject_exact_pin_and_part_corruption_before_any_write(self):
        with self.assertRaisesRegex(ValueError, "receipt_pin"):
            self.ingest(prepared=(self.folder, "0" * 64))
        (self.folder / "history-0.json").write_text(
            (self.folder / "history-0.json").read_text(encoding="utf8").replace("123A", "123B"), encoding="utf8",
        )
        with self.assertRaisesRegex(ValueError, "part_pin"):
            self.ingest()
        self.assertEqual(self.member.query("SELECT COUNT(*) AS n FROM private_projection_manifest"), [{"n": 0}])

    def test_reject_new_private_fields_and_unsupported_remote_statement_size(self):
        private = self.root / "private"
        private_pin = projection(
            private, source(4), alter=lambda parts: parts[0]["rows"][0].update({"owner": "fixture-only"}),
        )
        with self.assertRaisesRegex(ValueError, "public_row_shape"):
            self.ingest(prepared=(private, private_pin))
        large = self.root / "large"
        large_pin = projection(
            large, source(4), alter=lambda parts: parts[2]["rows"].extend(copy.deepcopy(parts[2]["rows"]) * 1699),
        )
        self.assertGreater((large / "chart-0.json").stat().st_size, 90_000)
        with self.assertRaisesRegex(ValueError, "sql_statement_budget"):
            self.ingest(prepared=(large, large_pin))
        self.assertEqual(self.member.query("SELECT COUNT(*) AS n FROM private_projection_manifest"), [{"n": 0}])

    def test_tiered_projections_require_completed_rows_to_match_an_exact_premium_predecessor(self):
        for index, (field, value) in enumerate((
            ("symbol", "123B"), ("state", "WATCHING"), ("completed_on", "2026-11-20"),
            ("completed_on", "2026-11-16"),
        )):
            with self.subTest(field=field):
                folder = self.root / f"tiered-invalid-{index}"
                def alter(parts):
                    parts[1]["rows"][0][field] = value
                pin = projection(folder, source(4), alter=alter, tiered=True)
                with self.assertRaisesRegex(ValueError, "completed_history|public_row_shape"):
                    import_member_projection(self.member, folder, receipt_sha256=pin,
                                             read_official_ready=lambda: source(4), expected_previous=None)
                self.assertIsNone(read_member_marker(self.member))
        folder = self.root / "tiered-valid"
        pin = projection(folder, source(4), tiered=True)
        result = import_member_projection(self.member, folder, receipt_sha256=pin,
                                          read_official_ready=lambda: source(4), expected_previous=None)
        self.assertEqual(result["status"], "activated")
        self.assertEqual(result["parts"], 7)

    def test_verified_fundamentals_require_exact_premium_row_and_complete_sidecar_readback(self):
        self.member.db.executescript((GATE / "member-migrations/0005_new_a_member_fundamental_reports.sql").read_text(encoding="utf-8"))
        report = {
            "date": "2026-11-17", "symbol": "123A", "company_name": "テスト会社",
            "analysis_cutoff": "2026-11-17T12:00:00+09:00",
            "fields": [{"label": label, "text": "公開済み本文"} for label in (
                "材料インパクト", "事業概要", "足元材料", "ファンダ要点", "注意点", "開示リンク", "Sources",
            )],
        }
        with self.assertRaisesRegex(ValueError, "fundamental_shape"):
            folder = self.root / "other-episode"
            self.ingest(prepared=(folder, projection(folder, source(4), report={**report, "symbol": "123B"})))
        with self.assertRaisesRegex(ValueError, "public_row_shape"):
            folder = self.root / "report-in-free-history"
            self.ingest(prepared=(folder, projection(
                folder, source(4), report=report,
                alter=lambda parts: parts[1]["rows"][0].update(fundamental_sha256=sha(encode(report))),
            )))
        folder = self.root / "exact-report"
        pin = projection(folder, source(4), report=report)
        body_hash = sha(encode(report))
        sidecar = folder / f"fundamental-{body_hash}.json"
        sidecar.write_bytes(sidecar.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "fundamental_pin"):
            self.ingest(prepared=(folder, pin))
        self.assertEqual(self.member.query("SELECT COUNT(*) AS total FROM private_projection_manifest"), [{"total": 0}])
        sidecar.write_bytes(encode(report).encode())
        prepared = (folder, pin)
        staged = self.ingest(prepared=prepared, activate=False)
        self.assertIsNone(read_member_marker(self.member))
        self.assertEqual(self.member.query("SELECT sha256,json FROM private_projection_fundamental WHERE identity=?",
                                           (staged["identity"],)), [{"sha256": body_hash, "json": encode(report)}])
        self.assertEqual(self.ingest(prepared=prepared)["status"], "activated")
        self.assertEqual(self.ingest(prepared=prepared)["status"], "already_active")
        self.member.query("UPDATE private_projection_fundamental SET json=json || ' '")
        with self.assertRaisesRegex(ValueError, "readback_fundamental_conflict"):
            self.ingest(prepared=prepared)

    def test_conflicting_existing_bytes_withhold_activation(self):
        staged = self.ingest(activate=False)
        self.member.query(
            "UPDATE private_projection_part SET json=? WHERE identity=? AND kind='history'",
            ('{"bad":true}', staged["identity"]),
        )
        with self.assertRaisesRegex(ValueError, "readback_part_conflict"):
            self.ingest()
        self.assertIsNone(read_member_marker(self.member))
        self.assertEqual(self.member.query(
            "SELECT json FROM private_projection_part WHERE identity=? AND kind='history'", (staged["identity"],),
        ), [{"json": '{"bad":true}'}])

    def test_owner_changes_before_marker_and_leaves_no_active_projection(self):
        read_count = 0

        def moves_during_stage():
            nonlocal read_count
            read_count += 1
            if read_count == 2:
                self.put_owner(source(5))
            return self.read_owner()

        with self.assertRaisesRegex(ValueError, "owner_ready_changed"):
            self.ingest(read_owner=moves_during_stage)
        self.assertIsNone(read_member_marker(self.member))
        self.assertEqual(self.member.query("SELECT COUNT(*) AS n FROM private_projection_part"), [{"n": 5}])

    def test_owner_change_during_cas_is_not_reported_as_success(self):
        wrapped = FaultableD1(self.member, before_marker=lambda: self.put_owner(source(5)))
        with self.assertRaisesRegex(ValueError, "owner_ready_changed"):
            self.ingest(db=wrapped)
        old = read_member_marker(self.member)
        self.assertEqual(old["identity"], encode(source(4)))
        self.assertEqual(self.read_owner(), source(5))
        self.assertEqual(wrapped.marker_writes, 1)

    def test_partial_immutable_stage_can_be_resumed_with_exact_bytes(self):
        class PartialStage(FaultableD1):
            def batch(self, statements):
                self.db.batch(statements[:1])
                raise RuntimeError("synthetic interrupted stage")

        wrapped = PartialStage(self.member)
        with self.assertRaisesRegex(RuntimeError, "interrupted stage"):
            self.ingest(db=wrapped)
        self.assertEqual(wrapped.marker_writes, 0)
        self.assertIsNone(read_member_marker(self.member))
        self.assertEqual(self.member.query("SELECT COUNT(*) AS n FROM private_projection_part"), [{"n": 1}])
        self.assertEqual(self.ingest()["status"], "activated")
        self.assertEqual(self.member.query("SELECT COUNT(*) AS n FROM private_projection_part"), [{"n": 5}])

    def test_concurrent_member_cas_keeps_the_other_marker(self):
        self.ingest()
        previous = read_member_marker(self.member)
        self.put_owner(source(6))
        folder = self.root / "p6"
        pin = projection(folder, source(6))
        competing = encode(source(5))
        competing_digest = "f" * 64

        def move_marker():
            self.member.query("INSERT INTO private_projection_manifest VALUES (?,?,?)", (competing, competing_digest, "{}"))
            self.member.query("UPDATE private_projection_ready SET identity=?,digest=?", (competing, competing_digest))

        wrapped = FaultableD1(self.member, before_marker=move_marker)
        with self.assertRaisesRegex(ValueError, "marker_compare_and_swap"):
            self.ingest(db=wrapped, prepared=(folder, pin), baseline=previous)
        self.assertEqual(read_member_marker(self.member), {"identity": competing, "digest": competing_digest})
        self.assertEqual(wrapped.marker_writes, 1)

    def test_unknown_write_outcome_reads_back_without_reissuing(self):
        class LostAck(FaultableD1):
            def query(self, sql, values=()):
                result = super().query(sql, values)
                if sql.lstrip().startswith("INSERT INTO private_projection_ready"):
                    raise RuntimeError("synthetic lost acknowledgement")
                return result

        wrapped = LostAck(self.member)
        self.assertEqual(self.ingest(db=wrapped)["status"], "activated")
        self.assertEqual(wrapped.marker_writes, 1)
        self.assertEqual(self.ingest(db=wrapped)["status"], "already_active")
        self.assertEqual(wrapped.marker_writes, 1)

    def test_unconfirmed_cas_preserves_marker_and_does_not_retry(self):
        def lose_ack_before_write():
            raise RuntimeError("synthetic unknown provider outcome")

        wrapped = FaultableD1(self.member, before_marker=lose_ack_before_write)
        with self.assertRaisesRegex(RuntimeError, "marker_unconfirmed"):
            self.ingest(db=wrapped)
        self.assertIsNone(read_member_marker(self.member))
        self.assertEqual(wrapped.marker_writes, 1)

    def publication_fixture(self, *, after_runtime_read=lambda count: None):
        root = private_root(self.root)
        bundle = root / "runs/fixture/bundle"
        bundle.mkdir(parents=True)
        row, manifest, active = read_active_metadata(self.owner)
        run = {
            "strategy": "A_BASE", "detection_executed": True, "dry_run": False,
            "latest_session": manifest["as_of"], "snapshot_sha256": manifest["daily_snapshot_sha256"],
            "source_version": row["source_version"], "bundle_directory": str(bundle),
        }
        publication = {
            "schema": "NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1", "published": True,
            "active_readback_verified": True, "existing_owner_gate_verified": True,
            "as_of": manifest["as_of"], "snapshot_sha256": manifest["daily_snapshot_sha256"],
            **{key: row[key] for key in ("dataset_id", "revision", "manifest_sha256", "source_version")},
        }
        atomic_write(root / "latest-run.json", run)
        atomic_write(root / "latest-publication.json", publication)
        release = {
            "source_commit": "5" * 40, "version_id": "12345678-1111-2222-3333-1234567890ab",
            "build_input_sha256": "6" * 64, "policy_sha256": "7" * 64,
        }
        reads = 0

        def observe(**kwargs):
            nonlocal reads
            reads += 1
            self.assertEqual(kwargs, {
                "source": release["source_commit"], "version_id": release["version_id"],
                "build_input_sha256": release["build_input_sha256"], "policy_sha256": release["policy_sha256"],
                "active": active,
            })
            after_runtime_read(reads)
            return "8" * 64

        def build(args, **kwargs):
            self.assertEqual(len(args), 10)
            entry = Path(args[1]).name
            self.assertIn(entry, {"prepare-new-a-member-projection.cjs", "prepare-new-a-reference-view.cjs"})
            self.assertEqual(kwargs["cwd"], self.root.resolve())
            self.assertTrue(kwargs["capture_output"])
            flags = dict(zip(args[2::2], args[3::2]))
            self.assertEqual(Path(flags["--bundle"]), bundle)
            proof_path = Path(flags["--ready-proof"])
            pin = file_sha(proof_path)
            self.assertEqual(flags["--ready-proof-sha256"], pin)
            proof = read(proof_path)
            self.assertEqual(proof["d1_active_sha256"], active)
            self.assertEqual(proof["active_manifest_sha256"], row["manifest_sha256"])
            self.assertEqual(proof["active_dataset_id"], row["dataset_id"])
            self.assertEqual(proof["active_revision"], row["revision"])
            self.assertIs(proof["owner_http_observed"], False)
            output = Path(flags["--out"])
            if entry == "prepare-new-a-reference-view.cjs":
                atomic_write(output / "reference-view.json", {
                    "source": source(row["revision"]),
                    "variants": {item: "<section>reference</section>" for item in VARIANTS},
                })
            else:
                projection(
                    output, source(row["revision"]),
                    source_manifest_sha256=proof["active_logical_manifest_sha256"], owner_readback_sha256=pin,
                )
            return SimpleNamespace(returncode=0)

        release_patch = patch.object(member_publication, "ordinary_runtime_release", return_value=release)
        observe_patch = patch.object(member_publication, "observe_normal_response", side_effect=observe)
        builder_patch = patch.object(member_publication.subprocess, "run", side_effect=build)
        for patcher in (release_patch, observe_patch, builder_patch):
            self.addCleanup(patcher.stop)
        release_patch.start()
        return root, release, observe_patch.start(), builder_patch.start()

    def test_publication_records_only_the_exact_owner_generation_and_replay(self):
        root, release, observer, builder = self.publication_fixture()
        result = member_publication.publish_current_member_view(self.root, self.owner, self.member, node="node")
        marker = read_member_marker(self.member)
        self.assertEqual(result, {
            "schema": "NEW_A_MEMBER_PUBLICATION_V1", "published": True, "active_readback_verified": True,
            "source": source(4), "projection_sha256": marker["digest"], "parts": 5,
            "worker_version_id": release["version_id"], "same_generation_replay": False,
        })
        self.assertEqual(marker["identity"], encode(source(4)))
        ready = self.member.query(
            "SELECT json FROM private_projection_part WHERE identity=? AND kind='analytics' AND idx=?",
            (marker["identity"] + "\n" + REFERENCE_SCHEMA, READY_INDEX),
        )
        self.assertEqual(len(ready), 1)
        self.assertEqual(read(root / "latest-member-publication.json"), result)
        self.assertEqual(observer.call_count, 2)
        self.assertEqual(builder.call_count, 2)
        replay = member_publication.publish_current_member_view(self.root, self.owner, self.member, node="node")
        self.assertEqual(replay, {**result, "same_generation_replay": True})

    def test_publication_rejects_mismatched_owner_revision_or_run_date_before_build(self):
        root, _, observer, builder = self.publication_fixture()
        for name, fields in (
            ("latest-publication.json", {"revision": 3}),
            ("latest-run.json", {"latest_session": "2026-11-18"}),
        ):
            with self.subTest(file=name):
                path = root / name
                original = read(path)
                atomic_write(path, {**original, **fields})
                with self.assertRaisesRegex(ValueError, "Active owner generation differs"):
                    member_publication.publish_current_member_view(self.root, self.owner, self.member, node="node")
                atomic_write(path, original)
        observer.assert_not_called()
        builder.assert_not_called()
        self.assertIsNone(read_member_marker(self.member))
        self.assertFalse((root / "latest-member-publication.json").exists())

    def test_publication_keeps_previous_receipt_when_owner_changes_after_import(self):
        def advance_after_second_observation(count):
            if count == 2:
                self.put_owner(source(5))

        root, _, observer, builder = self.publication_fixture(after_runtime_read=advance_after_second_observation)
        previous = {"schema": "NEW_A_MEMBER_PUBLICATION_V1", "source": source(3)}
        receipt_path = root / "latest-member-publication.json"
        atomic_write(receipt_path, previous)
        with self.assertRaisesRegex(ValueError, "owner generation changed after member publication"):
            member_publication.publish_current_member_view(self.root, self.owner, self.member, node="node")
        self.assertEqual(self.read_owner(), source(5))
        self.assertEqual(read_member_marker(self.member)["identity"], encode(source(4)))
        self.assertEqual(read(receipt_path), previous)
        self.assertEqual(observer.call_count, 2)
        self.assertEqual(builder.call_count, 2)

    @unittest.skipUnless(shutil.which("node"), "Node required to exercise the Worker reader")
    def test_worker_reader_serves_sqlite_import_and_withholds_superseded_generation(self):
        imported = self.ingest()
        # An owner update after member CAS can leave an active marker for the old generation.
        # Read using the unmodified Worker reader against the exact database we wrote.
        reader = r"""
          const assert = require('node:assert/strict');
          const { DatabaseSync } = require('node:sqlite');
          const { createNewAMemberProjectionReader } = require(process.argv[1]);
          const db = new DatabaseSync(process.argv[2], { readOnly: true });
          const source = JSON.parse(process.argv[3]);
          let official = source;
          const binding = {
            withSession(constraint) {
              assert.equal(constraint, 'first-primary');
              return { prepare(sql) {
                return {
                  bind(...args) { return { first: async () => db.prepare(sql).get(...args) ?? null }; },
                  first: async () => db.prepare(sql).get() ?? null,
                };
              } };
            },
          };
          const read = createNewAMemberProjectionReader(binding, async () => official);
          (async () => {
            const history = await read(source, 'history', 0);
            assert.deepEqual(history?.rows, [{ date: source.as_of, symbol: '123A', state: 'WATCHING' }]);
            official = { ...source, revision: source.revision + 1 };
            assert.equal(await read(source, 'history', 0), null);
            db.close();
          })().catch(error => { console.error(error); process.exitCode = 1; });
        """
        checked = subprocess.run(
            ["node", "-e", reader, str(GATE / "src/new-a-member-projection.ts"),
             str(self.member_path), imported["identity"]],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == "__main__":
    unittest.main()
