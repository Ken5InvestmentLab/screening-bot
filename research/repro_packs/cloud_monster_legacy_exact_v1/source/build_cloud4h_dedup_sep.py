import pandas as pd, numpy as np, itertools, json, math
from pathlib import Path

BASE=Path('/mnt/data/v3r')
raw=pd.read_csv(BASE/'teacher_ohlcv_4h_raw.csv')
# dedupe same symbol/timestamp: prefer repaired/midday rows over original new_session
raw['timestamp']=pd.to_datetime(raw['timestamp'], format='mixed')
# authoritative repair/midday rows first; otherwise keep the largest observed volume for duplicate sessions
_aid=raw['alert_id'].astype(str)
raw['_prio']=np.where(_aid.str.contains('REPAIR|MIDDAY', case=False, regex=True),2,1)
raw['_volprio']=pd.to_numeric(raw['volume'], errors='coerce').fillna(-1)
raw=raw.sort_values(['symbol','timestamp','_prio','_volprio']).drop_duplicates(['symbol','timestamp'],keep='last').drop(columns=['_prio','_volprio'])
raw['date']=raw['timestamp'].dt.normalize()
raw['hour']=raw['timestamp'].dt.hour
raw=raw.sort_values(['symbol','timestamp']).reset_index(drop=True)
raw['seq']=raw.groupby('symbol').cumcount()
for c in ['open','high','low','close','volume']:
    raw[c]=pd.to_numeric(raw[c], errors='coerce')
raw=raw.dropna(subset=['open','high','low','close','volume'])

# daily reference + 5 observed trading-day outcome
daily=(raw.groupby(['symbol','date'],as_index=False)
       .agg(open=('open','first'), high=('high','max'), low=('low','min'), close=('close','last'), volume=('volume','sum'))
       .sort_values(['symbol','date']))
gd=daily.groupby('symbol', group_keys=False)
daily['prev_close']=gd['close'].shift(1)
daily['prev_volume']=gd['volume'].shift(1)
daily['close_5bd']=gd['close'].shift(-5)
ref=daily[['symbol','date','prev_close','prev_volume','close_5bd']]
raw=raw.merge(ref,on=['symbol','date'],how='left')
raw['ret5']=raw['close_5bd']/raw['close']-1

# 4H-bar technicals, per symbol
parts=[]
for sym,g in raw.groupby('symbol',sort=False):
    g=g.sort_values('timestamp').copy()
    C=g['close']; O=g['open']; H=g['high']; L=g['low']; V=g['volume']
    pc=C.shift(1)
    tr=pd.concat([(H-L),(H-pc).abs(),(L-pc).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14,min_periods=14).mean()
    g['atrp']=atr/C
    g['ema20']=C.ewm(span=20,adjust=False,min_periods=20).mean()
    g['ema50']=C.ewm(span=50,adjust=False,min_periods=50).mean()
    g['ema75']=C.ewm(span=75,adjust=False,min_periods=75).mean()
    ema12=C.ewm(span=12,adjust=False,min_periods=12).mean(); ema26=C.ewm(span=26,adjust=False,min_periods=26).mean()
    macd=ema12-ema26; msig=macd.ewm(span=9,adjust=False,min_periods=9).mean(); hist=macd-msig
    g['macd_pos']=hist>0
    g['macd_cross']=(hist>0)&(hist.shift(1)<=0)
    # RSI Wilder 12
    d=C.diff(); up=d.clip(lower=0); dn=(-d).clip(lower=0)
    au=up.ewm(alpha=1/12,adjust=False,min_periods=12).mean(); ad=dn.ewm(alpha=1/12,adjust=False,min_periods=12).mean()
    rs=au/ad.replace(0,np.nan); rsi=100-100/(1+rs); rsi=rsi.fillna(100)
    g['rsi']=rsi; g['rsi_cross35']=(rsi>35)&(rsi.shift(1)<=35); g['rsi_cross40']=(rsi>40)&(rsi.shift(1)<=40); g['rsi_cross50']=(rsi>50)&(rsi.shift(1)<=50)
    mid=C.rolling(20,min_periods=20).mean(); sd=C.rolling(20,min_periods=20).std(ddof=0); lo=mid-2*sd; hi=mid+2*sd
    g['bbpct']=(C-lo)/(hi-lo).replace(0,np.nan)
    l14=L.rolling(14,min_periods=14).min(); h14=H.rolling(14,min_periods=14).max(); st=(C-l14)/(h14-l14).replace(0,np.nan)*100
    g['stoch']=st
    vavg=V.shift(1).rolling(20,min_periods=10).mean(); g['vsurge']=V/vavg
    g['body']=(C-O)/C
    rng=(H-L).replace(0,np.nan); g['lowerwick']=(np.minimum(C,O)-L)/rng
    g['gap_up']=O>pc
    g['pre_down3']=(C.shift(1)<C.shift(2))&(C.shift(2)<C.shift(3))
    g['pre_down2']=(C.shift(1)<C.shift(2))
    g['close_gt_ema20']=C>g['ema20']; g['close_gt_ema50']=C>g['ema50']; g['close_gt_ema75']=C>g['ema75']
    g['ema20_up']=g['ema20']>g['ema20'].shift(1); g['ema50_up']=g['ema50']>g['ema50'].shift(1)
    high20=H.shift(1).rolling(20,min_periods=10).max(); g['draw20']=C/high20-1
    low20=L.shift(1).rolling(20,min_periods=10).min(); g['offlow20']=C/low20-1
    g['ret1']=C/pc-1; g['ret2']=C/C.shift(2)-1; g['ret3']=C/C.shift(3)-1
    parts.append(g)
df=pd.concat(parts,ignore_index=True)

# Production-equivalent coarse universe constraints
base=(df['prev_close'].le(1000)&df['prev_volume'].ge(10000)&df['volume'].ge(5000)&df['ret5'].notna()&df['timestamp'].ge('2026-01-01')&df['timestamp'].lt('2026-09-11'))
df=df[base].copy()

# Boolean literals. All are current/past only.
lits={
 'AM': df.hour.eq(9), 'PM':df.hour.eq(13),
 'gap_up':df.gap_up, 'pre_down3':df.pre_down3, 'pre_down2':df.pre_down2,
 'body_pos':df.body.gt(0), 'body05':df.body.ge(.005), 'body1':df.body.ge(.01), 'body2':df.body.ge(.02),
 'wick30':df.lowerwick.ge(.30), 'wick50':df.lowerwick.ge(.50),
 'rsi_lt35':df.rsi.lt(35), 'rsi_lt40':df.rsi.lt(40), 'rsi_35_55':df.rsi.between(35,55), 'rsi_40_60':df.rsi.between(40,60),
 'rsi_cross35':df.rsi_cross35, 'rsi_cross40':df.rsi_cross40, 'rsi_cross50':df.rsi_cross50,
 'stoch_lt20':df.stoch.lt(20), 'stoch_lt30':df.stoch.lt(30), 'stoch_20_60':df.stoch.between(20,60),
 'bb_lt20':df.bbpct.le(.20), 'bb_lt35':df.bbpct.le(.35), 'bb_20_60':df.bbpct.between(.20,.60),
 'macd_pos':df.macd_pos, 'macd_cross':df.macd_cross,
 'ema20':df.close_gt_ema20, 'ema50':df.close_gt_ema50, 'ema75':df.close_gt_ema75,
 'ema20_up':df.ema20_up,'ema50_up':df.ema50_up,
 'vol12':df.vsurge.ge(1.2),'vol15':df.vsurge.ge(1.5),'vol20':df.vsurge.ge(2.0),'vol30':df.vsurge.ge(3.0),
 'atr_lt5':df.atrp.lt(.05),'atr_lt7':df.atrp.lt(.07),'atr_5_12':df.atrp.between(.05,.12),
 'draw5':df.draw20.le(-.05),'draw10':df.draw20.le(-.10),'draw15':df.draw20.le(-.15),'draw20':df.draw20.le(-.20),
 'ret1_pos':df.ret1.gt(0),'ret1_gt2':df.ret1.ge(.02),'ret1_lt0':df.ret1.lt(0),
}
for k,v in lits.items(): df[k]=v.fillna(False).astype(bool)


print('frame',df.shape,'dups',df.duplicated(['symbol','timestamp']).sum())
df.to_pickle(BASE/'cloud4h_frame_dedup_sep.pkl')
print('saved')
