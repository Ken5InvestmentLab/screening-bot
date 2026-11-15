"""検証済み既存データをreadonly参照する初期準備。通信/有効化/設定変更なし。"""
import argparse,json
from pathlib import Path
from .files import private_root,read,atomic_write,file_sha,verify_bootstrap
ROOT=Path(__file__).resolve().parents[2]
def provision(root,paths):
 root=Path(root).resolve()
 if root.name!='new-a-private':raise ValueError('dedicated new-A root required')
 if (root/'bootstrap/manifest.json').exists():raise ValueError('existing bootstrap retained; compare rather than overwrite')
 values={name:Path(value).resolve() for name,value in paths.items()}
 if set(values)!={'seed','calendar','history_input','presentation','quotes'}:raise ValueError('all verified inputs required')
 history=read(values['history_input']);seed=read(values['seed']);calendar=read(values['calendar']);presentation=read(values['presentation'])
 if calendar[:len(seed['calendar'])]!=seed['calendar'] or history['calendar']!=seed['calendar'] or len(history['episodes'])!=len(presentation['rows']) or presentation.get('schema')!='A_LEGACY_UI_INPUT_V1':raise ValueError('historical inputs do not share the verified cohort')
 if history['source_hashes']['quotesSQLite']!=file_sha(values['quotes']):raise ValueError('frozen quote evidence mismatch')
 manifest={'schema':'NEW_A_PRIVATE_BOOTSTRAP_V1','strategy':'A_BASE','code_hashes':{name:file_sha(Path(__file__).parent/name) for name in ['features.py','monitor.py']},'files':{name:{'path':str(p),'external_read_only':True,'sha256':file_sha(p)} for name,p in values.items()},'source_version':history['source_version']}
 atomic_write(root/'bootstrap/manifest.json',manifest);verify_bootstrap(root)
 activation=root/'activation.json'
 if not activation.exists():atomic_write(activation,{'schema':'NEW_A_OWNER_ACTIVATION_V1','strategy':'A_BASE','active':False,'external_actions_approved':False,'owner_acceptance':{}})
 return {'schema':'NEW_A_PROVISION_RECEIPT_V1','bootstrap_verified':True,'historical_episodes':len(history['episodes']),'source_version':history['source_version'],'active':False,'input_files_modified':0,'external_sends':0,'secrets_read':0,'github_writes':0}
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--root',default=str(private_root(ROOT)))
 for name in ['seed','calendar','history-input','presentation','quotes']:p.add_argument('--'+name,required=True)
 args=p.parse_args(argv);receipt=provision(args.root,{name:getattr(args,name) for name in ['seed','calendar','history_input','presentation','quotes']});print(json.dumps(receipt));return receipt
if __name__=='__main__':main()
