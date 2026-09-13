import unittest
import pandas as pd

from tvfree_screener.batch02.eval_causal_4h_scoring_v4 import add_cross_sectional_features


class CrossSectionFeaturesTests(unittest.TestCase):
    def test_ranks_and_context_are_within_same_cohort(self):
        rows=[]
        for sym,ret,rng,vol in [("A",-0.01,0.02,100),("B",0.00,0.03,200),("C",0.02,0.01,300)]:
            rows.append(dict(symbol=sym,date="2025-01-06",bin_name="AM_09_13",bar_log_return=ret,range_pct=rng,upper_wick_pct=0.01,lower_wick_pct=0.01,prev4_log_return_mean=ret,prev4_range_mean=rng,log_range_vs_prior20=rng,bin_volume=vol))
        d=add_cross_sectional_features(pd.DataFrame(rows))
        self.assertAlmostEqual(d.loc[d.symbol=="C","xrank_bar_log_return"].iloc[0],1.0)
        self.assertAlmostEqual(d["xctx_breadth_positive"].iloc[0],1/3)
        self.assertAlmostEqual(d.loc[d.symbol=="C","xrank_bin_volume"].iloc[0],1.0)


if __name__=="__main__":
    unittest.main()
