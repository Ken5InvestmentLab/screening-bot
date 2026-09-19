import pandas as pd, numpy as np, itertools
from pathlib import Path
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
B=Path('/mnt/data/v3r')
full=pd.read_pickle(B/'cloud4h_mtf_jpx5bd.pkl').copy();full['symbol']=full.symbol.astype(str);full['timestamp']=pd.to_datetime(full.timestamp);full['date']=pd.to_datetime(full.date)
# ---- Stable existing base trigger events, replace label from corrected full ----
s0=pd.read_pickle(B/'cloud_balanced_mtf.pkl').copy();s0['symbol']=s0.symbol.astype(str);s0['timestamp']=pd.to_datetime(s0.timestamp);s0['date']=pd.to_datetime(s0.date)
lab=full[['symbol','timestamp','ret5']].drop_duplicates(['symbol','timestamp'])
s=s0.drop(columns=['ret5'],errors='ignore').merge(lab,on=['symbol','timestamp'],how='left',validate='one_to_one');s=s[s.ret5.notna()].copy()
features=['d_pre3','d_pre2','d_gap','d_macdpos','d_ema20','d_ema25','d_ema50','d_ema75','d_rsi50_70','d_rsi60','d_stoch75','d_bb80','d_vol12','d_vol20','d_body1','d_body2','d_atr5','d_atr7']
def st(z):
 x=z.ret5.dropna().to_numpy(float);n=len(x)
 if n==0:return dict(n=0,avg=np.nan,med=np.nan,wr=np.nan,p10=np.nan,p20=np.nan,p30=np.nan,m10=np.nan,t5=np.nan,max=np.nan)
 sx=np.sort(x)[::-1];return dict(n=n,avg=x.mean(),med=np.median(x),wr=(x>0).mean(),p10=(x>=.1).mean(),p20=(x>=.2).mean(),p30=(x>=.3).mean(),m10=(x<=-.1).mean(),t5=sx[5:].mean() if n>5 else np.nan,max=sx[0])
scopes={'train':s.date<'2026-07-01','jul':(s.date>='2026-07-01')&(s.date<'2026-08-01'),'aug':(s.date>='2026-08-01')&(s.date<'2026-09-01'),'all':(s.date>='2026-03-01')&(s.date<'2026-09-01')}
rows=[]
combos=[()]+[(f,) for f in features]+list(itertools.combinations(features,2))
for combo in combos:
 m=np.ones(len(s),bool)
 for f in combo:m &= s[f].fillna(False).to_numpy(bool)
 rec={'rule':'BASE' if not combo else ' + '.join(combo)}
 for k,sm in scopes.items():
  q=st(s[m&sm.to_numpy()]);rec.update({f'{k}_{a}':b for a,b in q.items()})
 tr={q:rec['train_'+q] for q in ['n','avg','med','wr','p10','p20','m10','t5']};ju={q:rec['jul_'+q] for q in ['n','avg','med','wr','p10','p20','m10','t5']}
 rec['score']=(-999 if tr['n']<45 or ju['n']<12 else 2.5*min(tr['avg'],ju['avg'])+1.5*min(tr['t5'],ju['t5'])+.06*min(tr['wr'],ju['wr'])+.08*min(tr['p10'],ju['p10'])+.12*min(tr['p20'],ju['p20'])-.10*max(tr['m10'],ju['m10']))
 rows.append(rec)
srank=pd.DataFrame(rows).sort_values('score',ascending=False);srank.to_csv(B/'cloud_stable_mtf_jpx_rank.csv',index=False)
print('STABLE TOP')
print(srank[['rule','train_n','train_avg','train_med','train_wr','train_m10','jul_n','jul_avg','jul_med','jul_wr','jul_m10','aug_n','aug_avg','aug_med','aug_wr','aug_m10','all_n','all_avg','all_med','all_wr','all_p20','all_p30','all_m10','all_t5','score']].head(12).to_string(index=False,float_format=lambda x:f'{x:.4f}'))
# choose top stable rule by corrected ranking
best_rule=srank.iloc[0].rule;combo=[] if best_rule=='BASE' else best_rule.split(' + ');sm=np.ones(len(s),bool)
for f in combo:sm &= s[f].fillna(False).to_numpy(bool)
stable=s[sm&(s.date>='2026-03-01')&(s.date<'2026-09-01')].copy();stable['lane']='Stable'
# ---- Monster WATCH corrected label ----
w=full[(full.date>='2026-03-01')&(full.date<'2026-09-01')&full.d_pre3&full.d_gap&(full.ret3>=.06)&(full.ret3<5)&full.ret5.notna()].sort_values(['symbol','date','timestamp']).drop_duplicates(['symbol','date'],keep='first').copy();w['monster']=(w.ret5>=.20).astype(int);w['danger']=(w.ret5<=-.10).astype(int)
features2=['rsi','stoch','bbpct','vsurge','atrp','body','lowerwick','draw20','offlow20','ret1','ret2','ret3','d_rsi','d_stoch','d_bbpct','d_vsurge','d_atrp','d_body','macd_pos','macd_cross','close_gt_ema20','close_gt_ema50','close_gt_ema75','ema20_up','ema50_up','body_pos','body1','body2','wick30','wick50','vol12','vol15','vol20','vol30','atr_lt5','atr_lt7','d_macdpos','d_ema20','d_ema25','d_ema50','d_ema75','d_rsi50_70','d_rsi60','d_stoch75','d_bb80','d_vol12','d_vol20','d_vol30','d_body1','d_body2','d_atr5','d_atr7']
X=w[features2].replace([np.inf,-np.inf],np.nan)
def mod(seed=1):return make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=.15,max_iter=500,class_weight='balanced',random_state=seed))
folds=[('2026-04-01','2026-05-01'),('2026-05-01','2026-06-01'),('2026-06-01','2026-07-01')]
wf=[]
for frac in [.10,.20,.30]:
 ss=[]
 for ts,te in folds:
  tr=w.date<ts;test=(w.date>=ts)&(w.date<te);mm=mod();mm.fit(X[tr],w.loc[tr,'monster']);z=w.loc[test].copy();z['score']=mm.predict_proba(X[test])[:,1];n=max(1,int(np.ceil(len(z)*frac)));ss.append(st(z.nlargest(n,'score')))
 obj=np.mean([x['avg'] for x in ss])+1.5*np.mean([x['p20'] for x in ss])+.15*np.mean([x['wr'] for x in ss])-.6*np.mean([x['m10'] for x in ss])+.5*min(x['avg'] for x in ss)
 wf.append((obj,frac,ss))
wf=sorted(wf,reverse=True,key=lambda x:x[0]);print('\nMONSTER WF');
for x in wf:print(x)
frac=wf[0][1];tr=w.date<'2026-07-01';mm=mod();mm.fit(X[tr],w.loc[tr,'monster']);w['priority_score']=mm.predict_proba(X)[:,1];thr=w.loc[tr,'priority_score'].quantile(1-frac);w['priority']=w.priority_score>=thr
print('MONSTER SELECT frac',frac,'thr',thr)
for tag,m in [('train',tr),('jul',(w.date>='2026-07-01')&(w.date<'2026-08-01')),('aug',(w.date>='2026-08-01')&(w.date<'2026-09-01'))]:print(tag,'base',st(w[m]),'priority',st(w[m&w.priority]),'rate',(m&w.priority).sum()/m.sum())
monster=w[w.priority].copy();monster['lane']='Monster'
# ---- Union dedupe symbol-day ----
cols=['symbol','timestamp','date','close','ret5','lane'];u=pd.concat([stable[cols],monster[cols]],ignore_index=True).sort_values(['symbol','date','timestamp']); rows=[]
for (sym,date),z in u.groupby(['symbol','date'],sort=False):
 r=z.iloc[0].copy(); r['lane']='Both' if z.lane.nunique()>1 else z.iloc[0].lane;rows.append(r)
u=pd.DataFrame(rows)
print('\nFINAL LANES corrected')
for name,z in [('Stable',stable),('MonsterPriority',monster),('Union',u)]:
 print(name,st(z))
 for mon,g in z.groupby(z.date.dt.to_period('M')):print(mon,st(g))
# known current stable top +20 recall
cur=pd.read_csv(B/'teacher_stable6_confirmed.csv');cur['date']=pd.to_datetime(cur.date);cur['symbol']=cur.symbol.astype(str);known=cur[cur.perf_5bd>=.20].sort_values('perf_5bd',ascending=False)
for name,z in [('Stable',stable),('MonsterPriority',monster),('Union',u),('WATCH',w)]:
 hits=[]
 for _,r in known.iterrows():
  q=z[(z.symbol==r.symbol)&((z.date-r.date).abs()<=pd.Timedelta(days=7))]
  hits.append((r.symbol,r['name'],r.perf_5bd,bool(len(q))))
 print('RECALL',name,sum(x[3] for x in hits),'/',len(hits),hits)
stable.to_csv(B/'cloud_stable_jpx.csv',index=False);monster.to_csv(B/'cloud_monster_priority_jpx.csv',index=False);u.to_csv(B/'cloud_two_lane_union_jpx.csv',index=False);w.to_pickle(B/'cloud_monster_watch_jpx.pkl')
