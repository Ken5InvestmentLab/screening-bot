"""One stopped Nov16 run, distinct from ordinary Nov17 operation.

Host readers establish primary intent and actual stop/remote/source observations.
No approval-file CLI, credential, SQL, network or sender is provided here.
"""
import datetime,hashlib,json,os,re,subprocess
from pathlib import Path
from .files import read,encode,digest,file_sha,private_root
from .continuing_acceptance import primary_message,immutable,target

SCHEMA='NEW_A_DELAYED_STOPPED_RUN_V1'
SCOPE='ONE_STOPPED_NEW_A_20261116_V1'
TARGET='2026-11-16'
EXECUTION='2026-11-17'
KIND='DELAYED_SCHEDULED_OBSERVATION'
ORIGINAL='2026-11-16T13:28:10.435Z'

def now():return datetime.datetime.now(datetime.timezone.utc)
def jst_day(value=None):return (value or now()).astimezone(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
def head(repo):return subprocess.check_output(['git','--no-optional-locks','rev-parse','HEAD'],cwd=repo,text=True).strip()
def require(value,reason):
 if not value:raise ValueError(reason)
def stamp(value):
 t=datetime.datetime.fromisoformat(value.replace('Z','+00:00'));require(t.tzinfo is not None,'timezone required');return t
def base(repo):return private_root(repo)/'delayed-recovery'
def runtime(repo):return Path(repo).resolve()/'.cache/weak_early_beta/daily_runtime'
def inside(repo,relative,area):
 p=(Path(repo).resolve()/relative).resolve();require(p.is_relative_to(area.resolve()),'recovery path escapes its fixed area');return p
def ref(repo,p):return dict(path=str(p.relative_to(Path(repo).resolve())),sha256=file_sha(p))
def load_ref(repo,value,area):
 p=inside(repo,value.get('path',''),area);require(p.is_file() and file_sha(p)==value.get('sha256'),'recovery reference bytes changed');return p,read(p)
def process_identity(pid):
 """Query only Windows exit/creation metadata, never command memory or secrets."""
 import ctypes
 require(os.name=='nt','real Windows process inspector required')
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p
 kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
 kernel.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.POINTER(ctypes.c_ulonglong)]*4)];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
 handle=kernel.OpenProcess(0x1000,False,pid);require(handle,'process identity unavailable')
 try:
  code=ctypes.c_ulong();created=ctypes.c_ulonglong();exited=ctypes.c_ulonglong();system=ctypes.c_ulonglong();user=ctypes.c_ulonglong()
  require(kernel.GetExitCodeProcess(handle,ctypes.byref(code)) and kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(system),ctypes.byref(user)),'process identity unavailable')
  return dict(alive=code.value==259,created_filetime=created.value)
 finally:kernel.CloseHandle(handle)
def preserve_bytes(path,raw):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

def verify_original(repo,record,*,require_lock=True):
 original=record['original'];folder=inside(repo,original['folder'],runtime(repo));r=read(folder/'result.json')
 require(original['started_at']==ORIGINAL and r.get('identity')=='WEAK_EARLY_CLOUD_DAILY_V1' and r.get('date')==TARGET and r.get('startedAt')==original['started_at'] and r.get('stage')=='detection' and not r.get('completedAt') and r.get('ok') is False,'original stopped run identity differs')
 require(r.get('pid') in original.get('processes',[]) and r.get('new_a',{}).get('entry')=='new-a-verified-daily-v1','original is not New A')
 require(not any(r.get(k) for k in ['deployment','notifications','fundamentals']),'original external stage outcome needs separate reconciliation')
 require(file_sha(folder/'result.json')==original['result_sha256'] and file_sha(runtime(repo)/'daily-latest.json')==original['result_sha256'],'original/latest result changed')
 acquisition=r.get('acquisitionEvidence',[]);require(len(acquisition)==1 and acquisition[0].get('attempt')==1 and Path(acquisition[0]['directory']).resolve()==inside(repo,record['source']['folder'],Path(repo)/'.cache/weak_early_beta'),'retained source is not the original run acquisition')
 require(not (private_root(repo)/'daily-live.sqlite').exists(),'committed monitor watermark requires separate recovery')
 for name in ['new-a-publish.process.json','notify.process.json','notify-preview.process.json']:
  require(not (folder/name).exists(),'publication or send stage already exists')
 if require_lock:
  lock=runtime(repo)/'daily.lock';require(lock.is_file() and file_sha(lock)==original['lock_sha256'] and lock.read_text().strip()==original['started_at'],'stopped lock owner changed')
 return folder

def verify_retained(repo,source,*,verify_previous=True):
 folder=inside(repo,source['folder'],Path(repo).resolve()/'.cache/weak_early_beta');m=read(folder/'manifest.json')
 require(file_sha(folder/'manifest.json')==source['manifest_sha256'] and m.get('identity')=='CLOUD_ACQUISITION_V1' and m.get('status')=='acquiring','retained acquisition identity/status changed')
 context=m['context'];require(context.get('date')==TARGET and context.get('period')=='5y' and context.get('previousSourceSha256')==source['previous_csv_sha256'],'retained original date/period/source mismatch')
 require(m.get('requests')==47 and len(set(context['tickers']))==len(context['tickers'])==source['universe_count'],'retained request/universe mismatch')
 inventory=[];seen=[]
 for sequence in range(1,48):
  found=list(folder.glob(f'{sequence:05d}-*.json'));require(len(found)==1,'retained receipt absent/ambiguous');p=found[0];saved=read(p);request=saved.get('request');key=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()[:20]
  require(p.stem==f'{sequence:05d}-{key}' and request.get('kind')=='batch' and not saved.get('error'),'retained request identity/error mismatch')
  kwargs=request.get('kwargs',{});require(kwargs.get('period')==context['period'] and kwargs.get('interval')=='1d' and kwargs.get('actions') is True and kwargs.get('repair') is True and kwargs.get('auto_adjust') is False,'original acquisition rules differ')
  seen.extend(request.get('tickers',[]))
  packet=p.with_suffix('.pkl');require(packet.is_file() and file_sha(packet)==saved.get('sha256'),'retained packet absent/corrupt')
  inventory.append(dict(receipt=p.name,receipt_sha256=file_sha(p),packet_sha256=saved['sha256']))
 require(len(list(folder.glob('*.pkl')))==47 and digest(inventory)==source['inventory_sha256'],'retained inventory changed')
 require(len(seen)==len(set(seen)) and set(seen)==set(context['tickers']),'retained requests do not cover the original universe exactly')
 if verify_previous:
  csv=Path(repo)/'.cache/weak_early_beta/tse_daily.csv';quality=csv.with_suffix('.source-quality.json')
  require(file_sha(csv)==source['previous_csv_sha256']==read(quality).get('daily_sha256') and file_sha(quality)==source['previous_quality_sha256'],'previous corpus/quality changed')
 return folder

def issue(repo,plan,*,primary_reader,evidence_reader,decision_reader,authority):
 repo=Path(repo).resolve();require(plan.get('scope')==SCOPE and plan.get('target_date')==TARGET and plan.get('execution_date')==EXECUTION and jst_day()==EXECUTION,'one original delayed target only')
 require(plan.get('source_commit')==head(repo) and plan.get('target')==target(repo),'recovery source or database changed')
 until=stamp(plan['not_after']);require(now()<until<=now()+datetime.timedelta(hours=1) and jst_day(until)==EXECUTION,'finite recovery authority expired/overbroad')
 owner=primary_message(plan['owner_message'],primary_reader,authority)
 require(callable(decision_reader) and callable(evidence_reader),'actual host readers required')
 decision=decision_reader(owner['message_id'])
 require(decision.get('schema')=='NEW_A_HOST_DELAYED_RUN_DECISION_V1' and decision.get('decision')=='ONE_DELAYED_TARGET_RUN_WITH_RESULT_DELIVERY' and decision.get('scope')==SCOPE and decision.get('message_id')==owner['message_id'] and decision.get('text_sha256')==owner['text_sha256'] and decision.get('source_commit')==plan['source_commit'] and decision.get('target')==plan['target'] and decision.get('platform_signature_claimed') is False,'host reviewed scope/intent differs')
 evidence=evidence_reader(plan['evidence']['id']);require(digest(evidence)==plan['evidence']['sha256'],'actual evidence bytes differ')
 require(evidence.get('schema')=='NEW_A_HOST_STOPPED_RUN_OBSERVATION_V1' and evidence.get('platform_signature_claimed') is False and evidence.get('synthetic') is not True and evidence.get('source_commit')==plan['source_commit'] and evidence.get('target')==plan['target'],'stop observation provenance differs')
 require(now()-datetime.timedelta(minutes=10)<=stamp(evidence['observed_at'])<=now(),'fresh stop/remote readback required')
 require(evidence.get('original')==plan['original'] and evidence.get('retained_source')==plan['source'] and isinstance(plan['original'].get('processes'),list) and len(set(plan['original']['processes']))>=1 and all(type(v) is int and v>0 for v in plan['original']['processes']),'actual stop/source observation is not bound to this original run')
 require(evidence.get('original_processes_absent') is True and evidence.get('nov16_D1_datasets')==0 and evidence.get('nov16_D1_parts')==0 and evidence.get('result_notifications')==0 and evidence.get('destination_histories_complete') is True and evidence.get('start_message_id')=='1571879697464299631','ambiguous or existing external effect')
 require(evidence.get('active_revision')==plan['expected_revision'] and evidence.get('active_dataset_id')==plan['expected_dataset_id'] and evidence.get('active_as_of')<TARGET,'watermark/revision conflict')
 record={k:plan[k] for k in ['scope','target_date','execution_date','source_commit','target','original','source','expected_revision','expected_dataset_id','not_after']}
 record.update(schema=SCHEMA,owner_message=owner,host_decision=decision,observation=evidence,issued_at=now().isoformat(),platform_signature_claimed=False,issuance='HOST_VERIFIED_DELAYED_RUN_NOT_PLATFORM_SIGNATURE')
 verify_original(repo,record);verify_retained(repo,record['source']);pin=digest(record);p=base(repo)/'records'/(pin+'.json');immutable(p,record);return ref(repo,p)

def verify(repo,reference,*,administration=True):
 p,r=load_ref(repo,reference,base(repo)/'records');require(p.stem==digest(r) and r.get('schema')==SCHEMA and r.get('scope')==SCOPE and r.get('target_date')==TARGET and r.get('execution_date')==EXECUTION and r.get('source_commit')==head(repo) and r.get('target')==target(repo) and r.get('platform_signature_claimed') is False,'delayed run contract mismatch')
 require(jst_day()==EXECUTION,'delayed operation crossed its real execution day')
 if administration:require(now()<stamp(r['not_after']),'delayed administration expired')
 return p,r

def claim_stopped(repo,reference,invocation,*,preflight,processes_absent,activation_validator):
 """Only a trusted host/entry may supply real inspectors; no public flag CLI."""
 repo=Path(repo).resolve();p,r=verify(repo,reference);require(all(callable(x) for x in [preflight,processes_absent,activation_validator]),'normal inspectors required')
 require((runtime(repo)/'task-entry.lock').read_text()==invocation,'normal launch arbitration required')
 require(processes_absent(r['original']['processes']) is True,'original processes not proven absent')
 verify_original(repo,r);verify_retained(repo,r['source']);operation=base(repo)/'operations'/p.stem;operation.mkdir(parents=True,exist_ok=True)
 claim=dict(schema='NEW_A_DELAYED_RUN_CLAIM_V1',contract=reference,invocation=invocation,claimed_at=now().isoformat(),original_result_sha256=r['original']['result_sha256'])
 immutable(base(repo)/'original-claims'/(r['original']['result_sha256']+'.json'),claim)
 immutable(operation/'claim.json',claim)
 original=runtime(repo)/'daily.lock';dest=operation/'original-daily.lock';require(not dest.exists() and file_sha(original)==r['original']['lock_sha256'],'stale lock changed before archival')
 preserve_bytes(operation/'original-result.json',(runtime(repo)/'daily-latest.json').read_bytes())
 # Fixed, resolved same-repository paths; preserve rather than delete the lock.
 require(original.resolve().is_relative_to(repo) and dest.resolve().is_relative_to(repo),'lock archival escaped repository');verify(repo,reference);os.replace(original,dest)
 require(file_sha(dest)==r['original']['lock_sha256'],'archived original lock readback differs')
 try:
  ready=preflight();require(ready.get('ok') is True and ready.get('head')==r['source_commit'] and Path(ready.get('repository','')).resolve()==repo,'normal preflight not ready')
  activation_validator(repo)
 except BaseException:
  # The failed claim remains immutable; restore only the known original lock
  # while this entry still owns arbitration. Never unlock an ambiguous failure.
  if (runtime(repo)/'task-entry.lock').read_text()==invocation and not original.exists():preserve_bytes(original,dest.read_bytes())
  raise
 return ref(repo,operation/'claim.json')

def begin(repo,claim_reference,*,root_pid,started_at):
 p,claim=load_ref(repo,claim_reference,base(repo)/'operations');_,r=verify(repo,claim['contract']);require(claim.get('schema')=='NEW_A_DELAYED_RUN_CLAIM_V1' and p.name=='claim.json' and p.parent.name==Path(claim['contract']['path']).stem,'delayed claim identity differs')
 require((runtime(repo)/'daily.lock').read_text()==started_at and isinstance(root_pid,int) and root_pid>0,'normal root lock ownership required')
 require(stamp(started_at)<=now() and jst_day(stamp(started_at))==EXECUTION,'real root observation time invalid')
 require((runtime(repo)/'task-entry.lock').read_text()==claim['invocation'],'claim entry no longer owns arbitration')
 identity=process_identity(root_pid);require(identity['alive'],'normal root is not alive')
 created=datetime.datetime.fromtimestamp((identity['created_filetime']-116444736000000000)/10000000,datetime.timezone.utc)
 require(-5<=(stamp(started_at)-created).total_seconds()<=30,'root creation does not match actual run start')
 import shutil
 source=verify_retained(repo,r['source']);replay=p.parent/'replay-acquisition';replay.mkdir(exist_ok=False)
 for item in source.iterdir():
  if item.is_file():
   shutil.copyfile(item,replay/item.name);require(file_sha(replay/item.name)==file_sha(item),'retained replay copy differs')
 running=dict(schema='NEW_A_DELAYED_RUN_EXECUTING_V1',claim=claim_reference,contract=claim['contract'],root_pid=root_pid,root_created_filetime=identity['created_filetime'],started_at=started_at,execution_date=EXECUTION,target_date=TARGET,started_at_actual=True,replay_folder=str(replay.relative_to(Path(repo).resolve())))
 immutable(p.parent/'executing.json',running);return ref(repo,p.parent/'executing.json')

def runtime_context(repo,reference):
 p,running=load_ref(repo,reference,base(repo)/'operations');require(p.name=='executing.json' and running.get('schema')=='NEW_A_DELAYED_RUN_EXECUTING_V1','executing recovery required')
 _,record=verify(repo,running['contract'],administration=False);cp,claim=load_ref(repo,running['claim'],base(repo)/'operations')
 require(cp.parent==p.parent and claim.get('contract')==running['contract'] and p.parent.name==Path(running['contract']['path']).stem,'running/claim binding differs')
 require((runtime(repo)/'daily.lock').read_text()==running['started_at'],'recovery root no longer owns normal lock')
 require(read(base(repo)/'original-claims'/(record['original']['result_sha256']+'.json'))==claim,'original run claim changed')
 identity=process_identity(running['root_pid']);require(identity['alive'] and identity['created_filetime']==running['root_created_filetime'],'recovery root ended or PID reused')
 require(file_sha(p.parent/'original-daily.lock')==record['original']['lock_sha256'] and file_sha(p.parent/'original-result.json')==record['original']['result_sha256'],'preserved stopped input differs')
 replay=inside(repo,running['replay_folder'],p.parent);require(replay==p.parent/'replay-acquisition' and replay.is_dir(),'replay directory escaped claim')
 return {**record,'replay_directory':str(replay),'reference':reference,'root_pid':running['root_pid'],'started_at':running['started_at']}

def classify(repo,reference,*,as_of,observed_at):
 context=runtime_context(repo,reference);require(as_of==context['target_date'] and jst_day(stamp(observed_at))==context['execution_date'] and stamp(observed_at)<=now(),'real delayed observation/target mismatch')
 return context

def executing_reference(repo,path):
 p=Path(path).resolve();require(p.is_relative_to(base(repo)/'operations') and p.name=='executing.json','private executing recovery path required');reference=ref(repo,p);runtime_context(repo,reference);return reference

def assert_publication_pointer(context,pointer):
 require(pointer and pointer['revision']==context['expected_revision'] and pointer['dataset_id']==context['expected_dataset_id'],'delayed publication revision/watermark changed')
 manifest=json.loads(pointer['manifest_json']);require(manifest['as_of']<context['target_date'],'delayed publication would regress or duplicate a target day')


def delivery_context(repo,snapshot,publication=None):
 require(snapshot.get('observation_kind')==KIND and snapshot.get('new_live_signals')==0,'distinct delayed observation required')
 context=classify(repo,snapshot.get('delayed_recovery',{}),as_of=snapshot.get('as_of'),observed_at=snapshot.get('observed_at'))
 require(digest({k:v for k,v in snapshot.items() if k!='payload_sha256'})==snapshot.get('payload_sha256'),'delayed snapshot hash changed')
 events=snapshot.get('events',[])
 for event in events:
  flagged=event.get('is_delayed_scheduled_signal') is True
  if event.get('observation_kind')==KIND:
   require(event.get('session')==context['target_date'] and event.get('is_new_live_signal') is False and flagged==(event.get('kind')=='WATCH_STARTED'),'delayed event reclassification rejected')
  else:require(not flagged and not event.get('is_new_live_signal'),'unrelated catchup cannot be delivered')
 require(sum(e.get('is_delayed_scheduled_signal') is True for e in events)==snapshot.get('delayed_scheduled_signals'),'delayed delivery count changed')
 if publication is not None:
  require(publication.get('delayed_recovery')==snapshot['delayed_recovery'] and publication.get('snapshot_sha256')==snapshot['payload_sha256'] and publication.get('revision')==context['expected_revision']+1 and publication.get('as_of')==context['target_date'] and publication.get('active_readback_verified') is True and publication.get('published') is True and publication.get('existing_owner_gate_verified') is True,'delayed publication receipt mismatch')
 return context

def assert_published_pointer(context,pointer,publication):
 require(pointer and pointer['revision']==context['expected_revision']+1==publication['revision'] and pointer['dataset_id']==publication['dataset_id'],'active pointer changed after delayed publication')
 manifest=json.loads(pointer['manifest_json']);require(manifest['as_of']==context['target_date'] and manifest['daily_snapshot_sha256']==publication['snapshot_sha256'] and manifest['source_version']==publication['source_version'],'active delayed snapshot changed')


def entry_command(argv=None):
 """Inspect/consume an already host-issued private contract; never issue approval."""
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['inspect','inspect-claim','claim','begin']);parser.add_argument('--record',required=True);parser.add_argument('--invocation');parser.add_argument('--config');parser.add_argument('--acceptance-application');parser.add_argument('--root-pid',type=int);parser.add_argument('--started-at');args=parser.parse_args(argv)
 repo=Path(__file__).resolve().parents[2];p=Path(args.record).resolve()
 if args.command=='begin':
  reference=ref(repo,p);result=begin(repo,reference,root_pid=args.root_pid,started_at=args.started_at)
 elif args.command=='inspect-claim':
  require(p.is_relative_to(base(repo)/'operations') and p.name=='claim.json','private claim required');claim=read(p);_,r=verify(repo,claim['contract']);require(read(base(repo)/'original-claims'/(r['original']['result_sha256']+'.json'))==claim and file_sha(p.parent/'original-result.json')==r['original']['result_sha256'] and file_sha(p.parent/'original-daily.lock')==r['original']['lock_sha256'],'claim audit differs');result=dict(claim=ref(repo,p),target_date=r['target_date'],execution_date=r['execution_date'],original_run_id=r['original']['started_at'])
 elif args.command=='inspect':
  require(p.is_relative_to(base(repo)/'records'),'private issued record required');reference=ref(repo,p);_,r=verify(repo,reference);verify_original(repo,r);verify_retained(repo,r['source']);result=dict(contract=reference,target_date=r['target_date'],execution_date=r['execution_date'])
 else:
  require(p.is_relative_to(base(repo)/'records') and args.config and args.invocation and args.acceptance_application,'formal private claim inputs required');reference=ref(repo,p)
  application=Path(args.acceptance_application).resolve();require(application.is_relative_to(private_root(repo)/'continuing-acceptance'),'private accepted-source application required');issued=read(application)
  from . import continuing_acceptance as ca
  def normal_preflight():
   node=read(Path(args.config))['nodePath']
   return json.loads(subprocess.check_output([node,str(repo/'scripts/windows/weak-early-beta-launch-preflight.mjs'),str(Path(args.config).resolve()),'--strategy','A_BASE'],cwd=repo,text=True,encoding='utf8'))
  def absent(pids):
   for pid in pids:
    try:
     if process_identity(pid)['alive']:return False
    except ValueError:
     # Only ERROR_INVALID_PARAMETER means no such PID. Access denied is uncertain.
     import ctypes
     if ctypes.get_last_error()!=87:return False
   return True
  def accepted(_):
   from .run import require_activation
   activation=read(private_root(repo)/'activation.json');previous=activation.get('owner_acceptance',{}).get('continuing_acceptance')
   ca.apply(repo,issued,preflight=normal_preflight,previous_acceptance=previous,arbitration_owner=args.invocation);require_activation(private_root(repo),repo)
  result=claim_stopped(repo,reference,args.invocation,preflight=normal_preflight,processes_absent=absent,activation_validator=accepted)
 print(encode(result));return result

if __name__=='__main__':entry_command()
