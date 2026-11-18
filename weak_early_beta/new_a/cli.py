"""新A専用publish/notify入口。既存タスク・通知先・認証を変更しない。"""
import argparse,datetime,json,os
from pathlib import Path
from .files import private_root,read,atomic_write
from .run import require_activation
from .publisher import WranglerD1,LocalD1,publish_bundle,pointer
from .notifications import notify_day
ROOT=Path(__file__).resolve().parents[2]
def remote_database(root):
 activation=read(Path(root)/'activation.json')
 node=read(ROOT/'.cache/weak_early_beta/daily-runner.config.json')['nodePath'] if activation.get('operational_admission') else 'node'
 return WranglerD1(ROOT,Path(root)/'sql',execute=True,node=node)
def publish(root,db,*,owner_verified=False,operational_verified=False):
 run=read(Path(root)/'latest-run.json')
 from .operational_admission import action_context
 admission=action_context(Path(root).resolve().parents[2],date=run.get('latest_session'),run=run,snapshot=read(run['snapshot_file']),required=True) if operational_verified else None
 if run.get('strategy')!='A_BASE' or not run.get('detection_executed'):raise ValueError('completed New A detection required')
 context=None
 if run.get('delayed_recovery'):
  from . import delayed_recovery as delayed
  repo=Path(root).resolve().parents[2];snapshot=read(run['snapshot_file'])
  context=delayed.delivery_context(repo,snapshot)
  if run['delayed_recovery']!=snapshot['delayed_recovery'] or not (owner_verified or admission):raise ValueError('approved delayed remote publication required')
  active=pointer(db)
  finite_duplicate=bool(admission and active and active['revision']==context['expected_revision']+1)
  if not finite_duplicate:delayed.assert_publication_pointer(context,active)
 else:finite_duplicate=False
 if finite_duplicate:
  from .publisher import verify_dataset,logical_manifest,publication_receipt
  from .operational_admission import expected_finite_manifest
  stored,manifest=verify_dataset(db,active['dataset_id'])
  if logical_manifest(manifest)!=expected_finite_manifest(Path(root).resolve().parents[2]):raise ValueError('finite partial publication differs')
  receipt=publication_receipt(active,manifest,active['revision'],True,db.external)
 else:receipt=publish_bundle(db,run['bundle_directory'],**({'expected_revision':context['expected_revision']} if context else {}))
 receipt['existing_owner_gate_verified']=owner_verified
 if admission:
  receipt.update(operational_gate_continuity_verified=True,owner_http_observed=False,operational_admission=read(Path(root)/'activation.json')['operational_admission'])
 if context:receipt['delayed_recovery']=run['delayed_recovery']
 if receipt['snapshot_sha256']!=run['snapshot_sha256'] or receipt['source_version']!=run['source_version']:raise ValueError('publication source mismatch')
 atomic_write(Path(root)/'latest-publication.json',receipt);return receipt
def main(argv=None):
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True);pub=sub.add_parser('publish');pub.add_argument('--remote',action='store_true');pub.add_argument('--local',action='store_true');n=sub.add_parser('notify');n.add_argument('--date',required=True);n.add_argument('--dry-run',action='store_true');n.add_argument('--report-url',default='')
 for command in ['prepare-release','prearm-release']:
  initial=sub.add_parser(command);initial.add_argument('--remote',action='store_true');initial.add_argument('--local',action='store_true');initial.add_argument('--approval-file');initial.add_argument('--code-manifest')
  if command=='prepare-release':initial.add_argument('--bundle',required=True);initial.add_argument('--expected-revision',type=int,default=0)
  else:initial.add_argument('--version-receipt',required=True);initial.add_argument('--expected-revision',type=int,required=True)
 args=p.parse_args(argv);root=private_root(ROOT)
 if args.command in ['prepare-release','prearm-release']:
  from . import release
  if args.remote==args.local:raise ValueError('choose one preparation target')
  if args.remote:
   if not args.approval_file or not args.code_manifest:raise ValueError('explicit preparation approval and code manifest required')
   approved=release.authorization(root,ROOT,args.approval_file,args.code_manifest);db=WranglerD1(ROOT,root/'sql',execute=True)
  else:approved={'kind':'LOCAL_SYNTHETIC_UNAPPROVED'};db=LocalD1(root/'isolated-owner-d1.sqlite',ROOT/'weak-early-beta-gate/schema/new-a-private.sql')
  try:receipt=release.prepare(root,db,args.bundle,approved,expected_revision=args.expected_revision) if args.command=='prepare-release' else release.prearm(root,db,args.version_receipt,approved,expected_revision=args.expected_revision)
  finally:db.close()
  print(json.dumps(receipt,ensure_ascii=False));return receipt
 if args.command=='publish':
  if args.remote==args.local:raise ValueError('choose one publication target')
  if args.remote:
   activated=require_activation(root,ROOT);db=remote_database(root)
  else:db=LocalD1(root/'isolated-owner-d1.sqlite',ROOT/'weak-early-beta-gate/schema/new-a-private.sql')
  try:receipt=publish(root,db,owner_verified=args.remote and not activated.get('operational_admission') if args.remote else False,operational_verified=args.remote and bool(activated.get('operational_admission')) if args.remote else False)
  finally:db.close()
 else:
  require_activation(root,ROOT)
  run=read(root/'latest-run.json')
  from .operational_admission import action_context
  action_context(ROOT,date=args.date,run=run,snapshot=read(run['snapshot_file']),publication=read(root/'latest-publication.json'))
  if run.get('delayed_recovery'):
   from . import delayed_recovery as delayed
   snapshot=read(run['snapshot_file']);publication=read(root/'latest-publication.json');context=delayed.delivery_context(ROOT,snapshot,publication)
   if args.date!=context['target_date']:raise ValueError('delayed notification target mismatch')
   db=remote_database(root)
   try:delayed.assert_published_pointer(context,pointer(db),publication)
   finally:db.close()
  elif not args.dry_run and args.date!=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat():raise ValueError('same actual JST day required')
  receipt=notify_day(root,date=args.date,dry_run=args.dry_run,report_url=args.report_url or os.environ.get('WEAK_EARLY_BETA_REPORT_URL',''))
 print(json.dumps(receipt,ensure_ascii=False));return receipt
if __name__=='__main__':main()
