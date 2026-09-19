import pandas as pd, numpy as np
from pathlib import Path
B=Path('/mnt/data/v3r')
cf=pd.read_pickle(B/'cloud4h_frame_dedup_sep.pkl')[['symbol','timestamp']].copy();cf['symbol']=cf.symbol.astype(str);cf['timestamp']=pd.to_datetime(cf.timestamp);wanted=set(cf.symbol)
raw=pd.read_csv(B/'teacher_ohlcv_4h_raw.csv');raw['symbol']=raw.symbol.astype(str);raw=raw[raw.symbol.isin(wanted)].copy();raw['timestamp']=pd.to_datetime(raw.timestamp,format='mixed')
_a=raw.alert_id.astype(str);raw['_prio']=np.where(_a.str.contains('REPAIR|MIDDAY',case=False,regex=True),2,1);raw['_vp']=pd.to_numeric(raw.volume,errors='coerce').fillna(-1)
raw=raw.sort_values(['symbol','timestamp','_prio','_vp']).drop_duplicates(['symbol','timestamp'],keep='last').drop(columns=['_prio','_vp'])
for c in ['open','high','low','close','volume']:raw[c]=pd.to_numeric(raw[c],errors='coerce')
raw=raw.dropna(subset=['open','high','low','close','volume']).sort_values(['symbol','timestamp']).reset_index(drop=True);raw['date']=raw.timestamp.dt.normalize()
# current-day cumulative snapshot from 4h sessions
gsd=raw.groupby(['symbol','date'],sort=False)
raw['sopen']=gsd.open.transform('first');raw['shigh']=gsd.high.cummax();raw['slow']=gsd.low.cummin();raw['svol']=gsd.volume.cumsum();raw['sclose']=raw.close
# full daily table
d=(raw.groupby(['symbol','date'],as_index=False).agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum')).sort_values(['symbol','date']).reset_index(drop=True))
g=d.groupby('symbol',sort=False,group_keys=False)
# EMA via transform
def ewmcol(col,span): return g[col].transform(lambda s:s.ewm(span=span,adjust=False,min_periods=span).mean())
for p in [12,20,25,26,50,75]:d[f'e{p}']=ewmcol('close',p)
d['macd']=d.e12-d.e26;d['msig']=d.groupby('symbol',sort=False).macd.transform(lambda s:s.ewm(span=9,adjust=False,min_periods=9).mean())
# previous states
for c in ['close','e12','e20','e25','e26','e50','e75','msig']:
 d['p_'+c]=g[c].shift(1)
# daily diff/TR
d['diff']=g.close.diff();d['gain']=d['diff'].clip(lower=0);d['loss']=(-d['diff']).clip(lower=0)
pc=g.close.shift(1);d['tr']=pd.concat([(d.high-d.low),(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
# helper prior rolling per symbol
def prior_roll(col,w,fun):
 sh=g[col].shift(1)
 if fun=='sum': return sh.groupby(d.symbol,sort=False).rolling(w,min_periods=w).sum().reset_index(level=0,drop=True)
 if fun=='mean': return sh.groupby(d.symbol,sort=False).rolling(w,min_periods=w).mean().reset_index(level=0,drop=True)
 if fun=='max': return sh.groupby(d.symbol,sort=False).rolling(w,min_periods=w).max().reset_index(level=0,drop=True)
 if fun=='min': return sh.groupby(d.symbol,sort=False).rolling(w,min_periods=w).min().reset_index(level=0,drop=True)
d['pgain13']=prior_roll('gain',13,'sum');d['ploss13']=prior_roll('loss',13,'sum')
d['phigh13']=prior_roll('high',13,'max');d['plow13']=prior_roll('low',13,'min')
d['pclose19_sum']=prior_roll('close',19,'sum');d['pclose19_sq']=g.close.transform(lambda s:(s*s).shift(1).rolling(19,min_periods=19).sum())
d['ptr13_sum']=prior_roll('tr',13,'sum');d['pvol20']=prior_roll('volume',20,'mean')
d['prev1']=g.close.shift(1);d['prev2']=g.close.shift(2);d['prev3']=g.close.shift(3)
# merge daily prior state onto every raw snapshot
keep=['symbol','date','p_close','p_e12','p_e20','p_e25','p_e26','p_e50','p_e75','p_msig','pgain13','ploss13','phigh13','plow13','pclose19_sum','pclose19_sq','ptr13_sum','pvol20','prev1','prev2','prev3']
r=raw.merge(d[keep],on=['symbol','date'],how='left',validate='many_to_one')
sc=r.sclose;so=r.sopen;sh=r.shigh;sl=r.slow;sv=r.svol
# current partial daily EMA updates
for p in [12,20,25,26,50,75]:
 k=2/(p+1);r[f'de{p}']=sc*k+r[f'p_e{p}']*(1-k)
r['dmacd']=r.de12-r.de26;r['dmsig']=r.dmacd*.2+r.p_msig*.8;r['d_macdpos']=r.dmacd>r.dmsig
# RSI 14 simple
curdiff=sc-r.p_close;gain=curdiff.clip(lower=0);loss=(-curdiff).clip(lower=0);ag=(r.pgain13+gain)/14;al=(r.ploss13+loss)/14;r['d_rsi']=np.where(al>0,100-100/(1+ag/al),100.0)
# stoch
hh=np.maximum(r.phigh13,sh);ll=np.minimum(r.plow13,sl);r['d_stoch']=np.where(hh>ll,(sc-ll)/(hh-ll)*100,50.0)
# BB20 previous19+current
sm=r.pclose19_sum+sc;sq=r.pclose19_sq+sc*sc;mean=sm/20;var=(sq/20-mean*mean).clip(lower=0);sd=np.sqrt(var);r['d_bbpct']=np.where(sd>0,(sc-(mean-2*sd))/(4*sd),.5)
# ATR14
trnow=pd.concat([(sh-sl),(sh-r.p_close).abs(),(sl-r.p_close).abs()],axis=1).max(axis=1);atr=(r.ptr13_sum+trnow)/14;r['d_atrp']=atr/sc*100
r['d_vsurge']=sv/r.pvol20;r['d_body']=(sc-so)/sc*100
r['d_pre3']=(r.prev1<r.prev2)&(r.prev2<r.prev3);r['d_pre2']=r.prev1<r.prev2;r['d_gap']=so>r.p_close
for p in [20,25,50,75]:r[f'd_ema{p}']=sc>r[f'de{p}']
r['d_rsi50_70']=r.d_rsi.between(50,70, inclusive='left');r['d_rsi60']=r.d_rsi>=60;r['d_stoch75']=r.d_stoch>=75;r['d_bb80']=r.d_bbpct>=.8
r['d_vol12']=r.d_vsurge>=1.2;r['d_vol20']=r.d_vsurge>=2;r['d_vol30']=r.d_vsurge>=3;r['d_body1']=r.d_body>=1;r['d_body2']=r.d_body>=2;r['d_atr5']=r.d_atrp<5;r['d_atr7']=r.d_atrp<7
feat=['symbol','timestamp','d_pre3','d_pre2','d_gap','d_macdpos','d_ema20','d_ema25','d_ema50','d_ema75','d_rsi','d_stoch','d_bbpct','d_vsurge','d_atrp','d_body','d_rsi50_70','d_rsi60','d_stoch75','d_bb80','d_vol12','d_vol20','d_vol30','d_body1','d_body2','d_atr5','d_atr7']
out=r[feat].merge(cf,on=['symbol','timestamp'],how='inner',validate='one_to_one')
out.to_pickle(B/'mtf_features_all_fast.pkl');print('features',out.shape,'symbols',out.symbol.nunique())
full=pd.read_pickle(B/'cloud4h_frame_dedup_sep.pkl').copy();full['symbol']=full.symbol.astype(str);full['timestamp']=pd.to_datetime(full.timestamp);full=full.merge(out,on=['symbol','timestamp'],how='left',validate='one_to_one');full.to_pickle(B/'cloud4h_mtf_fast.pkl');print('full',full.shape,'missing',full.d_rsi.isna().mean())
# teacher validation exact-ish
t=pd.read_csv(B/'teacher_stable6_confirmed.csv');t['symbol']=t.symbol.astype(str);t['dt']=pd.to_datetime(t.received_at);t['date2']=pd.to_datetime(t.date);t['hour2']=np.where(t.dt.dt.hour<14,9,13)
rows=[]
for _,x in t.nlargest(10,'perf_5bd').iterrows():
 ts=pd.Timestamp(x.date2)+pd.Timedelta(hours=int(x.hour2));z=out[(out.symbol==x.symbol)&(out.timestamp==ts)]
 if z.empty:continue
 y=z.iloc[0];rows.append([x.symbol,x.perf_5bd,x.pre_down3,y.d_pre3,x.gap_up,y.d_gap,x._rsi,y.d_rsi,x._stoch,y.d_stoch,x._bbpct,y.d_bbpct,x._vsurge,y.d_vsurge])
print(pd.DataFrame(rows,columns=['sym','perf','tpre','dpre','tgap','dgap','trsi','drsi','tst','dst','tbb','dbb','tvs','dvs']).to_string(index=False))
