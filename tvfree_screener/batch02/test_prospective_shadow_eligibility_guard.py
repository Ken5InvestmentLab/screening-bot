from __future__ import annotations

import unittest

from prospective_shadow_eligibility_guard import evaluate_eligibility_rows


class EligibilityGuardTests(unittest.TestCase):
    def base_row(self):
        return {
            "symbol": "1234",
            "eligibility_status": "ELIGIBLE",
            "data_sufficient": True,
            "skip_reason": None,
            "missing_fields": [],
        }

    def test_valid_row_passes(self):
        r = evaluate_eligibility_rows([self.base_row()])
        self.assertTrue(r["eligibility_valid"])
        self.assertEqual(r["decision"], "ALLOW_ELIGIBLE_SHADOW_ROWS")

    def test_missing_data_blocks(self):
        row = self.base_row()
        row["data_sufficient"] = False
        r = evaluate_eligibility_rows([row])
        self.assertFalse(r["eligibility_valid"])
        self.assertEqual(r["violations"][0]["reason"], "data_sufficient_not_true")

    def test_skip_reason_blocks(self):
        row = self.base_row()
        row["skip_reason"] = "missing_1h_bins"
        r = evaluate_eligibility_rows([row])
        self.assertFalse(r["eligibility_valid"])
        self.assertEqual(r["violations"][0]["reason"], "skip_reason_present")

    def test_missing_fields_blocks(self):
        row = self.base_row()
        row["missing_fields"] = ["prior_close"]
        r = evaluate_eligibility_rows([row])
        self.assertFalse(r["eligibility_valid"])
        self.assertEqual(r["violations"][0]["reason"], "missing_fields_present")

    def test_missing_eligibility_status_blocks(self):
        row = self.base_row()
        row.pop("eligibility_status")
        r = evaluate_eligibility_rows([row])
        self.assertFalse(r["eligibility_valid"])
        self.assertEqual(r["violations"][0]["reason"], "eligibility_status_not_eligible")

    def test_empty_batch_blocks(self):
        r = evaluate_eligibility_rows([])
        self.assertFalse(r["eligibility_valid"])
        self.assertEqual(r["decision"], "BLOCK_INELIGIBLE_SHADOW_ROWS")


if __name__ == "__main__":
    unittest.main()
