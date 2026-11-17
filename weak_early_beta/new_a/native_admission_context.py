"""One bound Nov17 source-only continuation observed on actual Nov18.

No issuer, credential loader, SQL executor or sender. Legacy Nov16 contracts
remain separate. Only the normal owning root can begin this private context.
"""
import argparse,datetime,json,re,shutil
from pathlib import Path
from .files import read,file_sha,private_root
from . import delayed_recovery as d
from .native_recovery import inspect_source_evidence

KIND='NATIVE_ADMISSION_EXECUTION_V1'
TARGET='2026-11-17'
EXECUTION='2026-11-18'

def require(value,reason):
 if not value:raise ValueError('Native admission context: '+reason)

def within(root,path):
 root=Path(root).resolve();p=Path(path).resolve();require(p!=root and p.is_relative_to(root),'private path escapes');return p

def record_for_consumed(repo,path):
 repo=Path(repo).resolve();rt=d.runtime(repo);p=within(rt,path)
 require(re.fullmatch(r'native-admission-once-[a-f0-9]{64}\.json\.consumed',p.name) and p.parent==rt,'private consumed admission required')
 c=read(p);require(c.get('schema')=='CLOUD_NATIVE_ADMISSION_CONSUMED_V1','consumed audit schema differs')
 original_claim=Path(str(p).removesuffix('.consumed'));claim=read(original_claim)
 require(all(c.get(k)==claim.get(k) for k in ['record','invocation','original_run_id']) and claim.get('schema')=='CLOUD_NATIVE_ADMISSION_ONCE_V1','one-shot claim differs')
 rp=within(rt/'native-admission-continuations',c['record_file']);r=read(rp)
 require(rp.name=='record.json' and rp.parent.name==c['record'] and file_sha(rp)==c['record_file_sha256'],'issued record bytes differ')
 require(r.get('schema')=='CLOUD_NATIVE_ADMISSION_CONTINUATION_V1' and r.get('service')=='tentei-kyokuchi-cloud' and r.get('strategy')=='A_BASE' and r.get('date')==TARGET and r.get('execution_date')==EXECUTION and r.get('head')==d.head(repo) and r.get('platform_signature_claimed') is False and r.get('automatic_retry_counter_reset') is False,'source/target/execution scope differs')
 require(Path(r['repo']).resolve()==repo and Path(r['runtime']).resolve()==rt,'record repository/runtime differs')
 require(d.jst_day()==EXECUTION,'actual execution day changed')
 expected=d.target(repo);actual=r.get('target',{})
 require(all(actual.get(k)==v for k,v in expected.items()),'service/database target differs')
 require(file_sha(private_root(repo)/'activation.json')==r['activation_sha256'],'accepted source changed')
 proof=r['proof'];source=r['source']
 require(proof['original_run_id']==c['original_run_id'] and source['original_run_id']==c['original_run_id'] and source['date']==TARGET and source.get('inspection_wrote_or_sent') is False and source.get('network_fallback') is False,'original source scope differs')
 input_path=within(rt,proof['original_input']);original=read(input_path)
 require(file_sha(input_path)==proof['original_input_sha256'] and original['startedAt']==c['original_run_id'] and original['date']==TARGET,'immutable input differs')
 key=re.sub(r'[^0-9TZ-]','',original['startedAt'])
 require(file_sha(rt/f'recovery-{key}.json')==proof['reservation_sha256'],'original automatic reservation differs')
 original_folder=rt/('daily-'+original['startedAt'].replace(':','-').replace('.','-'))
 stopped_folder=rt/('daily-'+proof['stopped_run_id'].replace(':','-').replace('.','-'))
 require(file_sha(original_folder/'result.json')==proof['original_result_sha256'] and file_sha(stopped_folder/'result.json')==proof['stopped_result_sha256'],'preserved failure records differ')
 return p,c,r,rp,original

def require_accepted(repo):
 from .run import require_activation
 require_activation(private_root(repo),repo)

def begin(repo,consumed,*,root_pid,started_at):
 repo=Path(repo).resolve();p,c,r,rp,original=record_for_consumed(repo,consumed)
 require(d.now()<d.stamp(r['expires_at']) and d.now()-d.stamp(r['external']['at'])<datetime.timedelta(minutes=5),'admission or readback expired before start')
 require(c.get('root_pid')==root_pid and c.get('new_run_id')==started_at and root_pid>0,'claimed root differs')
 require((d.runtime(repo)/'daily.lock').read_text(encoding='utf8')==started_at,'root does not own daily lock')
 invoked=read(d.runtime(repo)/('daily-'+started_at.replace(':','-').replace('.','-'))/'invoked.json')
 require(invoked.get('identity')=='CLOUD_RUNNER_INVOKED_V1' and invoked.get('pid')==root_pid and invoked.get('startedAt')==started_at and invoked.get('date')==TARGET and invoked.get('executionDate')==EXECUTION and invoked.get('originalRunId')==original['startedAt'],'actual normal invocation differs')
 identity=d.process_identity(root_pid);require(identity['alive'],'root is not alive')
 created=datetime.datetime.fromtimestamp((identity['created_filetime']-116444736000000000)/10000000,datetime.timezone.utc)
 require(-5<=(d.stamp(started_at)-created).total_seconds()<=30 and d.jst_day(d.stamp(started_at))==EXECUTION,'root birth/time differs')
 require_accepted(repo)
 actual=inspect_source_evidence(repo,d.runtime(repo),original,TARGET,r['source']['previous_source_sha256'])
 require(actual==r['source'],'original retained source changed after issuance')
 directory=rp.parent;replay=directory/'replay-acquisition';replay.mkdir(exist_ok=False)
 source=within(d.runtime(repo),actual['directory'])
 for item in source.rglob('*'):
  require(not item.is_symlink() and item.resolve().is_relative_to(source),'retained artifact escapes source')
  destination=replay/item.relative_to(source)
  if item.is_dir():destination.mkdir(exist_ok=False)
  else:
   require(item.is_file(),'unexpected retained artifact');destination.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(item,destination);require(file_sha(item)==file_sha(destination),'replay copy differs')
 running={'schema':KIND,'consumed':d.ref(repo,p),'record_file':str(rp.relative_to(repo)),'record_sha256':file_sha(rp),'root_pid':root_pid,'root_created_filetime':identity['created_filetime'],'started_at':started_at,'target_date':TARGET,'execution_date':EXECUTION,'replay_folder':str(replay.relative_to(repo)),'started_at_actual':True}
 target=directory/'executing.json';d.immutable(target,running)
 return {**d.ref(repo,target),'kind':KIND}

def runtime_context(repo,reference):
 repo=Path(repo).resolve();area=d.runtime(repo)/'native-admission-continuations'
 p,running=d.load_ref(repo,reference,area)
 require(reference.get('kind')==KIND and p.name=='executing.json' and running.get('schema')==KIND,'typed native execution reference required')
 cp,c,r,rp,original=record_for_consumed(repo,within(repo,repo/running['consumed']['path']))
 require(file_sha(cp)==running['consumed']['sha256'] and rp.parent==p.parent and running['record_file']==str(rp.relative_to(repo)) and file_sha(rp)==running['record_sha256'],'running/consumed/record bytes differ')
 require(running['root_pid']==c['root_pid'] and running['started_at']==c['new_run_id'] and running['target_date']==TARGET and running['execution_date']==EXECUTION and running.get('started_at_actual') is True,'running root scope differs')
 require((d.runtime(repo)/'daily.lock').read_text(encoding='utf8')==running['started_at'],'root lock ownership changed')
 identity=d.process_identity(running['root_pid']);require(identity['alive'] and identity['created_filetime']==running['root_created_filetime'],'root ended or PID reused')
 current=read(d.runtime(repo)/'daily-latest.json')
 require(current.get('identity')=='WEAK_EARLY_CLOUD_DAILY_V1' and current.get('pid')==running['root_pid'] and current.get('startedAt')==running['started_at'] and current.get('date')==TARGET and current.get('executionDate')==EXECUTION and not current.get('completedAt'),'latest owning run differs or ended')
 replay=within(p.parent,repo/running['replay_folder']);require(replay==p.parent/'replay-acquisition' and replay.is_dir(),'replay directory differs')
 active=r['external']['d1']['active'];require(len(active)==1 and active[0]['as_of']<TARGET,'original pointer boundary differs')
 return {**r,'target_date':TARGET,'execution_date':EXECUTION,'replay_directory':str(replay),'reference':reference,'root_pid':running['root_pid'],'started_at':running['started_at'],'expected_revision':active[0]['revision'],'expected_dataset_id':active[0]['dataset_id']}

def executing_reference(repo,path):
 p=within(d.runtime(repo)/'native-admission-continuations',path);reference={**d.ref(repo,p),'kind':KIND};runtime_context(repo,reference);return reference

def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['begin']);parser.add_argument('--record',required=True);parser.add_argument('--root-pid',type=int,required=True);parser.add_argument('--started-at',required=True);args=parser.parse_args()
 repo=Path(__file__).resolve().parents[2];print(json.dumps(begin(repo,args.record,root_pid=args.root_pid,started_at=args.started_at),sort_keys=True))
if __name__=='__main__':main()
