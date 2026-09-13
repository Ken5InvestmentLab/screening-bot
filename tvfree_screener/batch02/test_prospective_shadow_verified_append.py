from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from prospective_shadow_admission_gate import evaluate_shadow_admission
from prospective_shadow_admission_receipt import build_admission_receipt
from prospective_shadow_verified_append import verified_append


class VerifiedAppendTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "experiment_id": "EXP-VA-1",
            "model_freeze_id": "FREEZE-VA-1",
            "frozen_at": "2026-09-14T00:00:00+09:00",
            "model_spec_sha256": "a" * 64,
        }
        self.rows = [
            {
                "experiment_id": "EXP-VA-1",
                "model_freeze_id": "FREEZE-VA-1",
                "symbol": "1234",
                "signal_date": "2026-09-14",
                "bin_name": "AM_09_13",
                "feature_cutoff": "2026-09-14T13:00:00+09:00",
                "source_tag": "RAW_CAUSAL_INTRADAY",
                "rank": 1,
                "eligibility_status": "ELIGIBLE",
                "data_sufficient": True,
                "skip_reason": None,
                "missing_fields": [],
            }
        ]
        self.admission = evaluate_shadow_admission(self.manifest, self.rows)
        self.receipt = build_admission_receipt(
            self.manifest,
            self.rows,
            self.admission,
            "2026-09-14T13:01:00+09:00",
        )

    def test_valid_receipt_appends(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            result = verified_append(path, self.manifest, self.rows, self.admission, self.receipt)
            self.assertTrue(result["appended"])
            self.assertEqual(result["decision"], "VERIFIED_APPEND_COMPLETE")
            self.assertEqual(result["append_result"]["added"], 1)
            self.assertTrue(path.exists())

    def test_tampered_receipt_blocks_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            path.write_text("seed\n", encoding="utf-8")
            before = path.read_bytes()
            receipt = dict(self.receipt, row_count=99)
            result = verified_append(path, self.manifest, self.rows, self.admission, receipt)
            self.assertFalse(result["appended"])
            self.assertEqual(result["decision"], "BLOCK_APPEND_RECEIPT_INVALID")
            self.assertEqual(path.read_bytes(), before)

    def test_changed_rows_block_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            changed = [dict(self.rows[0], symbol="5678")]
            result = verified_append(path, self.manifest, changed, self.admission, self.receipt)
            self.assertFalse(result["appended"])
            self.assertEqual(result["decision"], "BLOCK_APPEND_ADMISSION_REPLAY_MISMATCH")
            self.assertFalse(path.exists())

    def test_changed_admission_blocks_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            changed = dict(self.admission, checked_rows=2)
            result = verified_append(path, self.manifest, self.rows, changed, self.receipt)
            self.assertFalse(result["appended"])
            self.assertEqual(result["decision"], "BLOCK_APPEND_ADMISSION_REPLAY_MISMATCH")
            self.assertFalse(path.exists())

    def test_noncausal_source_never_writes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            bad_rows = [dict(self.rows[0], source_tag="POSTCLOSE_RECON_ONLY")]
            result = verified_append(path, self.manifest, bad_rows, self.admission, self.receipt)
            self.assertFalse(result["appended"])
            self.assertEqual(result["decision"], "BLOCK_APPEND_ADMISSION_REPLAY_MISMATCH")
            self.assertFalse(path.exists())

    def test_missing_data_never_writes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            bad_rows = [dict(self.rows[0], data_sufficient=False, skip_reason="missing_1h_bins")]
            result = verified_append(path, self.manifest, bad_rows, self.admission, self.receipt)
            self.assertFalse(result["appended"])
            self.assertEqual(result["decision"], "BLOCK_APPEND_ADMISSION_REPLAY_MISMATCH")
            self.assertFalse(path.exists())

    def test_duplicate_reappend_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            first = verified_append(path, self.manifest, self.rows, self.admission, self.receipt)
            snapshot = path.read_bytes()
            second = verified_append(path, self.manifest, self.rows, self.admission, self.receipt)
            self.assertTrue(first["appended"])
            self.assertTrue(second["appended"])
            self.assertEqual(second["append_result"]["added"], 0)
            self.assertEqual(second["append_result"]["skipped_duplicate"], 1)
            self.assertEqual(path.read_bytes(), snapshot)


if __name__ == "__main__":
    unittest.main()
