"""既存CLIから呼ぶ新A本体。旧ledger/report/queueを呼ばない。"""
import datetime,hashlib,json,subprocess
from pathlib import Path
from .files import read,atomic_write,file_sha,digest,private_root,verify_bootstrap
from .pipeline import Pipeline
from .publication import build_snapshot
from .packet import prepare_packet
from .bundle import prepare_bundle
ENTRY='new-a-verified-daily-v1'
def verify_code_contract(manifest):
 for name in ['features.py','monitor.py']:
  if manifest.get('code_hashes',{}).get(name)!=file_sha(Path(__file__).parent/name):raise ValueError('frozen feature/monitor code changed')
def execute_packet(root,packet,*,files=None,manifest=None,company_names=None,settlement_source=None):
 root=Path(root).resolve()
 if root.name!='new-a-private':raise ValueError('dedicated private root required')
 if files is None:manifest,files=verify_bootstrap(root)
 verify_code_contract(manifest)
 seed=read(files['seed']);calendar=read(files['calendar'])
 if packet['calendar']!=calendar or packet['strategy']!='A_BASE' or packet['source_quality_verified'] is not True:raise ValueError('packet contract mismatch')
 source_hash=packet['source_hash'];as_of=packet['as_of'];dry=packet['dry_run']
 if not dry and packet.get('activation_verified') is not True:raise ValueError('activation proof required')
 pipeline=Pipeline(root/('daily-dry.sqlite' if dry else 'daily-live.sqlite'),seed,allow_live=not dry)
 try:
  from .restriction_exits import observe
  forced_exits=observe(pipeline,packet.get('restriction_decisions',[]),calendar,as_of,live=not dry)
  restrictions={symbol:list(values) for symbol,values in packet.get('restrictions',{}).items()}
  for rule in forced_exits:restrictions.setdefault(rule['symbol'],[]).append({'start':rule['confirmed_on'],'end':None,'reason':'VERIFIED_RESTRICTED'})
  packet={**packet,'restrictions':restrictions}
  result=pipeline.run(as_of=as_of,observed_at=packet['observed_at'],calendar=calendar,rows_by_day=packet['rows_by_day'],source_hash=source_hash,quality_verified=True,universe=packet['universe'],restrictions=packet.get('restrictions'),dry_run=dry,resume_held=packet.get('resume_held',False),predecessor_source_hash=packet.get('predecessor_source_hash'),recovery_reference=packet.get('delayed_recovery'),freeze_missing_quotes=settlement_source is not None)
  result['source_revision_pending']=packet['source_revision_pending'];daily={**result,'events':[e for e in pipeline.all_events() if e['session']==as_of]};daily['new_live_signals']=sum(e.get('is_new_live_signal') is True for e in daily['events']);snapshot=build_snapshot(daily,allow_live=not dry,repo=root.parents[2]);snapshot['monitor_state']=pipeline.export_current();snapshot['payload_sha256']=digest({k:v for k,v in snapshot.items() if k!='payload_sha256'})
  target=root/'runs'/as_of/source_hash/('dry' if dry else 'live');target.mkdir(parents=True,exist_ok=True)
  snapshot_file=target/'snapshot.json'
  if snapshot_file.exists() and read(snapshot_file)!=snapshot:raise ValueError('immutable daily snapshot conflict')
  if not snapshot_file.exists():atomic_write(snapshot_file,snapshot)
  bundle=prepare_bundle(files,pipeline,snapshot,calendar,target/'bundle',company_names,settlement_source=settlement_source,restrictions=packet.get('restrictions'),forced_exits=forced_exits)
  receipt={'identity':'NEW_A_CLOUD_DAILY_V1','strategy':'A_BASE','entry':ENTRY,'latest_session':as_of,'selector_rows_latest':result['new_live_signals'],'detection_executed':True,'status':result['status'],'tail_rows_latest':result['processed_symbol_sessions'],'held_symbols':len(result['held']),'event_count':result['event_count'],'new_events':result['new_event_count'],'same_run_replay':result.get('same_run_replay',False),'source_sha256':source_hash,'source_version':bundle['source_version'],'snapshot_sha256':snapshot['payload_sha256'],'snapshot_file':str(snapshot_file),'bundle_directory':str(target/'bundle'),'dry_run':dry,'notifications_sent':0,'published':False,'old_logic_called':False,'old_ledger_written':False,'fundamentals':'NOT_REQUESTED'}
  if 'scheduled_exit_prices' in bundle:receipt['scheduled_exit_prices']=bundle['scheduled_exit_prices']
  if result.get('delayed_recovery'):receipt.update(delayed_recovery=result['delayed_recovery'],selector_rows_latest=result['delayed_scheduled_signals'],selector_semantics='DELAYED_TARGET_SESSION_SIGNALS_NOT_REALTIME')
 finally:pipeline.close()
 atomic_write(root/'latest-run.json',receipt);return receipt
def require_activation(root,repo):
 from .acceptance import validate_activation
 return validate_activation(read(Path(root)/'activation.json'),repo)
def command_daily(args,*,source_provider=None,root=None):
 repo=Path(__file__).resolve().parents[2];root=Path(root) if root else private_root(repo);isolated=bool(getattr(args,'new_a_isolated',False));manifest,files=verify_bootstrap(root);verify_code_contract(manifest)
 if not isolated:require_activation(root,repo)
 from .operational_admission import source_context
 source_context(repo,args)
 if getattr(args,'notify',False) or getattr(args,'dry_run_notify',False):raise ValueError('daily never sends; use verified post-publication new-A notify stage')
 recovery_reference=None
 if getattr(args,'delayed_recovery',None):
  from .delayed_recovery import executing_reference,runtime_context
  recovery_reference=executing_reference(repo,args.delayed_recovery);context=runtime_context(repo,recovery_reference)
  if isolated or getattr(args,'as_of',None)!=context['target_date'] or getattr(args,'refresh_live',False) or Path(getattr(args,'retained_acquisition','')).resolve()!=Path(context['replay_directory']).resolve():raise ValueError('delayed target/retained source must be explicit and bound')
 args.restriction_snapshot=str(root/'jpx-restrictions.json')
 if source_provider is None:
  from .source import acquire_and_validate
  source_provider=acquire_and_validate
 source=source_provider(args);as_of=getattr(args,'as_of',None) or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
 latest=source['frame']['date'].max();latest=latest.date().isoformat() if hasattr(latest,'date') else str(latest)[:10]
 if latest!=as_of:
  receipt={'identity':'NEW_A_CLOUD_DAILY_V1','strategy':'A_BASE','entry':ENTRY,'latest_session':latest,'selector_rows_latest':0,'detection_executed':False,'status':'STALE_SOURCE','dry_run':isolated,'source_sha256':source['source_hash'],'notifications_sent':0,'published':False}
  atomic_write(root/'latest-run.json',receipt);print(json.dumps(receipt));return receipt
 seed=read(files['seed']);calendar=read(files['calendar']);dbfile=root/('daily-dry.sqlite' if isolated else 'daily-live.sqlite');pipeline=Pipeline(dbfile,seed,allow_live=not isolated)
 try:
  from .source_baseline import apply as apply_source_baseline
  source=apply_source_baseline(source,pipeline,as_of)
  heads=pipeline.export_current()['heads']
  missing_quote_days=pipeline.missing_quote_days() if not recovery_reference else ()
 finally:pipeline.close()
 packet=prepare_packet(source,seed,calendar,heads,as_of=as_of,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),dry_run=isolated,missing_quote_days=missing_quote_days);packet['activation_verified']=not isolated
 if recovery_reference:packet['delayed_recovery']=recovery_reference
 predecessor=getattr(args,'new_a_resume_held_from_source',None)
 if predecessor:packet.update(resume_held=True,predecessor_source_hash=predecessor)
 if file_sha(source['daily_path'])!=source['source_hash']:raise ValueError('source changed during feature generation')
 settlement_source=source['frame'] if not recovery_reference else None
 receipt=execute_packet(root,packet,files=files,manifest=manifest,company_names=source['company_names'],settlement_source=settlement_source);print(json.dumps(receipt,ensure_ascii=False));return receipt
def command_report(args):
 repo=Path(__file__).resolve().parents[2];script=repo/'weak-early-beta-gate/scripts/sync-report.mjs'
 result=subprocess.run(['node',str(script)],cwd=script.parent.parent,capture_output=True,text=True,encoding='utf8',timeout=120)
 if result.returncode:raise RuntimeError('new_a_code_only_frame_generation_failed')
 receipt={'identity':'NEW_A_CODE_ONLY_REPORT_V1','source_prices_read':0,'private_output_in_report':False,'old_ledger_read':False,'notifications_sent':0};print(json.dumps(receipt));return receipt
