import unittest

from tvfree_screener.batch02.prospective_shadow_append_guard import compare_append_only_snapshots
from tvfree_screener.batch02.prospective_shadow_evidence_chain_audit import audit_evidence_chain


def base():
    manifest = {
        "experiment_id": "EXP",
        "model_freeze_id": "FREEZE-1",
        "freeze_manifest_sha256": "a" * 64,
        "model_spec_sha256": "b" * 64,
    }
    continuity = {"decision": "CONTINUE_SAME_FREEZE"}
    append_guard = compare_append_only_snapshots(["a"], ["a", "b"])
    maturity = {
        "mature": False,
        "counts": {"total_rows": 50, "resolved_rows": 40},
    }
    report = {
        "scope": "PROSPECTIVE_SHADOW_ONLY",
        "selection_or_threshold_tuning_allowed": False,
        "overall": {"rows": 50, "resolved": 40},
        "by_model_freeze": {"EXP|FREEZE-1": {"rows": 50, "resolved": 40}},
    }
    return manifest, continuity, append_guard, maturity, report


class EvidenceChainAuditTests(unittest.TestCase):
    def test_valid_chain_passes_before_maturity_when_not_required(self):
        self.assertTrue(audit_evidence_chain(*base())["ok"])

    def test_require_mature_blocks_immature_chain(self):
        self.assertFalse(audit_evidence_chain(*base(), require_mature=True)["ok"])

    def test_freeze_mismatch_partition_blocks(self):
        args = list(base())
        args[4]["by_model_freeze"] = {"EXP|FREEZE-X": {"rows": 50, "resolved": 40}}
        self.assertFalse(audit_evidence_chain(*args)["ok"])

    def test_count_mismatch_blocks(self):
        args = list(base())
        args[3]["counts"]["resolved_rows"] = 39
        self.assertFalse(audit_evidence_chain(*args)["ok"])

    def test_continuity_failure_blocks(self):
        args = list(base())
        args[1]["decision"] = "STOP_AND_ROTATE_FREEZE_ID"
        self.assertFalse(audit_evidence_chain(*args)["ok"])

    def test_append_only_failure_blocks(self):
        args = list(base())
        args[2] = compare_append_only_snapshots(["a", "b"], ["a"])
        self.assertFalse(audit_evidence_chain(*args)["ok"])

    def test_append_decision_contract_is_required(self):
        args = list(base())
        args[2]["decision"] = "OTHER"
        self.assertFalse(audit_evidence_chain(*args)["ok"])

    def test_legacy_mock_ok_flag_does_not_bypass_real_contract(self):
        args = list(base())
        args[2] = {"ok": True}
        self.assertFalse(audit_evidence_chain(*args)["ok"])

    def test_report_tuning_flag_blocks(self):
        args = list(base())
        args[4]["selection_or_threshold_tuning_allowed"] = True
        self.assertFalse(audit_evidence_chain(*args)["ok"])

    def test_bad_manifest_hash_blocks(self):
        args = list(base())
        args[0]["model_spec_sha256"] = "not-a-sha"
        self.assertFalse(audit_evidence_chain(*args)["ok"])


if __name__ == "__main__":
    unittest.main()
