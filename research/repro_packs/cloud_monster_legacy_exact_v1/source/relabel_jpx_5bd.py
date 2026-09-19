import pandas as pd, numpy as np
from pathlib import Path
import exchange_calendars as xc
B=Path('/mnt/data/v3r')
raw=pd.read_csv(B/'teacher_ohlcv_4h_raw.csv');raw['symbol']=raw.symbol.astype(str);raw['timestamp']=pd.to_datetime(raw.timestamp,format='mixed');raw['date']=raw.timestamp.dt.normalize()
for c in ['open','high','low','close','volume']:raw[c]=pd.to_numeric(raw[c],errors='coerce')
_a=raw.alert_id.astype(str);raw['_prio']=np.where(_a.str.contains('REPAIR|MIDDAY',case=False,regex=True),2,1);raw['_vp']=raw.volume.fillna(-1)
raw=raw.sort_values(['symbol','timestamp','_prio','_vp']).drop_duplicates(['symbol','timestamp'],keep='last').drop(columns=['_prio','_vp'])
valid=raw.dropna(subset=['close']).copy();daily=valid.groupby(['symbol','date'],as_index=False).agg(close=('close','last'))
cal=xc.get_calendar('JPX'); sessions=cal.sessions_in_range('2025-12-01','2026-09-30'); dates=pd.DatetimeIndex(sessions).tz_localize(None).normalize()
map5={dates[i]:dates[i+5] for i in range(len(dates)-5)}
print('sessions around Apr',dates[(dates>='2026-04-13')&(dates<='2026-04-23')].tolist())
df=pd.read_pickle(B/'cloud4h_mtf_fast.pkl').copy();df['date']=pd.to_datetime(df.date);df['symbol']=df.symbol.astype(str);df['target_date_5bd']=df.date.map(map5)
target=daily.rename(columns={'date':'target_date_5bd','close':'close_5bd_jpx'})
df=df.merge(target,on=['symbol','target_date_5bd'],how='left',validate='many_to_one');df['ret5_jpx']=df.close_5bd_jpx/df.close-1
print('coverage',df.ret5_jpx.notna().mean(),df.ret5_jpx.notna().sum(),len(df))
teach=pd.read_csv(B/'teacher_bottom_confirmed.csv');teach['symbol']=teach.symbol.astype(str);teach['date2']=pd.to_datetime(teach.date);teach['recv']=pd.to_datetime(teach.received_at);teach['hour']=np.where(teach.recv.dt.hour<14,9,13);teach['timestamp']=teach.date2+pd.to_timedelta(teach.hour,unit='h')
z=teach.merge(df[['symbol','timestamp','ret5_jpx']],on=['symbol','timestamp'],how='left');a=pd.to_numeric(z.perf_5bd,errors='coerce');b=z.ret5_jpx;m=a.notna()&b.notna();print('teacher matched',m.sum(),'corr',a[m].corr(b[m]),'MAE',(a[m]-b[m]).abs().mean(),'within2pp',((a[m]-b[m]).abs()<=.02).mean())
st=pd.read_csv(B/'teacher_stable6_confirmed.csv');st['symbol']=st.symbol.astype(str);st['date2']=pd.to_datetime(st.date);st['recv']=pd.to_datetime(st.received_at);st['hour']=np.where(st.recv.dt.hour<14,9,13);st['timestamp']=st.date2+pd.to_timedelta(st.hour,unit='h')
zz=st.merge(df[['symbol','timestamp','target_date_5bd','close','close_5bd_jpx','ret5_jpx']],on=['symbol','timestamp'],how='left');print(zz.nlargest(12,'perf_5bd')[['symbol','name','date','entry','perf_5bd','target_date_5bd','close','close_5bd_jpx','ret5_jpx']].to_string(index=False))
df['ret5_old']=df.ret5;df['ret5']=df.ret5_jpx;df.to_pickle(B/'cloud4h_mtf_jpx5bd.pkl')
