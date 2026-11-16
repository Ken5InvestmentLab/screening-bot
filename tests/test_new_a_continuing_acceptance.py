"""Synthetic host/measurements and private temporary files only; no remote action."""
import copy
import datetime
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from weak_early_beta.new_a import continuing_acceptance as ca
from weak_early_beta.new_a.acceptance import validate_activation
from weak_early_beta.new_a.files import atomic_write, digest, file_sha, private_root, read
from weak_early_beta.new_a import run as daily_run
from weak_early_beta.new_a import cli as private_cli

class ContinuingAcceptance(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.repo=Path(self.tmp.name)
  self.time=datetime.datetime(2026,11,16,12,tzinfo=datetime.timezone.utc)
  self.source='c'*40
  for name,value in [('head',lambda _repo:self.source),('now',lambda:self.time)]:
   context=patch.object(ca,name,value);context.start();self.addCleanup(context.stop)
  self.pins={}
  for name in ca.AUTH_FILES:
   p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('// synthetic protected source');self.pins[name]=file_sha(p)
  self.config=self.repo/'weak-early-beta-gate/wrangler.jsonc'
  atomic_write(self.config,dict(name=ca.SERVICE,d1_databases=[dict(binding='CLOUD_DB',database_name='tentei-cloud-settings',database_id='00000000-0000-4000-8000-000000000001')]))
  self.target=ca.target(self.repo)
  self.activation=private_root(self.repo)/'activation.json'
  self.closed=dict(schema='NEW_A_OWNER_ACTIVATION_V1',strategy='A_BASE',active=False,external_actions_approved=False,owner_acceptance={},unrelated_setting='PRESERVE')
  atomic_write(self.activation,self.closed);self.before=self.activation.read_bytes()
  self.authority=dict(author_id='SYNTHETIC_OWNER',room_id='SYNTHETIC_ROOM')
  text='Synthetic owner authorizes ongoing New A daily operation and the distinct unmeasured evidence policy.'
  self.binding=dict(message_id='SYNTHETIC_PRIMARY',**self.authority,text_sha256=digest(text))
  self.primary=dict(partial=False,room_id=self.authority['room_id'],message=dict(message_id=self.binding['message_id'],author='user',author_id=self.authority['author_id'],channel='chatgpt',sent_at='2026-11-16T11:00:00Z',content=dict(text=text)))
  self.measurements={}
  for kind,paths in ca.PATHS.items():
   self.measurements[kind]=dict(schema='NEW_A_HOST_OBSERVED_MEASUREMENT_V1',kind=kind,source_commit=self.source,auth_source_hashes=self.pins,target=self.target,platform_signature_claimed=False,observed_at='2026-11-16T11:30:00Z',raw_receipt_sha256=digest('synthetic '+kind),authenticated_nonowner_observed=False,source_kind='EXISTING_LEGITIMATE_OWNER_SESSION' if kind=='owner' else 'NO_AUTH_NO_COOKIES',owner_identity_verified=kind=='owner',cookies_sent=False,authorization_sent=False,deployment_version_id='SYNTHETIC_INITIAL_VERSION',observations=[dict(path=p,status=200 if kind=='owner' else 302 if not p.startswith('/api/') and p!='/auth/check' else 401,private_gate=True) for p in sorted(paths)])
  self.plan=dict(scope=ca.SCOPE,decision='CONTINUE_UNTIL_REVOKED_OR_BOUND_SOURCE_CHANGED',strategy='A_BASE',virtual_only=True,nonowner_evidence_mode='OWNER_DECISION_UNMEASURED',source_commit=self.source,target=self.target,auth_source_hashes=self.pins,owner_message=self.binding,measurements={k:dict(id=k,sha256=digest(v)) for k,v in self.measurements.items()},management_not_after='2026-11-16T12:30:00Z',expected_activation_sha256=file_sha(self.activation))
  self.review=self.review_for(self.binding,'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED')
 def review_for(self,binding,decision):
  return dict(schema='NEW_A_HOST_OPERATOR_INTERPRETATION_V1',decision=decision,scope=ca.SCOPE,source_commit=self.plan['source_commit'],target=self.target,message_id=binding['message_id'],text_sha256=binding['text_sha256'],author_id=binding['author_id'],room_id=binding['room_id'],platform_signature_claimed=False)
 def issue(self):
  return ca.issue(self.repo,self.plan,primary_reader=lambda _id:copy.deepcopy(self.primary),measurement_reader=lambda kind:copy.deepcopy(self.measurements[kind]),decision_reader=lambda _:copy.deepcopy(self.review),authority=self.authority)
 def revocation_binding(self):
  self.primary['message']['content']['text']='Synthetic owner revokes continuing acceptance.'
  binding={**self.binding,'text_sha256':digest(self.primary['message']['content']['text'])}
  self.review=self.review_for(binding,'REVOKE_CONTINUING_ACCEPTANCE')
  return binding
 def ready(self):return dict(ok=True,head=self.source,repository=str(self.repo))
 def apply(self,issued):return ca.apply(self.repo,issued,preflight=self.ready)
 def test_issue_alone_never_activates(self):
  issued=self.issue();record=ca.validate_record(self.repo,issued['acceptance'])
  self.assertEqual(self.activation.read_bytes(),self.before);self.assertNotIn('expires_at',record);self.assertNotIn('run_date',record);self.assertFalse(record['nonowner_denied']);self.assertFalse(record['platform_signature_claimed'])
 def test_same_acceptance_valid_on_nov17_and_nov18_after_management_expiry(self):
  issued=self.issue();self.apply(issued);value=read(self.activation);after=self.activation.read_bytes()
  for day in [16,17,18]:
   self.time=datetime.datetime(2026,11,day,13,tzinfo=datetime.timezone.utc)
   self.assertIs(validate_activation(value,self.repo),value)
  self.assertEqual(self.activation.read_bytes(),after);self.assertEqual(value['unrelated_setting'],'PRESERVE')
  with self.assertRaisesRegex(ValueError,'expired'):self.apply(issued)
 def test_completed_apply_is_idempotent_without_another_replace(self):
  issued=self.issue();a=self.apply(issued);original=private_root(self.repo)/'continuing-acceptance/applications'/Path(issued['application_grant']['path']).stem/'original.json'
  self.assertEqual(original.read_bytes(),self.before)
  with patch.object(ca,'atomic_write',side_effect=AssertionError('MUST NOT WRITE')):
   b=self.apply(issued)
  self.assertTrue(b['same_operation_replay']);self.assertEqual(a['after_sha256'],b['after_sha256'])
 def test_runtime_never_claims_nonowner_was_measured(self):
  issued=self.issue();self.apply(issued);value=read(self.activation)
  for key in ['nonowner_denied','authenticated_nonowner_observed']:
   changed=copy.deepcopy(value);changed['owner_acceptance'][key]=True
   with self.assertRaisesRegex(ValueError,'unmeasured'):validate_activation(changed,self.repo)
 def test_issued_record_cannot_activate_by_manually_flipping_flags(self):
  issued=self.issue();record=ca.validate_record(self.repo,issued['acceptance'])
  evidence=dict(actual_owner_allowed=True,anonymous_denied=True,private_direct_paths_denied=True,existing_auth_unchanged=True,nonowner_denied=False,authenticated_nonowner_observed=False,auth_source_hashes=record['auth_source_hashes'],continuing_acceptance=issued['acceptance'])
  with self.assertRaisesRegex(ValueError,'application audit'):validate_activation({**self.closed,'active':True,'external_actions_approved':True,'owner_acceptance':evidence},self.repo)
  self.assertEqual(self.activation.read_bytes(),self.before)
 def test_unrecorded_activation_file_edit_invalidates_completed_acceptance(self):
  issued=self.issue();self.apply(issued);value=read(self.activation);value['unrelated_setting']='UNRECORDED_CHANGE';atomic_write(self.activation,value)
  with self.assertRaisesRegex(ValueError,'audit or activation changed'):validate_activation(value,self.repo)
 def test_active_and_external_false_remain_closed(self):
  issued=self.issue();self.apply(issued);value=read(self.activation)
  for key in ['active','external_actions_approved']:
   with self.assertRaisesRegex(ValueError,'activation'):validate_activation({**value,key:False},self.repo)
 def test_primary_reader_and_verified_owner_authority_are_required(self):
  with self.assertRaisesRegex(ValueError,'reader required'):ca.issue(self.repo,self.plan,primary_reader=None,measurement_reader=lambda k:self.measurements[k],decision_reader=lambda _:self.review,authority=self.authority)
  self.authority['author_id']='OTHER'
  with self.assertRaisesRegex(ValueError,'authority'):self.issue()
 def test_partial_wrong_deleted_and_changed_primary_rejected(self):
  for location,key,value in [('root','partial',True),('root','room_id','OTHER'),('message','author','aeon'),('message','author_id','OTHER'),('message','channel','slack'),('message','message_id','OTHER'),('message','deleted_at','now'),('content','text','CHANGED')]:
   old=copy.deepcopy(self.primary);obj=self.primary if location=='root' else self.primary['message'] if location=='message' else self.primary['message']['content'];obj[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.issue()
   self.primary=old
 def test_measured_owner_and_anonymous_and_direct_paths_stay_required(self):
  for kind in ca.PATHS:
   old=copy.deepcopy(self.measurements[kind]);self.measurements[kind]['observations']=[];self.plan['measurements'][kind]['sha256']=digest(self.measurements[kind])
   with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'routes'):self.issue()
   self.measurements[kind]=old;self.plan['measurements'][kind]['sha256']=digest(old)
 def test_wrong_measurement_version_target_or_identity_rejected(self):
  for key,value in [('source_commit','d'*40),('target',{}),('auth_source_hashes',{}),('platform_signature_claimed',True),('authenticated_nonowner_observed',True),('synthetic',True),('observed_at','2030-01-01T00:00:00Z')]:
   old=copy.deepcopy(self.measurements['owner']);self.measurements['owner'][key]=value;self.plan['measurements']['owner']['sha256']=digest(self.measurements['owner'])
   with self.subTest(key=key),self.assertRaises(ValueError):self.issue()
   self.measurements['owner']=old;self.plan['measurements']['owner']['sha256']=digest(old)
 def test_owner_denied_or_anonymous_allowed_never_accepted(self):
  for kind,status in [('owner',403),('anonymous',200),('direct',200)]:
   old=copy.deepcopy(self.measurements[kind]);self.measurements[kind]['observations'][0]['status']=status;self.plan['measurements'][kind]['sha256']=digest(self.measurements[kind])
   with self.subTest(kind=kind),self.assertRaises(ValueError):self.issue()
   self.measurements[kind]=old;self.plan['measurements'][kind]['sha256']=digest(old)
 def test_host_measurement_hash_must_match_actual_reader_result(self):
  self.measurements['owner']['deployment_version_id']='CHANGED_OBSERVATION'
  with self.assertRaisesRegex(ValueError,'actual host measurement changed'):self.issue()
 def test_source_change_stops_continuing_acceptance(self):
  issued=self.issue();self.apply(issued);self.source='d'*40
  with self.assertRaisesRegex(ValueError,'source or target'):validate_activation(read(self.activation),self.repo)
 def test_auth_source_change_stops_continuing_acceptance(self):
  issued=self.issue();self.apply(issued);(self.repo/next(iter(ca.AUTH_FILES))).write_text('CHANGED')
  with self.assertRaisesRegex(ValueError,'source changed'):validate_activation(read(self.activation),self.repo)
 def test_database_or_worker_change_stops_acceptance(self):
  issued=self.issue();self.apply(issued);config=read(self.config);config['d1_databases'][0]['database_id']='00000000-0000-4000-8000-000000000002';atomic_write(self.config,config)
  with self.assertRaisesRegex(ValueError,'target changed'):validate_activation(read(self.activation),self.repo)
  config['name']='OTHER_WORKER';atomic_write(self.config,config)
  with self.assertRaisesRegex(ValueError,'unexpected service'):validate_activation(read(self.activation),self.repo)
 def test_new_deployment_identifier_is_not_a_daily_lifetime_condition(self):
  issued=self.issue();self.apply(issued);value=read(self.activation);value['latest_normal_code_only_deployment']='SYNTHETIC_NEW_VERSION_SAME_CODE'
  self.time=datetime.datetime(2026,11,17,12,tzinfo=datetime.timezone.utc);validate_activation(value,self.repo)
  self.assertEqual(ca.validate_record(self.repo,issued['acceptance'])['measurements']['owner']['deployment_version_id'],'SYNTHETIC_INITIAL_VERSION')
 def test_wrong_scope_or_dated_A_plan_cannot_issue_B(self):
  for key,value in [('scope','OTHER'),('decision','ONCE'),('strategy','OLD_CLOUD'),('virtual_only',False),('nonowner_evidence_mode','MEASURED'),('run_date','2026-11-16'),('expires_at','2026-11-17T00:00:00Z')]:
   old=copy.deepcopy(self.plan);self.plan[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.issue()
   self.plan=old
 def test_expired_or_overbroad_management_authority_rejected(self):
  for until in ['2026-11-16T11:00:00Z','2026-11-16T14:00:00Z']:
   self.plan['management_not_after']=until
   with self.assertRaisesRegex(ValueError,'management authority'):self.issue()
  self.assertEqual(self.activation.read_bytes(),self.before)
 def test_record_tamper_and_outside_private_reference_rejected(self):
  issued=self.issue();p=self.repo/issued['acceptance']['path'];p.write_text('{}')
  with self.assertRaisesRegex(ValueError,'reference mismatch'):ca.validate_record(self.repo,issued['acceptance'])
  p=self.repo/'public.json';atomic_write(p,{})
  with self.assertRaisesRegex(ValueError,'reference mismatch'):ca.validate_record(self.repo,dict(path='public.json',sha256=file_sha(p)))
 def test_other_acceptance_flags_remain_mandatory(self):
  issued=self.issue();self.apply(issued);value=read(self.activation)
  for key in ['actual_owner_allowed','anonymous_denied','private_direct_paths_denied','existing_auth_unchanged']:
   changed=copy.deepcopy(value);changed['owner_acceptance'][key]=False
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'incomplete'):validate_activation(changed,self.repo)
 def test_grant_does_not_apply_to_a_different_acceptance(self):
  a=self.issue();self.time+=datetime.timedelta(seconds=1);b=self.issue()
  with self.assertRaisesRegex(ValueError,'mismatched'):ca.apply(self.repo,dict(acceptance=b['acceptance'],application_grant=a['application_grant']),preflight=self.ready)
 def test_real_owner_revocation_stops_all_future_validation(self):
  issued=self.issue();self.apply(issued);binding=self.revocation_binding()
  ca.revoke(self.repo,issued['acceptance'],binding,primary_reader=lambda _:self.primary,decision_reader=lambda _:self.review,authority=self.authority)
  with self.assertRaisesRegex(ValueError,'revoked'):validate_activation(read(self.activation),self.repo)
 def test_another_authority_cannot_revoke(self):
  issued=self.issue()
  with self.assertRaisesRegex(ValueError,'original owner'):ca.revoke(self.repo,issued['acceptance'],self.binding,primary_reader=lambda _:self.primary,decision_reader=lambda _:self.review,authority=dict(author_id='OTHER',room_id=self.authority['room_id']))
 def test_revocation_still_possible_after_code_changed(self):
  issued=self.issue();self.source='d'*40
  binding=self.revocation_binding();ca.revoke(self.repo,issued['acceptance'],binding,primary_reader=lambda _:self.primary,decision_reader=lambda _:self.review,authority=self.authority)
  self.source='c'*40
  with self.assertRaisesRegex(ValueError,'revoked'):ca.validate_record(self.repo,issued['acceptance'])
 def test_false_normal_preflight_never_applies(self):
  issued=self.issue()
  with self.assertRaisesRegex(ValueError,'not ready'):ca.apply(self.repo,issued,preflight=lambda:dict(ok=False))
  self.assertEqual(self.activation.read_bytes(),self.before)
 def test_existing_daily_or_entry_or_reminder_lock_is_preserved(self):
  for relative in ['.cache/weak_early_beta/daily_runtime/task-entry.lock','.cache/weak_early_beta/daily_runtime/daily.lock','.cache/weak_early_beta/exit-reminder.lock','weak_early_beta/state/exit-reminder.lock']:
   issued=self.issue();p=self.repo/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('OTHER_OWNER')
   with self.subTest(relative=relative),self.assertRaises((FileExistsError,ValueError)):self.apply(issued)
   self.assertEqual(p.read_text(),'OTHER_OWNER');self.assertEqual(self.activation.read_bytes(),self.before);p.unlink()
 def test_cas_never_overwrites_a_concurrent_change(self):
  issued=self.issue()
  def changed():self.activation.write_text('{}');return self.ready()
  with self.assertRaisesRegex(ValueError,'baseline changed'):ca.apply(self.repo,issued,preflight=changed)
  self.assertEqual(self.activation.read_text(),'{}')
 def test_management_expiry_during_preflight_prevents_replace(self):
  issued=self.issue()
  def late():self.time+=datetime.timedelta(hours=2);return self.ready()
  with self.assertRaisesRegex(ValueError,'expired before replace'):ca.apply(self.repo,issued,preflight=late)
  self.assertEqual(self.activation.read_bytes(),self.before)
 def test_ambiguous_replace_keeps_claim_and_never_retries(self):
  issued=self.issue()
  with patch.object(ca,'atomic_write',side_effect=lambda *_:None):
   with self.assertRaisesRegex(ValueError,'ambiguous'):self.apply(issued)
  with self.assertRaises(FileExistsError):self.apply(issued)
  self.assertEqual(self.activation.read_bytes(),self.before)
 def test_concurrent_apply_uses_observed_entry_barrier(self):
  issued=self.issue();entered=threading.Event();release=threading.Event()
  def checking():entered.set();self.assertTrue(release.wait(10));return self.ready()
  with ThreadPoolExecutor(max_workers=1) as executor:
   first=executor.submit(ca.apply,self.repo,issued,preflight=checking)
   self.assertTrue(entered.wait(10))
   try:
    with self.assertRaises(FileExistsError):self.apply(issued)
   finally:release.set()
   self.assertFalse(first.result(timeout=10)['same_operation_replay'])
  validate_activation(read(self.activation),self.repo)
 def test_legacy_measured_acceptance_still_works(self):
  evidence={k:True for k in ['actual_owner_allowed','anonymous_denied','nonowner_denied','private_direct_paths_denied','existing_auth_unchanged']};evidence['auth_source_hashes']=self.pins
  validate_activation({**self.closed,'active':True,'external_actions_approved':True,'owner_acceptance':evidence},self.repo)
 def test_A_unmeasured_evidence_is_not_a_B_record(self):
  evidence=dict(actual_owner_allowed=True,anonymous_denied=True,private_direct_paths_denied=True,existing_auth_unchanged=True,nonowner_denied=False,owner_decision={'path':'DATED_A'},auth_source_hashes=self.pins)
  with self.assertRaisesRegex(ValueError,'incomplete'):validate_activation({**self.closed,'active':True,'external_actions_approved':True,'owner_acceptance':evidence},self.repo)
 def test_once_only_or_another_target_intent_cannot_authorize_continuing(self):
  for key,value in [('decision','ONCE_ONLY_NOV16'),('target',{}),('text_sha256','a'*64),('source_commit','d'*40),('platform_signature_claimed',True)]:
   old=copy.deepcopy(self.review);self.review[key]=value
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'intent or scope'):self.issue()
   self.review=old
 def test_continuing_intent_cannot_be_misused_as_revocation(self):
  issued=self.issue()
  with self.assertRaisesRegex(ValueError,'intent or scope'):ca.revoke(self.repo,issued['acceptance'],self.binding,primary_reader=lambda _:self.primary,decision_reader=lambda _:self.review,authority=self.authority)
 def bootstrap_for_real_daily_guard(self):
  actual_source=Path(daily_run.__file__).parent;synthetic_source=self.repo/'weak_early_beta/new_a';synthetic_source.mkdir(parents=True,exist_ok=True)
  hashes={}
  for name in ['features.py','monitor.py']:
   p=synthetic_source/name;p.write_bytes((actual_source/name).read_bytes());hashes[name]=file_sha(p)
  folder=private_root(self.repo)/'bootstrap';folder.mkdir(exist_ok=True);files={}
  for name in ['seed','calendar','history_input','presentation','quotes']:
   p=folder/(name+'.json');atomic_write(p,[] if name!='seed' else {});files[name]=dict(path=p.name,sha256=file_sha(p))
  atomic_write(folder/'manifest.json',dict(schema='NEW_A_PRIVATE_BOOTSTRAP_V1',strategy='A_BASE',files=files,code_hashes=hashes))
  return synthetic_source/'run.py'
 def test_actual_daily_entry_accepts_nov17_before_source_boundary_without_recovery(self):
  issued=self.issue();self.apply(issued);run_file=self.bootstrap_for_real_daily_guard();self.time=datetime.datetime(2026,11,17,12,tzinfo=datetime.timezone.utc);called=[]
  def source(args):called.append(args);raise RuntimeError('SYNTHETIC_SOURCE_BOUNDARY_NO_FETCH')
  with patch.object(daily_run,'__file__',str(run_file)):
   with self.assertRaisesRegex(RuntimeError,'SOURCE_BOUNDARY'):daily_run.command_daily(SimpleNamespace(new_a_isolated=False,as_of='2026-11-17'),source_provider=source,root=private_root(self.repo))
  self.assertEqual(len(called),1);self.assertFalse((private_root(self.repo)/'daily-live.sqlite').exists())
 def test_revoked_actual_daily_entry_never_calls_source(self):
  issued=self.issue();self.apply(issued);run_file=self.bootstrap_for_real_daily_guard();binding=self.revocation_binding();ca.revoke(self.repo,issued['acceptance'],binding,primary_reader=lambda _:self.primary,decision_reader=lambda _:self.review,authority=self.authority)
  with patch.object(daily_run,'__file__',str(run_file)):
   with self.assertRaisesRegex(ValueError,'revoked'):daily_run.command_daily(SimpleNamespace(new_a_isolated=False),source_provider=lambda _:self.fail('MUST NOT FETCH'),root=private_root(self.repo))
 def test_revoked_real_remote_publish_and_notify_never_construct_external_boundary(self):
  issued=self.issue();self.apply(issued);binding=self.revocation_binding();ca.revoke(self.repo,issued['acceptance'],binding,primary_reader=lambda _:self.primary,decision_reader=lambda _:self.review,authority=self.authority)
  with patch.object(private_cli,'ROOT',self.repo),patch.object(private_cli,'WranglerD1',side_effect=AssertionError('MUST NOT OPEN REMOTE D1')),patch.object(private_cli,'notify_day',side_effect=AssertionError('MUST NOT NOTIFY')):
   for argv in [['publish','--remote'],['notify','--date','2026-11-17']]:
    with self.subTest(argv=argv),self.assertRaisesRegex(ValueError,'revoked'):private_cli.main(argv)


 def upgrade_candidate(self):
  original=self.issue();self.apply(original);previous=original['acceptance'];before=self.activation.read_bytes();self.source='d'*40;self.plan['source_commit']=self.source;self.plan['expected_activation_sha256']=file_sha(self.activation)
  for kind,measurement in self.measurements.items():measurement['source_commit']=self.source
  self.plan['measurements']={k:dict(id=k,sha256=digest(v)) for k,v in self.measurements.items()};self.review=self.review_for(self.binding,'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED');return previous,before,self.issue()
 def test_audited_source_upgrade_keeps_active_and_continuing_nov17(self):
  previous,before,issued=self.upgrade_candidate();applied=ca.apply(self.repo,issued,preflight=self.ready,previous_acceptance=previous)
  value=read(self.activation);self.assertTrue(value['active']);self.assertTrue(value['external_actions_approved']);self.assertFalse(value['owner_acceptance']['nonowner_denied']);self.assertEqual(value['unrelated_setting'],'PRESERVE')
  self.assertEqual((ca.root(self.repo)/'applications'/Path(issued['application_grant']['path']).stem/'original.json').read_bytes(),before);self.assertEqual(applied['previous_acceptance'],previous)
  self.time=datetime.datetime(2026,11,17,8,tzinfo=datetime.timezone.utc);self.assertIs(validate_activation(value,self.repo),value)
 def test_source_upgrade_requires_exact_old_completed_audit(self):
  previous,before,issued=self.upgrade_candidate();other=copy.deepcopy(previous);other['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'upgrade baseline'):ca.apply(self.repo,issued,preflight=self.ready,previous_acceptance=other)
  self.assertEqual(self.activation.read_bytes(),before)
 def test_source_upgrade_does_not_revive_revoked_predecessor(self):
  previous,before,issued=self.upgrade_candidate();oldpath,_=ca.load_reference(self.repo,previous,'records');ca.immutable(ca.root(self.repo)/'revocations'/(oldpath.stem+'.json'),dict(synthetic=True))
  with self.assertRaisesRegex(ValueError,'revoked'):ca.apply(self.repo,issued,preflight=self.ready,previous_acceptance=previous)
  self.assertEqual(self.activation.read_bytes(),before)
 def test_source_upgrade_rejects_changed_authentication_sources(self):
  previous,before,issued=self.upgrade_candidate();p=self.repo/next(iter(ca.AUTH_FILES));p.write_text('// CHANGED')
  with self.assertRaisesRegex(ValueError,'authentication source'):ca.apply(self.repo,issued,preflight=self.ready,previous_acceptance=previous)
  self.assertEqual(self.activation.read_bytes(),before)
 def test_source_upgrade_holds_existing_entry_but_never_takes_other_owner(self):
  previous,before,issued=self.upgrade_candidate();runtime=self.repo/'.cache/weak_early_beta/daily_runtime';(runtime/'task-entry.lock').write_text('SYNTHETIC-ENTRY')
  with self.assertRaisesRegex(ValueError,'arbitration'):ca.apply(self.repo,issued,preflight=self.ready,previous_acceptance=previous,arbitration_owner='WRONG')
  ca.apply(self.repo,issued,preflight=self.ready,previous_acceptance=previous,arbitration_owner='SYNTHETIC-ENTRY');self.assertEqual((runtime/'task-entry.lock').read_text(),'SYNTHETIC-ENTRY');validate_activation(read(self.activation),self.repo)
 def test_revoked_predecessor_invalidates_upgraded_chain(self):
  previous,before,issued=self.upgrade_candidate();ca.apply(self.repo,issued,preflight=self.ready,previous_acceptance=previous);oldpath,_=ca.load_reference(self.repo,previous,'records');ca.immutable(ca.root(self.repo)/'revocations'/(oldpath.stem+'.json'),dict(synthetic=True))
  with self.assertRaisesRegex(ValueError,'revoked'):validate_activation(read(self.activation),self.repo)

if __name__=='__main__':unittest.main()
