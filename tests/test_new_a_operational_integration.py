"""Finite protocol integration using real local outbox/D1; all I/O synthetic."""
import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tests.test_new_a_connection as connection
import tests.test_new_a_release as release_tests
from weak_early_beta.new_a import operational_admission as op
from weak_early_beta.new_a.files import atomic_write,read,digest,file_sha,private_root,encode
from weak_early_beta.new_a.notifications import notify_day
from weak_early_beta.new_a.publisher import pointer,logical_manifest,publish_bundle
from weak_early_beta.new_a import cli

class FiniteDelivery(unittest.TestCase):
 def setUp(self):
  self.fixture=connection.Notifications();self.fixture.setUp();self.root=self.fixture.root;self.allowed=True;self.checks=0;self.sent=[]
  self.fixture.day=op.TARGET;self.fixture.snapshot['as_of']=op.TARGET;self.fixture.snapshot['events'][0]['session']=op.TARGET;self.fixture.save()
  publication=read(self.root/'latest-publication.json');publication.update(existing_owner_gate_verified=False,operational_gate_continuity_verified=True,owner_http_observed=False,operational_admission={'path':'synthetic','sha256':'a'*64});atomic_write(self.root/'latest-publication.json',publication)
 def tearDown(self):self.fixture.tearDown()
 def guard(self,repo,*,date,**kwargs):
  self.checks+=1
  if not self.allowed or date!=op.TARGET:raise ValueError('finite expired or wrong date')
  self.assertIs(kwargs['publication']['existing_owner_gate_verified'],False);return {'schema':op.SCHEMA}
 def send(self,payload):self.sent.append(payload['event_id']);return {'confirmed':True,'message_id':'synthetic'}
 def call(self,**kwargs):return notify_day(self.root,date=kwargs.pop('date',op.TARGET),dry_run=kwargs.pop('dry_run',False),report_url='https://synthetic.invalid/',transport=kwargs.pop('transport',self.send),**kwargs)
 def test_real_outbox_accepts_distinct_v3_then_deduplicates(self):
  with patch.object(op,'action_context',side_effect=self.guard):
   first=self.call();self.assertEqual(first['external_sends'],2);self.assertEqual(len(self.sent),2);self.call();self.assertEqual(len(self.sent),2)
  self.assertGreaterEqual(self.checks,5)
 def test_wrong_date_or_expiry_stops_before_outbox_creation_including_preview(self):
  for dry,date,allowed in [(True,'2026-11-18',True),(False,op.TARGET,False)]:
   self.allowed=allowed
   with self.subTest(dry=dry),patch.object(op,'action_context',side_effect=self.guard),self.assertRaises(ValueError):self.call(date=date,dry_run=dry)
   self.assertFalse((self.root/'notification-outbox.sqlite').exists());self.assertFalse(self.sent)
 def test_structural_operational_flags_without_finite_authority_cannot_stage(self):
  with patch.object(op,'local_record',return_value=None),self.assertRaisesRegex(ValueError,'no finite authority'):self.call()
  self.assertFalse((self.root/'notification-outbox.sqlite').exists());self.assertFalse(self.sent)
 def test_expiry_after_first_message_keeps_second_pending_and_resumes_only_unsent(self):
  def first(payload):
   result=self.send(payload);self.allowed=False;return result
  with patch.object(op,'action_context',side_effect=self.guard):
   with self.assertRaisesRegex(ValueError,'expired'):self.call(transport=first)
   db=sqlite3.connect(self.root/'notification-outbox.sqlite');statuses=dict(db.execute('SELECT status,count(*) FROM new_a_delivery GROUP BY status'));db.close();self.assertEqual(statuses,{'PENDING':1,'SENT':1})
   self.allowed=True;self.call();self.assertEqual(len(self.sent),2);self.assertEqual(len(set(self.sent)),2)

class FinitePublication(unittest.TestCase):
 def setUp(self):
  self.fixture=release_tests.InitialCutover();self.fixture.setUp();self.root=self.fixture.root;self.db=self.fixture.db;self.db.external=True
  manifest=read(self.fixture.folder/'manifest.json');manifest['as_of']=op.TARGET;(self.fixture.folder/'manifest.json').write_bytes(encode(manifest).encode());atomic_write(self.fixture.folder/'receipt.json',{'manifest_sha256':file_sha(self.fixture.folder/'manifest.json')})
  snapshot={'payload_sha256':manifest['daily_snapshot_sha256'],'delayed_recovery':{'synthetic':True}}
  atomic_write(self.root/'snapshot.json',snapshot);self.run={'strategy':'A_BASE','detection_executed':True,'latest_session':op.TARGET,'source_version':manifest['source_version'],'snapshot_sha256':snapshot['payload_sha256'],'snapshot_file':str(self.root/'snapshot.json'),'bundle_directory':str(self.fixture.folder),'delayed_recovery':snapshot['delayed_recovery']};atomic_write(self.root/'latest-run.json',self.run)
  atomic_write(self.root/'activation.json',{'operational_admission':{'path':'synthetic','sha256':'a'*64}})
  self.expected=manifest
 def tearDown(self):self.fixture.tearDown()
 def test_pointer_success_receipt_lost_reconciles_without_second_cas(self):
  publish_bundle(self.db,self.fixture.folder,expected_revision=0);self.db.query("UPDATE new_a_active_pointer SET revision=4 WHERE pointer_key='owner'")
  before=pointer(self.db)
  with patch.object(op,'action_context',return_value={'schema':op.SCHEMA}),patch.object(op,'expected_finite_manifest',return_value=self.expected),patch('weak_early_beta.new_a.delayed_recovery.delivery_context',return_value={'expected_revision':3}),patch.object(cli,'publish_bundle',side_effect=AssertionError('SECOND CAS FORBIDDEN')):
   receipt=cli.publish(self.root,self.db,operational_verified=True)
  self.assertEqual(pointer(self.db),before);self.assertTrue(receipt['same_dataset_replay']);self.assertTrue(receipt['operational_gate_continuity_verified']);self.assertIs(receipt['existing_owner_gate_verified'],False);self.assertIs(receipt['owner_http_observed'],False);self.assertEqual(read(self.root/'latest-publication.json'),receipt)
 def test_other_rev4_payload_is_rejected_before_receipt_creation(self):
  publish_bundle(self.db,self.fixture.folder,expected_revision=0);self.db.query("UPDATE new_a_active_pointer SET revision=4 WHERE pointer_key='owner'")
  wrong={**self.expected,'daily_snapshot_sha256':'f'*64}
  with patch.object(op,'action_context',return_value={'schema':op.SCHEMA}),patch.object(op,'expected_finite_manifest',return_value=wrong),patch('weak_early_beta.new_a.delayed_recovery.delivery_context',return_value={'expected_revision':3}),self.assertRaisesRegex(ValueError,'partial publication differs'):cli.publish(self.root,self.db,operational_verified=True)
  self.assertFalse((self.root/'latest-publication.json').exists())

class FiniteAdmissionCAS(unittest.TestCase):
 def test_other_launch_owner_wins_without_activation_change(self):
  with tempfile.TemporaryDirectory() as name:
   repo=Path(name);root=private_root(repo);root.mkdir(parents=True);source='1'*40;old={'active':True,'external_actions_approved':True,'strategy':'A_BASE'};atomic_write(root/'activation.json',old);before=(root/'activation.json').read_bytes();runtime=repo/'.cache/weak_early_beta/daily_runtime';runtime.mkdir()
   baseline={'as_of':'2026-11-16','revision':3,'published':True,'active_readback_verified':True,'dataset_id':'a-synthetic','source_version':'b'*64,'manifest_sha256':'c'*64};atomic_write(root/'latest-publication.json',baseline)
   authority={'schema':'CODEX_TRUSTED_USER_FINITE_AUTHORIZATION_V1','chat_id':'synthetic','source_commit':source,'target_date':op.TARGET,'execution_date':op.EXECUTION,'virtual_only':True,'platform_signature_claimed':False,'current_owner_http_required':False,'unmeasured_owner_http_accepted':True,'user_instruction_sha256':['d'*64]}
   review={'schema':'NEW_A_REVIEWED_AUTH_DIAGNOSTIC_DELTA_V1','source_commit':source,'historical_auth_source_hashes':{},'current_auth_source_hashes':{},'only_health_diagnostic_changed':True,'reviewed_diff_sha256':'e'*64,'existing_private_authorization_unchanged':True}
   observation={'active_as_of':'2026-11-16','active_revision':3,'active_dataset_id':baseline['dataset_id'],'active_source_version':baseline['source_version'],'active_manifest_sha256':baseline['manifest_sha256'],'dependencies':{}}
   ci={'schema':'NEW_A_NORMAL_CI_DEPLOYMENT_V1','source_commit':source,'worker':'tentei-kyokuchi-cloud','workflow':'weak-early-beta-report-deploy.yml','status':'completed','conclusion':'success','standard_wrangler_deploy':True,'tag':'cloud-deploy-synthetic','version_id':'11111111-2222-3333-4444-555555555555','build_input_sha256':'2'*64,'raw_log_sha256':'3'*64,'run_id':1}
   def preflight():
    (runtime/'task-entry.lock').write_text('other-owner');return {'ok':True,'head':source}
   with patch.object(op,'head',return_value=source),patch.object(op,'day',return_value=op.EXECUTION),patch.object(op,'now',return_value=op.stamp('2026-11-18T12:00:00+09:00')),patch.object(op,'git',return_value=b''),patch.object(op.ca,'AUTH_FILES',frozenset()),patch.object(op.ca,'target',return_value={}),patch.object(op,'historical_review',return_value={'auth_source_hashes':{}}):
    with self.assertRaises(FileExistsError):op.issue(repo,authorization_reader=lambda _:authority,ci_reader=lambda _:ci,auth_review_reader=lambda _:review,source_recovery={},not_after='2026-11-18T17:00:00+09:00',preflight=preflight,observer=lambda *_:observation)
   self.assertEqual((root/'activation.json').read_bytes(),before);self.assertEqual((runtime/'task-entry.lock').read_text(),'other-owner');self.assertFalse((runtime/'daily.lock').exists())

if __name__=='__main__':unittest.main()
