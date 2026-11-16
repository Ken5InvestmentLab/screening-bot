"""Synthetic local fixtures only; no production input, auth, SQL or network."""
import copy,datetime,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weak_early_beta.new_a import delayed_recovery as d
from weak_early_beta.new_a.files import atomic_write,read,file_sha,digest,private_root
from weak_early_beta.new_a import continuing_acceptance as ca

class DelayedRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.repo=Path(self.tmp.name);self.time=datetime.datetime(2026,11,16,15,40,tzinfo=datetime.timezone.utc);self.source='c'*40;self.created_filetime=116444736000000000+int(self.time.timestamp()*10000000)
  for module,name,value in [(d,'now',lambda:self.time),(d,'head',lambda _:self.source),(ca,'now',lambda:self.time),(d,'process_identity',lambda _:dict(alive=True,created_filetime=self.created_filetime))]:
   c=patch.object(module,name,value);c.start();self.addCleanup(c.stop)
  atomic_write(self.repo/'weak-early-beta-gate/wrangler.jsonc',dict(name='tentei-kyokuchi-cloud',d1_databases=[dict(binding='CLOUD_DB',database_name='tentei-cloud-settings',database_id='SYNTHETIC-DB')]))
  self.rt=d.runtime(self.repo);self.folder=self.rt/'daily-2026-11-16T13-28-10-435Z';self.archive=self.folder/'acquisition-1';self.archive.mkdir(parents=True)
  self.original=dict(identity='WEAK_EARLY_CLOUD_DAILY_V1',date=d.TARGET,startedAt=d.ORIGINAL,pid=123,stage='detection',ok=False,new_a=dict(strategy='A_BASE',entry='new-a-verified-daily-v1'),acquisitionEvidence=[dict(attempt=1,directory=str(self.archive))])
  # Pretty bytes intentionally differ from canonical JSON: preservation must be exact.
  raw=(json.dumps(self.original,indent=2)+'\n').encode();(self.folder/'result.json').write_bytes(raw);(self.rt/'daily-latest.json').write_bytes(raw);(self.rt/'daily.lock').write_text(d.ORIGINAL)
  (self.rt/'task-entry.lock').write_text('SYNTHETIC-INVOCATION');self.older=self.rt/'daily-1928-preserved.json';self.older.write_bytes(b'SYNTHETIC ORIGINAL 1928 DO NOT TOUCH');self.older_bytes=self.older.read_bytes()
  csv=self.repo/'.cache/weak_early_beta/tse_daily.csv';csv.write_text('symbol,date,close\n0001,2026-11-13,100\n');quality=csv.with_suffix('.source-quality.json');atomic_write(quality,dict(identity='CLOUD_SOURCE_QUALITY_V1',daily_sha256=file_sha(csv)))
  tickers=[f'{i:04d}.T' for i in range(1,48)];inventory=[]
  for i,ticker in enumerate(tickers,1):
   request=dict(kind='batch',tickers=[ticker],kwargs=dict(period='5y',interval='1d',actions=True,repair=True,auto_adjust=False));key=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()[:20];p=self.archive/f'{i:05d}-{key}.json';packet=p.with_suffix('.pkl');packet.write_bytes(b'SYNTHETIC OPAQUE PACKET '+str(i).encode());atomic_write(p,dict(request=request,sha256=file_sha(packet),providerErrors={}))
   inventory.append(dict(receipt=p.name,receipt_sha256=file_sha(p),packet_sha256=file_sha(packet)))
  atomic_write(self.archive/'manifest.json',dict(identity='CLOUD_ACQUISITION_V1',status='acquiring',requests=47,context=dict(date=d.TARGET,period='5y',previousSourceSha256=file_sha(csv),tickers=tickers)))
  self.authority=dict(author_id='SYNTHETIC_OWNER',room_id='SYNTHETIC_ROOM');text='Synthetic owner authorizes one actual delayed Nov16 run and distinct late result delivery, without fake observation times.'
  self.binding=dict(message_id='SYNTHETIC_APPROVAL',**self.authority,text_sha256=digest(text));self.primary=dict(partial=False,room_id=self.authority['room_id'],message=dict(message_id=self.binding['message_id'],author='user',author_id=self.authority['author_id'],channel='chatgpt',sent_at='2026-11-16T15:08:00Z',content=dict(text=text)))
  self.evidence=dict(schema='NEW_A_HOST_STOPPED_RUN_OBSERVATION_V1',platform_signature_claimed=False,source_commit=self.source,target=d.target(self.repo),observed_at=self.time.isoformat(),original_processes_absent=True,nov16_D1_datasets=0,nov16_D1_parts=0,result_notifications=0,destination_histories_complete=True,start_message_id='1571879697464299631',active_revision=2,active_dataset_id='SYNTHETIC-OLD-DATASET',active_as_of='2026-11-13')
  self.plan=dict(scope=d.SCOPE,target_date=d.TARGET,execution_date=d.EXECUTION,source_commit=self.source,target=d.target(self.repo),expected_revision=2,expected_dataset_id='SYNTHETIC-OLD-DATASET',not_after=(self.time+datetime.timedelta(minutes=30)).isoformat(),owner_message=self.binding,evidence=dict(id='ACTUAL_HOST_CALLBACK_REQUIRED',sha256=digest(self.evidence)),original=dict(folder=str(self.folder.relative_to(self.repo)),started_at=d.ORIGINAL,result_sha256=file_sha(self.folder/'result.json'),lock_sha256=file_sha(self.rt/'daily.lock'),processes=[123,124]),source=dict(folder=str(self.archive.relative_to(self.repo)),manifest_sha256=file_sha(self.archive/'manifest.json'),previous_csv_sha256=file_sha(csv),previous_quality_sha256=file_sha(quality),universe_count=47,inventory_sha256=digest(inventory)))
  self.evidence.update(original=copy.deepcopy(self.plan['original']),retained_source=copy.deepcopy(self.plan['source']));self.plan['evidence']['sha256']=digest(self.evidence)
  self.decision=dict(schema='NEW_A_HOST_DELAYED_RUN_DECISION_V1',decision='ONE_DELAYED_TARGET_RUN_WITH_RESULT_DELIVERY',scope=d.SCOPE,message_id=self.binding['message_id'],text_sha256=self.binding['text_sha256'],source_commit=self.source,target=self.plan['target'],platform_signature_claimed=False)
 def issue(self):return d.issue(self.repo,self.plan,primary_reader=lambda _:copy.deepcopy(self.primary),evidence_reader=lambda _:copy.deepcopy(self.evidence),decision_reader=lambda _:copy.deepcopy(self.decision),authority=self.authority)
 def ready(self):return dict(ok=True,head=self.source,repository=str(self.repo))
 def claim(self,ref,**kw):return d.claim_stopped(self.repo,ref,'SYNTHETIC-INVOCATION',preflight=kw.get('preflight',self.ready),processes_absent=kw.get('processes_absent',lambda _:True),activation_validator=kw.get('activation_validator',lambda _:True))
 def running(self):
  reference=self.issue();claim=self.claim(reference);started=self.time.isoformat();(self.rt/'daily.lock').write_text(started);running=d.begin(self.repo,claim,root_pid=555,started_at=started);return reference,claim,running
 def test_issue_never_clears_original_lock_or_marks_day_complete(self):
  self.issue();self.assertEqual((self.rt/'daily.lock').read_text(),d.ORIGINAL);self.assertEqual(read(self.rt/'daily-latest.json'),self.original);self.assertFalse((private_root(self.repo)/'daily-live.sqlite').exists())
 def test_47_packets_hash_checked_without_deserializing_or_network(self):
  self.assertEqual(d.verify_retained(self.repo,self.plan['source']),self.archive)
 def test_missing_or_corrupt_packet_rejected(self):
  p=next(self.archive.glob('*.pkl'));p.write_bytes(b'CORRUPT')
  with self.assertRaisesRegex(ValueError,'packet absent/corrupt'):self.issue()
 def test_other_original_day_or_acquisition_cannot_be_substituted(self):
  self.plan['original']['started_at']='2026-11-16T10:28:01.570Z';self.evidence['original']=copy.deepcopy(self.plan['original']);self.plan['evidence']['sha256']=digest(self.evidence)
  with self.assertRaisesRegex(ValueError,'identity differs'):self.issue()
 def test_changed_previous_source_and_quality_rejected(self):
  (self.repo/'.cache/weak_early_beta/tse_daily.csv').write_text('CHANGED')
  with self.assertRaisesRegex(ValueError,'previous corpus/quality'):self.issue()
 def test_undeclared_completed_cache_status_cannot_skip_validation(self):
  m=read(self.archive/'manifest.json');m['status']='cached';atomic_write(self.archive/'manifest.json',m)
  with self.assertRaisesRegex(ValueError,'identity/status changed'):self.issue()
 def test_universe_or_acquisition_rule_mismatch_rejected(self):
  self.plan['source']['universe_count']=48;self.evidence['retained_source']=copy.deepcopy(self.plan['source']);self.plan['evidence']['sha256']=digest(self.evidence)
  with self.assertRaisesRegex(ValueError,'request/universe'):self.issue()
 def test_primary_intent_and_real_host_readers_mandatory(self):
  self.primary['partial']=True
  with self.assertRaisesRegex(ValueError,'primary message'):self.issue()
 def test_ambiguous_remote_write_send_or_process_state_rejected(self):
  for key,value in [('original_processes_absent',False),('nov16_D1_datasets',1),('nov16_D1_parts',1),('result_notifications',1),('destination_histories_complete',False)]:
   old=copy.deepcopy(self.evidence);self.evidence[key]=value;self.plan['evidence']['sha256']=digest(self.evidence)
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'ambiguous or existing'):self.issue()
   self.evidence=old;self.plan['evidence']['sha256']=digest(old)
 def test_evidence_hash_and_source_commit_pinned(self):
  self.evidence['active_revision']=3
  with self.assertRaisesRegex(ValueError,'evidence bytes'):self.issue()
 def test_source_and_database_change_refused(self):
  ref=self.issue();self.source='d'*40
  with self.assertRaisesRegex(ValueError,'contract mismatch'):d.verify(self.repo,ref)
 def test_approval_not_widened_to_other_day(self):
  self.plan['target_date']='2026-11-17'
  with self.assertRaisesRegex(ValueError,'one original'):self.issue()
 def test_ttl_and_execution_day_enforced(self):
  ref=self.issue();self.time+=datetime.timedelta(hours=1)
  with self.assertRaisesRegex(ValueError,'expired'):d.verify(self.repo,ref)
 def test_claim_preserves_exact_original_bytes_and_1928_record(self):
  before=(self.rt/'daily-latest.json').read_bytes();ref=self.issue();claim=self.claim(ref);folder=(self.repo/claim['path']).parent
  self.assertFalse((self.rt/'daily.lock').exists());self.assertEqual((folder/'original-daily.lock').read_text(),d.ORIGINAL);self.assertEqual((folder/'original-result.json').read_bytes(),before);self.assertEqual((self.rt/'daily-latest.json').read_bytes(),before);self.assertEqual(self.older.read_bytes(),self.older_bytes)
 def test_wrong_lock_owner_or_actual_pid_survivor_never_claims(self):
  ref=self.issue()
  with self.assertRaisesRegex(ValueError,'not proven absent'):self.claim(ref,processes_absent=lambda _:False)
  self.assertTrue((self.rt/'daily.lock').exists())
 def test_arbitration_and_normal_preflight_are_not_skipped(self):
  ref=self.issue()
  with self.assertRaisesRegex(ValueError,'normal preflight'):self.claim(ref,preflight=lambda:dict(ok=False))
  self.assertTrue((self.rt/'daily.lock').exists())
 def test_existing_activation_rejection_propagates_without_unlock(self):
  ref=self.issue()
  def reject(_):raise ValueError('SOURCE_ACCEPTANCE_NOT_UPGRADED')
  with self.assertRaisesRegex(ValueError,'SOURCE_ACCEPTANCE'):self.claim(ref,activation_validator=reject)
  self.assertTrue((self.rt/'daily.lock').exists())
 def test_same_contract_cannot_be_claimed_twice(self):
  ref=self.issue();self.claim(ref)
  with self.assertRaises((ValueError,FileExistsError)):self.claim(ref)
 def test_runtime_context_retains_real_observation_and_separate_target(self):
  _,_,ref=self.running();ctx=d.classify(self.repo,ref,as_of='2026-11-16',observed_at=self.time.isoformat());self.assertEqual(ctx['execution_date'],'2026-11-17');self.assertEqual(ctx['target_date'],'2026-11-16')
 def test_faked_observation_date_or_wrong_target_rejected(self):
  _,_,ref=self.running()
  for target,observed in [('2026-11-17',self.time.isoformat()),('2026-11-16','2026-11-16T13:30:00Z')]:
   with self.assertRaisesRegex(ValueError,'real delayed observation'):d.classify(self.repo,ref,as_of=target,observed_at=observed)
 def test_original_root_exit_or_pid_reuse_closes_context(self):
  _,_,ref=self.running()
  with patch.object(d,'process_identity',return_value=dict(alive=True,created_filetime=999)):
   with self.assertRaisesRegex(ValueError,'PID reused'):d.runtime_context(self.repo,ref)
 def test_finite_claim_expiry_does_not_fake_runtime_day(self):
  _,_,ref=self.running();self.time+=datetime.timedelta(hours=2);self.assertEqual(d.runtime_context(self.repo,ref)['target_date'],d.TARGET)
  self.time+=datetime.timedelta(days=1)
  with self.assertRaisesRegex(ValueError,'real execution day'):d.runtime_context(self.repo,ref)
 def test_newer_active_dataset_or_revision_refuses_publication(self):
  _,_,ref=self.running();ctx=d.runtime_context(self.repo,ref)
  good=dict(revision=2,dataset_id='SYNTHETIC-OLD-DATASET',manifest_json=json.dumps(dict(as_of='2026-11-13')));d.assert_publication_pointer(ctx,good)
  with self.assertRaisesRegex(ValueError,'watermark changed'):d.assert_publication_pointer(ctx,{**good,'revision':3})
  with self.assertRaisesRegex(ValueError,'regress or duplicate'):d.assert_publication_pointer(ctx,{**good,'manifest_json':json.dumps(dict(as_of='2026-11-17'))})
 def test_unstarted_contract_is_not_a_runtime_capability(self):
  ref=self.issue()
  with self.assertRaises(ValueError):d.runtime_context(self.repo,ref)


 def snapshot(self):
  _,_,reference=self.running()
  from weak_early_beta.new_a import monitor
  from weak_early_beta.new_a.pipeline import Pipeline
  from weak_early_beta.new_a.publication import build_snapshot
  from tests.test_new_a_connection import bar
  calendar=['2026-11-13','2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20','2026-11-24','2026-11-25'];seed=monitor.initial(calendar,['1111'],'SYNTHETIC_LATE');seed['cursor']=0;seed['previous']={'1111':bar()};pipeline=Pipeline(private_root(self.repo)/'daily-live.sqlite',seed,allow_live=True)
  try:
   result=pipeline.run(as_of=d.TARGET,observed_at=self.time.isoformat(),calendar=calendar,rows_by_day={calendar[0]:{'1111':bar()},d.TARGET:{'1111':bar(True)}},source_hash='a'*64,quality_verified=True,universe=['1111'],dry_run=False,recovery_reference=reference)
   snapshot=build_snapshot(result,allow_live=True,repo=self.repo)
  finally:pipeline.close()
  publication=dict(published=True,active_readback_verified=True,existing_owner_gate_verified=True,snapshot_sha256=snapshot['payload_sha256'],source_version='e'*64,revision=3,dataset_id='SYNTHETIC-LATE',as_of=d.TARGET,delayed_recovery=reference)
  root=private_root(self.repo);atomic_write(root/'snapshot.json',snapshot);atomic_write(root/'latest-run.json',dict(strategy='A_BASE',source_sha256='a'*64,source_version='e'*64,snapshot_sha256=snapshot['payload_sha256'],snapshot_file=str(root/'snapshot.json'),delayed_recovery=reference));atomic_write(root/'latest-publication.json',publication)
  return root,snapshot,publication
 def test_actual_pipeline_late_kind_never_fakes_live_or_observation(self):
  root,snapshot,publication=self.snapshot();self.assertEqual(snapshot['observation_kind'],d.KIND);self.assertEqual(snapshot['observed_at'],self.time.isoformat());self.assertEqual(snapshot['as_of'],d.TARGET);self.assertEqual(snapshot['new_live_signals'],0);self.assertEqual(snapshot['delayed_scheduled_signals'],1);self.assertFalse(any(e['is_new_live_signal'] for e in snapshot['events']));d.delivery_context(self.repo,snapshot,publication)
 def test_original_retained_packets_are_not_mutated_by_runtime_replay(self):
  _,_,reference=self.running();context=d.runtime_context(self.repo,reference);clone=Path(context['replay_directory']);self.assertNotEqual(clone,self.archive);self.assertEqual(file_sha(clone/'manifest.json'),file_sha(self.archive/'manifest.json'));(clone/'manifest.json').write_text('SYNTHETIC REPLAY STATUS');self.assertEqual(d.verify_retained(self.repo,self.plan['source']),self.archive)
 def test_late_notifications_use_same_outbox_and_never_send_twice(self):
  from weak_early_beta.new_a.notifications import notify_day,message
  root,snapshot,publication=self.snapshot();calls=[]
  def send(payload):calls.append(payload);return dict(confirmed=True,message_id='SYNTHETIC-'+str(len(calls)))
  sent=notify_day(root,date=d.TARGET,dry_run=False,report_url='https://synthetic.invalid/',transport=send);self.assertEqual(sent['external_sends'],2);self.assertEqual(len(calls),2);self.assertTrue(all(c['observation_kind']==d.KIND and c['observed_at']==self.time.isoformat() for c in calls));self.assertIn('delayed',message(calls[0],'https://synthetic.invalid/')['embeds'][0]['title']);notify_day(root,date=d.TARGET,dry_run=False,report_url='https://synthetic.invalid/',transport=send);self.assertEqual(len(calls),2)
 def test_late_uncertain_delivery_is_never_reset_or_resent(self):
  from weak_early_beta.new_a.notifications import notify_day
  root,snapshot,publication=self.snapshot();calls=[]
  def uncertain(payload):calls.append(payload);return dict(confirmed=False)
  with self.assertRaises(RuntimeError):notify_day(root,date=d.TARGET,dry_run=False,report_url='https://synthetic.invalid/',transport=uncertain)
  with self.assertRaisesRegex(ValueError,'unconfirmed'):notify_day(root,date=d.TARGET,dry_run=False,report_url='https://synthetic.invalid/',transport=uncertain)
  self.assertEqual(len(calls),1)
 def test_unrelated_or_realtime_event_cannot_be_delayed_delivery(self):
  root,snapshot,publication=self.snapshot();snapshot['events'][0]['session']='2026-11-13';snapshot['payload_sha256']=digest({k:v for k,v in snapshot.items() if k!='payload_sha256'})
  with self.assertRaisesRegex(ValueError,'reclassification'):d.delivery_context(self.repo,snapshot)
 def test_newer_pointer_after_publication_prevents_delayed_send(self):
  root,snapshot,publication=self.snapshot();context=d.delivery_context(self.repo,snapshot,publication);pointer=dict(revision=3,dataset_id=publication['dataset_id'],manifest_json=json.dumps(dict(as_of=d.TARGET,daily_snapshot_sha256=snapshot['payload_sha256'],source_version='e'*64)));d.assert_published_pointer(context,pointer,publication)
  with self.assertRaisesRegex(ValueError,'pointer changed'):d.assert_published_pointer(context,{**pointer,'revision':4},publication)
 def test_unstarted_or_dead_root_never_stages_delayed_delivery(self):
  from weak_early_beta.new_a.outbox import Outbox
  root,snapshot,publication=self.snapshot();box=Outbox(root/'test-outbox.sqlite')
  try:
   with patch.object(d,'process_identity',return_value=dict(alive=False,created_filetime=123456)):
    with self.assertRaisesRegex(ValueError,'root ended'):box.stage(snapshot,publication,existing_notifications_enabled=True)
   self.assertEqual(box.db.execute('SELECT COUNT(*) FROM new_a_delivery').fetchone()[0],0)
  finally:box.close()
 def test_regular_late_catchup_remains_ineligible_without_contract(self):
  from weak_early_beta.new_a.notifications import eligible
  self.assertEqual(eligible(dict(as_of=d.TARGET,observation_kind='CATCHUP_NOT_NEW',events=[dict(kind='WATCH_STARTED',session=d.TARGET,is_new_live_signal=False)])),[])


 def test_late_classification_preserves_the_existing_monitor_state_exactly(self):
  root,snapshot,publication=self.snapshot()
  from weak_early_beta.new_a import monitor
  from weak_early_beta.new_a.pipeline import Pipeline
  from tests.test_new_a_connection import bar
  calendar=['2026-11-13','2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20','2026-11-24','2026-11-25'];seed=monitor.initial(calendar,['1111'],'SYNTHETIC_LATE');seed['cursor']=0;seed['previous']={'1111':bar()};other=Pipeline(root/'synthetic-control.sqlite',seed,allow_live=True);actual=Pipeline(root/'daily-live.sqlite',seed,allow_live=True)
  try:
   result=other.run(as_of=d.TARGET,observed_at=self.time.isoformat(),calendar=calendar,rows_by_day={calendar[0]:{'1111':bar()},d.TARGET:{'1111':bar(True)}},source_hash='a'*64,quality_verified=True,universe=['1111'],dry_run=False)
   self.assertEqual(actual.export_current(),other.export_current());self.assertEqual(actual.observed_quotes(),other.observed_quotes());self.assertEqual(result['observation_kind'],'CATCHUP_NOT_NEW');self.assertEqual(result['new_live_signals'],0)
  finally:other.close();actual.close()
 def test_nov17_ordinary_session_remains_live_without_recovery_reference(self):
  root,snapshot,publication=self.snapshot()
  from weak_early_beta.new_a import monitor
  from weak_early_beta.new_a.pipeline import Pipeline
  from tests.test_new_a_connection import bar
  from types import SimpleNamespace
  import weak_early_beta.new_a.pipeline as module
  calendar=['2026-11-13','2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20','2026-11-24','2026-11-25'];seed=monitor.initial(calendar,['1111'],'SYNTHETIC_LATE');seed['cursor']=0;seed['previous']={'1111':bar()};pipeline=Pipeline(root/'daily-live.sqlite',seed,allow_live=True)
  real=datetime.datetime
  class Clock(real):
   @classmethod
   def now(cls,tz=None):return real(2026,11,17,8,tzinfo=datetime.timezone.utc).astimezone(tz)
  try:
   with patch.object(module,'datetime',SimpleNamespace(datetime=Clock,timezone=datetime.timezone,timedelta=datetime.timedelta)),patch.object(monitor,'datetime',Clock):
    result=pipeline.run(as_of='2026-11-17',observed_at='2026-11-17T08:00:00Z',calendar=calendar,rows_by_day={'2026-11-16':{'1111':bar(True),'2222':bar()},'2026-11-17':{'1111':bar(),'2222':bar(True)}},source_hash='b'*64,quality_verified=True,universe=['1111','2222'],dry_run=False)
   self.assertEqual(result['observation_kind'],'LIVE_OBSERVATION');self.assertEqual(result['new_live_signals'],1);self.assertNotIn('delayed_recovery',result);self.assertFalse(any(e.get('is_delayed_scheduled_signal') for e in result['events']))
  finally:pipeline.close()

if __name__=='__main__':unittest.main()
