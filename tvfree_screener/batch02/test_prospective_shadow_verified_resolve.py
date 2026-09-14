from __future__ import annotations

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

    def test_first_verified_resolution_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions = ["2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-21","2026-09-22"]
            daily = [
                {"symbol":"1111.T","date":"2026-09-16","open":100.0,"close":101.0},
                {"symbol":"1111.T","date":"2026-09-22","open":119.0,"close":120.0},
            ]
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

    def test_same_resolution_rerun_is_allowed_and_receipt_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions = ["2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-21","2026-09-22"]
            daily = [
                {"symbol":"1111.T","date":"2026-09-16","open":100.0,"close":101.0},
                {"symbol":"1111.T","date":"2026-09-22","open":119.0,"close":120.0},
            ]
            first = verified_resolve_shadow_file(shadow, out, daily, sessions)
            snapshot = out.read_bytes()
            receipt_snapshot = Path(first["endpoint_completeness_receipt_path"]).read_bytes()
            second = verified_resolve_shadow_file(shadow, out, daily, sessions)
            self.assertTrue(first["resolved_written"])
            self.assertTrue(second["resolved_written"])
            self.assertEqual(snapshot, out.read_bytes())
            self.assertEqual(first["endpoint_completeness_receipt_path"], second["endpoint_completeness_receipt_path"])
            self.assertEqual(receipt_snapshot, Path(second["endpoint_completeness_receipt_path"]).read_bytes())

    def test_changed_resolved_endpoint_blocks_and_preserves_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shadow = self._shadow(root)
            out = root / "resolved.jsonl"
            sessions = ["2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-21","2026-09-22"]
            daily = [
                {"symbol":"1111.T","date":"2026-09-16","open":100.0,"close":101.0},
                {"symbol":"1111.T","date":"2026-09-22","open":119.0,"close":120.0},
            ]
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

            full_sessions = ["2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-21","2026-09-22"]
            daily = [
                {"symbol":"1111.T","date":"2026-09-16","open":100.0,"close":101.0},
                {"symbol":"1111.T","date":"2026-09-22","open":119.0,"close":120.0},
            ]
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
