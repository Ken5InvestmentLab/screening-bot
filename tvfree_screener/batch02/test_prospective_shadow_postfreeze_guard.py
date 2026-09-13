import unittest

from prospective_shadow_postfreeze_guard import evaluate_postfreeze_rows


MANIFEST = {
    "experiment_id": "EXP-1",
    "model_freeze_id": "FREEZE-1",
    "frozen_at": "2026-09-14T00:00:00+09:00",
}


def row(cutoff, **extra):
    base = {
        "experiment_id": "EXP-1",
        "model_freeze_id": "FREEZE-1",
        "feature_cutoff": cutoff,
    }
    base.update(extra)
    return base


class PostFreezeGuardTests(unittest.TestCase):
    def test_strictly_after_passes(self):
        out = evaluate_postfreeze_rows(MANIFEST, [row("2026-09-14T00:00:01+09:00")])
        self.assertTrue(out["postfreeze_valid"])

    def test_equal_freeze_blocks(self):
        out = evaluate_postfreeze_rows(MANIFEST, [row("2026-09-14T00:00:00+09:00")])
        self.assertFalse(out["postfreeze_valid"])

    def test_pre_freeze_blocks(self):
        out = evaluate_postfreeze_rows(MANIFEST, [row("2026-09-13T23:59:59+09:00")])
        self.assertFalse(out["postfreeze_valid"])

    def test_utc_equivalent_after_passes(self):
        out = evaluate_postfreeze_rows(MANIFEST, [row("2026-09-13T15:00:01Z")])
        self.assertTrue(out["postfreeze_valid"])

    def test_naive_cutoff_blocks(self):
        out = evaluate_postfreeze_rows(MANIFEST, [row("2026-09-14T00:00:01")])
        self.assertFalse(out["postfreeze_valid"])
        self.assertIn("timezone-aware", out["violations"][0]["reason"])

    def test_identity_mismatch_blocks(self):
        out = evaluate_postfreeze_rows(MANIFEST, [row("2026-09-14T00:00:01+09:00", model_freeze_id="OTHER")])
        self.assertFalse(out["postfreeze_valid"])
        self.assertEqual(out["violations"][0]["reason"], "model_freeze_id_mismatch")

    def test_one_bad_row_blocks_whole_batch(self):
        out = evaluate_postfreeze_rows(MANIFEST, [
            row("2026-09-14T00:00:01+09:00"),
            row("2026-09-14T00:00:00+09:00"),
        ])
        self.assertFalse(out["postfreeze_valid"])
        self.assertEqual(out["checked_rows"], 2)
        self.assertEqual(out["violation_count"], 1)

    def test_empty_batch_blocks(self):
        out = evaluate_postfreeze_rows(MANIFEST, [])
        self.assertFalse(out["postfreeze_valid"])
        self.assertEqual(out["checked_rows"], 0)


if __name__ == "__main__":
    unittest.main()
