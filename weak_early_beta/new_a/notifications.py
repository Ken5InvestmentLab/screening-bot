"""新A専用receiptで既存Discord transportを呼ぶ。宛先設定は流用し変更しない。"""
import datetime,json,os
from urllib.parse import urljoin,urlparse
from .files import read,digest
from .outbox import Outbox
def eligible(snapshot):return [e for e in snapshot['events'] if (e.get('is_new_live_signal') is True or (snapshot.get('observation_kind')=='DELAYED_SCHEDULED_OBSERVATION' and e.get('is_delayed_scheduled_signal') is True)) and e['kind']=='WATCH_STARTED' and e['session']==snapshot['as_of']]
def message(event,report_url):
 summary=event.get('kind')=='DAILY_SUMMARY';label='新A 日次検出' if summary else str(event['symbol'])+' 仕込み候補・監視開始'
 fields=[{'name':'検出日','value':event['signal_date'],'inline':True},{'name':'状態','value':'監視開始・未約定','inline':True}]
 if event.get('observation_kind')=='DELAYED_SCHEDULED_OBSERVATION':
  label+=' (delayed scheduled result)';fields.append({'name':'Actual observed at','value':event['observed_at'],'inline':False})
 if summary:fields.append({'name':'新規銘柄数','value':str(event['count']),'inline':True})
 payload={'content':'','embeds':[{'title':label,'url':urljoin(report_url,'weak_early_beta_latest.html'),'fields':fields,'footer':{'text':'A_BASE | '+event['event_id']},'color':0x5B8DEF}],'allowed_mentions':{'parse':[]}}
 if not summary:
  from ..notify import chart_components
  payload['components']=chart_components(event['symbol'])
 return payload
def default_transport(report_url):
 # 通常通知の既存保管経路をライブラリ内だけで使用。値/長さを返さない。
 from .. import notify
 webhook=os.environ.get(notify.WEBHOOK_ENV,'').strip();token=(os.environ.get('WEAK_EARLY_BETA_DISCORD_BOT_TOKEN') or os.environ.get('DISCORD_TOKEN') or '').strip()
 def send(event):
  payload=message(event,report_url)
  try:
   if event.get('kind')=='DAILY_SUMMARY':
    if not token:raise RuntimeError('existing_summary_transport_unavailable')
    receipt=notify._post_bot(notify.SUMMARY_CHANNEL_ID,token,payload)
   else:
    if not webhook:raise RuntimeError('existing_signal_transport_unavailable')
    receipt=notify._post_webhook(webhook,payload)
  except Exception:raise RuntimeError('existing_notification_transport_failed_reconcile_before_retry') from None
  return {'confirmed':bool(receipt.get('id')),'message_id':str(receipt.get('id',''))}
 return send
def notify_day(root,*,date,dry_run,report_url,transport=None):
 root=__import__('pathlib').Path(root);run=read(root/'latest-run.json');snapshot=read(run['snapshot_file']);publication=read(root/'latest-publication.json')
 if publication.get('operational_gate_continuity_verified') is True:
  from .operational_admission import action_context
  action_context(root.resolve().parents[2],date=date,run=run,snapshot=snapshot,publication=publication,required=True)
 if date!=snapshot['as_of'] or run['strategy']!='A_BASE' or run['snapshot_sha256']!=snapshot['payload_sha256']:raise ValueError('matching New A daily snapshot required')
 if digest({k:v for k,v in snapshot.items() if k!='payload_sha256'})!=snapshot['payload_sha256'] or run['source_sha256']!=snapshot['source_sha256'] or run['source_version']!=publication.get('source_version'):raise ValueError('private notification source bytes changed')
 local_historical_preview=dry_run and snapshot['observation_kind']=='DRY_RUN_HISTORICAL' and publication.get('local_d1_emulation') is True
 from .operational_admission import publication_gate_verified
 if publication.get('snapshot_sha256')!=snapshot['payload_sha256'] or publication.get('active_readback_verified') is not True or (not local_historical_preview and (not publication_gate_verified(publication) or publication.get('published') is not True)):raise ValueError('verified private publication required')
 delayed=snapshot.get('observation_kind')=='DELAYED_SCHEDULED_OBSERVATION'
 if delayed:
  from .delayed_recovery import delivery_context
  delivery_context(root.resolve().parents[2],snapshot,publication)
 if not dry_run and snapshot['observation_kind']!='LIVE_OBSERVATION' and not delayed:raise ValueError('historical/catchup notifications prohibited')
 outbox=Outbox(root/'notification-outbox.sqlite');new=eligible(snapshot)
 try:
  outbox.stage(snapshot,publication,existing_notifications_enabled=True)
  # 0件では通常の銘柄/完了通知を送らない。処理成功は日次receiptで別に証明。
  if new:
   summary={'kind':'DAILY_SUMMARY','event_id':digest(['A_BASE',date,'DAILY_SUMMARY']),'signal_date':date,'count':len({e['symbol'] for e in new}),'strategy':'A_BASE','signal_phase':'WATCH_STARTED','execution_status':'NOT_EXECUTED'}
   if delayed:summary.update(observation_kind=snapshot['observation_kind'],observed_at=snapshot['observed_at'],delayed_recovery=snapshot['delayed_recovery'])
   with outbox.db:outbox.db.execute('INSERT OR IGNORE INTO new_a_delivery VALUES (?,?,"PENDING",NULL)',(summary['event_id'],json.dumps(summary,sort_keys=True)))
  allrows=outbox.db.execute('SELECT event_id,payload_json,status FROM new_a_delivery').fetchall();rows=[(event_id,json.loads(raw),status) for event_id,raw,status in allrows if json.loads(raw).get('signal_date')==date]
  if any(status=='ATTEMPTED_UNCONFIRMED' for _,_,status in rows):raise ValueError('notification outcome unconfirmed; reconcile before retry')
  pending=[r for r in rows if r[2]=='PENDING'];counts={'signal_notifications':sum(p.get('kind')!='DAILY_SUMMARY' for _,p,_ in pending),'completion_notifications':sum(p.get('kind')=='DAILY_SUMMARY' for _,p,_ in pending)}
  if not dry_run and pending:
   if publication.get('operational_gate_continuity_verified') is True:
    from .operational_admission import action_context
    action_context(root.resolve().parents[2],date=date,run=run,snapshot=snapshot,publication=publication,required=True)
   target=urlparse(report_url)
   if target.scheme!='https' or not target.netloc:raise ValueError('existing Cloud report URL is required before send')
   send=transport or default_transport(report_url)
   for event_id,payload,_ in sorted(pending,key=lambda r:r[1].get('kind')=='DAILY_SUMMARY'):
    if publication.get('operational_gate_continuity_verified') is True:action_context(root.resolve().parents[2],date=date,run=run,snapshot=snapshot,publication=publication,required=True)
    receipt=outbox.deliver(event_id,send,execute=True)
    if receipt.get('sent') is not True:raise RuntimeError('notification_unconfirmed_reconcile_before_retry')
  return {'date':date,'dry_run':dry_run,**counts,'strategy':'A_BASE','source_sha256':snapshot['source_sha256'],'snapshot_sha256':snapshot['payload_sha256'],'old_ledger_written':False,'external_sends':0 if dry_run else sum(counts.values())}
 finally:outbox.close()
