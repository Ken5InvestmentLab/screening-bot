import unittest
import pandas as pd

from tvfree_screener.batch02.eval_causal_4h_scoring_v3 import metrics, passes


class Causal4HV3MetricTests(unittest.TestCase):
    def test_core_gate_can_pass(self):
        rows = [
            {"endpoint_status": "RESOLVED", "ret5bd_gross": 0.02, "date": "2025-03-03", "symbol": str(1000 + i)}
            for i in range(60)
        ]
        self.assertTrue(passes("core", metrics(pd.DataFrame(rows), 0.005)))

    def test_monster_gate_requires_right_tail(self):
        rows = [
            {"endpoint_status": "RESOLVED", "ret5bd_gross": 0.02, "date": "2025-03-03", "symbol": str(1000 + i)}
            for i in range(40)
        ]
        self.assertFalse(passes("monster", metrics(pd.DataFrame(rows), 0.005)))


if __name__ == "__main__":
    unittest.main()
