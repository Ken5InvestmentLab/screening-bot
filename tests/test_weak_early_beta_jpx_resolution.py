"""Offline synthetic JPX pipeline regression; no requests or private archives."""
import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from weak_early_beta.acquisition import AcquisitionArchive
from weak_early_beta.corporate_actions import normalize_daily,validate_source_revision,fetch_daily,CorporateActionError
from weak_early_beta.jpx_decisions import Evidence
from weak_early_beta.jpx_resolver import resolve
from weak_early_beta.jpx_holds import apply,audit,carry,ISSUE

def frame(value=100,symbol='1234',date='2026-11-09'):
 return normalize_daily(pd.DataFrame([dict(symbol=symbol,date=date,open=value,high=120,low=90,close=110,volume=1000,split_ratio=0)]))
def official(value):
 return {('1234','2026-11-09','open'):Evidence('1234','2026-11-09','open',str(value),'https://www.jpx.co.jp/automation/markets/statistics-equities/daily/files/202611/stq_20261109.pdf','a'*64,1,'JPY','actual_session_units','morning_first_trade',True)}
class Archive:
 def verified_revision_info(self):return {'responseInventorySha256':'5'*64,'manifestSha256':'2'*64,'directory':'synthetic','requests':1}
class JPXTests(unittest.TestCase):
 def run_resolve(self,old,new,evidence):return resolve(old,new,evidence=evidence,previous_source_sha256='1'*64,archive=Archive())
 def test_old_confirmed_preserves_inputs(self):
  old,new=frame(),frame(110);out,r=self.run_resolve(old,new,official(100))
  self.assertEqual(out.open.iloc[0],100);self.assertEqual(new.open.iloc[0],110);self.assertEqual(r['jpxDecisions'][0]['decision'],'keep_old');normalize_daily(out)
 def test_new_confirmed_preserves_old(self):
  old=frame();out,r=self.run_resolve(old,frame(110),official(110));self.assertEqual(old.open.iloc[0],100);self.assertEqual(out.open.iloc[0],110);self.assertEqual(r['jpxDecisions'][0]['decision'],'accept_new')
 def test_neither_and_missing_hold_only_symbol(self):
  for e in ({},official(105)):
   old=pd.concat([frame(),frame(symbol='5678')],ignore_index=True);new=pd.concat([frame(110),frame(symbol='5678')],ignore_index=True)
   out,r=self.run_resolve(old,new,e);self.assertEqual(len(out),2);self.assertFalse(out[out.symbol.eq('1234')].source_usable.any());self.assertTrue(out[out.symbol.eq('5678')].source_usable.all())
   restored=pd.read_csv(io.StringIO(out.to_csv(index=False)),dtype={'symbol':str},parse_dates=['date']);normalize_daily(restored)
 def test_hold_next_day_needs_quality_lineage(self):
  old,_=self.run_resolve(frame(),frame(110),{})
  new=normalize_daily(pd.concat([frame(110),frame(110,date='2026-11-10')],ignore_index=True)[['symbol','date','open','high','low','close','volume','split_ratio']])
  with self.assertRaises(ValueError):carry(old,new,archive=Archive())
  old.attrs['source_sha256']='3'*64;old.attrs['jpx_hold_lineage']={'dailySha256':'3'*64,'holds':audit(old)}
  out=normalize_daily(carry(old,new,archive=Archive()));self.assertEqual(len(out),2);self.assertFalse(out.source_usable.any())
 def test_tamper_is_not_a_hold(self):
  out,_=self.run_resolve(frame(),frame(110),{});out.loc[0,'open']=111
  with self.assertRaises(CorporateActionError):normalize_daily(out)
  f=frame();f.source_usable=False;f.source_issue=ISSUE
  with self.assertRaises(CorporateActionError):normalize_daily(f)
 def test_default_gate_and_threshold_unchanged(self):
  with self.assertRaises(CorporateActionError):validate_source_revision(frame(),frame(110))
  out,r=self.run_resolve(frame(),frame(101),{});self.assertTrue(out.source_usable.all());self.assertNotIn('jpxDecisions',r)
 def test_held_endpoint_not_updated(self):
  from weak_early_beta.model import refresh_forward_endpoints
  out,_=self.run_resolve(frame(),frame(110),{})
  ledger=pd.DataFrame([dict(symbol='1234',signal_date='2026-11-09',source_scope='FORWARD_CAUSAL',updated_at='keep')])
  with patch('weak_early_beta.model.build_endpoint_receipts',side_effect=AssertionError('held touched')):
   result=refresh_forward_endpoints(ledger,out)
  self.assertEqual(result.updated_at.iloc[0],'keep')
 def test_fetch_connection_only_one_vendor_request(self):
  old=frame();old.attrs['source_sha256']='1'*64
  source=pd.DataFrame([dict(Open=110,High=120,Low=90,Close=110,Volume=1000,**{'Stock Splits':0})],index=pd.to_datetime(['2026-11-09']))
  with tempfile.TemporaryDirectory() as t:
   a=AcquisitionArchive(Path(t)/'archive',{'synthetic':True})
   with patch('yfinance.download',return_value=source) as get,patch('weak_early_beta.jpx_reports.load',return_value=({},{})):
    out=fetch_daily(pd.DataFrame({'ticker':['1234.T']}),'5y',previous=old,archive=a)
   self.assertEqual(get.call_count,1);self.assertFalse(out.source_usable.any())

class LineageTests(unittest.TestCase):
 def test_cached_scoring_cannot_recreate_missing_receipt(self):
  from weak_early_beta.jpx_holds import verify_cached_lineage
  held,_=resolve(frame(),frame(110),evidence={},previous_source_sha256='1'*64,archive=Archive())
  for q in ({},{'identity':'CLOUD_SOURCE_QUALITY_V1','daily_sha256':'3'*64,'source_revision':{'jpxHolds':audit(held)}}):
   with self.assertRaises(ValueError):verify_cached_lineage(held,q,'4'*64)
  q={'identity':'CLOUD_SOURCE_QUALITY_V1','daily_sha256':'4'*64,'source_revision':{'jpxHolds':audit(held)}}
  self.assertEqual(verify_cached_lineage(held,q,'4'*64),audit(held))

class InventoryTests(unittest.TestCase):
 def test_inventory_pins_packets_and_rejects_tampering(self):
  from weak_early_beta.acquisition import RetainedResponseError
  with tempfile.TemporaryDirectory() as t:
   a=AcquisitionArchive(Path(t)/'archive',{'synthetic':True})
   with self.assertRaises(RetainedResponseError):a.verified_revision_info()
   a.request({'ticker':'1234.T'},lambda:{'synthetic':1},{})
   info=a.verified_revision_info();self.assertEqual(len(info['responseInventorySha256']),64)
   next(a.directory.glob('*.pkl')).write_bytes(b'changed')
   with self.assertRaises(RetainedResponseError):a.verified_revision_info()
