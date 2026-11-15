"""凍結特徴量だけを元コードから同一ASTで抽出。episode規則はmonitorが担当。"""
import numpy as np
import pandas as pd
def flags(s):return s.fillna(False).astype(str).str.lower().isin(['true','1']).to_numpy()

def prepare(frame,market_calendar=None):
 x=frame.copy()
 if 'date' in x:x=x.set_index(pd.to_datetime(x.pop('date')))
 if market_calendar is not None:x=x.reindex(pd.DatetimeIndex(market_calendar))
 x.index.name='date'
 if not isinstance(x.index,pd.DatetimeIndex) or x.index.has_duplicates or not x.index.is_monotonic_increasing:raise ValueError('Sorted unique full market calendar required')
 return x

def raw_valid(x):
 a=x[['open','high','low','close']].to_numpy(dtype=float,na_value=np.nan);o,h,l,c=a.T
 return np.isfinite(a).all(axis=1)&(a>0).all(axis=1)&flags(x.source_usable)&(l<=np.minimum(o,c))&(np.maximum(o,c)<=h)

def compute_features(frame,market_calendar=None):
 x=prepare(frame,market_calendar);v=raw_valid(x)
 a=x[['actual_close','split_factor']].to_numpy(dtype=float,na_value=np.nan)
 b=x[['volume','actual_volume']].to_numpy(dtype=float,na_value=np.nan)
 valid=v&np.isfinite(a).all(axis=1)&(a>0).all(axis=1)&np.isfinite(b).all(axis=1)&(b>=0).all(axis=1)
 x['quality60']=pd.Series(valid,index=x.index).rolling(60,min_periods=60).sum().eq(60)
 x['positive_volume20']=((x.volume>0)&(x.actual_volume>0)).rolling(20,min_periods=20).sum().eq(20)
 tv=x.actual_close*x.actual_volume
 x['median_turnover20']=tv.rolling(20,min_periods=20).median()
 x['liquidity']=x.median_turnover20.ge(20000000)&tv.rolling(5,min_periods=5).min().ge(5000000)
 x['eligible_common']=x.quality60&x.positive_volume20&x.liquidity
 x['high20']=x.high.rolling(20,min_periods=20).max();x['low20']=x.low.rolling(20,min_periods=20).min()
 x['range20']=x.high20/x.low20-1;x['position20']=(x.close-x.low20)/(x.high20-x.low20)
 x['ret20']=x.close/x.close.shift(20)-1;x['ret5']=x.close/x.close.shift(5)-1
 x['turnover_ratio']=tv.rolling(5,min_periods=5).mean()/tv.shift(5).rolling(20,min_periods=20).mean()
 up_tv=tv.where(x.close>x.close.shift(1),0.)
 x['up_turnover_share10']=up_tv.rolling(10,min_periods=10).sum()/tv.rolling(10,min_periods=10).sum()
 x['candidate']=x.eligible_common&x.range20.gt(0)&x.range20.le(.20)&x.ret20.abs().le(.08)&x.ret5.abs().le(.05)&x.position20.between(.30,.75)&x.turnover_ratio.ge(1.30)&x.up_turnover_share10.ge(.65)
 return x

