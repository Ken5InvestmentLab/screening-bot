import unittest

from tvfree_screener.batch02.eval_causal_4h_scoring_v6 import month_bounds


class V6ScheduleTests(unittest.TestCase):
    def test_month_bounds(self):
        self.assertEqual(month_bounds("2025-02"), ("2025-02-01", "2025-02-28"))
        self.assertEqual(month_bounds("2025-07"), ("2025-07-01", "2025-07-31"))


if __name__=="__main__":
    unittest.main()
