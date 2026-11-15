"""Synthetic initial-cutover protocol; no network, credentials, deployment or notifications."""
import copy,datetime,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from weak_early_beta.new_a.publisher import LocalD1,stage_bundle,activate_prepared,publish_bundle,pointer,hash_text,verify_dataset
from weak_early_beta.new_a.files import encode,read,atomic_write,file_sha
from weak_early_beta.new_a import release

class InitialCutover(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'new-a-private';self.root.mkdir();self.repo=Path(__file__).resolve().parents[1]
  atomic_write(self.root/'activation.json',{'schema':'NEW_A_OWNER_ACTIVATION_V1','active':False})
  self.activation=(self.root/'activation.json').read_bytes();self.db=LocalD1(self.root/'owner.sqlite',self.repo/'weak-early-beta-gate/schema/new-a-private.sql')
  self.db.query('CREATE TABLE cloud_member_preferences(member_id TEXT PRIMARY KEY,preferences_json TEXT)');self.db.query('INSERT INTO cloud_member_preferences VALUES (?,?)',('SYNTHETIC_OWNER','{"notifications":{"reminder":false},"base_shares":200}'))
  self.old=self.db.query('SELECT * FROM cloud_member_preferences');self.folder=self.bundle('bundle','a');self.local={'kind':'LOCAL_SYNTHETIC_UNAPPROVED'}
  self.version=self.root/'version.json';atomic_write(self.version,{'schema':'NEW_A_UPLOADED_VERSION_RECEIPT_V1','target_worker':release.WORKER,'version_id':'22222222-2222-4222-8222-222222222222','uploaded_only':True,'not_in_live_deployment':True,'configuration_unchanged':True,'durable_object_lifecycle_unchanged':True,'preview_urls_unchanged':True,'synthetic':True})
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def bundle(self,name,suffix):
  folder=self.root/name;folder.mkdir();cols={};quotes=[]
  for kind in ['episodes','intents','watches','presentation','current_daily','quotes']:
   raw=encode([{'synthetic':suffix}]);part=kind+'-000.json';(folder/part).write_text(raw,'utf8');d={'name':part,'sha256':hash_text(raw),'bytes':len(raw.encode()),'rows':1}
   if kind=='quotes':quotes=[d]
   else:cols[kind]=[d]
  manifest={'schema':'A_BROWSER_PRIVATE_INPUT_V1','audience':'EXISTING_CLOUD_OWNER_ONLY','strategy':'A_BASE','source_version':suffix*64,'input_header':{'source_version':suffix*64},'collections':cols,'quotes':quotes,'as_of':'SYNTHETIC_SESSION','daily_snapshot_sha256':'b'*64}
  raw=encode(manifest);(folder/'manifest.json').write_text(raw,'utf8');atomic_write(folder/'receipt.json',{'manifest_sha256':hash_text(raw)})
  return folder
 def assert_old_preserved(self):
  self.assertEqual(self.db.query('SELECT * FROM cloud_member_preferences'),self.old);self.assertEqual((self.root/'activation.json').read_bytes(),self.activation);self.assertFalse((self.root/'latest-publication.json').exists())
 def test_prepare_ready_without_active_pointer_or_runtime_activation(self):
  p=release.prepare(self.root,self.db,self.folder,self.local);self.assertFalse(p['published']);self.assertFalse(p['traffic_changed']);self.assertIsNone(pointer(self.db));self.assertEqual(verify_dataset(self.db,p['dataset']['dataset_id'])[0]['status'],'READY');self.assert_old_preserved()
 def test_repeated_preparation_has_same_dataset_and_no_duplicate_parts(self):
  a=release.prepare(self.root,self.db,self.folder,self.local);counts=[len(self.db.query('SELECT * FROM '+t)) for t in ['new_a_private_datasets','new_a_private_parts']];b=release.prepare(self.root,self.db,self.folder,self.local);self.assertEqual(a,b);self.assertEqual(counts,[len(self.db.query('SELECT * FROM '+t)) for t in ['new_a_private_datasets','new_a_private_parts']]);self.assertIsNone(pointer(self.db));self.assert_old_preserved()
 def test_corrupt_prepared_part_stops_without_pointer(self):
  m=read(self.folder/'manifest.json');(self.folder/m['quotes'][0]['name']).write_text('[]','utf8')
  with self.assertRaisesRegex(ValueError,'prepared part'):release.prepare(self.root,self.db,self.folder,self.local)
  self.assertIsNone(pointer(self.db));self.assert_old_preserved()
 def test_prearm_is_not_publication_and_does_not_enable_daily(self):
  release.prepare(self.root,self.db,self.folder,self.local);r=release.prearm(self.root,self.db,self.version,self.local,expected_revision=0);self.assertTrue(r['ready_for_explicit_cutover']);self.assertFalse(r['published']);self.assertFalse(r['existing_owner_gate_verified']);self.assertEqual(pointer(self.db)['revision'],1);self.assert_old_preserved()
  repeated=release.prearm(self.root,self.db,self.version,self.local,expected_revision=0);self.assertTrue(repeated['same_dataset_replay']);self.assertEqual(pointer(self.db)['revision'],1)
 def test_mutated_prepared_receipt_or_part_stops_prearm(self):
  release.prepare(self.root,self.db,self.folder,self.local);p=read(self.root/'prepared-release.json');p['dataset']['source_version']='c'*64;atomic_write(self.root/'prepared-release.json',p)
  with self.assertRaisesRegex(ValueError,'receipt invalid'):release.prearm(self.root,self.db,self.version,self.local,expected_revision=0)
  self.assertIsNone(pointer(self.db))
 def test_database_part_corruption_after_ready_stops_prearm(self):
  release.prepare(self.root,self.db,self.folder,self.local);self.db.query("UPDATE new_a_private_parts SET payload_json='[]' WHERE name='quotes-000.json'")
  with self.assertRaisesRegex(ValueError,'part mismatch'):release.prearm(self.root,self.db,self.version,self.local,expected_revision=0)
  self.assertIsNone(pointer(self.db))
 def test_changed_approved_bundle_cannot_prearm_an_old_preparation(self):
  approved={'kind':'REMOTE_APPROVED_PREPARATION','code_manifest_sha256':'d'*64,'baseline_version_id':'11111111-1111-4111-8111-111111111111','bundle_manifest_sha256':file_sha(self.folder/'manifest.json'),'expected_private_revision':0}
  release.prepare(self.root,self.db,self.folder,approved);v=read(self.version);v.update(synthetic=False,code_manifest_sha256='d'*64);atomic_write(self.version,v);approved['bundle_manifest_sha256']='e'*64
  with self.assertRaisesRegex(ValueError,'preparation source mismatch'):release.prearm(self.root,self.db,self.version,approved,expected_revision=0)
  self.assertIsNone(pointer(self.db))
 def test_uploaded_version_already_live_or_unknown_configuration_denied(self):
  release.prepare(self.root,self.db,self.folder,self.local)
  for key in ['uploaded_only','not_in_live_deployment','configuration_unchanged','durable_object_lifecycle_unchanged','preview_urls_unchanged']:
   v=read(self.version);v[key]=False;atomic_write(self.root/'bad-version.json',v)
   with self.assertRaisesRegex(ValueError,'inactive version proof'):release.prearm(self.root,self.db,self.root/'bad-version.json',self.local,expected_revision=0)
  self.assertIsNone(pointer(self.db))
 def test_pointer_race_never_overwrites_other_candidate(self):
  prepared=stage_bundle(self.db,self.folder,expected_revision=0);other=publish_bundle(self.db,self.bundle('other','c'),expected_revision=0)
  with self.assertRaisesRegex(ValueError,'revision conflict'):activate_prepared(self.db,prepared,expected_revision=0)
  self.assertEqual(pointer(self.db)['dataset_id'],other['dataset_id'])
 def test_existing_publish_contract_still_stages_and_promotes_once(self):
  first=publish_bundle(self.db,self.folder,expected_revision=0);self.assertFalse(first['same_dataset_replay']);second=publish_bundle(self.db,self.folder,expected_revision=1);self.assertTrue(second['same_dataset_replay']);self.assertEqual(second['revision'],1)
 def test_initial_preparation_refuses_enabled_daily_state(self):
  atomic_write(self.root/'activation.json',{'schema':'NEW_A_OWNER_ACTIVATION_V1','active':True})
  with self.assertRaisesRegex(ValueError,'inactive'):release.prepare(self.root,self.db,self.folder,self.local)
  self.assertIsNone(pointer(self.db))
 def test_unapproved_remote_cli_stops_before_wrangler_creation(self):
  from weak_early_beta.new_a import cli
  for argv in [['prepare-release','--remote','--bundle',str(self.folder)],['prearm-release','--remote','--version-receipt',str(self.version),'--expected-revision','0']]:
   with patch.object(cli,'private_root',return_value=self.root),patch.object(cli,'WranglerD1',side_effect=AssertionError('REMOTE_MUST_NOT_RUN')) as remote:
    with self.assertRaisesRegex(ValueError,'explicit preparation approval'):cli.main(argv)
    remote.assert_not_called()
 def test_synthetic_approval_refused_for_remote_before_source_or_secret_access(self):
  a=self.root/'approval.json';atomic_write(a,{'schema':'NEW_A_PREPARATION_AUTHORIZATION_V1','scope':'PREPARE_PRIVATE_DATA_NO_TRAFFIC_CHANGE','target_worker':release.WORKER,'synthetic':True})
  with self.assertRaisesRegex(ValueError,'real preparation authorization'):release.authorization(self.root,self.repo,a,self.root/'not-a-real-manifest.json')
 def test_synthetic_preparation_never_accepted_by_remote_helper(self):
  self.db.external=True
  with self.assertRaisesRegex(ValueError,'approval absent'):release.prepare(self.root,self.db,self.folder,self.local)
  self.db.external=False;self.assertIsNone(pointer(self.db))
 def test_source_pin_guard_catches_changed_code_without_creating_db(self):
  fake_repo=self.root/'code';fake_repo.mkdir();pins={}
  for rel in release.AUTH_FILES|{'weak_early_beta/new_a/release.py'}:
   p=fake_repo/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic source','utf8');pins[rel]=file_sha(p)
  manifest=self.root/'code-manifest.json';atomic_write(manifest,{'files':[{'path':'weak_early_beta/new_a/release.py','sha256':pins['weak_early_beta/new_a/release.py']}]})
  a={'schema':'NEW_A_PREPARATION_AUTHORIZATION_V1','scope':'PREPARE_PRIVATE_DATA_NO_TRAFFIC_CHANGE','target_worker':release.WORKER,'synthetic':False,'approved':True,'full_standard_check_passed':True,'baseline_source_verified':True,'baseline_ignores_new_tables':True,'baseline_owner_session_verified':True,'existing_auth_unchanged':True,'frozen_contract_verified':True,'repository':'Ken5InvestmentLab/screening-bot','branch':'research/weak-early-beta','visibility':'private','baseline_version_id':'11111111-1111-4111-8111-111111111111','expires_at':(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)).isoformat(),'code_manifest_sha256':file_sha(manifest),'auth_source_hashes':{k:pins[k] for k in release.AUTH_FILES},'bundle_manifest_sha256':file_sha(self.folder/'manifest.json')}
  a['expected_private_revision']=0;path=self.root/'synthetic-local-fixture-approval.json';atomic_write(path,a)
  # This only tests a parser with fabricated source/UUIDs; no remote DB or real approval exists.
  self.assertEqual(release.authorization(self.root,fake_repo,path,manifest)['kind'],'REMOTE_APPROVED_PREPARATION')
  (fake_repo/'weak_early_beta/new_a/release.py').write_text('changed code','utf8')
  with self.assertRaisesRegex(ValueError,'source changed'):release.authorization(self.root,fake_repo,path,manifest)
 def test_after_legacy_rollback_preparation_can_resume_explicit_revision_without_deleting_records(self):
  release.prepare(self.root,self.db,self.folder,self.local);release.prearm(self.root,self.db,self.version,self.local,expected_revision=0);before={p.relative_to(self.root) for p in (self.root/'release-records').rglob('*.json')}
  resumed=release.prepare(self.root,self.db,self.folder,self.local,expected_revision=1);self.assertEqual(resumed['dataset']['expected_revision'],1);self.assertTrue(resumed['dataset']['already_active']);self.assertTrue(release.prearm(self.root,self.db,self.version,self.local,expected_revision=1)['same_dataset_replay']);self.assertEqual(pointer(self.db)['revision'],1);self.assertTrue(before.issubset({p.relative_to(self.root) for p in (self.root/'release-records').rglob('*.json')}));self.assert_old_preserved()

if __name__=='__main__':unittest.main()
