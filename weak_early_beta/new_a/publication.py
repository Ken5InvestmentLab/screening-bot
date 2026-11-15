"""公開物の準備境界。owner専用のprivate snapshotを作るだけで送信しない。"""
import hashlib,json
def encode(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def build_snapshot(result,*,allow_live=False):
 if (result.get('dry_run') is not True and not allow_live) or result.get('publication_executed') is not False:raise ValueError('isolated result required')
 if result.get('status') not in ['COMPLETED','COMPLETED_WITH_HELD_SYMBOLS'] or len(result.get('source_hash',''))!=64:raise ValueError('incomplete daily result')
 events=result.get('events',[])
 allowed={'WATCH_STARTED','WATCH_TERMINAL','ENTRY_CANDIDATE','REFERENCE_OPEN','MONITOR_RESET'}
 kinds=['DRY_RUN_HISTORICAL'] if result['dry_run'] else ['LIVE_OBSERVATION','CATCHUP_NOT_NEW']
 if any(e.get('kind') not in allowed or e.get('observation_kind') not in kinds or (e.get('is_new_live_signal') and (result['dry_run'] or e['session']!=result['as_of'] or e['kind']!='WATCH_STARTED')) for e in events):raise ValueError('old/reclassified signal rejected')
 if len({e['event_id'] for e in events})!=len(events):raise ValueError('duplicate publication events')
 if any(e.get('execution_status') not in [None,'NOT_EXECUTED'] for e in events):raise ValueError('actual fills not permitted')
 snapshot={'schema':'NEW_A_OWNER_DAILY_SNAPSHOT_V1','strategy':'A_BASE','audience':'EXISTING_CLOUD_OWNER_ONLY','as_of':result['as_of'],'observed_at':result['observed_at'],'source_sha256':result['source_hash'],'observation_kind':result.get('observation_kind','DRY_RUN_HISTORICAL' if result['dry_run'] else 'CATCHUP_NOT_NEW'),'new_live_signals':result['new_live_signals'],'data_status':result['status'],'held_symbols':result['held'],'source_revision_pending':result.get('source_revision_pending',{'status':'not_supplied'}),'events':events,'notifications_sent':0,'published':False}
 snapshot['payload_sha256']=hashlib.sha256(encode(snapshot).encode()).hexdigest();return snapshot

def validate_for_owner_read(snapshot,owner_context):
 if owner_context.get('owner') is not True or owner_context.get('role_authorized') is not True or owner_context.get('current') is not True:raise PermissionError('existing owner gate required')
 if snapshot.get('schema')!='NEW_A_OWNER_DAILY_SNAPSHOT_V1' or snapshot.get('strategy')!='A_BASE' or snapshot.get('audience')!='EXISTING_CLOUD_OWNER_ONLY':raise ValueError('strategy/audience mismatch')
 unsigned={k:v for k,v in snapshot.items() if k!='payload_sha256'}
 if hashlib.sha256(encode(unsigned).encode()).hexdigest()!=snapshot.get('payload_sha256'):raise ValueError('snapshot hash mismatch')
 return snapshot
