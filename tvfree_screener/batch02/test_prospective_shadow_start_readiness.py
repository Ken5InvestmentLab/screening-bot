import unittest

from tvfree_screener.batch02.prospective_shadow_start_readiness import (
    REQUIRED_CHECKS,
    evaluate_start_readiness,
)


class ProspectiveShadowStartReadinessTests(unittest.TestCase):
    def test_all_checks_true_allows_start(self):
        payload = {name: True for name in REQUIRED_CHECKS}
        result = evaluate_start_readiness(payload)
        self.assertTrue(result["ready_for_prospective_shadow"])
        self.assertEqual(result["decision"], "ALLOW_PROSPECTIVE_SHADOW_START")
        self.assertEqual(result["missing_requirements"], [])

    def test_representation_pass_alone_is_not_enough(self):
        result = evaluate_start_readiness({"representation_gate_passed": True})
        self.assertFalse(result["ready_for_prospective_shadow"])
        self.assertIn("supervised_evaluation_preregistered", result["missing_requirements"])
        self.assertIn("h1_policy_frozen", result["missing_requirements"])

    def test_missing_freeze_blocks_start(self):
        payload = {name: True for name in REQUIRED_CHECKS}
        payload["model_freeze_manifest_valid"] = False
        result = evaluate_start_readiness(payload)
        self.assertEqual(result["decision"], "BLOCK_PROSPECTIVE_SHADOW_START")
        self.assertEqual(result["missing_requirements"], ["model_freeze_manifest_valid"])

    def test_missing_causal_preflight_blocks_start(self):
        payload = {name: True for name in REQUIRED_CHECKS}
        payload["causal_preflight_passed"] = False
        result = evaluate_start_readiness(payload)
        self.assertIn("causal_preflight_passed", result["missing_requirements"])

    def test_gate_never_promotes_model(self):
        payload = {name: True for name in REQUIRED_CHECKS}
        result = evaluate_start_readiness(payload)
        integrity = result["integrity"]
        self.assertFalse(integrity["opens_strategy_returns"])
        self.assertFalse(integrity["changes_model"])
        self.assertIn("never promotes", integrity["note"])


if __name__ == "__main__":
    unittest.main()
