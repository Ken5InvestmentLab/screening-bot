"""新A接続の境界試験。合成価格だけ、ネットワーク/通知は使用しない。"""
import copy,datetime,json,sqlite3,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from weak_early_beta.new_a import monitor
from weak_early_beta.new_a.pipeline import Pipeline
from weak_early_beta.new_a.publisher import LocalD1,publish_bundle,verify_dataset,pointer,literal
from weak_early_beta.new_a.files import atomic_write,digest,encode

def market_days():
 values=[];d=datetime.date(2026,5,1)
 while len(values)<80:
  if d.weekday()<5:values.append(d.isoformat())
  d+=datetime.timedelta(days=1)
 return values
def bar(candidate=False):return dict(open=104.,high=108.,low=100.,close=104.,actual_close=104.,volume=100000.,actual_volume=100000.,split_factor=1.,source_usable=True,candidate=candidate,low20=100.,high20=110.,median_turnover20=20000000.)
class DailyResume(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.cal=market_days();self.day=self.cal[-1];self.seed=monitor.initial(self.cal,['1111','2222'],'SYNTHETIC_A_ONLY');self.seed['cursor']=78;self.seed['previous']={s:bar() for s in self.seed['symbols']};self.p=Pipeline(Path(self.temp.name)/'state.sqlite',self.seed);self.rows={self.cal[-2]:{s:bar() for s in self.seed['symbols']},self.day:{'1111':bar(True),'2222':None}}
 def tearDown(self):self.p.close();self.temp.cleanup()
 def run_day(self,**patch):
  args=dict(as_of=self.day,observed_at=self.day+'T08:00:00Z',calendar=self.cal,rows_by_day=self.rows,source_hash='a'*64,quality_verified=True,universe=self.seed['symbols'],dry_run=True);args.update(patch);return self.p.run(**args)
 def test_one_late_held_quote_same_day_does_not_advance_other_symbol(self):
  first=self.run_day();healthy=monitor.encode(self.p.read('1111'));count=self.p.db.execute('SELECT count(*) FROM symbol_days WHERE symbol="1111"').fetchone()[0];self.assertEqual(first['processed_symbol_sessions'],1);self.rows[self.day]['2222']=bar(True)
  later=self.run_day(source_hash='b'*64,resume_held=True,predecessor_source_hash='a'*64);self.assertTrue(later['held_resume']);self.assertEqual(later['processed_symbol_sessions'],1);self.assertEqual(later['new_event_count'],1);self.assertFalse(later['held']);self.assertEqual(monitor.encode(self.p.read('1111')),healthy);self.assertEqual(self.p.db.execute('SELECT count(*) FROM symbol_days WHERE symbol="1111"').fetchone()[0],count);self.assertEqual(self.p.read('1111')['calendar'],self.cal);self.assertEqual(self.p.read('1111')['pending'],json.loads(healthy)['pending']);self.assertEqual(self.p.db.execute('SELECT count(*) FROM events').fetchone()[0],2)
  again=self.run_day(source_hash='b'*64);self.assertEqual(again['new_event_count'],0);self.assertEqual(monitor.encode(self.p.read('1111')),healthy)
  with self.assertRaisesRegex(ValueError,'stale source'):self.run_day()
 def test_late_held_resume_rejects_any_committed_bar_change(self):
  self.run_day();healthy=monitor.encode(self.p.read('1111'));self.rows[self.day]['2222']=bar(True);self.rows[self.day]['1111']['volume']+=1
  with self.assertRaisesRegex(ValueError,'committed input'):self.run_day(source_hash='b'*64,resume_held=True,predecessor_source_hash='a'*64)
  self.assertEqual(monitor.encode(self.p.read('1111')),healthy);self.assertEqual(self.p.read('2222')['cursor'],78)
 def test_held_resume_keeps_existing_watch_age_and_pending_holding_indices(self):
  seed=copy.deepcopy(self.seed);episode=dict(symbol='1111',candidate_date=self.cal[70],episode_id=2,support=100.,resistance=110.,priority_score=20000000.,detection_count=1)
  seed['active']['1111']=copy.deepcopy(episode);seed['watches']['1111|2']={'episode':copy.deepcopy(episode),'start_index':70}
  seed['pending']=[dict(episode,episode_id=1,trigger_date=self.cal[69],entry_index=70,reference_exit_index=89,reference_entry_date=self.cal[70],reference_exit_date=None,reference_open=104.,price_status='HISTORICAL_REFERENCE_ONLY',execution_status='NOT_EXECUTED')]
  rich=Pipeline(Path(self.temp.name)/'rich-state.sqlite',seed)
  try:
   rows=copy.deepcopy(self.rows);rows[self.day]['1111']=bar(False)
   args=dict(as_of=self.day,observed_at=self.day+'T08:00:00Z',calendar=self.cal,rows_by_day=rows,source_hash='c'*64,quality_verified=True,universe=seed['symbols'],dry_run=True)
   first=rich.run(**args);healthy=rich.read('1111');self.assertEqual(first['processed_symbol_sessions'],1)
   age=healthy['cursor']-healthy['watches']['1111|2']['start_index'];holding_age=healthy['cursor']-healthy['pending'][0]['entry_index'];self.assertEqual((age,holding_age),(9,9))
   rows[self.day]['2222']=bar(True);args.update(source_hash='d'*64,resume_held=True,predecessor_source_hash='c'*64)
   later=rich.run(**args);after=rich.read('1111');self.assertEqual(later['processed_symbol_sessions'],1);self.assertEqual(later['new_event_count'],1)
   self.assertEqual(monitor.encode(after),monitor.encode(healthy));self.assertEqual((after['cursor']-after['watches']['1111|2']['start_index'],after['cursor']-after['pending'][0]['entry_index']),(age,holding_age));self.assertEqual(after['pending'][0]['reference_exit_index'],89)
   self.assertEqual(rich.db.execute('SELECT count(*) FROM symbol_days WHERE symbol="1111"').fetchone()[0],1)
   self.assertEqual(rich.run(**args)['new_event_count'],0)
  finally:rich.close()
 def test_no_generic_same_day_revision_or_dry_live_switch(self):
  self.run_day()
  with self.assertRaisesRegex(ValueError,'requires review'):self.run_day(source_hash='b'*64)
  with self.assertRaisesRegex(ValueError,'requires review'):self.run_day(source_hash='b'*64,resume_held=True,predecessor_source_hash='c'*64)
 def test_causal_designation_and_relisting_intervals(self):
  restrictions={'1111':[{'start':self.day,'end':None,'reason':'VERIFIED_RESTRICTED'}],'2222':[{'start':self.cal[-3],'end':self.day,'reason':'VERIFIED_DELISTED'}]};self.rows[self.day]['2222']=bar(True);r=self.run_day(restrictions=restrictions);self.assertEqual(r['held']['1111']['reason'],'VERIFIED_RESTRICTED');self.assertNotIn('2222',r['held'])
 def test_late_catchup_is_not_live_and_new_universe_warmup_emits_no_backfill(self):
  rows={d:{'1111':bar(False),'2222':bar(False),'999A':bar(True)} for d in self.cal};r=self.run_day(rows_by_day=rows,universe=['1111','2222','999A']);events=[e for e in r['events'] if e['symbol']=='999A'];self.assertEqual(len(events),1);self.assertEqual(events[0]['session'],self.day);self.assertFalse(events[0]['is_new_live_signal'])
 def test_new_member_missing_prelisting_warmup_does_not_stall_current_day(self):
  from weak_early_beta.new_a.features import compute_features
  import pandas as pd
  values=[]
  for day in self.cal[-3:]:values.append({'date':day,**{k:v for k,v in bar().items() if k not in ['candidate','low20','high20','median_turnover20']}})
  features=compute_features(pd.DataFrame(values),self.cal);self.assertFalse(bool(features.loc[pd.Timestamp(self.day),'quality60']));self.assertFalse(bool(features.loc[pd.Timestamp(self.day),'candidate']))
  rows={d:{'1111':bar(False),'2222':bar(False),'999A':None} for d in self.cal};rows[self.day]['999A']=bar(False);r=self.run_day(rows_by_day=rows,universe=['1111','2222','999A']);self.assertEqual(self.p.read('999A')['cursor'],79);self.assertNotIn('999A',r['held']);self.assertFalse([e for e in r['events'] if e['symbol']=='999A'])
class Publisher(unittest.TestCase):
 def test_sql_literal_does_not_move_placeholders_or_leak_values(self):
  self.assertEqual(literal("x?'雪;"),"'x?''雪;'")
 def test_activation_is_closed_without_actual_owner_evidence(self):
  from weak_early_beta.new_a.acceptance import validate_activation
  with self.assertRaisesRegex(ValueError,'activation'):validate_activation({},Path('.'))
  with self.assertRaisesRegex(ValueError,'owner acceptance'):validate_activation({'schema':'NEW_A_OWNER_ACTIVATION_V1','active':True,'external_actions_approved':True,'strategy':'A_BASE'},Path('.'))
class Notifications(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'new-a-private';self.root.mkdir();self.day='2026-06-01';self.calls=[]
  self.snapshot={'schema':'NEW_A_OWNER_DAILY_SNAPSHOT_V1','strategy':'A_BASE','audience':'EXISTING_CLOUD_OWNER_ONLY','as_of':self.day,'source_sha256':'a'*64,'observation_kind':'LIVE_OBSERVATION','new_live_signals':1,'events':[{'event_id':'b'*64,'kind':'WATCH_STARTED','symbol':'1111','session':self.day,'is_new_live_signal':True}],'published':False};self.save()
 def save(self):
  self.snapshot['payload_sha256']=digest({k:v for k,v in self.snapshot.items() if k!='payload_sha256'});atomic_write(self.root/'snapshot.json',self.snapshot);atomic_write(self.root/'latest-run.json',{'strategy':'A_BASE','source_sha256':'a'*64,'source_version':'c'*64,'snapshot_sha256':self.snapshot['payload_sha256'],'snapshot_file':str(self.root/'snapshot.json')});atomic_write(self.root/'latest-publication.json',{'published':True,'active_readback_verified':True,'existing_owner_gate_verified':True,'snapshot_sha256':self.snapshot['payload_sha256'],'source_version':'c'*64})
 def tearDown(self):self.temp.cleanup()
 def test_only_newA_receipts_and_existing_transport_callback_no_repeat(self):
  from weak_early_beta.new_a.notifications import notify_day
  before=notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/');self.assertEqual((before['signal_notifications'],before['completion_notifications']),(1,1));self.assertFalse(self.calls)
  def fake(payload):self.calls.append(payload['event_id']);return{'confirmed':True,'message_id':'SYNTHETIC_ONLY'}
  sent=notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=fake);self.assertEqual(len(self.calls),2);self.assertEqual(sent['signal_notifications'],1)
  remaining=notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/');self.assertEqual(remaining['signal_notifications']+remaining['completion_notifications'],0)
  notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=fake);self.assertEqual(len(self.calls),2)
 def test_unknown_send_never_retries_automatically(self):
  from weak_early_beta.new_a.notifications import notify_day
  def uncertain(payload):self.calls.append(payload['event_id']);return{'confirmed':False}
  with self.assertRaises(RuntimeError):notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=uncertain)
  with self.assertRaisesRegex(ValueError,'unconfirmed'):notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/')
  self.assertEqual(len(self.calls),1)
 def test_live_unpublished_blocks_summary_and_signals_before_callback(self):
  from weak_early_beta.new_a.notifications import notify_day
  pub=json.loads((self.root/'latest-publication.json').read_text());pub['published']=False;atomic_write(self.root/'latest-publication.json',pub)
  for dry in [True,False]:
   with self.assertRaisesRegex(ValueError,'publication'):notify_day(self.root,date=self.day,dry_run=dry,report_url='https://synthetic.invalid/',transport=lambda p:self.calls.append(p))
  self.assertFalse(self.calls);self.assertFalse((self.root/'notification-outbox.sqlite').exists())
 def test_corrupt_private_snapshot_rejected_before_callback(self):
  from weak_early_beta.new_a.notifications import notify_day
  self.snapshot['events'][0]['symbol']='9999';atomic_write(self.root/'snapshot.json',self.snapshot)
  with self.assertRaisesRegex(ValueError,'bytes changed'):notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=lambda p:self.calls.append(p))
  self.assertFalse(self.calls)
 def test_historical_local_preview_has_zero_notifications_and_no_credentials(self):
  from weak_early_beta.new_a.notifications import notify_day
  self.snapshot['observation_kind']='DRY_RUN_HISTORICAL';self.snapshot['new_live_signals']=0;self.snapshot['events'][0]['is_new_live_signal']=False;self.save();pub=json.loads((self.root/'latest-publication.json').read_text());pub.update(published=False,existing_owner_gate_verified=False,local_d1_emulation=True);atomic_write(self.root/'latest-publication.json',pub)
  with patch('weak_early_beta.new_a.notifications.default_transport',side_effect=AssertionError('credentials forbidden')):
   preview=notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/');self.assertEqual(preview['signal_notifications']+preview['completion_notifications'],0)
  with self.assertRaises(ValueError):notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/')
if __name__=='__main__':unittest.main()
