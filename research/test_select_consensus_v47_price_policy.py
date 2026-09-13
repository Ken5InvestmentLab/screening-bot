from __future__ import annotations

import unittest

from select_consensus_v47_price_policy import choose_dev, validate_winner


def arm(n=20, mean=1.0, top3=0.5, median=0.2):
    return {
        "n": n,
        "mean_net_0p5_pct": mean,
        "top3_ex_net_0p5_pct": top3,
        "median_net_0p5_pct": median,
    }


class V47PricePolicyContractTests(unittest.TestCase):
    def test_mean_difference_exactly_0p50_uses_mean(self):
        d = {
            "NOCAP": arm(mean=1.50, top3=-10, median=-10),
            "CAP1000_PIT": arm(mean=1.00, top3=10, median=10),
        }
        self.assertEqual(choose_dev(d)["winner"], "NOCAP")

    def test_mean_difference_below_0p50_uses_top3(self):
        d = {
            "NOCAP": arm(mean=1.49, top3=0.10, median=10),
            "CAP1000_PIT": arm(mean=1.00, top3=0.40, median=-10),
        }
        self.assertEqual(choose_dev(d)["winner"], "CAP1000_PIT")

    def test_top3_difference_exactly_0p25_uses_top3(self):
        d = {
            "NOCAP": arm(mean=1.10, top3=0.50, median=-10),
            "CAP1000_PIT": arm(mean=1.00, top3=0.25, median=10),
        }
        self.assertEqual(choose_dev(d)["winner"], "NOCAP")

    def test_top3_difference_below_0p25_uses_median(self):
        d = {
            "NOCAP": arm(mean=1.10, top3=0.49, median=0.10),
            "CAP1000_PIT": arm(mean=1.00, top3=0.25 + 0.01, median=0.20),
        }
        self.assertEqual(choose_dev(d)["winner"], "CAP1000_PIT")

    def test_full_tie_prefers_nocap(self):
        d = {"NOCAP": arm(), "CAP1000_PIT": arm()}
        out = choose_dev(d)
        self.assertEqual(out["winner"], "NOCAP")
        self.assertTrue(out["nonwinner_h2_must_remain_unopened"])

    def test_development_n_below_20_fails_closed(self):
        d = {"NOCAP": arm(n=19), "CAP1000_PIT": arm()}
        with self.assertRaises(RuntimeError):
            choose_dev(d)

    def test_validation_wrong_arm_fails_closed(self):
        with self.assertRaises(RuntimeError):
            validate_winner("NOCAP", {"arm": "CAP1000_PIT", "mean_net_0p5_pct": 1.0})

    def test_validation_requires_strictly_positive_mean(self):
        self.assertFalse(
            validate_winner("NOCAP", {"arm": "NOCAP", "mean_net_0p5_pct": 0.0})[
                "continued_research_pass"
            ]
        )
        self.assertTrue(
            validate_winner("NOCAP", {"arm": "NOCAP", "mean_net_0p5_pct": 0.0001})[
                "continued_research_pass"
            ]
        )


if __name__ == "__main__":
    unittest.main()
