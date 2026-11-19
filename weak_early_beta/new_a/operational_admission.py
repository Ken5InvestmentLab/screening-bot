"""Finite Nov17 operational continuity, distinct from owner HTTP acceptance.

The owner HTTP observation remains unmeasured. Normal CI, actual runtime
metadata, effective policy, existing-loader identities and D1 are independent
requirements. No cookie, management deployment GET, SQL write or sender exists
in this observer. V1/V2 records retain their original meaning.
"""
import argparse,copy,datetime,hashlib,json,os,re,secrets,shutil,subprocess,tempfile
from pathlib import Path
import requests
from .files import read,file_sha,digest,encode,private_root,verify_bootstrap,atomic_write
from . import continuing_acceptance as ca

SCHEMA='NEW_A_OPERATIONAL_CONTINUITY_V3'
TARGET='2026-11-17'
EXECUTION='2026-11-18'
ORIGIN='https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev'
HEX=re.compile('[a-f0-9]{64}')
VERSION=re.compile(r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}')

def require(value,reason):
 if not value:raise ValueError('Operational admission: '+reason)
def now():return datetime.datetime.now(datetime.timezone.utc)
def stamp(value):
 parsed=datetime.datetime.fromisoformat(value.replace('Z','+00:00'));require(parsed.tzinfo is not None,'timezone required');return parsed
def day():return now().astimezone(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
def git(repo,*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=repo)
def head(repo):return git(repo,'rev-parse','HEAD').decode().strip()
def area(repo):return private_root(repo)/'operational-admission'
def ref(repo,path):return {'path':str(Path(path).resolve().relative_to(Path(repo).resolve())).replace('\\','/'),'sha256':file_sha(path)}
def load_ref(repo,reference):
 p=(Path(repo)/reference['path']).resolve();require(p.is_relative_to(area(repo)) and p.name=='record.json' and file_sha(p)==reference['sha256'],'record reference changed');r=read(p);require(p.parent.name==digest(r),'record identity changed');return p,r

def checked_ci(value,source):
 require(value.get('schema')=='NEW_A_NORMAL_CI_DEPLOYMENT_V1' and value.get('source_commit')==source and value.get('worker')=='tentei-kyokuchi-cloud' and value.get('workflow')=='weak-early-beta-report-deploy.yml' and value.get('status')=='completed' and value.get('conclusion')=='success' and value.get('standard_wrangler_deploy') is True and str(value.get('tag','')).startswith('cloud-deploy-') and VERSION.fullmatch(str(value.get('version_id',''))) and HEX.fullmatch(str(value.get('build_input_sha256',''))) and HEX.fullmatch(str(value.get('raw_log_sha256',''))) and type(value.get('run_id')) is int and value['run_id']>0,'exact normal CI receipt unavailable')
 return value

def fixed_dependencies(repo,loader):
 manifest,files=verify_bootstrap(private_root(repo))
 require(loader.get('schema')=='NEW_A_EXISTING_LOADER_METADATA_V1' and loader.get('credential_values_returned') is False and loader.get('report_origin')==ORIGIN,'existing-loader metadata unavailable')
 keys=['runner_configuration_sha256','loader_precedence_sha256','runtime_sha256','policy_sha256','signal_destination_sha256','summary_destination_sha256']
 require(all(HEX.fullmatch(str(loader.get(k,''))) for k in keys),'loader identities incomplete')
 return {'bootstrap_manifest_sha256':file_sha(private_root(repo)/'bootstrap/manifest.json'),'bootstrap_files':{k:file_sha(v) for k,v in sorted(files.items())},'loader':{k:loader[k] for k in keys}}

def default_loader(repo):
 config=Path(repo)/'.cache/weak_early_beta/daily-runner.config.json';c=read(config)
 result=subprocess.run([c['nodePath'],str(Path(repo)/'scripts/windows/new-a-operational-loader.mjs'),str(config)],cwd=repo,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=120)
 require(result.returncode==0,'existing-loader service metadata failed')
 try:return json.loads(result.stdout)
 except ValueError:raise ValueError('Operational admission: loader response invalid') from None

def default_database(repo):
 from .publisher import WranglerD1
 config=read(Path(repo)/'.cache/weak_early_beta/daily-runner.config.json')
 return WranglerD1(repo,private_root(repo)/'sql',execute=True,node=config['nodePath'])

def active_metadata(repo,database_factory=None):
 db=(database_factory or (lambda:default_database(repo)))()
 try:return read_active_metadata(db)
 finally:db.close()

def read_active_metadata(db):
 rows=db.query("SELECT p.dataset_id,p.revision,d.status,d.source_version,d.manifest_sha256,d.manifest_json FROM new_a_active_pointer p JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id WHERE p.pointer_key='owner'")
 require(len(rows)==1,'active D1 state unavailable');row=rows[0];manifest=json.loads(row['manifest_json'])
 require(hashlib.sha256(row['manifest_json'].encode()).hexdigest()==row['manifest_sha256'] and manifest.get('source_version')==row['source_version'] and row['status']=='READY','D1 active integrity changed')
 active=digest(['NEW_A_ACTIVE_METADATA_V1',row['dataset_id'],row['revision'],row['status'],row['source_version'],row['manifest_sha256'],manifest['as_of']])
 return row,manifest,active

def observe_normal_response(*,source,version_id,build_input_sha256,policy_sha256,active,http_get=None):
 """Verify the existing normal-origin Worker and its live D1 challenge."""
 nonce=secrets.token_hex(32)
 get=http_get or requests.get
 response=get(ORIGIN+'/healthz',params={'new_a_probe':nonce},headers={'Cache-Control':'no-cache','User-Agent':'screening-bot-operational-readback/1.0'},allow_redirects=False,timeout=30)
 require(response.status_code==200 and response.url==ORIGIN+'/healthz?new_a_probe='+nonce and 'no-store' in response.headers.get('cache-control',''),'normal runtime response unavailable')
 try:actual=response.json()
 except ValueError:raise ValueError('Operational admission: runtime response invalid') from None
 version=actual.get('version',{});target=actual.get('target',{})
 require(actual.get('schema')=='NEW_A_OPERATIONAL_READBACK_V1' and actual.get('nonce')==nonce and actual.get('source_commit')==source and actual.get('build_input_sha256')==build_input_sha256 and target=={'worker':'tentei-kyokuchi-cloud','database':'tentei-cloud-settings'} and version.get('id')==version_id and version.get('tag')==source and actual.get('authentication_probe') is False and actual.get('owner_http_observed') is False and actual.get('d1_writes')==0,'runtime provenance mismatch')
 require(stamp(version['timestamp'])<=now(),'runtime version is in future')
 require(actual['policy_sha256']==policy_sha256,'effective authentication policy changed')
 prefix=['NEW_A_OPERATIONAL_CHALLENGE_V1',nonce,target['worker'],target['database'],version['id'],version['tag'],version['timestamp'],source,actual['build_input_sha256']]
 require(actual['d1_active_sha256']==active and actual['policy_challenge_sha256']==digest([*prefix,'policy',policy_sha256]) and actual['d1_challenge_sha256']==digest([*prefix,'d1-active',active]),'actual D1 binding or fresh challenge mismatch')
 return hashlib.sha256(response.content).hexdigest()

def observe(repo,ci,*,loader_reader=None,database_factory=None,http_get=None):
 """Genuine current normal-origin readback; no source of JSON/flags can replace it."""
 repo=Path(repo).resolve();source=head(repo);checked_ci(ci,source)
 loader=(loader_reader or (lambda:default_loader(repo)))();deps=fixed_dependencies(repo,loader)
 before_row,before_manifest,before_active=active_metadata(repo,database_factory)
 raw_response_sha256=observe_normal_response(source=source,version_id=ci['version_id'],
    build_input_sha256=ci['build_input_sha256'],policy_sha256=loader['policy_sha256'],
    active=before_active,http_get=http_get)
 row,manifest,active=active_metadata(repo,database_factory)
 require((row,manifest,active)==(before_row,before_manifest,before_active),'active D1 state raced during readback')
 require(head(repo)==source and fixed_dependencies(repo,(loader_reader or (lambda:default_loader(repo)))())==deps,'loader or source changed during readback')
 from .publisher import logical_manifest
 return {'schema':'NEW_A_OPERATIONAL_OBSERVATION_V1','observed_at':now().isoformat(),'source_commit':source,'version_id':ci['version_id'],'build_input_sha256':ci['build_input_sha256'],'dependencies':deps,'d1_active_sha256':active,'active_as_of':manifest['as_of'],'active_revision':row['revision'],'active_dataset_id':row['dataset_id'],'active_source_version':row['source_version'],'active_manifest_sha256':row['manifest_sha256'],'active_logical_manifest_sha256':digest(logical_manifest(manifest)),'raw_response_sha256':raw_response_sha256,'owner_http_observed':False,'authenticated_nonowner_observed':False,'authentication_probe':False,'management_deployment_observed':False,'traffic_percentages_observed':False,'final_worker_artifact_sha256_observed':False}

def historical_review(repo,value,*,activation_path=None):
 """Replay the genuine old V1 audit in its historical source view only."""
 evidence=value['owner_acceptance'];_,record=ca.load_reference(repo,evidence['continuing_acceptance'],'records');source=record['source_commit']
 original=Path(activation_path) if activation_path is not None else private_root(repo)/'activation.json'
 original_bytes=original.read_bytes()
 require(json.loads(original_bytes.decode('utf-8-sig'))==value,'historical activation differs from the reviewed value')
 with tempfile.TemporaryDirectory(prefix='new-a-historical-review-') as name:
  view=Path(name);private=private_root(view);private.mkdir(parents=True)
  shutil.copytree(ca.root(repo),ca.root(view))
  for path in ca.AUTH_FILES:
   blob=git(repo,'show',source+':'+path);pin=record['auth_source_hashes'][path]
   representations=[blob,blob.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
   matching=[raw for raw in representations if hashlib.sha256(raw).hexdigest()==pin]
   require(matching,'historical auth blob cannot reproduce its accepted checkout bytes')
   p=view/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(matching[0])
  p=view/'weak-early-beta-gate/wrangler.jsonc';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(git(repo,'show',source+':weak-early-beta-gate/wrangler.jsonc'))
  # Preserve exact Windows newline bytes for the old application CAS audit.
  activation=private/'activation.json';activation.write_bytes(original_bytes)
  ca.validate_evidence(evidence,view,_activation_path=activation,_historical_source=source)
 return {'source_commit':source,'acceptance':evidence['continuing_acceptance'],'auth_source_hashes':record['auth_source_hashes'],'owner_http_observed_at_historical_source':True,'current_owner_http_observed':False}

def issue(repo,*,authorization_reader,ci_reader,auth_review_reader,source_recovery,not_after,preflight,observer=observe):
 repo=Path(repo).resolve();source=head(repo);activation=private_root(repo)/'activation.json';before=read(activation);before_hash=file_sha(activation)
 require('operational_admission' not in before,'existing finite admission must be reconciled')
 require(before.get('active') is True and before.get('external_actions_approved') is True and before.get('strategy')=='A_BASE','existing owner activation unavailable')
 require(all(callable(x) for x in [authorization_reader,ci_reader,auth_review_reader,preflight]),'trusted host readers required')
 authority=authorization_reader(source)
 require(authority.get('schema')=='CODEX_TRUSTED_USER_FINITE_AUTHORIZATION_V1' and authority.get('chat_id') and authority.get('source_commit')==source and authority.get('target_date')==TARGET and authority.get('execution_date')==EXECUTION and authority.get('virtual_only') is True and authority.get('platform_signature_claimed') is False and authority.get('current_owner_http_required') is False and authority.get('unmeasured_owner_http_accepted') is True and len(authority.get('user_instruction_sha256',[]))>=1 and all(HEX.fullmatch(str(x)) for x in authority['user_instruction_sha256']),'finite host authorization unavailable')
 require(day()==EXECUTION and now()<stamp(not_after)<=min(now()+datetime.timedelta(hours=6),stamp(EXECUTION+'T23:59:59+09:00')),'finite execution window invalid')
 require(git(repo,'status','--porcelain=v1','--untracked-files=all')==b'','execution checkout dirty')
 historical=historical_review(repo,before);review=auth_review_reader(source)
 current_auth={p:file_sha(repo/p) for p in ca.AUTH_FILES}
 require(review.get('schema')=='NEW_A_REVIEWED_AUTH_DIAGNOSTIC_DELTA_V1' and review.get('source_commit')==source and review.get('historical_auth_source_hashes')==historical['auth_source_hashes'] and review.get('current_auth_source_hashes')==current_auth and review.get('only_health_diagnostic_changed') is True and HEX.fullmatch(str(review.get('reviewed_diff_sha256',''))) and review.get('existing_private_authorization_unchanged') is True,'independent exact auth delta review missing')
 ci=checked_ci(ci_reader(source),source);observation=observer(repo,ci)
 baseline_publication=read(private_root(repo)/'latest-publication.json')
 require(baseline_publication.get('as_of')=='2026-11-16' and baseline_publication.get('revision')==3 and baseline_publication.get('published') is True and baseline_publication.get('active_readback_verified') is True and observation['active_as_of']=='2026-11-16' and observation['active_revision']==3 and all(observation.get('active_'+key)==baseline_publication[key] for key in ['dataset_id','source_version','manifest_sha256']),'original Nov16 revision3 publication boundary changed')
 ready=preflight();require(ready.get('ok') is True and ready.get('head')==source,'normal preflight failed')
 record={'schema':SCHEMA,'target_date':TARGET,'execution_date':EXECUTION,'source_commit':source,'strategy':'A_BASE','target':ca.target(repo),'issued_at':now().isoformat(),'not_after':not_after,'authorization':authority,'historical_acceptance':historical,'auth_review':review,'current_auth_source_hashes':current_auth,'original_activation_sha256':before_hash,'ci':ci,'initial_observation':observation,'dependencies':observation['dependencies'],'source_recovery':source_recovery,'owner_http_observed':False,'authenticated_nonowner_observed':False,'platform_signature_claimed':False,'scope':'FINITE_NOV17_NATIVE_ONCE_WITH_PREDEPLOYED_CODE_ONLY_WORKER'}
 folder=area(repo)/digest(record);folder.mkdir(parents=True,exist_ok=False)
 (folder/'original-activation.json').write_bytes(activation.read_bytes());ca.immutable(folder/'record.json',record)
 require(file_sha(activation)==before_hash and head(repo)==source,'activation/source changed before finite apply')
 # Independent finite CAS, using the same exact arbitration/daily locks as ca.apply.
 runtime=repo/'.cache/weak_early_beta/daily_runtime';held=[]
 try:
  for lock in [runtime/'task-entry.lock',runtime/'daily.lock']:
   fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
   try:os.write(fd,digest(record).encode());os.fsync(fd)
   finally:os.close(fd)
   held.append(lock)
  for name in ['.cache/weak_early_beta/exit-reminder-runner.lock','.cache/weak_early_beta/exit-reminder.lock','weak_early_beta/state/exit-reminder.lock','weak_early_beta/state/daily_runtime/daily.lock']:
   require(not (repo/name).exists(),'reminder or legacy owner appeared before apply')
  require(file_sha(activation)==before_hash and head(repo)==source and now()<stamp(not_after),'activation/source/authority changed before CAS')
  value={**before,'operational_admission':ref(repo,folder/'record.json')};atomic_write(activation,value)
  require(read(activation)==value and head(repo)==source,'finite activation readback failed')
 finally:
  for lock in reversed(held):
   if lock.exists() and lock.read_text()==digest(record):lock.unlink()
 return value['operational_admission']

def local_record(repo,value=None):
 repo=Path(repo).resolve()
 if value is None and not (private_root(repo)/'activation.json').exists():return None
 value=read(private_root(repo)/'activation.json') if value is None else value
 reference=value.get('operational_admission')
 if reference is None:return None
 require(value.get('active') is True and value.get('external_actions_approved') is True and value.get('strategy')=='A_BASE','finite owner activation disabled')
 p,r=load_ref(repo,reference)
 require(r.get('schema')==SCHEMA and r.get('target_date')==TARGET and r.get('execution_date')==EXECUTION and r.get('source_commit')==head(repo) and r.get('target')==ca.target(repo) and r.get('strategy')=='A_BASE' and r.get('owner_http_observed') is False and r.get('authenticated_nonowner_observed') is False and r.get('platform_signature_claimed') is False,'finite scope changed')
 require(day()==EXECUTION and now()<stamp(r['not_after']),'finite admission expired')
 require(file_sha(p.parent/'original-activation.json')==r['original_activation_sha256'],'historical activation bytes changed')
 require({k:v for k,v in value.items() if k!='operational_admission'}==read(p.parent/'original-activation.json'),'historical owner acceptance modified')
 require({name:file_sha(repo/name) for name in ca.AUTH_FILES}==r['current_auth_source_hashes'],'reviewed auth source changed')
 require(git(repo,'status','--porcelain=v1','--untracked-files=all')==b'','finite execution checkout dirty')
 return r

def validate(repo,value=None,*,observer=observe):
 r=local_record(repo,value);require(r is not None,'finite admission missing');actual=observer(repo,r['ci'])
 require(actual['dependencies']==r['dependencies'] and actual['version_id']==r['initial_observation']['version_id'],'effective dependency or Worker changed')
 initial=r['initial_observation']
 if actual['active_revision']==3:
  require(actual['d1_active_sha256']==initial['d1_active_sha256'],'original D1 pointer changed')
 else:
  require(actual['active_revision']==4 and actual['active_as_of']==TARGET,'finite D1 watermark moved outside scope')
  expected=expected_finite_manifest(repo)
  require(actual['active_source_version']==expected['source_version'] and actual['active_logical_manifest_sha256']==digest(expected),'current D1 is not the exact finite published dataset')
 require(head(repo)==r['source_commit'],'source changed after observation');return r,actual

def expected_finite_manifest(repo):
 run=read(private_root(repo)/'latest-run.json');require(run.get('latest_session')==TARGET and run.get('strategy')=='A_BASE' and run.get('delayed_recovery'),'finite detected run required')
 snapshot_path=Path(run['snapshot_file']).resolve();folder=Path(run['bundle_directory']).resolve()
 require(snapshot_path.is_relative_to(private_root(repo)/'runs'/TARGET) and folder.is_relative_to(snapshot_path.parent),'finite bundle/snapshot escapes target run')
 snapshot=read(snapshot_path)
 from .delayed_recovery import delivery_context
 delivery_context(repo,snapshot)
 require(snapshot['payload_sha256']==run['snapshot_sha256'] and digest({k:v for k,v in snapshot.items() if k!='payload_sha256'})==snapshot['payload_sha256'],'finite snapshot changed')
 manifest=read(folder/'manifest.json');receipt=read(folder/'receipt.json')
 require(file_sha(folder/'manifest.json')==receipt['manifest_sha256'] and manifest.get('daily_snapshot_sha256')==snapshot['payload_sha256'] and manifest.get('source_version')==run.get('source_version')==receipt.get('source_version') and manifest.get('as_of')==TARGET,'finite immutable bundle differs')
 return manifest

def source_context(repo,args):
 r=local_record(repo)
 if r is None:return None
 require(getattr(args,'as_of',None)==TARGET and not getattr(args,'new_a_isolated',False) and getattr(args,'delayed_recovery',None),'finite admission cannot authorize another date or ordinary daily')
 from .delayed_recovery import executing_reference,runtime_context
 context=runtime_context(repo,executing_reference(repo,args.delayed_recovery))
 require(context['target_date']==TARGET and context['execution_date']==EXECUTION and Path(args.retained_acquisition).resolve()==Path(context['replay_directory']).resolve(),'finite retained execution differs')
 return r['source_recovery']

def action_context(repo,*,date,run=None,snapshot=None,publication=None,required=False):
 r=local_record(repo)
 if r is None:
  require(not required,'operational publication has no finite authority')
  return None
 require(date==TARGET,'finite admission cannot authorize another date')
 if run is not None:require(run.get('strategy')=='A_BASE' and run.get('latest_session')==TARGET and run.get('delayed_recovery'),'finite run context missing')
 if snapshot is not None:
  from .delayed_recovery import delivery_context
  delivery_context(repo,snapshot)
  require(snapshot.get('as_of')==TARGET,'finite snapshot date differs')
 if publication is not None:require(publication.get('operational_gate_continuity_verified') is True and publication.get('existing_owner_gate_verified') is False and publication.get('owner_http_observed') is False and publication.get('operational_admission')==read(private_root(repo)/'activation.json')['operational_admission'],'finite publication contract differs')
 return validate(repo)[0]

def publication_gate_verified(publication):
 if publication.get('operational_gate_continuity_verified') is True:
  return publication.get('existing_owner_gate_verified') is False and publication.get('owner_http_observed') is False and isinstance(publication.get('operational_admission'),dict)
 return publication.get('existing_owner_gate_verified') is True

def main(argv=None):
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['inspect']);args=parser.parse_args(argv);repo=Path(__file__).resolve().parents[2]
 r,actual=validate(repo)
 print(json.dumps({'schema':'NEW_A_FINITE_OPERATIONAL_READY_V1','target_date':TARGET,'execution_date':EXECUTION,'source_commit':r['source_commit'],'ci':r['ci'],'owner_http_observed':False,'observation':actual},sort_keys=True))
if __name__=='__main__':main()
