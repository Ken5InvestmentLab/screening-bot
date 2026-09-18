"""Recovered verbatim Monster section of /mnt/data/v3r/revalidate_lanes_jpx.py.

Provenance: ChatGPT conversation `研修継続報告`, message
3141d527-c580-4ae7-a045-764138f04611, tool call
`安定したモンスター銘柄を再検証した`.  This is research-only evidence.
It intentionally requires the historical `cloud4h_mtf_jpx5bd.pkl` and does not
substitute a newly engineered feature frame.
"""
import pandas as pd, numpy as np
from pathlib import Path
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

B = Path('/mnt/data/v3r')
full = pd.read_pickle(B/'cloud4h_mtf_jpx5bd.pkl').copy()
full['symbol'] = full.symbol.astype(str)
full['timestamp'] = pd.to_datetime(full.timestamp)
full['date'] = pd.to_datetime(full.date)

def st(z):
    x=z.ret5.dropna().to_numpy(float); n=len(x)
    if n==0:
        return dict(n=0,avg=np.nan,med=np.nan,wr=np.nan,p10=np.nan,p20=np.nan,p30=np.nan,m10=np.nan,t5=np.nan,max=np.nan)
    sx=np.sort(x)[::-1]
    return dict(n=n,avg=x.mean(),med=np.median(x),wr=(x>0).mean(),p10=(x>=.1).mean(),p20=(x>=.2).mean(),p30=(x>=.3).mean(),m10=(x<=-.1).mean(),t5=sx[5:].mean() if n>5 else np.nan,max=sx[0])

w=full[(full.date>='2026-03-01')&(full.date<'2026-09-01')&full.d_pre3&full.d_gap&(full.ret3>=.06)&(full.ret3<5)&full.ret5.notna()].sort_values(['symbol','date','timestamp']).drop_duplicates(['symbol','date'],keep='first').copy()
w['monster']=(w.ret5>=.20).astype(int)
w['danger']=(w.ret5<=-.10).astype(int)
features2=['rsi','stoch','bbpct','vsurge','atrp','body','lowerwick','draw20','offlow20','ret1','ret2','ret3','d_rsi','d_stoch','d_bbpct','d_vsurge','d_atrp','d_body','macd_pos','macd_cross','close_gt_ema20','close_gt_ema50','close_gt_ema75','ema20_up','ema50_up','body_pos','body1','body2','wick30','wick50','vol12','vol15','vol20','vol30','atr_lt5','atr_lt7','d_macdpos','d_ema20','d_ema25','d_ema50','d_ema75','d_rsi50_70','d_rsi60','d_stoch75','d_bb80','d_vol12','d_vol20','d_vol30','d_body1','d_body2','d_atr5','d_atr7']
X=w[features2].replace([np.inf,-np.inf],np.nan)

def mod(seed=1):
    return make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=.15,max_iter=500,class_weight='balanced',random_state=seed))

folds=[('2026-04-01','2026-05-01'),('2026-05-01','2026-06-01'),('2026-06-01','2026-07-01')]
wf=[]
for frac in [.10,.20,.30]:
    ss=[]
    for ts,te in folds:
        tr=w.date<ts; test=(w.date>=ts)&(w.date<te); mm=mod(); mm.fit(X[tr],w.loc[tr,'monster']); z=w.loc[test].copy(); z['score']=mm.predict_proba(X[test])[:,1]; n=max(1,int(np.ceil(len(z)*frac))); ss.append(st(z.nlargest(n,'score')))
    obj=np.mean([x['avg'] for x in ss])+1.5*np.mean([x['p20'] for x in ss])+.15*np.mean([x['wr'] for x in ss])-.6*np.mean([x['m10'] for x in ss])+.5*min(x['avg'] for x in ss)
    wf.append((obj,frac,ss))
wf=sorted(wf,reverse=True,key=lambda x:x[0])
frac=wf[0][1]
tr=w.date<'2026-07-01'
mm=mod(); mm.fit(X[tr],w.loc[tr,'monster'])
w['priority_score']=mm.predict_proba(X)[:,1]
thr=w.loc[tr,'priority_score'].quantile(1-frac)
w['priority']=w.priority_score>=thr
monster=w[w.priority].copy(); monster['lane']='Monster'
monster.to_csv(B/'cloud_monster_priority_jpx.csv',index=False)
print('MONSTER SELECT frac',frac,'thr',thr)
print(st(monster))
