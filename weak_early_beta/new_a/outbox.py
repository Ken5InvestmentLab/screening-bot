"""新A event_idの重複防止と既存transportへの受渡し。宛先・鍵・通信を持たない。"""
import json,sqlite3
class Outbox:
 def __init__(self,path):
  self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE IF NOT EXISTS new_a_delivery(event_id TEXT PRIMARY KEY,payload_json TEXT NOT NULL,status TEXT NOT NULL,receipt_json TEXT)');self.db.commit()
 def stage(self,snapshot,publication_receipt,*,existing_notifications_enabled):
  if not existing_notifications_enabled:return []
  if snapshot.get('observation_kind')!='LIVE_OBSERVATION' or publication_receipt.get('published') is not True:return []
  if publication_receipt.get('snapshot_sha256')!=snapshot.get('payload_sha256') or publication_receipt.get('existing_owner_gate_verified') is not True:raise ValueError('verified owner publication required')
  staged=[]
  with self.db:
   for e in snapshot['events']:
    if not(e.get('is_new_live_signal') is True and e['kind']=='WATCH_STARTED' and e['session']==snapshot['as_of']):continue
    payload={'event_id':e['event_id'],'symbol':e['symbol'],'signal_date':e['session'],'strategy':'A_BASE','signal_phase':'WATCH_STARTED','display_label':'仕込み候補・監視開始','execution_status':'NOT_EXECUTED'}
    inserted=self.db.execute('INSERT OR IGNORE INTO new_a_delivery VALUES (?,?,"PENDING",NULL)',(e['event_id'],json.dumps(payload,sort_keys=True))).rowcount
    if inserted:staged.append(payload)
  return staged
 def deliver(self,event_id,existing_transport,*,execute=False):
  row=self.db.execute('SELECT payload_json,status FROM new_a_delivery WHERE event_id=?',(event_id,)).fetchone()
  if not row or row[1]!='PENDING' or not execute:return {'sent':False,'reason':'disabled_or_not_pending'}
  with self.db:claimed=self.db.execute('UPDATE new_a_delivery SET status="ATTEMPTED_UNCONFIRMED" WHERE event_id=? AND status="PENDING"',(event_id,)).rowcount
  if claimed!=1:return {'sent':False,'reason':'already_claimed'}
  # 通信成否不明をPENDINGに戻さず、既存transportの正規GET照合へ渡す。
  receipt=existing_transport(json.loads(row[0]))
  if not isinstance(receipt,dict) or receipt.get('confirmed') is not True:return {'sent':False,'reason':'reconciliation_required'}
  with self.db:self.db.execute('UPDATE new_a_delivery SET status="SENT",receipt_json=? WHERE event_id=?',(json.dumps(receipt),event_id))
  return {'sent':True}
 def close(self):self.db.close()
