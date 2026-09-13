import unittest

from tvfree_screener.batch02.prospective_shadow_freeze_validator import validate_freeze_manifest


GOOD_SHA = "a" * 64


def good_manifest():
    return {
        "experiment_id": "TVFREE-PROSPECTIVE-CANDIDATE-01",
        "model_freeze_id": "freeze-20260914-001",
        "frozen_at": "2026-09-14T00:30:00+09:00",
        "model_spec_sha256": GOOD_SHA,
        "notes": "immutable prospective freeze",
    }


class ProspectiveShadowFreezeValidatorTests(unittest.TestCase):
    def test_valid_manifest_is_ready(self):
        result = validate_freeze_manifest(good_manifest(), expected_model_spec_sha256=GOOD_SHA)
        self.assertTrue(result["ready_for_shadow_ingest"])
        self.assertEqual(result["decision"], "READY_FOR_SHADOW_INGEST")
        self.assertEqual(result["errors"], [])

    def test_template_placeholder_is_blocked(self):
        data = good_manifest()
        data["experiment_id"] = "REPLACE_WITH_EXPERIMENT_ID"
        result = validate_freeze_manifest(data)
        self.assertFalse(result["ready_for_shadow_ingest"])
        self.assertTrue(any("placeholder" in error for error in result["errors"]))

    def test_naive_timestamp_is_blocked(self):
        data = good_manifest()
        data["frozen_at"] = "2026-09-14T00:30:00"
        result = validate_freeze_manifest(data)
        self.assertFalse(result["ready_for_shadow_ingest"])
        self.assertTrue(any("timezone" in error for error in result["errors"]))

    def test_model_spec_sha_mismatch_is_blocked(self):
        result = validate_freeze_manifest(good_manifest(), expected_model_spec_sha256="b" * 64)
        self.assertFalse(result["ready_for_shadow_ingest"])
        self.assertTrue(any("does not match" in error for error in result["errors"]))

    def test_invalid_sha_shape_is_blocked(self):
        data = good_manifest()
        data["model_spec_sha256"] = "1234"
        result = validate_freeze_manifest(data)
        self.assertFalse(result["ready_for_shadow_ingest"])
        self.assertTrue(any("64 hexadecimal" in error for error in result["errors"]))

    def test_freeze_id_cannot_equal_experiment_id(self):
        data = good_manifest()
        data["model_freeze_id"] = data["experiment_id"]
        result = validate_freeze_manifest(data)
        self.assertFalse(result["ready_for_shadow_ingest"])
        self.assertTrue(any("distinct" in error for error in result["errors"]))

    def test_unknown_fields_warn_but_do_not_block(self):
        data = good_manifest()
        data["extra_audit_note"] = "preserved"
        result = validate_freeze_manifest(data)
        self.assertTrue(result["ready_for_shadow_ingest"])
        self.assertEqual(len(result["warnings"]), 1)


if __name__ == "__main__":
    unittest.main()
