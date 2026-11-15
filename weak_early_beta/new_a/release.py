"""Initial preparation only. Never uploads code, changes traffic, or enables daily work."""
import datetime,json,re
from pathlib import Path
from .files import read,atomic_write,file_sha,digest
from .publisher import stage_bundle,activate_prepared,pointer

WORKER='tentei-kyokuchi-cloud'
AUTH_FILES={'weak-early-beta-gate/src/cloud-owner-only.ts','weak-early-beta-gate/src/cloud-role-authority.ts','weak-early-beta-gate/src/cloud-membership.ts','weak-early-beta-gate/src/cloud-api.ts','report-gate/src/index.ts','weak-early-beta-gate/wrangler.jsonc'}
HEX=re.compile('[a-f0-9]{64}')
UUID=re.compile('[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}')

def private_record(root,path):
 p=Path(path).resolve()
 if not p.is_relative_to(Path(root).resolve()) or p.suffix!='.json':raise ValueError('private release record required')
 return read(p)

def inactive(root):
 if Path(root).resolve().name!='new-a-private':raise ValueError('dedicated new-A private root required')
 value=read(Path(root)/'activation.json')
 if value.get('schema')!='NEW_A_OWNER_ACTIVATION_V1' or value.get('active') is not False:raise ValueError('initial preparation requires inactive daily engine')

def authorization(root,repo,approval_path,manifest_path):
 """Operator evidence must come from actual approval/checks, never from this function."""
 inactive(root);a=private_record(root,approval_path)
 if a.get('schema')!='NEW_A_PREPARATION_AUTHORIZATION_V1' or a.get('synthetic') is not False or a.get('scope')!='PREPARE_PRIVATE_DATA_NO_TRAFFIC_CHANGE' or a.get('target_worker')!=WORKER:raise ValueError('real preparation authorization required')
 for k in ['approved','full_standard_check_passed','baseline_source_verified','baseline_ignores_new_tables','baseline_owner_session_verified','existing_auth_unchanged','frozen_contract_verified']:
  if a.get(k) is not True:raise ValueError('preparation evidence incomplete')
 if a.get('repository')!='Ken5InvestmentLab/screening-bot' or a.get('branch')!='research/weak-early-beta' or a.get('visibility')!='private' or not UUID.fullmatch(str(a.get('baseline_version_id',''))):raise ValueError('preparation target mismatch')
 until=datetime.datetime.fromisoformat(str(a.get('expires_at','')).replace('Z','+00:00'))
 if until.tzinfo is None or until<=datetime.datetime.now(datetime.timezone.utc):raise ValueError('preparation authorization expired')
 if not HEX.fullmatch(str(a.get('code_manifest_sha256',''))) or file_sha(Path(manifest_path))!=a['code_manifest_sha256']:raise ValueError('code manifest mismatch')
 m=read(manifest_path);pins={v['path']:v['sha256'] for v in m['files']}
 auth=a.get('auth_source_hashes',{})
 if set(auth)!=AUTH_FILES:raise ValueError('unchanged auth source pins required')
 pins.update(auth)
 for rel,h in pins.items():
  p=(Path(repo)/rel).resolve()
  if not p.is_relative_to(Path(repo).resolve()) or any(x in Path(rel).parts for x in ['.env','private','.cache','node_modules']) or '.generated.' in rel or not HEX.fullmatch(str(h)) or file_sha(p)!=h:raise ValueError('approved code or auth source changed')
 if not HEX.fullmatch(str(a.get('bundle_manifest_sha256',''))):raise ValueError('approved private bundle pin required')
 if type(a.get('expected_private_revision')) is not int or a['expected_private_revision']<0:raise ValueError('explicit private revision proof required')
 return {**a,'kind':'REMOTE_APPROVED_PREPARATION'}

def retained_record(root,alias,value):
 path=Path(root)/'release-records'/value['schema']/(digest(value)+'.json')
 if path.exists() and read(path)!=value:raise ValueError('immutable release record conflict')
 if not path.exists():atomic_write(path,value)
 atomic_write(Path(root)/alias,value)

def version_receipt(root,path,approved):
 v=private_record(root,path)
 if v.get('schema')!='NEW_A_UPLOADED_VERSION_RECEIPT_V1' or v.get('target_worker')!=WORKER or not UUID.fullmatch(str(v.get('version_id',''))) or v.get('version_id')==approved.get('baseline_version_id'):raise ValueError('uploaded version identity required')
 for k in ['uploaded_only','not_in_live_deployment','configuration_unchanged','durable_object_lifecycle_unchanged','preview_urls_unchanged']:
  if v.get(k) is not True:raise ValueError('inactive version proof incomplete')
 if approved.get('kind')!='LOCAL_SYNTHETIC_UNAPPROVED' and (v.get('synthetic') is not False or v.get('code_manifest_sha256')!=approved['code_manifest_sha256']):raise ValueError('uploaded version source mismatch')
 return v

def prepare(root,db,bundle,approved,*,expected_revision=0):
 inactive(root)
 if db.external and approved.get('kind')!='REMOTE_APPROVED_PREPARATION':raise ValueError('remote preparation approval absent')
 if approved.get('kind')!='LOCAL_SYNTHETIC_UNAPPROVED' and file_sha(Path(bundle)/'manifest.json')!=approved.get('bundle_manifest_sha256'):raise ValueError('approved bundle changed')
 if approved.get('kind')!='LOCAL_SYNTHETIC_UNAPPROVED' and expected_revision!=approved.get('expected_private_revision'):raise ValueError('approved private revision mismatch')
 p=stage_bundle(db,bundle,expected_revision=expected_revision)
 value={'schema':'NEW_A_INITIAL_PREPARATION_V1','dataset':p,'input_bundle_manifest_sha256':file_sha(Path(bundle)/'manifest.json'),'code_manifest_sha256':approved.get('code_manifest_sha256'),'authorization_kind':approved.get('kind','REMOTE_APPROVED_PREPARATION'),'baseline_version_id':approved.get('baseline_version_id'),'target_worker':WORKER,'published':False,'traffic_changed':False,'daily_enabled':False,'notifications_sent':0}
 retained_record(root,'prepared-release.json',value);return value

def prearm(root,db,version_path,approved,*,expected_revision):
 inactive(root);p=read(Path(root)/'prepared-release.json');v=version_receipt(root,version_path,approved)
 if db.external and approved.get('kind')!='REMOTE_APPROVED_PREPARATION':raise ValueError('remote preparation approval absent')
 if approved.get('kind')!='LOCAL_SYNTHETIC_UNAPPROVED' and expected_revision!=approved.get('expected_private_revision'):raise ValueError('approved private revision mismatch')
 if p.get('schema')!='NEW_A_INITIAL_PREPARATION_V1' or p.get('published') is not False or p.get('traffic_changed') is not False or p.get('target_worker')!=WORKER:raise ValueError('prepared release contract invalid')
 if approved.get('kind')!='LOCAL_SYNTHETIC_UNAPPROVED' and (p.get('authorization_kind')!='REMOTE_APPROVED_PREPARATION' or p.get('code_manifest_sha256')!=approved['code_manifest_sha256'] or p.get('baseline_version_id')!=approved['baseline_version_id'] or p.get('input_bundle_manifest_sha256')!=approved['bundle_manifest_sha256']):raise ValueError('initial preparation source mismatch')
 result=activate_prepared(db,p['dataset'],expected_revision=expected_revision)
 value={**result,'schema':'NEW_A_PREARMED_RELEASE_V1','published':False,'existing_owner_gate_verified':False,'traffic_changed':False,'daily_enabled':False,'ready_for_explicit_cutover':True,'candidate_version_id':v['version_id'],'baseline_version_id':approved.get('baseline_version_id'),'code_manifest_sha256':approved.get('code_manifest_sha256'),'authorization_kind':approved.get('kind','REMOTE_APPROVED_PREPARATION')}
 retained_record(root,'prearmed-release.json',value)
 # Deliberately do not write latest-publication.json or activation.json.
 return value
