import unittest
import pandas as pd
from weak_early_beta.corporate_actions import normalize_daily
class AuditCounter:
 copies=0
 def __deepcopy__(self,memo):type(self).copies+=1;return type(self)()
class MetadataTests(unittest.TestCase):
 def frame(self):
  return pd.DataFrame([dict(symbol=s,date=d,open=99.,high=102.,low=98.,close=100.,volume=10000.,split_ratio=0.) for s in ['1234','5678'] for d in pd.bdate_range('2026-09-24',periods=4)])
 def test_nested_lineage_preserved_independently(self):
  frame=self.frame();frame.attrs={'audit':{'items':[{'sha':'a'*64,'reason':'verified'}]}}
  result=normalize_daily(frame);self.assertEqual(result.attrs,frame.attrs)
  result.attrs['audit']['items'].append({'changed':True});self.assertEqual(len(frame.attrs['audit']['items']),1)
  self.assertNotIn('actual_open',frame)
 def test_reapplication_preserves_metadata_and_values(self):
  frame=self.frame();frame.attrs={'lineage':[{'sha':'b'*64}]};once=normalize_daily(frame);twice=normalize_daily(once)
  pd.testing.assert_frame_equal(once,twice);self.assertEqual(once.attrs,twice.attrs)
 def test_audit_copied_once_not_per_group_or_slice(self):
  frame=self.frame();frame.attrs={'counter':AuditCounter()};AuditCounter.copies=0
  result=normalize_daily(frame);self.assertEqual(AuditCounter.copies,1);self.assertIn('counter',result.attrs)
 def test_empty_preserves_nested_lineage(self):
  frame=self.frame().iloc[:0];frame.attrs={'audit':{'items':[1]}};result=normalize_daily(frame)
  self.assertEqual(result.attrs,frame.attrs);result.attrs['audit']['items'].append(2);self.assertEqual(frame.attrs['audit']['items'],[1])
if __name__=='__main__':unittest.main()
