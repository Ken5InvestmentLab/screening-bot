"""Operational measurements stay distinct from unmeasured owner HTTP."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weak_early_beta.new_a import operational_admission as op
from weak_early_beta.new_a.files import digest,encode,atomic_write,file_sha,private_root

SOURCE='1'*40
VERSION='11111111-2222-3333-4444-555555555555'
CI={'schema':'NEW_A_NORMAL_CI_DEPLOYMENT_V1','source_commit':SOURCE,'worker':'tentei-kyokuchi-cloud','workflow':'weak-early-beta-report-deploy.yml','status':'completed','conclusion':'success','standard_wrangler_deploy':True,'tag':'cloud-deploy-synthetic','version_id':VERSION,'build_input_sha256':'2'*64,'raw_log_sha256':'3'*64,'run_id':123}
POLICY='4'*64
DEPS={'synthetic':'dependencies'}

class ObservationTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.repo=Path(self.folder.name)
  manifest=encode({'schema':'A_BROWSER_PRIVATE_INPUT_V1','audience':'EXISTING_CLOUD_OWNER_ONLY','strategy':'A_BASE','source_version':'5'*64,'as_of':'2026-11-16','quotes':[],'collections':{}})
  self.row={'dataset_id':'a-'+'6'*24,'revision':3,'status':'READY','source_version':'5'*64,'manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),'manifest_json':manifest}
  self.mutate=lambda value:value;self.closed=0;self.queries=0
 def tearDown(self):self.folder.cleanup()
 def database(self):
  owner=self
  class DB:
   def query(self,sql):
    owner.queries+=1;owner.assertTrue(sql.startswith('SELECT '));owner.assertNotIn('INSERT',sql);return [dict(owner.row)]
   def close(self):owner.closed+=1
  return DB()
 def http(self,url,*,params,headers,allow_redirects,timeout):
  self.assertEqual(url,op.ORIGIN+'/healthz');self.assertFalse(allow_redirects);self.assertNotIn('Cookie',headers);self.assertNotIn('Authorization',headers)
  nonce=params['new_a_probe'];row=self.row
  active=digest(['NEW_A_ACTIVE_METADATA_V1',row['dataset_id'],row['revision'],row['status'],row['source_version'],row['manifest_sha256'],'2026-11-16'])
  timestamp='2026-11-18T00:00:00Z';prefix=['NEW_A_OPERATIONAL_CHALLENGE_V1',nonce,'tentei-kyokuchi-cloud','tentei-cloud-settings',VERSION,SOURCE,timestamp,SOURCE,CI['build_input_sha256']]
  value={'schema':'NEW_A_OPERATIONAL_READBACK_V1','nonce':nonce,'source_commit':SOURCE,'build_input_sha256':CI['build_input_sha256'],'target':{'worker':'tentei-kyokuchi-cloud','database':'tentei-cloud-settings'},'version':{'id':VERSION,'tag':SOURCE,'timestamp':timestamp},'policy_sha256':POLICY,'d1_active_sha256':active,'policy_challenge_sha256':digest([*prefix,'policy',POLICY]),'d1_challenge_sha256':digest([*prefix,'d1-active',active]),'authentication_probe':False,'owner_http_observed':False,'d1_writes':0}
  value=self.mutate(value)
  class Response:
   status_code=200;headers={'cache-control':'no-store, max-age=0'};content=encode(value).encode()
   def json(self):return value
  response=Response();response.url=url+'?new_a_probe='+nonce;return response
 def observe(self):
  with patch.object(op,'head',return_value=SOURCE),patch.object(op,'fixed_dependencies',return_value=DEPS):
   return op.observe(self.repo,CI,loader_reader=lambda:{'policy_sha256':POLICY},database_factory=self.database,http_get=self.http)
 def test_actual_chain_preserves_unmeasured_owner_and_artifact(self):
  result=self.observe();self.assertEqual(result['dependencies'],DEPS);self.assertEqual(result['active_revision'],3);self.assertEqual(self.queries,2);self.assertEqual(self.closed,2)
  for name in ['owner_http_observed','authenticated_nonowner_observed','management_deployment_observed','traffic_percentages_observed','final_worker_artifact_sha256_observed']:self.assertIs(result[name],False)
 def test_version_policy_nonce_or_status_cannot_be_flags(self):
  for key,value in [('owner_http_observed',True),('authentication_probe',True),('d1_writes',1),('policy_sha256','a'*64),('nonce','0'*64),('build_input_sha256','a'*64),('d1_challenge_sha256','a'*64)]:
   with self.subTest(key=key):
    self.mutate=lambda actual,k=key,v=value:{**actual,k:v}
    with self.assertRaises(ValueError):self.observe()
 def test_wrong_runtime_version(self):
  self.mutate=lambda actual:{**actual,'version':{**actual['version'],'id':'99999999-2222-3333-4444-555555555555'}}
  with self.assertRaisesRegex(ValueError,'provenance'):self.observe()
 def test_d1_race(self):
  http=self.http
  def raced(*args,**kwargs):
   response=http(*args,**kwargs);self.row['revision']=4;return response
  with patch.object(op,'head',return_value=SOURCE),patch.object(op,'fixed_dependencies',return_value=DEPS):
   with self.assertRaisesRegex(ValueError,'raced'):op.observe(self.repo,CI,loader_reader=lambda:{'policy_sha256':POLICY},database_factory=self.database,http_get=raced)
 def test_d1_corrupt_manifest(self):
  self.row['manifest_json']='{}'
  with self.assertRaisesRegex(ValueError,'integrity'):self.observe()
 def test_deployment_not_claimed_from_build_hash(self):
  for key,value in [('source_commit','f'*40),('status','queued'),('conclusion','failure'),('standard_wrangler_deploy',False)]:
   with self.subTest(key=key),self.assertRaises(ValueError):op.checked_ci({**CI,key:value},SOURCE)

class FiniteScopeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.repo=Path(self.tmp.name);self.old={'schema':'NEW_A_OWNER_ACTIVATION_V1','strategy':'A_BASE','active':True,'external_actions_approved':True,'owner_acceptance':{'historical':True}}
  self.auth=self.repo/'a.ts';self.auth.write_text('synthetic authority')
  self.record={'schema':op.SCHEMA,'target_date':op.TARGET,'execution_date':op.EXECUTION,'source_commit':SOURCE,'target':{},'strategy':'A_BASE','not_after':'2026-11-18T23:59:59+09:00','owner_http_observed':False,'authenticated_nonowner_observed':False,'platform_signature_claimed':False,'original_activation_sha256':digest(self.old),'current_auth_source_hashes':{'a.ts':file_sha(self.auth)}}
  # File hashes pin bytes, independently of record JSON identities.
  original=encode(self.old)+'\n';self.record['original_activation_sha256']=hashlib.sha256(original.encode()).hexdigest()
  folder=op.area(self.repo)/digest(self.record);folder.mkdir(parents=True);(folder/'original-activation.json').write_bytes(original.encode());atomic_write(folder/'record.json',self.record)
  self.activation={**self.old,'operational_admission':op.ref(self.repo,folder/'record.json')};atomic_write(private_root(self.repo)/'activation.json',self.activation)
  self.patches=[patch.object(op,'head',return_value=SOURCE),patch.object(op,'day',return_value=op.EXECUTION),patch.object(op,'now',return_value=op.stamp('2026-11-18T12:00:00+09:00')),patch.object(op,'git',return_value=b''),patch.object(op.ca,'target',return_value={}),patch.object(op.ca,'AUTH_FILES',frozenset({'a.ts'}))]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def test_old_owner_evidence_retained_without_promotion(self):self.assertEqual(op.local_record(self.repo),self.record)
 def test_disabled_activation_rejects(self):
  for key in ['active','external_actions_approved']:
   with self.subTest(key=key),self.assertRaises(ValueError):op.local_record(self.repo,{**self.activation,key:False})
 def test_changed_history_auth_or_source_rejects(self):
  self.auth.write_text('changed')
  with self.assertRaisesRegex(ValueError,'auth source'):op.local_record(self.repo)
 def test_different_action_date_rejects_before_network(self):
  with self.assertRaisesRegex(ValueError,'another date'):op.action_context(self.repo,date='2026-11-18')
 def test_publication_fields_keep_meanings_distinct(self):
  self.assertTrue(op.publication_gate_verified({'existing_owner_gate_verified':True}))
  self.assertFalse(op.publication_gate_verified({'operational_gate_continuity_verified':True,'existing_owner_gate_verified':True,'owner_http_observed':False,'operational_admission':{}}))
  self.assertTrue(op.publication_gate_verified({'operational_gate_continuity_verified':True,'existing_owner_gate_verified':False,'owner_http_observed':False,'operational_admission':{}}))
 def test_rev4_exact_immutable_bundle_is_valid_without_local_publication_receipt(self):
  expected={'source_version':'a'*64,'daily_snapshot_sha256':'b'*64};record={**self.record,'ci':CI,'dependencies':DEPS,'initial_observation':{'version_id':VERSION}}
  actual={'dependencies':DEPS,'version_id':VERSION,'active_revision':4,'active_as_of':op.TARGET,'active_source_version':expected['source_version'],'active_logical_manifest_sha256':digest(expected)}
  with patch.object(op,'local_record',return_value=record),patch.object(op,'expected_finite_manifest',return_value=expected):
   self.assertEqual(op.validate(self.repo,observer=lambda *_:actual)[0],record)
   with self.assertRaisesRegex(ValueError,'exact finite published'):op.validate(self.repo,observer=lambda *_:{**actual,'active_logical_manifest_sha256':'f'*64})

if __name__=='__main__':unittest.main()
