from __future__ import annotations

import unittest

from .core_orderly_pullback_recovery import _recovery_decision


class OrderlyPullbackRecoveryTests(unittest.TestCase):
    def test_reject_skips_policy_metrics(self):
        decision, policy = _recovery_decision("REJECT")
        self.assertEqual(decision, "REJECT")
        self.assertEqual(policy, "NOT_EVALUATED_FAMILY_NOT_KEEP")

    def test_inconclusive_skips_policy_metrics(self):
        decision, policy = _recovery_decision("INCONCLUSIVE_INCOMPLETE_POOL_COHORT_COVERAGE")
        self.assertEqual(decision, "INCONCLUSIVE_INCOMPLETE_POOL_COHORT_COVERAGE")
        self.assertEqual(policy, "NOT_EVALUATED_FAMILY_NOT_KEEP")

    def test_keep_conflicts_with_prior_trace_and_fails_closed(self):
        decision, policy = _recovery_decision("KEEP")
        self.assertEqual(decision, "RECOVERY_ABORT_PRIOR_TRACE_DISAGREEMENT")
        self.assertEqual(policy, "NOT_EVALUATED_RECOVERY_FAIL_CLOSED")

    def test_unknown_gate_decision_is_rejected(self):
        with self.assertRaises(ValueError):
            _recovery_decision("PROMOTE")


if __name__ == "__main__":
    unittest.main()