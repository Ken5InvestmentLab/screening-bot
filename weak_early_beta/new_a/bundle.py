"""不変の検証履歴と観測した日次stateを結合し、本人専用小分け入力へ。"""
import base64,copy,hashlib,math,sqlite3
from pathlib import Path
from .files import encode,digest,read,atomic_write
FIELDS=['open','high','low','close','volume','actual_close','actual_volume','split_factor','source_usable']
def key(row):return f"{row['symbol']}|{row['candidate_date']}|{row['episode_id']}"
def valid(row):return bool(row) and all(isinstance(row.get(k),(int,float)) and math.isfinite(row[k]) and row[k]>0 for k in ['open','high','low','close','actual_close']) and row.get('source_usable') in [True,1,'true','1'] and row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high'] and row.get('volume',0)>0 and row.get('actual_volume',0)>0
def prepare_bundle(files,pipeline,snapshot,full_calendar,folder,company_names=None,*,settlement_source=None,restrictions=None):
 old=read(files['history_input']);presentation=read(files['presentation']);frozen_end=old['calendar'][-1];as_of=snapshot['as_of'];calendar=[d for d in full_calendar if d<=as_of]
 if calendar[:len(old['calendar'])]!=old['calendar']:raise ValueError('historical calendar changed')
 episodes={key(e):copy.deepcopy(e) for e in old['episodes']};watches={key(w):copy.deepcopy(w) for w in old['watches']};intents={key(i):copy.deepcopy(i) for i in old['intents']}
 events=sorted(pipeline.all_events(),key=lambda e:(e['session'],e['symbol'],e['episode_id'],{'WATCH_STARTED':0,'ENTRY_CANDIDATE':1,'WATCH_TERMINAL':2}.get(e['kind'],3)))
 for e in events:
  k=key(e)
  if e['kind']=='WATCH_STARTED':
   episode={f:e[f] for f in ['symbol','candidate_date','episode_id','support','resistance','priority_score']};episode['detection_count']=1
   if k in episodes and any(episodes[k][f]!=episode[f] for f in episode):raise ValueError('frozen episode rewritten')
   episodes.setdefault(k,episode);watches.setdefault(k,{**episode,'watch_status':'WATCHING','trigger_date':None,'terminal_date':None})
  if e['kind']=='ENTRY_CANDIDATE':
   if k not in episodes:raise ValueError('entry without A watch')
   intent={**episodes[k],'trigger_date':e['session']}
   if k in intents and intents[k]!=intent:raise ValueError('frozen intent rewritten')
   intents.setdefault(k,intent);watches[k].update(watch_status='TRIGGERED',trigger_date=e['session'],terminal_date=e['session'])
  if e['kind']=='WATCH_TERMINAL':
   if k not in watches:raise ValueError('terminal without A watch')
   watches[k].update(watch_status=e['reason'],terminal_date=e['session'])
 # 過去経済値を上書きせず、未来の確認済み価格だけ別の連続basisで追加。
 observed=pipeline.observed_quotes()
 # 新universe構成員のwarmupは過去の検証価格/検出へ混ぜない。
 observed={k:v for k,v in observed.items() if k[1]>frozen_end}
 db=sqlite3.connect(Path(files['quotes']).resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;cache={}
 def quote(symbol,day):
  k=(symbol,day)
  if k in observed:return observed[k]
  if day>frozen_end:return None
  if k not in cache:
   r=db.execute('SELECT * FROM quotes WHERE symbol=? AND date=?',k).fetchone();cache[k]=dict(r) if r else None
  return cache[k]
 index={d:i for i,d in enumerate(calendar)};needed=set()
 def add(s,d):
  if d:needed.add((s,d))
 for e in episodes.values():add(e['symbol'],e['candidate_date'])
 for e in intents.values():
  i=index[e['trigger_date']]+1
  add(e['symbol'],e['trigger_date'])
  if i>=len(calendar):continue
  add(e['symbol'],calendar[i-1])
  for j in range(i,min(i+20,len(calendar))):add(e['symbol'],calendar[j])
  for hold in [5,6,20]:
   j=i+hold-1
   if j>=len(calendar):continue
   r=quote(e['symbol'],calendar[j])
   if not valid(r) or r['high']==r['low']:
    for d in calendar[j+1:]:add(e['symbol'],d)
 settlement={};skipped=set()
 if settlement_source is not None:
  from .settlement_recovery import recover_scheduled_exits
  skipped={k for k in pipeline.missing_quote_days() & needed if k[1]>frozen_end and quote(*k) is None}
  settlement=recover_scheduled_exits(
   pipeline,settlement_source,calendar,intents.values(),quote,frozen_end=frozen_end,as_of=as_of,
   restrictions=restrictions or {},identity_unverified_before=old['limits']['identityUnverifiedBefore'],
   source_hash=snapshot['source_sha256'],
  )
  if not settlement.keys()<=skipped:raise ValueError('scheduled exit is not a recorded price gap')
 rows={r['identity']:copy.deepcopy(r) for r in presentation['rows']};names={**{r['symbol']:r['companyName'] for r in rows.values()},**(company_names or {})}
 for k,e in episodes.items():
  w=watches[k]
  if k not in rows:
   signal=quote(e['symbol'],e['candidate_date']);known=valid(signal)
   rows[k]={'identity':k,'symbol':e['symbol'],'companyName':names.get(e['symbol'],'名称未照合'),'nameStatus':'CURRENT_SOURCE_REFERENCE_NOT_HISTORICAL_NAME' if e['symbol'] in names else 'NAME_UNVERIFIED','candidateDate':e['candidate_date'],'signalDate':e['candidate_date'],'measurementAnchorDate':e['candidate_date'],'selectors':['A_BASE'],'signalClose':{'status':'verified' if known else 'unresolved','date':e['candidate_date'],'price':signal.get('actual_close') if known else None},'entry':{},'endpoints':{},'analysisCutoff':None,'fundamental':None}
  row=rows[k];row.update(triggerDate=w.get('trigger_date'),watchStatus=w['watch_status'],watchTerminalDate=w.get('terminal_date'))
  # 既存の確定済み参照は凍結のまま。未確認だった参照だけ実観測の予定日へ結ぶ。
  if w.get('trigger_date'):
   entry_i=full_calendar.index(w['trigger_date'])+1;entry_day=full_calendar[entry_i] if entry_i<len(full_calendar) else None;entry=quote(e['symbol'],entry_day) if entry_day and entry_day<=as_of else None
   if row.get('entry',{}).get('status')!='verified':
    price=entry['open']*entry['actual_close']/entry['close'] if valid(entry) and entry['high']!=entry['low'] else None
    row['entry']={'status':'verified' if price is not None else 'pending' if entry_day and entry_day>as_of else 'unresolved','date':entry_day,'price':price,'cost100':price*100 if price is not None else None,'basis':'NEXT_SESSION_OPEN_REFERENCE','simulation':True}
   for name,offset,basis in [('d5_close',4,'CLOSE'),('d6_open',5,'OPEN')]:
    if row.get('endpoints',{}).get(name,{}).get('status')=='verified':continue
    day=full_calendar[entry_i+offset] if entry_i+offset<len(full_calendar) else None;r=quote(e['symbol'],day) if day and day<=as_of else None
    price=(r['actual_close'] if basis=='CLOSE' else r['open']*r['actual_close']/r['close']) if valid(r) and r['high']!=r['low'] else None
    row.setdefault('endpoints',{})[name]={'status':'reference_price_only' if price is not None else 'pending' if day and day>as_of else 'unresolved','measurementKind':'A_SIGNAL_LEGACY_D5_D6','key':name,'anchorDate':e['candidate_date'],'date':day,'basis':basis,'price':price,'proceeds100':None,'exitShares100':None,'return':None,'shareActionReceipt':'REFERENCE_PRICE_ONLY_NOT_SETTLEMENT'}
  else:
   row.setdefault('entry',{}).update(status='not_triggered',date=None,price=None,cost100=None,basis='NEXT_SESSION_OPEN_REFERENCE',simulation=True)
  row['chartAllowed']=not(e['symbol'] in old['limits']['identityUnverifiedBefore'] and e['candidate_date']<old['limits']['identityUnverifiedBefore'][e['symbol']])
 def sort(e):return(e['candidate_date'],-e['priority_score'],e['symbol'],e['episode_id'])
 limits={**old['limits'],'completeThrough':as_of,'latestUnverified':None,'partialSource':bool(snapshot['held_symbols']),'heldSymbols':snapshot['held_symbols'],'nextPlannedSession':next((d for d in full_calendar if d>as_of),None),'nextOpenConfirmed':False}
 version_inputs={'historySourceVersion':old['source_version'],'sourceSHA256':snapshot['source_sha256'],'dailySnapshotSHA256':snapshot['payload_sha256'],'asOf':as_of}
 if settlement:
  version_inputs['scheduledExitEvidenceSHA256']=digest([[*k,v] for k,v in sorted(settlement.items())])
 if skipped:
  version_inputs['skippedQuoteKeysSHA256']=digest(sorted(skipped))
 source_version=digest(version_inputs)
 input_header={k:copy.deepcopy(v) for k,v in old.items() if k not in ['episodes','intents','watches','source_version','calendar','limits']};input_header.update(source_version=source_version,calendar=calendar,limits=limits)
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);collections={};all_parts={}
 def parts(kind,values):
  descriptors=[];batch=[];size=2
  def flush():
   nonlocal batch,size
   if not batch:return
   text=encode(batch);name=f'{kind}-{len(descriptors):03d}.json';raw=text.encode();(folder/name).write_bytes(raw);descriptors.append({'name':name,'rows':len(batch),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()});all_parts[name]=text;batch=[];size=2
  for value in values:
   count=len(encode(value).encode())+1
   if count>64*1024-2:raise ValueError('oversized private record')
   if size+count>64*1024:flush()
   batch.append(value);size+=count
  flush();return descriptors
 display={k:copy.deepcopy(v) for k,v in snapshot.items() if k not in ['schema','payload_sha256','monitor_state']};display.update(schema='NEW_A_OWNER_DAILY_DISPLAY_V1',source_snapshot_sha256=snapshot['payload_sha256'])
 state=snapshot['monitor_state'];head_counts={}
 for day in state['heads'].values():head_counts[str(day)]=head_counts.get(str(day),0)+1
 current_symbols={event['symbol'] for event in snapshot['events'] if event['session']==as_of}
 current_symbols.update(watch['episode']['symbol'] for watch in state['watches'].values())
 today_index=full_calendar.index(as_of)
 current_symbols.update(ref['symbol'] for ref in state['pending_references'] if today_index-ref['entry_index']<20)
 held=snapshot['held_symbols']
 held_symbols=set(held) if isinstance(held,dict) else {item['symbol'] for item in held}
 display['latest_closes']={}
 for symbol in sorted(current_symbols-held_symbols):
  price=quote(symbol,as_of)
  if valid(price):
   display['latest_closes'][symbol]={'date':as_of,'price':price['actual_close']}
 display['monitor_state']={k:copy.deepcopy(v) for k,v in state.items() if k!='heads'};display['monitor_state']['heads_by_date_counts']=head_counts;display['display_payload_sha256']=digest(display)
 display_raw=encode(display).encode();count=(len(display_raw)+32767)//32768
 if len(display_raw)>8*1024*1024 or count>256:raise ValueError('current display resource budget exceeded')
 display_sha=hashlib.sha256(display_raw).hexdigest();fragments=[{'schema':'NEW_A_CURRENT_JSON_FRAGMENT_V1','index':i,'count':count,'display_sha256':display_sha,'bytes_total':len(display_raw),'payload_base64':base64.b64encode(display_raw[i*32768:(i+1)*32768]).decode('ascii')} for i in range(count)]
 for kind,values in [('episodes',sorted(episodes.values(),key=sort)),('intents',sorted(intents.values(),key=sort)),('watches',sorted(watches.values(),key=sort)),('presentation',[rows[key(e)] for e in sorted(episodes.values(),key=sort)]),('current_daily',fragments)]:collections[kind]=parts(kind,values)
 records=[]
 quote_fields=[*FIELDS]
 if skipped:quote_fields.append('decision_skipped')
 if settlement:quote_fields.append('scheduled_exit')
 for sym,day in sorted(needed,key=lambda k:(k[1]>frozen_end,k[0],k[1])):
  r=quote(sym,day);exit_receipt=settlement.get((sym,day));skip=(sym,day) in skipped
  values=[r.get(f) for f in FIELDS] if r else [None]*len(FIELDS) if skip else None
  if values is not None:
   if skipped:values.append(True if skip else None)
   if settlement:values.append(exit_receipt['price'] if exit_receipt else None)
  records.append([sym,day,values])
 quote_parts=parts('quotes',records);db.close()
 manifest={'schema':'A_BROWSER_PRIVATE_INPUT_V1','audience':'EXISTING_CLOUD_OWNER_ONLY','strategy':'A_BASE','source_version':source_version,'input_header':input_header,'collections':collections,'quote_fields':quote_fields,'quotes':quote_parts,'expected_quote_keys':len(records),'as_of':as_of,'daily_snapshot_sha256':snapshot['payload_sha256'],'live':snapshot['observation_kind']=='LIVE_OBSERVATION'}
 text=encode(manifest);raw=text.encode();manifest_sha=hashlib.sha256(raw).hexdigest();dataset_id='a-'+manifest_sha[:24];(folder/'manifest.json').write_bytes(raw)
 descriptors=[*quote_parts,*[d for values in collections.values() for d in values]]
 if len(descriptors)>512:raise ValueError('private part count limit')
 receipt={'schema':'NEW_A_PRIVATE_BUNDLE_RECEIPT_V1','dataset_id':dataset_id,'manifest_sha256':manifest_sha,'source_version':source_version,'as_of':as_of,'daily_snapshot_sha256':snapshot['payload_sha256'],'episodes':len(episodes),'intents':len(intents),'presentation':len(rows),'parts':len(descriptors),'bytes':len(raw)+sum(d['bytes'] for d in descriptors),'frozen_history_unchanged':True,'new_live_signals':snapshot['new_live_signals'],'source_revision_pending':snapshot['source_revision_pending'],'published':False}
 if settlement:
  receipt.update(scheduled_exit_prices=len(settlement),scheduled_exit_evidence_sha256=version_inputs['scheduledExitEvidenceSHA256'])
 atomic_write(folder/'receipt.json',receipt);return receipt
