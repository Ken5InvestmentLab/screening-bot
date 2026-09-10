from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

import no_tv_v10_standalone as base

PINE_FEATURES = [
    "pine_bottom", "pine_cross_buy", "pine_exit_short", "pine_trend_flip_up", "pine_force_reverse_buy",
    "pine_rsi12", "pine_rsi12_delta", "pine_mid_slope_pct", "pine_width", "pine_atr_pct",
    "pine_last_signal_before", "pine_bars_since_signal", "pine_wait_pullback_before",
]
HYBRID_FEATURES = base.FEATURES + PINE_FEATURES


def wilder_rma(values, length):
    x=np.asarray(values,float); out=np.full(len(x),np.nan)
    if len(x)<length:return out
    seed=None
    for i in range(length-1,len(x)):
        w=x[i-length+1:i+1]
        if np.all(np.isfinite(w)):
            out[i]=float(np.mean(w)); seed=i; break
    if seed is None:return out
    a=1.0/length
    for i in range(seed+1,len(x)):
        out[i]=a*x[i]+(1-a)*out[i-1] if np.isfinite(x[i]) else out[i-1]
    return out


def pine_rsi(close,length=12):
    c=np.asarray(close,float); d=np.full(len(c),np.nan); d[1:]=c[1:]-c[:-1]
    up=np.where(np.isnan(d),np.nan,np.maximum(d,0)); dn=np.where(np.isnan(d),np.nan,np.maximum(-d,0))
    au=wilder_rma(up,length); ad=wilder_rma(dn,length); out=np.full(len(c),np.nan)
    both=(au==0)&(ad==0); out[both]=50.; only=(ad==0)&(au>0); out[only]=100.
    normal=(ad>0)&np.isfinite(au); rs=np.zeros(len(c)); rs[normal]=au[normal]/ad[normal]; out[normal]=100-100/(1+rs[normal])
    return out


def true_range(h,l,c):
    h=np.asarray(h,float);l=np.asarray(l,float);c=np.asarray(c,float);tr=np.full(len(c),np.nan)
    if len(c):tr[0]=h[0]-l[0]
    if len(c)>1:
        pc=c[:-1];tr[1:]=np.maximum.reduce([h[1:]-l[1:],np.abs(h[1:]-pc),np.abs(l[1:]-pc)])
    return tr


def pine_state_frame(sessions):
    s=sessions.sort_values(["date","session"]).reset_index(drop=True).copy()
    c=s.close.to_numpy(float);h=s.high.to_numpy(float);l=s.low.to_numpy(float);n=len(s)
    mid=pd.Series(c).rolling(20,min_periods=20).mean().to_numpy();sd=pd.Series(c).rolling(20,min_periods=20).std(ddof=0).to_numpy()
    rsi=pine_rsi(c,12);atr=wilder_rma(true_range(h,l,c),14);slope=np.full(n,np.nan);slope[1:]=mid[1:]-mid[:-1]
    width=np.full(n,np.nan);good=np.isfinite(mid)&(mid!=0);width[good]=4*sd[good]/mid[good]
    out={k:np.zeros(n,dtype=float) for k in PINE_FEATURES}; out["pine_rsi12"][:]=rsi
    out["pine_rsi12_delta"][:]=np.r_[np.nan,np.diff(rsi)]
    out["pine_mid_slope_pct"][:]=np.where(np.isfinite(mid)&(mid!=0),slope/mid*100,np.nan)
    out["pine_width"][:]=width; out["pine_atr_pct"][:]=np.where(c>0,atr/c*100,np.nan)
    last_signal=0;extreme=0.;last_idx=0;wait=False
    for i in range(1,n):
        out["pine_last_signal_before"][i]=last_signal
        out["pine_bars_since_signal"][i]=i-last_idx
        out["pine_wait_pullback_before"][i]=int(wait)
        ri,rp=rsi[i],rsi[i-1];si,sp=slope[i],slope[i-1]
        cross_buy=bool(np.isfinite(ri) and np.isfinite(rp) and ri>35 and rp<=35)
        cross_sell=bool(np.isfinite(ri) and np.isfinite(rp) and ri<75 and rp>=75)
        flip_dn=bool(np.isfinite(si) and np.isfinite(sp) and si<0 and sp>=0 and np.isfinite(ri) and np.isfinite(rp) and ri<50 and rp>=50)
        flip_up=bool(np.isfinite(si) and np.isfinite(sp) and si>0 and sp<=0 and np.isfinite(ri) and np.isfinite(rp) and ri>50 and rp<=50)
        ai=atr[i];dist=ai*2.5 if np.isfinite(ai) else np.nan;cool=(i-last_idx)>5
        exit_long=bool(last_signal==1 and np.isfinite(dist) and c[i]<(extreme-dist))
        exit_short=bool(last_signal==-1 and np.isfinite(dist) and c[i]>(extreme+dist))
        frb=bool(last_signal==-1 and np.isfinite(dist) and c[i]>extreme+dist)
        frs=bool(last_signal==1 and np.isfinite(dist) and c[i]<extreme-dist)
        wp=wait
        if last_signal==-1 and np.isfinite(si) and si>0 and not frb:wp=True
        if last_signal==1 and np.isfinite(si) and si<0 and not frs:wp=True
        if flip_up or flip_dn:wp=False
        common=(not wp) and cool
        bottom=bool((common and (cross_buy or exit_short or flip_up) and last_signal!=1) or frb)
        top=bool((common and (cross_sell or exit_long or flip_dn) and last_signal!=-1) or frs)
        out["pine_bottom"][i]=int(bottom);out["pine_cross_buy"][i]=int(cross_buy);out["pine_exit_short"][i]=int(exit_short)
        out["pine_trend_flip_up"][i]=int(flip_up);out["pine_force_reverse_buy"][i]=int(frb)
        wait=wp
        if bottom:last_signal=1;last_idx=i;extreme=c[i]
        if top:last_signal=-1;last_idx=i;extreme=c[i]
    for k,v in out.items():s[k]=v
    return s[["date","session"]+PINE_FEATURES]


def fetch_v12(code,start,end):
    chart,err=base.fetch_chart(code)
    if err:return None,err
    hourly=base.parse_1h_chart(chart or {})
    if hourly is None:return None,"parse_failed"
    sessions=base.synthetic_sessions(hourly).reset_index(drop=True)
    state=pine_state_frame(sessions)
    cand=base.build_issue_candidates(code,chart or {},start,end)
    if cand is None:return None,"no_data"
    if cand.empty:return cand,None
    cand=cand.merge(state,on=["date","session"],how="left")
    return cand,None


def class_from_binary(df,col):
    y=df.label.to_numpy(int);p=df[col].fillna(0).to_numpy(int)>0;tn=int(np.sum((y==0)&~p));fp=int(np.sum((y==0)&p));fn=int(np.sum((y==1)&~p));tp=int(np.sum((y==1)&p));days=max(1,df.date.nunique())
    return {"n":len(y),"positive":int(y.sum()),"precision":float(tp/max(1,tp+fp)),"recall":float(tp/max(1,tp+fn)),"f1":float(2*tp/max(1,2*tp+fp+fn)),"tn":tn,"fp":fp,"fn":fn,"tp":tp,"predicted":int(p.sum()),"predicted_per_day":float(p.sum()/days),"fp_per_day":float(fp/days)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int);ap.add_argument("--max-workers",type=int,default=20);ap.add_argument("--output-dir",default="research_artifacts/v12_pine")
    a=ap.parse_args();teacher=base.load_teacher(a.teacher);wl,_,wl_stats=base.load_exact_watchlists(a.watchlist_repo,base.TRAIN_START,base.TEST_END)
    monitor_keys=set();union=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=base.TEST_END:
            union.update(syms);monitor_keys.update(f"{d}|{s}" for s in syms)
    teacher["monitor_key"]=teacher.signal_date+"|"+teacher.symbol_code;tm=teacher[teacher.monitor_key.isin(monitor_keys)&teacher.signal_date.between(base.TRAIN_START,base.TEST_END)].copy();pos=set(tm.key)
    if a.max_symbols:
        freq={s:0 for s in union}
        for syms in wl.values():
            for s in syms:
                if s in freq:freq[s]+=1
        must=set(tm.loc[tm.signal_date.between(base.TEST_START,base.TEST_END),"symbol_code"]);ordered=sorted(union,key=lambda s:(s not in must,-freq[s],s))[:a.max_symbols];union=set(ordered)
        monitor_keys={k for k in monitor_keys if k.split("|",1)[1] in union};pos={k for k in pos if k.split("|",1)[0] in union}
    frames=[];errors={};codes=sorted(union)
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(fetch_v12,c,base.TRAIN_START,base.FETCH_END):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try:fr,err=f.result()
            except Exception as e:fr,err=None,type(e).__name__
            if fr is not None and not fr.empty:frames.append(fr)
            elif err:errors[err]=errors.get(err,0)+1
            if i%100==0:print(f"progress {i}/{len(codes)} frames={len(frames)}",flush=True)
    if not frames:raise RuntimeError("no rows")
    data=pd.concat(frames,ignore_index=True);data["monitor_key"]=data.date.astype(str)+"|"+data.symbol.astype(str);data=data[data.monitor_key.isin(monitor_keys)&data.date.between(base.TRAIN_START,base.TEST_END)].copy()
    data["key"]=data.symbol.astype(str)+"|"+data.date.astype(str)+"|"+data.session.astype(int).astype(str);data["label"]=data.key.isin(pos).astype(int)
    train=data[data.date.between(base.TRAIN_START,base.TRAIN_END)].copy();valid=data[data.date.between(base.VALID_START,base.VALID_END)].copy();test=data[data.date.between(base.TEST_START,base.TEST_END)].copy()
    model=HistGradientBoostingClassifier(learning_rate=.04,max_iter=220,max_leaf_nodes=15,min_samples_leaf=35,l2_regularization=2.0,random_state=120)
    ytr=train.label.to_numpy(int);model.fit(train[HYBRID_FEATURES].astype(float),ytr,sample_weight=base.balanced_weights(ytr));pv=model.predict_proba(valid[HYBRID_FEATURES].astype(float))[:,1];th=base.choose_threshold(valid.label.to_numpy(int),pv);pt=model.predict_proba(test[HYBRID_FEATURES].astype(float))[:,1];test["hybrid_prob"]=pt
    exact=test[test.pine_bottom>0].copy();hybrid=test[test.hybrid_prob>=th["threshold"]].copy()
    # comparison subset: actual bottom on rows available from Yahoo/base filtering
    actual=test[test.label==1].copy()
    result={"scope":"Yahoo 730d exact Tenchi Pine state + hybrid distiller","watchlists":wl_stats,"yahoo":{"requested":len(codes),"errors":errors},"rows":len(data),"split":{"train":{"n":len(train),"pos":int(train.label.sum())},"valid":{"n":len(valid),"pos":int(valid.label.sum())},"test":{"n":len(test),"pos":int(test.label.sum())}},
      "exact_pine":{"validation":class_from_binary(valid,"pine_bottom"),"test":class_from_binary(test,"pine_bottom")},"hybrid":{"threshold":th,"validation":base.class_stats(valid,pv,th["threshold"]),"test":base.class_stats(test,pt,th["threshold"])},"current_champion":base.CHAMPION,
      "trading_test":{"actual_bottom":base.trade_stats(actual),"exact_pine":base.trade_stats(exact),"exact_pine_stable6":base.trade_stats(exact[exact.stable_score==6]),"hybrid":base.trade_stats(hybrid),"hybrid_stable6":base.trade_stats(hybrid[hybrid.stable_score==6])},
      "exact_reason_counts":exact[["pine_cross_buy","pine_exit_short","pine_trend_flip_up","pine_force_reverse_buy"]].sum().astype(int).to_dict()}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v12_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps(result,ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
