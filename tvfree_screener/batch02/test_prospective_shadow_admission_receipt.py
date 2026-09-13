from __future__ import annotations

import unittest

from prospective_shadow_admission_receipt import (
    build_admission_receipt,
    verify_admission_receipt,
)


class AdmissionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "experiment_id": "EXP-1",
            "model_freeze_id": "FREEZE-1",
            "frozen_at": "2026-09-14T00:00:00+09:00",
            "model_spec_sha256": "a" * 64,
        }
        self.rows = [
            {
                "experiment_id": "EXP-1",
                "model_freeze_id": "FREEZE-1",
                "symbol": "1234",
                "signal_date": "2026-09-14",
                "bin_name": "AM_09_13",
                "feature_cutoff": "2026-09-14T13:00:00+09:00",
                "source_tag": "RAW_CAUSAL_INTRADAY",
            }
        ]
        self.admission = {
            "admitted": True,
            "decision": "ADMIT_PROSPECTIVE_SHADOW_BATCH",
            "checked_rows": 1,
        }

    def receipt(self):
        return build_admission_receipt(
            self.manifest, self.rows, self.admission, "2026-09-14T13:01:00+09:00"
        )

    def test_valid_receipt_verifies(self):
        result = verify_admission_receipt(self.receipt(), self.manifest, self.rows, self.admission)
        self.assertTrue(result["valid"])
        self.assertEqual(result["decision"], "ADMISSION_RECEIPT_VERIFIED")

    def test_candidate_row_change_invalidates(self):
        rows = [dict(self.rows[0], symbol="5678")]
        result = verify_admission_receipt(self.receipt(), self.manifest, rows, self.admission)
        self.assertFalse(result["valid"])
        self.assertIn("candidate_rows_sha256_mismatch", result["errors"])

    def test_manifest_change_invalidates(self):
        manifest = dict(self.manifest, frozen_at="2026-09-14T00:01:00+09:00")
        result = verify_admission_receipt(self.receipt(), manifest, self.rows, self.admission)
        self.assertFalse(result["valid"])
        self.assertIn("manifest_sha256_mismatch", result["errors"])

    def test_admission_change_invalidates(self):
        admission = dict(self.admission, checked_rows=2)
        result = verify_admission_receipt(self.receipt(), self.manifest, self.rows, admission)
        self.assertFalse(result["valid"])
        self.assertIn("admission_result_sha256_mismatch", result["errors"])

    def test_receipt_tamper_invalidates(self):
        receipt = self.receipt()
        receipt["row_count"] = 999
        result = verify_admission_receipt(receipt, self.manifest, self.rows, self.admission)
        self.assertFalse(result["valid"])
        self.assertIn("receipt_sha256_mismatch", result["errors"])

    def test_cannot_build_from_blocked_admission(self):
        blocked = {"admitted": False, "decision": "BLOCK_PROSPECTIVE_SHADOW_BATCH"}
        with self.assertRaises(ValueError):
            build_admission_receipt(self.manifest, self.rows, blocked, "2026-09-14T13:01:00+09:00")

    def test_production_flag_tamper_invalidates(self):
        receipt = self.receipt()
        receipt["production_authorized"] = True
        result = verify_admission_receipt(receipt, self.manifest, self.rows, self.admission)
        self.assertFalse(result["valid"])
        self.assertIn("production_authorized_must_be_false", result["errors"])


if __name__ == "__main__":
    unittest.main()
