from __future__ import annotations

import unittest

from tvfree_screener.batch02.causal_label_maturity import (
    causal_training_row,
    mature_before_validation,
)


class CausalLabelMaturityTests(unittest.TestCase):
    def test_exit_before_validation_is_mature(self):
        self.assertTrue(mature_before_validation(
            exit_date="2025-06-30", validation_start="2025-07-01"
        ))

    def test_exit_on_validation_start_is_not_mature(self):
        self.assertFalse(mature_before_validation(
            exit_date="2025-07-01", validation_start="2025-07-01"
        ))

    def test_late_june_signal_is_rejected_when_5bd_exit_is_in_july(self):
        self.assertFalse(causal_training_row(
            signal_date="2025-06-30",
            exit_date="2025-07-07",
            train_start="2025-01-01",
            train_end="2025-06-30",
            validation_start="2025-07-01",
        ))

    def test_mature_h1_signal_is_accepted(self):
        self.assertTrue(causal_training_row(
            signal_date="2025-06-23",
            exit_date="2025-06-30",
            train_start="2025-01-01",
            train_end="2025-06-30",
            validation_start="2025-07-01",
        ))


if __name__ == "__main__":
    unittest.main()
