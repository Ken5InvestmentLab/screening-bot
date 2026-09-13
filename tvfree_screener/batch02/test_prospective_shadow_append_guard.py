import unittest

from tvfree_screener.batch02.prospective_shadow_append_guard import compare_append_only_snapshots


class ProspectiveShadowAppendGuardTests(unittest.TestCase):
    def test_clean_append_passes(self):
        old = ['{"k":1}', '{"k":2}']
        new = ['{"k":1}', '{"k":2}', '{"k":3}']
        result = compare_append_only_snapshots(old, new)
        self.assertTrue(result["append_only_valid"])
        self.assertEqual(result["appended_rows"], 1)

    def test_identical_snapshot_passes_with_zero_append(self):
        old = ['{"k":1}', '{"k":2}']
        result = compare_append_only_snapshots(old, list(old))
        self.assertTrue(result["append_only_valid"])
        self.assertEqual(result["appended_rows"], 0)

    def test_historical_rewrite_blocks(self):
        old = ['{"k":1}', '{"k":2}']
        new = ['{"k":1}', '{"k":999}', '{"k":3}']
        result = compare_append_only_snapshots(old, new)
        self.assertFalse(result["append_only_valid"])
        self.assertEqual(result["first_mismatch_row"], 2)

    def test_truncation_blocks(self):
        old = ['{"k":1}', '{"k":2}']
        new = ['{"k":1}']
        result = compare_append_only_snapshots(old, new)
        self.assertFalse(result["append_only_valid"])

    def test_reordering_blocks(self):
        old = ['{"k":1}', '{"k":2}']
        new = ['{"k":2}', '{"k":1}', '{"k":3}']
        result = compare_append_only_snapshots(old, new)
        self.assertFalse(result["append_only_valid"])
        self.assertEqual(result["first_mismatch_row"], 1)

    def test_blank_lines_are_ignored(self):
        old = ['{"k":1}', '', '{"k":2}']
        new = ['{"k":1}', '{"k":2}', '', '{"k":3}']
        result = compare_append_only_snapshots(old, new)
        self.assertTrue(result["append_only_valid"])
        self.assertEqual(result["appended_rows"], 1)


if __name__ == "__main__":
    unittest.main()
