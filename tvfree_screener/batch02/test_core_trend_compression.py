import unittest
import numpy as np
import pandas as pd
from tvfree_screener.batch02.core_trend_compression_audit import rolling_stats
from tvfree_screener.batch01.selection import PolicySpec,apply_selection_policy,rank_candidate_pool

class CoreTrendCompressionTests(unittest.TestCase):
 def test_rolling_volatility_requires_20_consecutive_sessions(self):
  r=np.array([.01,-.005,.002,.004,-.003]*4,dtype=float)
  ix=np.arange(20)
  rv5,rv20,ok=rolling_stats(ix,r)
  self.assertTrue(bool(ok[-1]))
  self.assertAlmostEqual(rv5[-1],np.std(r[-5:],ddof=0))
  self.assertAlmostEqual(rv20[-1],np.std(r,ddof=0))
  gap=ix.copy(); gap[10:]+=1
  self.assertFalse(bool(rolling_stats(gap,r)[2][-1]))

 def test_topn_cooldown_and_multiple_names_per_session(self):
  dates=pd.date_range("2023-01-02",periods=3,freq="B")
  rows=[]
  for d in dates:
   for rank,sym in enumerate(("A","B"),1):
    rows.append({"date":d,"symbol":sym,"family":"core_trend_compression","spec_hash":"frozen",
     "identity_key":sym,"rv_ratio_5_20":float(rank),"ret20":.1})
  ranked=rank_candidate_pool(pd.DataFrame(rows),sessions=dates,feature_columns=["rv_ratio_5_20","ret20"],
   ranking_terms=[("rv_ratio_5_20",True),("ret20",False)])
  one=apply_selection_policy(ranked,sessions=dates,policy=PolicySpec("core",1,"top1")).selected
  byday=one.groupby("date")["symbol"].apply(list).to_dict()
  self.assertEqual(byday[dates[0]],["A"]); self.assertEqual(byday[dates[1]],["B"]); self.assertEqual(byday[dates[2]],["A"])
  two=apply_selection_policy(ranked,sessions=dates,policy=PolicySpec("core",2,"top2")).selected
  self.assertEqual(two.loc[two["date"].eq(dates[0]),"symbol"].tolist(),["A","B"])

if __name__=="__main__": unittest.main()
