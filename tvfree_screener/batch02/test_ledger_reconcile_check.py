import unittest

from tvfree_screener.batch02.ledger_reconcile_check import compare_ledger, entry_ids


class LedgerReconcileCheckTests(unittest.TestCase):
    def test_entry_ids_uses_heading_id_only(self):
        text = "# x\n## EXP-A — PASS\n## EXP-B — REJECT\n"
        self.assertEqual(entry_ids(text), ["EXP-A", "EXP-B"])

    def test_reports_missing_without_mutation(self):
        ledger = "# ledger\n## EXP-A — PASS\n"
        pending = "# pending\n## EXP-A — PASS\n## EXP-B — REJECT\n"
        result = compare_ledger(ledger, pending)
        self.assertEqual(result["present"], ["EXP-A"])
        self.assertEqual(result["missing"], ["EXP-B"])
        self.assertFalse(result["safe_to_delete_pending_file"])

    def test_all_present_is_reconciled(self):
        ledger = "# ledger\n## EXP-A — PASS\n## EXP-B — REJECT\n"
        pending = "# pending\n## EXP-A — PASS\n## EXP-B — REJECT\n"
        result = compare_ledger(ledger, pending)
        self.assertEqual(result["missing_entries"], 0)
        self.assertTrue(result["safe_to_delete_pending_file"])

    def test_empty_pending_is_not_deletable(self):
        result = compare_ledger("# ledger\n", "# pending\n")
        self.assertEqual(result["pending_entries"], 0)
        self.assertFalse(result["safe_to_delete_pending_file"])


if __name__ == "__main__":
    unittest.main()
