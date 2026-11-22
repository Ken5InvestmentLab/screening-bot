"""既存品質検査を通ったsourceから凍結Aの因果特徴量を生成する。"""
import datetime,math,time
import pandas as pd
from .features import compute_features
from .files import digest
FIELDS=['open','high','low','close','volume','actual_close','actual_volume','split_factor','source_usable','candidate','low20','high20','median_turnover20']
def clean(value):
 if pd.isna(value):return None
 if hasattr(value,'item'):value=value.item()
 return None if isinstance(value,float) and not math.isfinite(value) else value
def restriction_intervals(rows):
 result={}
 for row in rows:
  start=row.get('designation_date') or row.get('delisting_date')
  if not start:continue
  result.setdefault(str(row['code']),[]).append({'start':start,'end':row.get('relisting_date'),'reason':'VERIFIED_DELISTED' if row.get('delisting_date') and start==row['delisting_date'] else 'VERIFIED_RESTRICTED'})
 return result
def prepare_packet(source,seed,calendar,current_heads,*,as_of,observed_at,dry_run,missing_quote_days=()):
 frame=source['frame'];latest=pd.to_datetime(frame.date).max().date().isoformat()
 if latest!=as_of:raise ValueError('fresh completed-session source required')
 if as_of not in calendar or calendar!=sorted(set(calendar)) or calendar[:len(seed['calendar'])]!=seed['calendar']:raise ValueError('verified market-calendar prefix required')
 positions={day:index for index,day in enumerate(calendar)}
 end=positions[as_of];universe=sorted(set(seed['symbols'])|set(frame.symbol.astype(str)))
 heads={s:current_heads.get(s,calendar[max(0,end-1)]) for s in universe}
 missing_by_symbol={}
 for symbol,day in missing_quote_days:
  missing_by_symbol.setdefault(symbol,set()).add(day)
 anchors=[]
 for sym,day in heads.items():
  if day is None:continue
  index=positions[day];missing=missing_by_symbol.get(sym,())
  while index>0 and calendar[index] in missing:index-=1
  anchors.append(index)
 first=min(anchors);start=max(0,first-60);feature_calendar=calendar[start:end+1];days=calendar[first:end+1]
 parts=frame.loc[pd.to_datetime(frame.date).between(pd.Timestamp(feature_calendar[0]),pd.Timestamp(as_of)),['date','symbol']+FIELDS[:9]].copy();groups={str(s):g.drop(columns='symbol') for s,g in parts.groupby('symbol',sort=False)};rows={d:{} for d in days};cpu=time.process_time();wall=time.monotonic()
 for i,sym in enumerate(universe):
  group=groups.get(sym,pd.DataFrame(columns=['date']+FIELDS[:9]))
  if sym in missing_by_symbol:
   group=group.loc[~pd.to_datetime(group['date']).isin(pd.to_datetime(sorted(missing_by_symbol[sym])))]
  features=compute_features(group,feature_calendar)
  for day in days:
   value={k:clean(features.loc[pd.Timestamp(day),k]) for k in FIELDS};rows[day][sym]=value if any(value[k] is not None for k in ['open','high','low','close']) else None
  if i%100==99:
   delay=(time.process_time()-cpu)/.4-(time.monotonic()-wall)
   if delay>0:time.sleep(min(delay,2))
 return {'schema':'NEW_A_VERIFIED_FEATURE_PACKET_V1','strategy':'A_BASE','as_of':as_of,'observed_at':observed_at,'calendar':calendar,'calendar_verified':True,'source_quality_verified':True,'source_hash':source['source_hash'],'rows_by_day':rows,'universe':universe,'restrictions':restriction_intervals(source['restrictions']),'dry_run':dry_run,'source_revision_pending':{'frozenPrefixRewritten':False,'frozenEqualityClaimed':False,'currentSourceSHA256':source['source_hash'],'existingSourceRevision':source.get('source_revision',{}),'qualityAuditSHA256':source.get('source_quality',{}).get('audit_sha256'),'policy':'frozen historical inputs immutable; new observations carry their actual source vintage'}}
