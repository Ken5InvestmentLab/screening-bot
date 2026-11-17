"""Synthetic private receipts only; no live state, credential or external work."""
import copy,datetime,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_new_a_native_recovery as fixtures
from weak_early_beta.new_a import native_admission_context as n
from weak_early_beta.new_a.files import read,file_sha

class AdmissionContextTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.NativeRecoveryTests('test_native_source_failure_can_replay_without_side_effects');self.f.setUp();self.addCleanup(self.f.doCleanups)
  f=self.f;self.repo=f.repo;self.rt=f.runtime;self.time=datetime.datetime(2026,11,17,15,10,tzinfo=datetime.timezone.utc);self.head='f'*40;self.pid=45678;self.start=self.time.isoformat().replace('+00:00','Z')
  self.birth=116444736000000000+int((self.time-datetime.timedelta(seconds=1)).timestamp()*10000000)
  for obj,name,value in [(n.d,'now',lambda:self.time),(n.d,'head',lambda _:self.head),(n.d,'runtime',lambda _:self.rt),(n.d,'process_identity',lambda _:dict(alive=True,created_filetime=self.birth)),(n,'require_accepted',lambda _:None)]:
   p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
  f.write(self.repo/'worker.tmp',{})
  (self.repo/'weak-early-beta-gate').mkdir();f.write(self.repo/'weak-early-beta-gate/wrangler.jsonc',{'name':'tentei-kyokuchi-cloud','d1_databases':[{'binding':'CLOUD_DB','database_name':'tentei-cloud-settings','database_id':'TEST_ONLY_DB'}]})
  f.write(f.private/'activation.json',{'TEST_ONLY':True});source=f.run_inspect();self.source=source
  self.original_input=self.rt/'recovery-input-2026-11-17T080024610Z.json';f.write(self.original_input,f.prior)
  self.reservation=self.rt/'recovery-2026-11-17T080024610Z.json';f.write(self.reservation,{'invocation':'TEST_ONLY_OLD_ENTRY','priorStartedAt':f.start})
  stopped=self.rt/'daily-2026-11-17T12-42-59-478Z';stopped.mkdir();f.write(stopped/'result.json',{'TEST_ONLY_STOPPED':True})
  evidence_dir=f.archive/'jpx-evidence';evidence_dir.mkdir();(evidence_dir/'fixture.json').write_text('SYNTHETIC_PUBLIC_SOURCE_RECEIPT')
  proof={'original_run_id':f.start,'stopped_run_id':'2026-11-17T12:42:59.478Z','original_input':str(self.original_input),'original_input_sha256':file_sha(self.original_input),'reservation_sha256':file_sha(self.reservation),'original_result_sha256':file_sha(f.folder/'result.json'),'stopped_result_sha256':file_sha(stopped/'result.json')}
  self.operation=self.rt/'native-admission-continuations'/('c'*64);self.operation.mkdir(parents=True);self.record_path=self.operation/'record.json'
  self.record={'schema':'CLOUD_NATIVE_ADMISSION_CONTINUATION_V1','service':'tentei-kyokuchi-cloud','strategy':'A_BASE','date':n.TARGET,'execution_date':n.EXECUTION,'head':self.head,'target':n.d.target(self.repo),'repo':str(self.repo),'runtime':str(self.rt),'proof':proof,'source':source,'activation_sha256':file_sha(f.private/'activation.json'),'platform_signature_claimed':False,'automatic_retry_counter_reset':False,'expires_at':(self.time+datetime.timedelta(minutes=20)).isoformat(),'external':{'at':(self.time-datetime.timedelta(seconds=5)).isoformat(),'d1':{'active':[{'as_of':'2026-11-16','revision':3,'dataset_id':'a-'+'d'*24}]}}}
  f.write(self.record_path,self.record)
  self.claim_path=self.rt/('native-admission-once-'+proof['original_input_sha256']+'.json');claim={'schema':'CLOUD_NATIVE_ADMISSION_ONCE_V1','record':'c'*64,'invocation':'TEST_ONLY_NEW_ENTRY','original_run_id':f.start};f.write(self.claim_path,claim)
  self.consumed=Path(str(self.claim_path)+'.consumed');f.write(self.consumed,{**claim,'schema':'CLOUD_NATIVE_ADMISSION_CONSUMED_V1','root_pid':self.pid,'new_run_id':self.start,'record_file':str(self.record_path),'record_file_sha256':file_sha(self.record_path)})
  self.running={'identity':'WEAK_EARLY_CLOUD_DAILY_V1','startedAt':self.start,'pid':self.pid,'date':n.TARGET,'executionDate':n.EXECUTION,'originalRunId':f.start,'ok':False,'stage':'detection'}
  folder=self.rt/('daily-'+self.start.replace(':','-').replace('.','-'));folder.mkdir();f.write(folder/'invoked.json',{**self.running,'identity':'CLOUD_RUNNER_INVOKED_V1'});f.write(self.rt/'daily-latest.json',self.running);(self.rt/'daily.lock').write_text(self.start)
 def begin(self):return n.begin(self.repo,self.consumed,root_pid=self.pid,started_at=self.start)
 def change_record(self,**delta):
  r=read(self.record_path);r.update(delta);self.f.write(self.record_path,r);c=read(self.consumed);c['record_file_sha256']=file_sha(self.record_path);self.f.write(self.consumed,c)
 def test_real_target_and_execution_dates_remain_distinct_and_originals_unchanged(self):
  before={str(p):file_sha(p) for p in [self.original_input,self.reservation,self.f.folder/'result.json',self.f.archive/'manifest.json',self.f.packet]}
  reference=self.begin();context=n.d.runtime_context(self.repo,reference)
  self.assertEqual(reference['kind'],n.KIND);self.assertEqual(context['target_date'],'2026-11-17');self.assertEqual(context['execution_date'],'2026-11-18')
  self.assertEqual(n.d.classify(self.repo,reference,as_of=n.TARGET,observed_at=self.time.isoformat())['target_date'],n.TARGET)
  self.assertEqual(before,{p:file_sha(Path(p)) for p in before});self.assertTrue((Path(context['replay_directory'])/'jpx-evidence/fixture.json').is_file())
  with self.assertRaises(ValueError):n.d.classify(self.repo,reference,as_of=n.TARGET,observed_at='2026-11-17T12:00:00Z')
 def test_begin_is_once_and_never_reuses_a_partial_replay(self):
  self.begin()
  with self.assertRaises(FileExistsError):self.begin()
 def test_wrong_source_target_execution_or_activation_is_rejected(self):
  for delta in [{'head':'e'*40},{'date':'2026-11-16'},{'execution_date':'2026-11-19'},{'activation_sha256':'0'*64},{'repo':str(self.repo.parent)}]:
   with self.subTest(delta=delta):
    old=self.record_path.read_bytes();oldc=self.consumed.read_bytes();self.change_record(**delta)
    with self.assertRaises(ValueError):self.begin()
    self.record_path.write_bytes(old);self.consumed.write_bytes(oldc)
 def test_reused_or_dead_pid_or_wrong_lock_is_rejected(self):
  reference=self.begin()
  for identity in [dict(alive=False,created_filetime=self.birth),dict(alive=True,created_filetime=self.birth+1)]:
   with patch.object(n.d,'process_identity',return_value=identity):
    with self.assertRaises(ValueError):n.runtime_context(self.repo,reference)
  (self.rt/'daily.lock').write_text('OTHER_OWNER')
  with self.assertRaises(ValueError):n.runtime_context(self.repo,reference)
 def test_next_actual_execution_day_rejected_without_clock_faking(self):
  reference=self.begin();self.time+=datetime.timedelta(days=1)
  with self.assertRaises(ValueError):n.runtime_context(self.repo,reference)
 def test_revised_original_claim_or_record_hash_rejected(self):
  reference=self.begin();self.reservation.write_text('{}')
  with self.assertRaises(ValueError):n.runtime_context(self.repo,reference)
 def test_changed_packet_before_start_rejected(self):
  self.f.packet.write_bytes(b'CORRUPT')
  with self.assertRaises(ValueError):self.begin()
 def test_expired_start_grant_rejected_but_running_context_uses_real_day_and_pid(self):
  reference=self.begin();self.time+=datetime.timedelta(minutes=25)
  self.assertEqual(n.runtime_context(self.repo,reference)['target_date'],n.TARGET)
  with self.assertRaises(ValueError):self.begin()
 def test_publication_never_regresses_or_ignores_revision(self):
  context=n.runtime_context(self.repo,self.begin());p={'revision':3,'dataset_id':'a-'+'d'*24,'manifest_json':json.dumps({'as_of':'2026-11-16'})};n.d.assert_publication_pointer(context,p)
  for changed in [{**p,'revision':4},{**p,'manifest_json':json.dumps({'as_of':'2026-11-17'})},{**p,'manifest_json':json.dumps({'as_of':'2026-11-18'})}]:
   with self.assertRaises(ValueError):n.d.assert_publication_pointer(context,changed)
 def test_legacy_contract_constants_are_not_repurposed(self):
  self.assertEqual((n.d.TARGET,n.d.EXECUTION,n.d.ORIGINAL),('2026-11-16','2026-11-17','2026-11-16T13:28:10.435Z'))
 def test_real_pipeline_snapshot_and_delivery_validation_keep_actual_observation(self):
  from weak_early_beta.new_a import monitor
  from weak_early_beta.new_a.pipeline import Pipeline
  from weak_early_beta.new_a.publication import build_snapshot
  from tests.test_new_a_connection import bar
  dates=[];day=datetime.date(2026,11,17)
  while len(dates)<80:
   if day.weekday()<5:dates.append(day.isoformat())
   day-=datetime.timedelta(days=1)
  dates.sort();seed=monitor.initial(dates,['1111'],'SYNTHETIC_ONLY');seed['cursor']=78;seed['previous']={'1111':bar()}
  self.f.db.unlink();pipeline=Pipeline(self.f.db,seed,allow_live=True);self.addCleanup(pipeline.close)
  reference=self.begin()
  result=pipeline.run(as_of=n.TARGET,observed_at=self.time.isoformat(),calendar=dates,rows_by_day={dates[-2]:{'1111':bar()},dates[-1]:{'1111':bar(True)}},source_hash='a'*64,quality_verified=True,universe=['1111'],dry_run=False,recovery_reference=reference)
  self.assertEqual(result['new_live_signals'],0);self.assertEqual(result['delayed_scheduled_signals'],1);self.assertEqual(result['observed_at'],self.time.isoformat())
  snapshot=build_snapshot(result,allow_live=True,repo=self.repo);context=n.d.delivery_context(self.repo,snapshot)
  self.assertEqual(context['target_date'],n.TARGET);self.assertTrue(all(e['is_new_live_signal'] is False for e in snapshot['events']));self.assertEqual(snapshot['events'][0]['session'],n.TARGET)

if __name__=='__main__':unittest.main()
