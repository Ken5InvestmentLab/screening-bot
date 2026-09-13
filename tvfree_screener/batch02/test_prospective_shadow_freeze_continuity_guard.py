import unittest

from tvfree_screener.batch02.prospective_shadow_freeze_continuity_guard import validate_continuity


BASELINE = {
    "experiment_id": "EXP-1",
    "model_freeze_id": "FREEZE-1",
    "freeze_manifest_sha256": "a" * 64,
    "model_spec_sha256": "b" * 64,
}
CURRENT = {
    "experiment_id": "EXP-1",
    "model_freeze_id": "FREEZE-1",
    "model_spec_sha256": "b" * 64,
}


class FreezeContinuityGuardTests(unittest.TestCase):
    def test_intact_continuity_passes(self):
        r = validate_continuity(BASELINE, CURRENT, "a" * 64, "b" * 64)
        self.assertTrue(r["continuity_intact"])
        self.assertEqual(r["decision"], "CONTINUE_PROSPECTIVE_SHADOW")

    def test_changed_experiment_id_stops(self):
        cur = dict(CURRENT, experiment_id="EXP-2")
        r = validate_continuity(BASELINE, cur, "a" * 64, "b" * 64)
        self.assertFalse(r["continuity_intact"])

    def test_changed_freeze_id_stops(self):
        cur = dict(CURRENT, model_freeze_id="FREEZE-2")
        r = validate_continuity(BASELINE, cur, "a" * 64, "b" * 64)
        self.assertEqual(r["decision"], "STOP_AND_ROTATE_FREEZE_ID")

    def test_changed_manifest_sha_stops(self):
        r = validate_continuity(BASELINE, CURRENT, "c" * 64, "b" * 64)
        self.assertFalse(r["checks"]["freeze_manifest_sha256_unchanged"])

    def test_changed_model_spec_sha_stops(self):
        r = validate_continuity(BASELINE, CURRENT, "a" * 64, "d" * 64)
        self.assertFalse(r["checks"]["model_spec_sha256_unchanged"])

    def test_manifest_declared_spec_change_stops(self):
        cur = dict(CURRENT, model_spec_sha256="e" * 64)
        r = validate_continuity(BASELINE, cur, "a" * 64, "b" * 64)
        self.assertFalse(r["checks"]["manifest_declared_model_spec_sha256_unchanged"])

    def test_incomplete_baseline_rejected(self):
        bad = dict(BASELINE)
        bad.pop("model_freeze_id")
        with self.assertRaises(ValueError):
            validate_continuity(bad, CURRENT, "a" * 64, "b" * 64)


if __name__ == "__main__":
    unittest.main()
