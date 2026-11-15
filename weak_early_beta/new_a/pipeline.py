"""取得・品質検証後の新A日次本体。通信・通知・タスク操作を持たない。"""
import copy,datetime,hashlib,json,re,sqlite3
from pathlib import Path
from . import monitor

class Pipeline:
 def __init__(self,db_path,verified_checkpoint,*,allow_live=False):
  self.allow_live=allow_live
  self.db=sqlite3.connect(db_path);self.db.executescript('CREATE TABLE IF NOT EXISTS symbol_heads(symbol TEXT PRIMARY KEY,state_json TEXT NOT NULL,state_hash TEXT NOT NULL);CREATE TABLE IF NOT EXISTS symbol_days(symbol TEXT NOT NULL,day TEXT NOT NULL,input_hash TEXT NOT NULL,PRIMARY KEY(symbol,day));CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,event_json TEXT NOT NULL,publication_state TEXT NOT NULL);CREATE TABLE IF NOT EXISTS runs(run_key TEXT PRIMARY KEY,source_hash TEXT NOT NULL,result_json TEXT NOT NULL);CREATE TABLE IF NOT EXISTS held(symbol TEXT PRIMARY KEY,day TEXT NOT NULL,reason TEXT NOT NULL);')
  self.db.execute('CREATE TABLE IF NOT EXISTS observed_quotes(symbol TEXT NOT NULL,day TEXT NOT NULL,row_json TEXT NOT NULL,row_hash TEXT NOT NULL,PRIMARY KEY(symbol,day))')
  seed=verified_checkpoint
  self.db.execute('CREATE TABLE IF NOT EXISTS checkpoint_identity(id INTEGER PRIMARY KEY CHECK(id=1),seed_hash TEXT NOT NULL)')
  seed_hash=monitor.digest(seed);identity=self.db.execute('SELECT seed_hash FROM checkpoint_identity WHERE id=1').fetchone()
  if identity and identity[0]!=seed_hash:self.db.close();raise ValueError('seed checkpoint changed')
  if not identity and self.db.execute('SELECT COUNT(*) FROM symbol_heads').fetchone()[0]:self.db.close();raise ValueError('legacy isolated checkpoint requires explicit migration')
  if not identity:self.db.execute('INSERT INTO checkpoint_identity VALUES (1,?)',(seed_hash,))
  existing_symbols={r[0] for r in self.db.execute('SELECT symbol FROM symbol_heads')}
  for sym in seed['symbols']:
   if sym in existing_symbols:continue
   one=monitor.initial(seed['calendar'],[sym],seed['contract']);one['cursor']=seed['cursor']
   for name in ['active','sequence','previous','identities','bases']:
    if sym in seed[name]:one[name][sym]=copy.deepcopy(seed[name][sym])
   one['watches']={k:copy.deepcopy(v) for k,v in seed['watches'].items() if v['episode']['symbol']==sym}
   one['pending']=[copy.deepcopy(v) for v in seed['pending'] if v['symbol']==sym]
   self.db.execute('INSERT OR IGNORE INTO symbol_heads VALUES (?,?,?)',(sym,monitor.encode(one),monitor.digest(one)))
  self.db.commit()
 def read(self,sym):
  row=self.db.execute('SELECT state_json,state_hash FROM symbol_heads WHERE symbol=?',(sym,)).fetchone()
  if not row:return None
  state=json.loads(row[0])
  if monitor.digest(state)!=row[1]:raise ValueError('corrupt symbol state')
  return state
 def run(self,*,as_of,observed_at,calendar,rows_by_day,source_hash,quality_verified,universe,restrictions=None,dry_run=True,resume_held=False,predecessor_source_hash=None):
  if quality_verified is not True or not re.fullmatch('[a-f0-9]{64}',source_hash):raise ValueError('verified source receipt required')
  if calendar!=sorted(set(calendar)) or as_of not in calendar:raise ValueError('verified market calendar required')
  obs=datetime.datetime.fromisoformat(observed_at.replace('Z','+00:00'));jst=datetime.timezone(datetime.timedelta(hours=9))
  if obs.tzinfo is None or obs>datetime.datetime.now(datetime.timezone.utc) or obs<datetime.datetime.fromisoformat(as_of+'T15:30:00+09:00'):raise ValueError('completed-session observation required')
  if not universe or len(set(universe))!=len(universe) or any(set(values)!=set(universe) for values in rows_by_day.values()):raise ValueError('complete explicit universe required')
  key=as_of+'|'+source_hash+'|'+('DRY_RUN' if dry_run else 'LIVE');old=self.db.execute('SELECT result_json FROM runs WHERE run_key=?',(key,)).fetchone()
  latest=self.db.execute('SELECT source_hash,result_json FROM runs WHERE run_key LIKE ? ORDER BY rowid DESC LIMIT 1',(as_of+'|%',)).fetchone()
  if old:
   if latest and latest[0]!=source_hash:raise ValueError('stale source replay after held-source completion')
   return {**json.loads(old[0]),'same_run_replay':True,'new_event_count':0}
  if not dry_run and not self.allow_live:raise ValueError('live activation not authorized/configured in isolated harness')
  restrictions=restrictions or {};emitted=[];holds={};processed=0
  with self.db:
   self.db.execute('BEGIN IMMEDIATE')
   previous_run=self.db.execute('SELECT source_hash,result_json FROM runs WHERE run_key LIKE ? ORDER BY rowid DESC LIMIT 1',(as_of+'|%',)).fetchone()
   if previous_run:
    prior_result=json.loads(previous_run[1])
    if prior_result['dry_run']!=dry_run:raise ValueError('dry/live stores must remain separate')
    if previous_run[0]==source_hash:return {**prior_result,'same_run_replay':True,'new_event_count':0}
    if resume_held is not True or predecessor_source_hash!=previous_run[0] or not prior_result['held'] or prior_result.get('universe_hash')!=monitor.digest(sorted(universe)):raise ValueError('committed session source revision requires review')
    # 正規source到着で保留を再開するときも、既処理inputが1セルでも変われば拒否。
    for day,values in rows_by_day.items():
     for sym,h in self.db.execute('SELECT symbol,input_hash FROM symbol_days WHERE day=?',(day,)):
      if sym not in values or monitor.digest({sym:values[sym]})!=h:raise ValueError('committed input changed during held resume')
   for sym in sorted(universe):
    state=self.read(sym)
    newly_observed_member=state is None
    if state is None:
     # 新規構成員の過去60日はfeature専用warmup。未観測の過去を日次stateへ再生しない。
     state=monitor.initial(calendar,[sym],'A_BASE_DYNAMIC_UNIVERSE_V1');state['cursor']=calendar.index(as_of)-1
     warmup=rows_by_day.get(calendar[state['cursor']],{}).get(sym) if state['cursor']>=0 else None
     if monitor.valid(warmup,True):state['previous'][sym]=copy.deepcopy(warmup)
    if calendar[:len(state['calendar'])]!=state['calendar']:raise ValueError('calendar prefix changed')
    state['calendar']=calendar;before=copy.deepcopy(state)
    for p in state['pending']:
     if p.get('reference_entry_date') is None and p['entry_index']<len(calendar):p['reference_entry_date']=calendar[p['entry_index']]
     if p.get('reference_exit_date') is None and p['reference_exit_index']<len(calendar):p['reference_exit_date']=calendar[p['reference_exit_index']]
    for idx in range(state['cursor']+1,calendar.index(as_of)+1):
     day=calendar[idx];r=rows_by_day.get(day,{}).get(sym)
     rules=restrictions.get(sym,[])
     if isinstance(rules,str):rules=[{'start':rules,'reason':'VERIFIED_DELISTED'}]
     restricted=next((v for v in rules if day>=v['start'] and (not v.get('end') or day<v['end'])),None)
     if restricted:holds[sym]={'day':day,'reason':restricted['reason']};break
     if r is None or not monitor.valid(r,True):holds[sym]={'day':day,'reason':'MISSING_SOURCE' if r is None else 'SOURCE_QUARANTINED'};break
     # 従前の観測basisへ合わせる。過去OHLCを上書きせず基準close同一が必須。
     previous=state['previous'].get(sym);prior=rows_by_day.get(state['calendar'][state['cursor']],{}).get(sym) if state['cursor']>=0 else None
     scaled=copy.deepcopy(r)
     if newly_observed_member and day<as_of:scaled['candidate']=False
     if previous and not monitor.valid(prior,True):holds[sym]={'day':day,'reason':'PRIOR_OBSERVED_ANCHOR_MISSING'};break
     if previous and prior:
      if previous['actual_close']!=prior['actual_close']:holds[sym]={'day':day,'reason':'PRIOR_OBSERVED_CLOSE_REVISED'};break
      k=previous['close']/prior['close']
      for fld in ['open','high','low','close','low20','high20']:
       if scaled.get(fld) is not None:scaled[fld]*=k
      scaled['volume']/=k;scaled['split_factor']/=k
     # phase-specific timestamp stays actual DRY_RUN observation; no synthetic realtime fills.
     state,events=monitor.advance(state,day,{sym:scaled},observed_at)
     h=monitor.digest({sym:r});existing=self.db.execute('SELECT input_hash FROM symbol_days WHERE symbol=? AND day=?',(sym,day)).fetchone()
     if existing and existing[0]!=h:raise ValueError('conflicting committed day')
     self.db.execute('INSERT OR IGNORE INTO symbol_days VALUES (?,?,?)',(sym,day,h));processed+=1
     self.db.execute('INSERT INTO observed_quotes VALUES (?,?,?,?)',(sym,day,monitor.encode(scaled),monitor.digest(scaled)))
     for e in events:
      live_signal=not dry_run and day==as_of==obs.astimezone(jst).date().isoformat() and e['kind']=='WATCH_STARTED'
      tagged={**e,'observation_kind':'DRY_RUN_HISTORICAL' if dry_run else 'LIVE_OBSERVATION' if day==as_of==obs.astimezone(jst).date().isoformat() else 'CATCHUP_NOT_NEW','is_new_live_signal':live_signal,'publication_state':'LOCAL_ONLY_NOT_SENT' if dry_run else 'PENDING_PUBLISH_NOT_SENT'}
      self.db.execute('INSERT INTO events VALUES (?,?,?)',(e['event_id'],monitor.encode(tagged),tagged['publication_state']));emitted.append(tagged)
    self.db.execute('INSERT INTO symbol_heads VALUES (?,?,?) ON CONFLICT(symbol) DO UPDATE SET state_json=excluded.state_json,state_hash=excluded.state_hash',(sym,monitor.encode(state),monitor.digest(state)))
    if sym in holds:self.db.execute('INSERT INTO held VALUES (?,?,?) ON CONFLICT(symbol) DO UPDATE SET day=excluded.day,reason=excluded.reason',(sym,holds[sym]['day'],holds[sym]['reason']))
    else:self.db.execute('DELETE FROM held WHERE symbol=?',(sym,))
   result={'status':'COMPLETED_WITH_HELD_SYMBOLS' if holds else 'COMPLETED','as_of':as_of,'observed_at':observed_at,'source_hash':source_hash,'dry_run':dry_run,'universe_hash':monitor.digest(sorted(universe)),'held_resume':bool(previous_run and previous_run[0]!=source_hash),'observation_kind':'DRY_RUN_HISTORICAL' if dry_run else 'LIVE_OBSERVATION' if as_of==obs.astimezone(jst).date().isoformat() else 'CATCHUP_NOT_NEW','new_live_signals':sum(e['is_new_live_signal'] for e in emitted),'event_count':len(emitted),'new_event_count':len(emitted),'processed_symbol_sessions':processed,'held':holds,'events':emitted,'notification_sends':0,'publication_executed':False,'zero_detection_is_success':True}
   self.db.execute('INSERT INTO runs VALUES (?,?,?)',(key,source_hash,monitor.encode(result)))
  return result
 def export_current(self):
  # 表示用の最新状態。過去イベントを当日の新規eventへ変換しない。
  heads={};watches={};pending=[]
  for (sym,) in self.db.execute('SELECT symbol FROM symbol_heads ORDER BY symbol'):
   state=self.read(sym);heads[sym]=state['calendar'][state['cursor']] if state['cursor']>=0 else None
   for key,value in state['watches'].items():
    if key in watches:raise ValueError('duplicate watch identity')
    watches[key]=copy.deepcopy(value)
   pending.extend(copy.deepcopy(state['pending']))
  return {'schema':'NEW_A_CURRENT_MONITOR_STATE_V1','strategy':'A_BASE','heads':heads,'watches':watches,'pending_references':pending,'actual_fills':False}
 def observed_quotes(self):
  values={}
  for sym,day,raw,h in self.db.execute('SELECT symbol,day,row_json,row_hash FROM observed_quotes ORDER BY symbol,day'):
   row=json.loads(raw)
   if monitor.digest(row)!=h:raise ValueError('corrupt observed quote')
   values[(sym,day)]=row
  return values
 def all_events(self):return [json.loads(r[0]) for r in self.db.execute('SELECT event_json FROM events ORDER BY event_id')]
 def close(self):self.db.close()
