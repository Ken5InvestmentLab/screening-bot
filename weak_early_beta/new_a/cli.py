"""新A専用publish/notify入口。既存タスク・通知先・認証を変更しない。"""
import argparse,datetime,json,os
from pathlib import Path
from .files import private_root,read,atomic_write
from .run import require_activation
from .publisher import WranglerD1,LocalD1,publish_bundle
from .notifications import notify_day
ROOT=Path(__file__).resolve().parents[2]
def publish(root,db,*,owner_verified=False):
 run=read(Path(root)/'latest-run.json')
 if run.get('strategy')!='A_BASE' or not run.get('detection_executed'):raise ValueError('completed New A detection required')
 receipt=publish_bundle(db,run['bundle_directory']);receipt['existing_owner_gate_verified']=owner_verified
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
   require_activation(root,ROOT);db=WranglerD1(ROOT,root/'sql',execute=True)
  else:db=LocalD1(root/'isolated-owner-d1.sqlite',ROOT/'weak-early-beta-gate/schema/new-a-private.sql')
  try:receipt=publish(root,db,owner_verified=args.remote)
  finally:db.close()
 else:
  require_activation(root,ROOT)
  if not args.dry_run and args.date!=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat():raise ValueError('same actual JST day required')
  receipt=notify_day(root,date=args.date,dry_run=args.dry_run,report_url=args.report_url or os.environ.get('WEAK_EARLY_BETA_REPORT_URL',''))
 print(json.dumps(receipt,ensure_ascii=False));return receipt
if __name__=='__main__':main()
