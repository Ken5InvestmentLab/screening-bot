import unittest
import numpy as np


class V5FormulaTests(unittest.TestCase):
    def test_monster_score_penalizes_negative_q10(self):
        q90=0.30
        self.assertAlmostEqual(q90+min(-0.10,0),0.20)
        self.assertAlmostEqual(q90+min(0.02,0),0.30)

    def test_quantile_sort_is_deterministic(self):
        x=np.array([[0.2,-0.1,0.05]])
        y=np.sort(x,axis=1)
        self.assertTrue(np.allclose(y,[[-0.1,0.05,0.2]]))


if __name__=="__main__":
    unittest.main()
