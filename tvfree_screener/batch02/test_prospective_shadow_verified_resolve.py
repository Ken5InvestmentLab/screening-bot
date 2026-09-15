from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prospective_shadow import ShadowCandidate, append_candidates
from prospective_shadow_verified_resolve import verified_resolve_shadow_file


class VerifiedResolveTests(unittest.TestCase):
    def _shadow(self, root: Path, signal_date="2026-09-15") -> Path:
        path = root / "shadow.jsonl"
        append_candidates(
            path,
            [
                ShadowCandidate(
                    experiment_id="EXP",
                    model_freeze_id="FREEZE",
                    symbol="1111.T",
                    signal_date=signal_date,
                    bin_name="AM_09_13",
                    feature_cutoff=f"{signal_date}T13:00:00+09:00",
                    source_tag="RAW_CAUSAL_INTRADAY",
                    rank=1,
                )
            ],
        )
        return path

    def _resolved_inputs(self):
        sessions = ["2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-21","2026-09-22"]
        daily = [
            {"symbol":"1111.T","date":"2026-09-16","open":100.0,"close":101.0},
            {"symbol":"1111.T","date":"2026-09-22","open":119.0,"close":120.0},
        ]
        return sessions, daily

    def test_first_verified_resolution_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions, daily = self._resolved_inputs()
            result = verified_resolve_shadow_file(shadow, out, daily, sessions)
            self.assertTrue(result["resolved_written"])
            self.assertEqual(result["decision"], "VERIFIED_RESOLUTION_WRITE_COMPLETE")
            self.assertTrue(out.exists())
            receipt_path = Path(result["endpoint_completeness_receipt_path"])
            self.assertTrue(receipt_path.exists())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertTrue(receipt["endpoint_completeness_valid"])
            self.assertFalse(receipt["strategy_outcomes_opened"])
            self.assertEqual(receipt["receipt_sha256"], result["endpoint_completeness_receipt_sha256"])

    def test_required_provenance_artifacts_are_bound_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions, daily = self._resolved_inputs()
            daily_manifest = root / "daily.manifest.json"
            sessions_csv = root / "sessions.csv"
            sessions_manifest = root / "sessions.manifest.json"
            daily_manifest.write_text('{"endpoint_dataset_valid":true}\n', encoding="utf-8")
            sessions_csv.write_text("date\n" + "\n".join(sessions) + "\n", encoding="utf-8")
            sessions_manifest.write_text('{"calendar_valid":true}\n', encoding="utf-8")

            result = verified_resolve_shadow_file(
                shadow,
                out,
                daily,
                sessions,
                daily_manifest_path=daily_manifest,
                sessions_csv_path=sessions_csv,
                sessions_manifest_path=sessions_manifest,
                require_provenance_chain=True,
            )
            self.assertTrue(result["resolved_written"])
            self.assertTrue(result["integrity"]["provenance_chain_enforced"])
            receipt = json.loads(Path(result["endpoint_completeness_receipt_path"]).read_text(encoding="utf-8"))
            self.assertTrue(receipt["provenance_chain_enforced"])
            self.assertEqual(receipt["daily_endpoint_manifest_sha256"], hashlib.sha256(daily_manifest.read_bytes()).hexdigest())
            self.assertEqual(receipt["pinned_xtks_calendar_sha256"], hashlib.sha256(sessions_csv.read_bytes()).hexdigest())
            self.assertEqual(receipt["frozen_selection_ledger_sha256"], hashlib.sha256(shadow.read_bytes()).hexdigest())

    def test_required_provenance_missing_artifact_blocks_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions, daily = self._resolved_inputs()
            result = verified_resolve_shadow_file(
                shadow,
                out,
                daily,
                sessions,
                daily_manifest_path=root / "missing.manifest.json",
                sessions_csv_path=root / "missing.sessions.csv",
                sessions_manifest_path=root / "missing.sessions.manifest.json",
                require_provenance_chain=True,
            )
            self.assertFalse(result["resolved_written"])
            self.assertEqual(result["decision"], "BLOCK_PROVENANCE_CHAIN_MISSING_ARTIFACT")
            self.assertFalse(out.exists())

    def test_same_resolution_rerun_is_allowed_and_receipt_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions, daily = self._resolved_inputs()
            first = verified_resolve_shadow_file(shadow, out, daily, sessions)
            snapshot = out.read_bytes()
            receipt_snapshot = Path(first["endpoint_completeness_receipt_path"]).read_bytes()
            second = verified_resolve_shadow_file(shadow, out, daily, sessions)
            self.assertTrue(first["resolved_written"])
            self.assertTrue(second["resolved_written"])
            self.assertEqual(snapshot, out.read_bytes())
            self.assertEqual(first["endpoint_completeness_receipt_path"], second["endpoint_completeness_receipt_path"])
            self.assertEqual(receipt_snapshot, Path(second["endpoint_completeness_receipt_path"]).read_bytes())

    def test_pre_replace_chain_guard_blocks_before_resolved_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions, daily = self._resolved_inputs()
            calls = []

            def guard(staged_path, provisional_result):
                calls.append((staged_path.exists(), provisional_result["output_sha256_after"]))
                return {"allow_replace": False, "decision": "TEST_BLOCK"}

            result = verified_resolve_shadow_file(
                shadow,
                out,
                daily,
                sessions,
                pre_replace_guard=guard,
            )
            self.assertFalse(result["resolved_written"])
            self.assertEqual(result["decision"], "BLOCK_PRE_REPLACE_CHAIN_GUARD")
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0][0])
            self.assertFalse(out.exists())

    def test_pre_replace_chain_guard_exception_preserves_resolved_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions, daily = self._resolved_inputs()

            def guard(_staged_path, _provisional_result):
                raise RuntimeError("sidecar persistence failed")

            result = verified_resolve_shadow_file(
                shadow,
                out,
                daily,
                sessions,
                pre_replace_guard=guard,
            )
            self.assertFalse(result["resolved_written"])
            self.assertEqual(result["decision"], "BLOCK_PRE_REPLACE_CHAIN_GUARD_ERROR")
            self.assertFalse(out.exists())

    def test_changed_resolved_endpoint_blocks_and_preserves_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions, daily = self._resolved_inputs()
            verified_resolve_shadow_file(shadow, out, daily, sessions)
            snapshot = out.read_bytes()
            changed = [
                {"symbol":"1111.T","date":"2026-09-16","open":100.0,"close":101.0},
                {"symbol":"1111.T","date":"2026-09-22","open":119.0,"close":121.0},
            ]
            result = verified_resolve_shadow_file(shadow, out, changed, sessions)
            self.assertFalse(result["resolved_written"])
            self.assertEqual(result["decision"], "BLOCK_RESOLUTION_CONTINUITY_FAILURE")
            self.assertEqual(snapshot, out.read_bytes())
            self.assertTrue(Path(result["endpoint_completeness_receipt_path"]).exists())

    def test_pending_can_advance_to_resolved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            short_sessions = ["2026-09-15","2026-09-16","2026-09-17"]
            first = verified_resolve_shadow_file(shadow, out, [], short_sessions)
            self.assertTrue(first["resolved_written"])
            self.assertEqual(json.loads(out.read_text().splitlines()[0])["status"], "PENDING_5BD")

            full_sessions, daily = self._resolved_inputs()
            second = verified_resolve_shadow_file(shadow, out, daily, full_sessions)
            self.assertTrue(second["resolved_written"])
            self.assertEqual(json.loads(out.read_text().splitlines()[0])["status"], "RESOLVED")
            self.assertNotEqual(first["endpoint_completeness_receipt_path"], second["endpoint_completeness_receipt_path"])

    def test_mature_missing_endpoint_fails_closed_and_emits_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions = ["2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-21","2026-09-22"]
            result = verified_resolve_shadow_file(
                shadow,
                out,
                [{"symbol":"1111.T","date":"2026-09-16","open":100.0,"close":101.0}],
                sessions,
            )
            self.assertFalse(result["resolved_written"])
            self.assertEqual(result["decision"], "BLOCK_ENDPOINT_COMPLETENESS_FAILURE")
            self.assertFalse(out.exists())
            receipt_path = Path(result["endpoint_completeness_receipt_path"])
            self.assertTrue(receipt_path.exists())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertFalse(receipt["endpoint_completeness_valid"])
            self.assertEqual(receipt["missing_required_endpoint_pair_count"], 1)
            self.assertFalse(receipt["strategy_outcomes_opened"])


if __name__ == "__main__":
    unittest.main()
