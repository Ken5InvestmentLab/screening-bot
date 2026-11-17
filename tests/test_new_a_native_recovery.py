import copy,hashlib,json,sqlite3,tempfile,unittest,sys,subprocess
from contextlib import closing
from pathlib import Path
from weak_early_beta.new_a.native_recovery import inspect,NATIVE_EXIT
class NativeRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.repo=Path(self.temp.name);self.runtime=self.repo/'runtime';self.runtime.mkdir();self.date='2026-11-17';self.start='2026-11-17T08:00:24.610Z'
  self.folder=self.runtime/('daily-'+self.start.replace(':','-').replace('.','-'));self.folder.mkdir();self.archive=self.folder/'acquisition-1';self.archive.mkdir()
  self.prior={'identity':'WEAK_EARLY_CLOUD_DAILY_V1','pid':123456,'date':self.date,'startedAt':self.start,'completedAt':'2026-11-17T09:36:28Z','ok':False,'stage':'detection','new_a':{'entry':'new-a-verified-daily-v1'},'acquisitionEvidence':[{'attempt':1,'directory':str(self.archive)}]}
  self.write(self.runtime/'daily-latest.json',self.prior)
  self.write(self.folder/'result.json',self.prior)
  self.write(self.folder/'invoked.json',{'identity':'CLOUD_RUNNER_INVOKED_V1','pid':self.prior['pid'],'date':self.date,'startedAt':self.start})
  self.child=self.folder/'detect-1.process.json';self.write(self.child,{'identity':'CLOUD_CHILD_PROCESS_V1','status':'exited','pid':987654,'completedAt':'2026-11-17T09:36:23Z','code':NATIVE_EXIT})
  (self.folder/'detect-1.stdout').write_text('');(self.folder/'detect-1.stderr').write_text(json.dumps({'identity':'CLOUD_DAILY_PHASE_V1','stage':'corporate-action-normalization','event':'started'})+'\n')
  cache=self.repo/'.cache/weak_early_beta';cache.mkdir(parents=True);self.source=cache/'tse_daily.csv';self.source.write_text('synthetic preserved source\n');self.sha=hashlib.sha256(self.source.read_bytes()).hexdigest();self.write(self.source.with_suffix('.source-quality.json'),{'identity':'CLOUD_SOURCE_QUALITY_V1','daily_sha256':self.sha})
  self.manifest=self.archive/'manifest.json';self.write(self.manifest,{'identity':'CLOUD_ACQUISITION_V1','status':'acquiring','requests':1,'context':{'date':self.date,'previousSourceSha256':self.sha,'tickers':['1234.T'],'period':'5y'}})
  request={'kind':'batch','tickers':['1234.T']};key=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()[:20];self.packet=self.archive/f'00001-{key}.pkl';self.packet.write_bytes(b'synthetic bytes; not deserialized');self.receipt=self.packet.with_suffix('.json');self.write(self.receipt,{'request':request,'sha256':hashlib.sha256(self.packet.read_bytes()).hexdigest()})
  self.private=cache/'new-a-private';self.private.mkdir();self.db=self.private/'daily-live.sqlite'
  with closing(sqlite3.connect(self.db)) as c:c.executescript('CREATE TABLE runs(run_key TEXT);CREATE TABLE symbol_days(day TEXT);')
 def write(self,p,v):p.write_text(json.dumps(v),encoding='utf8')
 def run_inspect(self):return inspect(self.repo,self.runtime,self.prior,self.date,self.sha)
 def mutate(self,p,**kw):v=json.loads(p.read_text());v.update(kw);self.write(p,v)
 def assertRejected(self):
  with self.assertRaises(ValueError):self.run_inspect()
 def test_native_source_failure_can_replay_without_side_effects(self):
  before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.repo.rglob('*') if p.is_file()};a=self.run_inspect();b=self.run_inspect();self.assertEqual(a,b);self.assertFalse(a['network_fallback']);self.assertFalse(a['inspection_wrote_or_sent']);self.assertTrue(a['remote_readback_required']);self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.repo.rglob('*') if p.is_file()})
 def test_normal_python_failure_keeps_existing_cache_path(self):self.mutate(self.child,code=1);self.assertIsNone(self.run_inspect())
 def test_success_is_not_retried(self):self.prior['ok']=True;self.assertRejected()
 def test_still_running_is_not_retried(self):self.prior.pop('completedAt');self.assertRejected()
 def test_other_day_is_not_retried(self):self.prior['date']='2026-11-16';self.assertRejected()
 def test_latest_receipt_changed(self):self.mutate(self.runtime/'daily-latest.json',error='changed');self.assertRejected()
 def active_fixture(self):
  self.active_start='2026-11-17T12:42:59.478Z';self.active_pid=24680
  self.active_folder=self.runtime/('daily-'+self.active_start.replace(':','-').replace('.','-'));self.active_folder.mkdir()
  self.current={'identity':'WEAK_EARLY_CLOUD_DAILY_V1','pid':self.active_pid,'date':self.date,'startedAt':self.active_start,'ok':False,'stage':'detection','originalRunId':self.start}
  self.write(self.runtime/'daily-latest.json',self.current);self.write(self.active_folder/'result.json',self.current)
  self.write(self.active_folder/'invoked.json',{**self.current,'identity':'CLOUD_RUNNER_INVOKED_V1'})
  (self.runtime/'daily.lock').write_text(self.active_start,encoding='utf8')
  self.key='2026-11-17T080024610Z'
  self.write(self.runtime/f'recovery-{self.key}.json',{'invocation':'synthetic-invocation','priorStartedAt':self.start})
  self.write(self.runtime/f'recovery-input-{self.key}.json',self.prior)
 def inspect_active(self):return inspect(self.repo,self.runtime,self.prior,self.date,self.sha,active_run=(self.active_start,self.active_pid))
 def test_normal_runner_progress_replaces_latest_but_preserved_prior_stays_immutable(self):
  self.active_fixture();self.assertRejected()
  before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.repo.rglob('*') if p.is_file()}
  self.assertEqual(self.inspect_active()['requests'],1)
  self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.repo.rglob('*') if p.is_file()})
 def test_active_context_rejects_wrong_identity_date_stage_or_terminal_state(self):
  self.active_fixture()
  for update in [{'startedAt':self.start},{'pid':1},{'date':'2026-11-18'},{'ok':True},{'completedAt':'2026-11-17T13:00:00Z'},{'stage':'publish'},{'originalRunId':'other'},{'deployment':{}}]:
   with self.subTest(update=update):
    changed={**self.current,**update};self.write(self.runtime/'daily-latest.json',changed);self.write(self.active_folder/'result.json',changed)
    with self.assertRaises(ValueError):self.inspect_active()
 def test_active_context_rejects_lock_or_invoked_or_reservation_or_input_change(self):
  self.active_fixture()
  for file in [self.runtime/'daily.lock',self.active_folder/'invoked.json',self.runtime/f'recovery-{self.key}.json',self.runtime/f'recovery-input-{self.key}.json',self.active_folder/'result.json']:
   with self.subTest(file=file.name):
    original=file.read_bytes();file.write_text('{}',encoding='utf8')
    with self.assertRaises(ValueError):self.inspect_active()
    file.write_bytes(original)
 def test_active_context_rejects_detection_already_attempted(self):
  self.active_fixture();self.write(self.active_folder/'detect-1.process.json',{'code':1})
  with self.assertRaises(ValueError):self.inspect_active()
 def test_publication_or_send_ambiguity_is_not_retried(self):
  for key in ['deployment','notifications','notificationPreview','latestSession','selectorRows']:
   with self.subTest(key=key):
    self.prior[key]={};self.write(self.runtime/'daily-latest.json',self.prior);self.write(self.folder/'result.json',self.prior);self.assertRejected();self.prior.pop(key)
 def test_committed_pipeline_is_not_retried(self):
  with closing(sqlite3.connect(self.db)) as c:
   with c:c.execute('INSERT INTO runs VALUES (?)',(self.date+'|source|LIVE',))
  self.assertRejected()
 def test_advanced_symbol_day_is_not_retried(self):
  with closing(sqlite3.connect(self.db)) as c:
   with c:c.execute('INSERT INTO symbol_days VALUES (?)',(self.date,))
  self.assertRejected()
 def test_target_detection_receipt_is_not_retried(self):self.write(self.private/'latest-run.json',{'identity':'NEW_A_CLOUD_DAILY_V1','strategy':'A_BASE','entry':'new-a-verified-daily-v1','latest_session':self.date});self.assertRejected()
 def test_target_bundle_is_not_retried(self):(self.private/'runs'/self.date).mkdir(parents=True);self.assertRejected()
 def test_changed_packet_is_not_retried(self):self.packet.write_bytes(b'corrupt');self.assertRejected()
 def test_missing_packet_is_not_retried(self):self.packet.unlink();self.assertRejected()
 def test_changed_source_is_not_retried(self):self.source.write_text('changed');self.assertRejected()
 def test_changed_context_is_not_retried(self):v=json.loads(self.manifest.read_text());v['context']['date']='2026-11-16';self.write(self.manifest,v);self.assertRejected()
 def test_post_source_stage_is_not_retried(self):
  with (self.folder/'detect-1.stderr').open('a') as f:f.write(json.dumps({'identity':'CLOUD_DAILY_PHASE_V1','stage':'source-cache-write','event':'started'})+'\n')
  self.assertRejected()
 def test_ambiguous_source_output_is_not_retried(self):(self.folder/'detect-1.stdout').write_text('{}');self.assertRejected()
 def test_completed_archive_not_replayed_as_failed_source(self):self.mutate(self.manifest,status='cached');self.assertRejected()
 def test_outside_acquisition_is_not_retried(self):self.prior['acquisitionEvidence'][0]['directory']=str(self.runtime);self.write(self.runtime/'daily-latest.json',self.prior);self.write(self.folder/'result.json',self.prior);self.assertRejected()
 def test_existing_target_notification_is_not_retried(self):
  with closing(sqlite3.connect(self.private/'notification-outbox.sqlite')) as c:
   c.execute('CREATE TABLE new_a_delivery(payload_json TEXT)')
   with c:c.execute('INSERT INTO new_a_delivery VALUES (?)',(json.dumps({'strategy':'A_BASE','signal_date':self.date}),))
  self.assertRejected()
 def test_changed_original_terminal_record_is_not_retried(self):self.mutate(self.folder/'result.json',error='changed');self.assertRejected()
 def test_changed_original_invocation_is_not_retried(self):self.mutate(self.folder/'invoked.json',pid=1);self.assertRejected()
 def test_unrecognized_older_detection_receipt_is_not_retried(self):self.write(self.private/'latest-run.json',{'latest_session':'2026-11-16'});self.assertRejected()
 def test_valid_older_detection_receipt_is_preserved(self):self.write(self.private/'latest-run.json',{'identity':'NEW_A_CLOUD_DAILY_V1','strategy':'A_BASE','entry':'new-a-verified-daily-v1','latest_session':'2026-11-16'});self.assertEqual(self.run_inspect()['requests'],1)
 def test_unrecognized_outbox_is_not_retried(self):
  with closing(sqlite3.connect(self.private/'notification-outbox.sqlite')) as c:
   c.execute('CREATE TABLE new_a_delivery(payload_json TEXT)')
   with c:c.execute('INSERT INTO new_a_delivery VALUES (?)',(json.dumps({'unknown':True}),))
  self.assertRejected()
 def test_valid_older_outbox_is_preserved(self):
  with closing(sqlite3.connect(self.private/'notification-outbox.sqlite')) as c:
   c.execute('CREATE TABLE new_a_delivery(payload_json TEXT)')
   with c:c.execute('INSERT INTO new_a_delivery VALUES (?)',(json.dumps({'strategy':'A_BASE','signal_date':'2026-11-16'}),))
  self.assertEqual(self.run_inspect()['requests'],1)
 @unittest.skipUnless(sys.platform=='win32','real Windows native-exit injection')
 def test_actual_native_exit_retains_source_and_can_be_inspected_for_once_only_resume(self):
  source_before=self.source.read_bytes();packet_before=self.packet.read_bytes()
  # ExitProcess supplies the real Windows native status without corrupting
  # memory or involving any live service; only this disposable child exits.
  code='import ctypes,json,sys;print(json.dumps({"identity":"CLOUD_DAILY_PHASE_V1","stage":"corporate-action-normalization","event":"started"}),file=sys.stderr,flush=True);ctypes.windll.kernel32.ExitProcess(0xC0000005)'
  child=subprocess.Popen([sys.executable,'-B','-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  stdout,stderr=child.communicate(timeout=30)
  self.assertEqual(child.returncode,NATIVE_EXIT);self.assertEqual(stdout,b'')
  (self.folder/'detect-1.stderr').write_bytes(stderr)
  self.mutate(self.child,code=child.returncode,pid=child.pid)
  proof=self.run_inspect();self.assertEqual(proof['requests'],1);self.assertEqual(source_before,self.source.read_bytes());self.assertEqual(packet_before,self.packet.read_bytes())
if __name__=='__main__':unittest.main()
