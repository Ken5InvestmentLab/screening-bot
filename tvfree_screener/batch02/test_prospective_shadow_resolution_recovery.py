from __future__ import annotations

import unittest

from tvfree_screener.batch02.prospective_shadow_resolution_recovery import classify_resolution_recovery_state


class ResolutionRecoveryStateTest(unittest.TestCase):
    def test_committed_when_tail_matches_current(self):
        state = classify_resolution_recovery_state(
            [{"resolved_output_sha256": "aaa"}], "AAA", chain_valid=True
        )
        self.assertEqual(state.state, "committed")
        self.assertFalse(state.recovery_allowed)

    def test_sidecar_ahead_when_prior_matches_current(self):
        state = classify_resolution_recovery_state(
            [
                {"resolved_output_sha256": "aaa"},
                {"resolved_output_sha256": "bbb"},
            ],
            "aaa",
            chain_valid=True,
        )
        self.assertEqual(state.state, "sidecar_ahead_interrupted")
        self.assertTrue(state.recovery_allowed)
        self.assertEqual(state.tail_resolved_sha256, "bbb")
        self.assertEqual(state.prior_resolved_sha256, "aaa")

    def test_invalid_when_chain_verification_failed(self):
        state = classify_resolution_recovery_state(
            [{"resolved_output_sha256": "aaa"}], "aaa", chain_valid=False
        )
        self.assertEqual(state.state, "invalid_tampered")
        self.assertFalse(state.recovery_allowed)

    def test_invalid_when_current_matches_neither_tail_nor_prior(self):
        state = classify_resolution_recovery_state(
            [
                {"resolved_output_sha256": "aaa"},
                {"resolved_output_sha256": "bbb"},
            ],
            "ccc",
            chain_valid=True,
        )
        self.assertEqual(state.state, "invalid_tampered")
        self.assertFalse(state.recovery_allowed)

    def test_does_not_mutate_chain(self):
        chain = [
            {"resolved_output_sha256": "aaa", "marker": [1]},
            {"resolved_output_sha256": "bbb", "marker": [2]},
        ]
        before = repr(chain)
        classify_resolution_recovery_state(chain, "aaa", chain_valid=True)
        self.assertEqual(repr(chain), before)


if __name__ == "__main__":
    unittest.main()
