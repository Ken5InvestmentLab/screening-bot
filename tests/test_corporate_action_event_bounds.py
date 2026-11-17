import unittest
from unittest.mock import patch
import pandas as pd
from weak_early_beta.corporate_actions import normalize_daily,validate_source_revision,CorporateActionError
class EventBoundsTests(unittest.TestCase):
 def raw(self,count=2):return pd.DataFrame([dict(symbol=str(1000+s),date=d,open=99.,high=102.,low=98.,close=100.,volume=10000.,split_ratio=r) for s in range(count) for d,r in zip(pd.bdate_range('2026-09-24',periods=4),[0,0,2,0])])
 def test_historical_events_do_not_trigger_full_corpus_symbol_scans(self):
  previous=normalize_daily(self.raw(24));scans=[];original=pd.Series.eq
  def measured(series,other,*a,**kw):
   if series.name=='symbol' and len(series)==len(previous):scans.append(len(series))
   return original(series,other,*a,**kw)
  with patch.object(pd.Series,'eq',measured):result=validate_source_revision(previous,previous)
  self.assertEqual(result['comparedRows'],96);self.assertEqual(scans,[])
 def test_missing_symbol_retains_existing_skip_rule(self):
  previous=normalize_daily(self.raw());current=previous[previous.symbol.eq('1000')]
  self.assertEqual(validate_source_revision(previous,current)['comparedRows'],4)
 def test_event_before_current_coverage_retains_existing_skip_rule(self):
  previous=normalize_daily(self.raw());current=previous[previous.date.eq(previous.date.max())]
  self.assertEqual(validate_source_revision(previous,current)['comparedRows'],2)
 def test_removed_event_inside_overlap_still_fails_closed(self):
  previous=normalize_daily(self.raw());current=normalize_daily(self.raw().assign(split_ratio=0))
  with self.assertRaisesRegex(CorporateActionError,'previously recorded split event was removed/revised'):validate_source_revision(previous,current)
if __name__=='__main__':unittest.main()
