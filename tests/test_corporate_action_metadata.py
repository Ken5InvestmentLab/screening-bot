import unittest
import pandas as pd
from weak_early_beta.corporate_actions import normalize_daily,validate_source_revision,quarantine_repaired_volume_revisions
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
 def test_revision_audit_not_copied_per_symbol_or_comparison(self):
  previous=normalize_daily(self.frame());previous.attrs={'counter':AuditCounter(),'source_sha256':'f'*64};current=normalize_daily(self.frame());current.attrs={'counter':AuditCounter()};AuditCounter.copies=0
  result=validate_source_revision(previous,current);self.assertEqual(result['comparedRows'],8);self.assertLessEqual(AuditCounter.copies,3);self.assertIn('counter',previous.attrs);self.assertIn('counter',current.attrs);self.assertEqual(previous.attrs['source_sha256'],'f'*64)
 def test_volume_revision_preserves_output_lineage_without_group_copies(self):
  previous=normalize_daily(self.frame());previous.attrs={'counter':AuditCounter(),'source_sha256':'f'*64};current=normalize_daily(self.frame());current.attrs={'counter':AuditCounter(),'audit':{'items':[1]}};AuditCounter.copies=0
  result=quarantine_repaired_volume_revisions(previous,current);self.assertLessEqual(AuditCounter.copies,3);self.assertIn('counter',result.attrs);self.assertEqual(result.attrs['audit'],{'items':[1]});result.attrs['audit']['items'].append(2);self.assertEqual(current.attrs['audit'],{'items':[1]});self.assertIn('counter',previous.attrs)
if __name__=='__main__':unittest.main()
