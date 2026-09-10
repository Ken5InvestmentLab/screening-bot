from __future__ import annotations

import argparse
import csv
import io
import json
import math
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

JST = ZoneInfo("Asia/Tokyo")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.T"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
WATCHLIST_CSV = "output/tradingview_tse_price_le_1000.csv"
TRAIN_START, TRAIN_END = "2026-03-05", "2026-06-30"
VALID_START, VALID_END = "2026-07-01", "2026-07-31"
TEST_START, TEST_END = "2026-08-01", "2026-08-31"
FETCH_END = "2026-09-10"
CHAMPION = {"name":"Production TradingView Stable★6","n":55,"avg":0.066,"wr":0.564,"hits":10,"target_rate":10/55}

FEATURES = [
    "session13", "log_price", "session_ret", "session_range_pct", "session_body_pct",
    "session_close_loc", "session_vol_ratio20", "ret_1d", "ret_2d", "ret_3d", "ret_5d",
    "ret_10d", "ret_20d", "gap_pct", "day_range_pct", "day_body_pct", "day_close_loc",
    "drawdown_high20", "recovery_low20", "rsi14", "atr14_pct", "bb_pct", "bb_width_pct",
    "ema25_gap_pct", "ema75_gap_pct", "macd_hist_pct", "stoch14", "day_vol_ratio5",
    "day_vol_ratio20", "pre_down3", "gap_up",
]


def now_jst():
    return datetime.now(JST)


def run_git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr[-1200:]}")
    return p.stdout


def parse_watchlist_csv(text):
    out = set()
    for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        tv = str(row.get("tv_symbol") or "").strip()
        if tv:
            out.add(tv.split(":", 1)[-1].strip())
    return {x for x in out if x}


def load_exact_watchlists(repo, start_date, end_date):
    log = run_git(repo, "log", "--format=%H\t%cI", "--", WATCHLIST_CSV)
    commits = []
    for line in log.splitlines():
        if not line.strip():
            continue
        sha, ts = line.split("\t", 1)
        local = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)
        effective = local.date() if local.hour < 12 else local.date() + timedelta(days=1)
        commits.append((effective, local, sha))
    commits.sort(key=lambda x: x[1])
    if not commits:
        raise RuntimeError("no historical watchlist commits")

    start = date.fromisoformat(start_date); end = date.fromisoformat(end_date)
    by_effective = {}
    hours = []
    for effective, local, sha in commits:
        if effective > end or effective < start - timedelta(days=14):
            continue
        try:
            symbols = parse_watchlist_csv(run_git(repo, "show", f"{sha}:{WATCHLIST_CSV}"))
        except Exception:
            continue
        if symbols:
            by_effective[effective] = (local, sha, symbols)
            hours.append(local.hour + local.minute / 60.0)
    if not by_effective:
        raise RuntimeError("no usable historical watchlist snapshots")

    edates = sorted(by_effective); mapping = {}; meta = {}; latest = None; ei = 0; cur = start
    while cur <= end:
        while ei < len(edates) and edates[ei] <= cur:
            latest = edates[ei]; ei += 1
        if latest is not None:
            local, sha, symbols = by_effective[latest]
            mapping[cur.isoformat()] = symbols
            meta[cur.isoformat()] = {"snapshot_effective": latest.isoformat(), "commit": sha, "commit_jst": local.isoformat(), "symbols": len(symbols)}
        cur += timedelta(days=1)
    return mapping, meta, {
        "snapshot_commits": len(by_effective), "earliest_effective": min(edates).isoformat(),
        "latest_effective": max(edates).isoformat(), "commit_hour_min": float(min(hours)),
        "commit_hour_max": float(max(hours)),
    }


def fetch_chart(code):
    last = None
    for attempt in range(4):
        try:
            r = requests.get(YAHOO.format(symbol=code), params={"range":"730d", "interval":"1h"},
                             headers={"User-Agent":UA, "Accept":"application/json,text/plain,*/*"}, timeout=30)
            if r.status_code in {429, 502, 503, 504}:
                last = f"http_{r.status_code}"; time.sleep(0.8 * (attempt + 1)); continue
            r.raise_for_status(); payload = r.json(); err = payload.get("chart", {}).get("error")
            if err:
                return None, err.get("description") or "chart_error"
            result = payload["chart"]["result"][0]; q = result.get("indicators", {}).get("quote", [{}])[0]
            ts = result.get("timestamp") or []
            if not ts or not q:
                return None, "empty_chart"
            return {"timestamp":ts, "open":q.get("open") or [], "high":q.get("high") or [],
                    "low":q.get("low") or [], "close":q.get("close") or [], "volume":q.get("volume") or []}, None
        except Exception as exc:
            last = type(exc).__name__; time.sleep(0.5 * (attempt + 1))
    return None, last or "fetch_failed"


def parse_1h_chart(chart):
    try:
        n = min(len(chart.get(k, [])) for k in ("timestamp", "open", "high", "low", "close", "volume"))
    except Exception:
        return None
    rows = []
    for i in range(n):
        vals = [chart["open"][i], chart["high"][i], chart["low"][i], chart["close"][i], chart["volume"][i]]
        if any(x is None for x in vals):
            continue
        o, h, l, c, v = map(float, vals)
        if c <= 0 or h <= 0 or l <= 0 or h < l or v < 0:
            continue
        ts = pd.to_datetime(int(chart["timestamp"][i]), unit="s", utc=True).tz_convert("Asia/Tokyo")
        rows.append((ts, o, h, l, c, v))
    if len(rows) < 200:
        return None
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["date"] = df.ts.dt.date.astype(str)
    return df


def synthetic_sessions(hourly):
    x = hourly.copy(); mins = x.ts.dt.hour * 60 + x.ts.dt.minute
    x["session"] = np.where(mins < 13 * 60, 9, 13)
    return x.groupby(["date", "session"], sort=True).agg(ts=("ts","last"), open=("open","first"),
        high=("high","max"), low=("low","min"), close=("close","last"), volume=("volume","sum")).reset_index()


def daily_completed(hourly):
    return hourly.groupby("date", sort=True).agg(open=("open","first"), high=("high","max"), low=("low","min"), close=("close","last"), volume=("volume","sum")).reset_index()


def ema_seed(values, period):
    values = np.asarray(values, dtype=float); out = np.full(len(values), np.nan)
    if len(values) < period: return out
    e = float(np.mean(values[:period])); out[period - 1] = e; k = 2.0 / (period + 1.0)
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k); out[i] = e
    return out


def wilder_rsi(values, period=14):
    values = np.asarray(values, dtype=float)
    if len(values) <= period: return np.nan
    d = np.diff(values); gains = np.maximum(d, 0.0); losses = np.maximum(-d, 0.0)
    ag = float(np.mean(gains[:period])); al = float(np.mean(losses[:period]))
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period; al = (al * (period - 1) + losses[i]) / period
    if al == 0: return 100.0 if ag > 0 else 50.0
    rs = ag / al; return 100.0 - 100.0 / (1.0 + rs)


def build_asof_daily(completed, sessions, upto_idx):
    cur = sessions.iloc[upto_idx]
    past = completed[completed.date < cur.date][["date","open","high","low","close","volume"]].copy()
    today = sessions.iloc[:upto_idx + 1]; today = today[today.date == cur.date]
    current = pd.DataFrame([{"date":cur.date, "open":float(today.iloc[0].open), "high":float(today.high.max()),
        "low":float(today.low.min()), "close":float(today.iloc[-1].close), "volume":float(today.volume.sum())}])
    return pd.concat([past, current], ignore_index=True)


def technical_features(asof):
    if len(asof) < 80: return None
    o=asof.open.to_numpy(float); h=asof.high.to_numpy(float); l=asof.low.to_numpy(float); c=asof.close.to_numpy(float); v=asof.volume.to_numpy(float)
    last=len(c)-1; close=c[-1]
    if not np.isfinite(close) or close <= 0: return None
    e12=ema_seed(c,12); e25=ema_seed(c,25); e26=ema_seed(c,26); e75=ema_seed(c,75)
    valid=np.where(np.isfinite(e12)&np.isfinite(e26))[0]; macd_hist=np.nan; macd_pos=False
    if len(valid)>=9:
        ml=(e12[valid]-e26[valid]).astype(float); sig=ema_seed(ml,9)
        if np.isfinite(sig[-1]): macd_hist=float(ml[-1]-sig[-1]); macd_pos=macd_hist>0
    tr=[]
    for i in range(max(1,last-13),last+1): tr.append(max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])))
    atr14_pct=float(np.mean(tr))/close*100 if tr else np.nan
    bb=c[max(0,last-19):last+1]; basis=float(np.mean(bb)); dev=float(np.std(bb,ddof=0))
    if dev>0:
        bb_pct=float(np.clip((close-(basis-2*dev))/(4*dev),0,1)); bb_width_pct=float(4*dev/basis*100) if basis else np.nan
    else: bb_pct,bb_width_pct=.5,0.
    lo14=float(np.min(l[max(0,last-13):last+1])); hi14=float(np.max(h[max(0,last-13):last+1])); stoch14=(close-lo14)/(hi14-lo14)*100 if hi14>lo14 else 50.
    prev_close=c[-2]; gap_pct=(o[-1]/prev_close-1)*100 if prev_close else np.nan; day_range_pct=(h[-1]-l[-1])/prev_close*100 if prev_close else np.nan
    day_body_pct=(c[-1]-o[-1])/o[-1]*100 if o[-1] else np.nan; day_close_loc=(c[-1]-l[-1])/(h[-1]-l[-1]) if h[-1]>l[-1] else .5
    def ret(n): return float(c[-1]/c[-1-n]-1) if len(c)>n and c[-1-n] else np.nan
    hi20=float(np.max(h[max(0,last-20):last])); lo20=float(np.min(l[max(0,last-20):last])); prior_v=v[:-1]
    vr5=v[-1]/float(np.mean(prior_v[-5:])) if len(prior_v)>=5 and np.mean(prior_v[-5:])>0 else np.nan
    vr20=v[-1]/float(np.mean(prior_v[-20:])) if len(prior_v)>=20 and np.mean(prior_v[-20:])>0 else np.nan
    pre_down3=bool(last>=3 and c[last-1]<c[last-2] and c[last-2]<c[last-3]); gap_up=bool(last>0 and o[-1]>c[-2])
    bits={"ema25":bool(np.isfinite(e25[-1]) and close>e25[-1]), "macdpos":macd_pos, "stoch75":bool(stoch14>=75),
          "bb80":bool(bb_pct>=.80), "pre_down3":pre_down3, "gap_up":gap_up}
    return {"ret_1d":ret(1),"ret_2d":ret(2),"ret_3d":ret(3),"ret_5d":ret(5),"ret_10d":ret(10),"ret_20d":ret(20),
        "gap_pct":gap_pct,"day_range_pct":day_range_pct,"day_body_pct":day_body_pct,"day_close_loc":day_close_loc,
        "drawdown_high20":close/hi20-1 if hi20 else np.nan,"recovery_low20":close/lo20-1 if lo20 else np.nan,"rsi14":wilder_rsi(c,14),
        "atr14_pct":atr14_pct,"bb_pct":bb_pct,"bb_width_pct":bb_width_pct,"ema25_gap_pct":(close/e25[-1]-1)*100 if np.isfinite(e25[-1]) else np.nan,
        "ema75_gap_pct":(close/e75[-1]-1)*100 if np.isfinite(e75[-1]) else np.nan,"macd_hist_pct":macd_hist/close*100 if np.isfinite(macd_hist) else np.nan,
        "stoch14":stoch14,"day_vol_ratio5":vr5,"day_vol_ratio20":vr20,"pre_down3":int(pre_down3),"gap_up":int(gap_up),
        "stable_score":sum(int(x) for x in bits.values()), **{f"stable_{k}":int(val) for k,val in bits.items()}}


def build_issue_candidates(code, chart, start_date, end_date):
    hourly=parse_1h_chart(chart)
    if hourly is None or hourly.empty: return None
    sessions=synthetic_sessions(hourly).reset_index(drop=True); completed=daily_completed(hourly)
    if len(completed)<90 or len(sessions)<120: return None
    d=completed.copy(); d["day_index"]=np.arange(len(d)); d["future_close_5"]=d.close.shift(-5); d["exit_date_5bd"]=d.date.shift(-5); daymap=d.set_index("date")
    svolume=sessions.volume.to_numpy(float); rows=[]
    for i,row in sessions.iterrows():
        dt=str(row.date)
        if dt<start_date or dt>end_date or row.date not in daymap.index: continue
        di=int(daymap.loc[row.date,"day_index"])
        if di<1: continue
        prev=d.iloc[di-1]
        if not (float(prev.close)<=1000 and float(prev.volume)>=10000 and float(row.volume)>=5000): continue
        tf=technical_features(build_asof_daily(completed,sessions,i))
        if tf is None: continue
        prev20=svolume[max(0,i-20):i]; svr=float(row.volume/np.mean(prev20)) if len(prev20)>=5 and np.mean(prev20)>0 else np.nan; rng=float(row.high-row.low)
        rec={"date":dt,"session":int(row.session),"symbol":str(code),"entry":float(row.close),"session_volume":float(row.volume),
             "session13":int(row.session==13),"log_price":math.log(max(float(row.close),1e-9)),"session_ret":float(row.close/row.open-1) if row.open else np.nan,
             "session_range_pct":float(rng/row.open) if row.open else np.nan,"session_body_pct":float((row.close-row.open)/row.open) if row.open else np.nan,
             "session_close_loc":float((row.close-row.low)/rng) if rng>0 else .5,"session_vol_ratio20":svr,**tf}
        fc=daymap.loc[row.date,"future_close_5"]; ex=daymap.loc[row.date,"exit_date_5bd"]
        rec["perf_5bd"]=float(fc/row.close-1) if pd.notna(fc) and row.close else np.nan; rec["exit_date_5bd"]=str(ex) if pd.notna(ex) else ""; rows.append(rec)
    return pd.DataFrame(rows)


def fetch_one(code,start_date,end_date):
    chart,err=fetch_chart(code)
    if err:return None,err
    fr=build_issue_candidates(code,chart or {},start_date,end_date)
    return fr,None if fr is not None else "no_data"


def load_teacher(path):
    t=pd.read_csv(path,dtype={"symbol_code":str}); t["signal_date"]=pd.to_datetime(t.signal_date).dt.strftime("%Y-%m-%d")
    t["symbol_code"]=t.symbol_code.astype(str).str.replace(r"\.0$","",regex=True).str.strip(); t["session"]=pd.to_numeric(t.session,errors="coerce").astype("Int64")
    t=t[t.session.isin([9,13])].copy(); t["key"]=t.symbol_code+"|"+t.signal_date+"|"+t.session.astype(str)
    return t.drop_duplicates("key",keep="last")


def balanced_weights(y):
    y=np.asarray(y,dtype=int); n=len(y); pos=max(1,int(y.sum())); neg=max(1,n-pos); return np.where(y==1,n/(2*pos),n/(2*neg))


def choose_threshold(y,p):
    y=np.asarray(y,dtype=int); p=np.asarray(p,float); best=None; cand=set(np.linspace(.001,.999,250).tolist())
    if len(p): cand.update(np.quantile(p,np.linspace(.40,.999,180)).tolist())
    for th in sorted(cand):
        pred=(p>=th).astype(int); n=int(pred.sum())
        if n<5: continue
        pr=float(precision_score(y,pred,zero_division=0)); rc=float(recall_score(y,pred,zero_division=0)); f=float(f1_score(y,pred,zero_division=0)); rank=f+.02*pr
        if best is None or rank>best["rank"]: best={"threshold":float(th),"precision":pr,"recall":rc,"f1":f,"predicted":n,"rank":rank}
    return best or {"threshold":.5,"precision":0.,"recall":0.,"f1":0.,"predicted":0,"rank":0.}


def class_stats(df,probs,th):
    y=df.label.to_numpy(int); p=np.asarray(probs,float); pred=(p>=th).astype(int); tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel(); days=max(1,df.date.nunique())
    auc=roc_auc_score(y,p) if len(np.unique(y))==2 else np.nan; ap=average_precision_score(y,p) if y.sum()>0 else np.nan
    return {"n":int(len(y)),"positive":int(y.sum()),"positive_rate":float(y.mean()),"roc_auc":float(auc) if np.isfinite(auc) else None,"pr_auc":float(ap) if np.isfinite(ap) else None,
            "precision":float(precision_score(y,pred,zero_division=0)),"recall":float(recall_score(y,pred,zero_division=0)),"f1":float(f1_score(y,pred,zero_division=0)),
            "tn":int(tn),"fp":int(fp),"fn":int(fn),"tp":int(tp),"predicted":int(pred.sum()),"predicted_per_day":float(pred.sum()/days),"false_positives_per_day":float(fp/days)}


def trade_stats(df):
    x=pd.to_numeric(df.perf_5bd,errors="coerce").dropna().to_numpy(float) if not df.empty else np.array([])
    if not len(x): return {"n":0,"avg":0.,"median":0.,"robust_avg":0.,"wr":0.,"hits":0,"target_rate":0.}
    dec=x[x!=0]; wr=float(np.mean(dec>0)) if len(dec) else 0.; robust=float(np.mean(x))
    if len(x)>=10:
        lo,hi=np.quantile(x,[.05,.95]); robust=float(np.mean(np.clip(x,lo,hi)))
    hits=int(np.sum(x>=.10)); return {"n":int(len(x)),"avg":float(np.mean(x)),"median":float(np.median(x)),"robust_avg":robust,"wr":wr,"hits":hits,"target_rate":float(hits/len(x))}


def top_per_day(df,n):
    if df.empty:return df
    return df.sort_values(["date","prob"],ascending=[True,False]).groupby("date",sort=False).head(n)


def pct(x): return f"{x*100:.1f}%"


def make_report(r):
    c=r["classification"]["test"]; t=r["trading_test"]; ch=r["current_champion"]
    lines=["# No-TV V10 Standalone — Full BOTTOM + Exact Historical Watchlists","",f"- Teacher: {r['teacher']['rows']} BOTTOM / {r['teacher']['symbols']} symbols",
      f"- Exact watchlist commits: {r['watchlists']['snapshot_commits']}",f"- Candidate rows: {r['candidate_rows']}",f"- Train: {TRAIN_START}..{TRAIN_END}",f"- Validation: {VALID_START}..{VALID_END}",f"- Untouched test: {TEST_START}..{TEST_END}",
      f"- threshold: {r['threshold']['threshold']:.5f}","","## August untouched classification","","|Metric|Result|","|---|---:|",f"|Positive rate|{pct(c['positive_rate'])}|",
      f"|ROC-AUC|{c['roc_auc']:.3f}|" if c['roc_auc'] is not None else "|ROC-AUC|-|",f"|PR-AUC|{c['pr_auc']:.3f}|" if c['pr_auc'] is not None else "|PR-AUC|-|",
      f"|Precision|{pct(c['precision'])}|",f"|Recall|{pct(c['recall'])}|",f"|F1|{pct(c['f1'])}|",f"|Predicted/day|{c['predicted_per_day']:.2f}|",f"|FP/day|{c['false_positives_per_day']:.2f}|","",
      "## August 5BD","","|Variant|n|Avg|Median|Robust|Win|+10% hit|","|---|---:|---:|---:|---:|---:|---:|",f"|Production Stable★6 reference (1y)|{ch['n']}|{pct(ch['avg'])}|-|-|{pct(ch['wr'])}|{ch['hits']} ({pct(ch['target_rate'])})|"]
    for k,label in [("teacher_all","Actual TV BOTTOM"),("model_all","V10 threshold"),("model_top30","V10 top30/day"),("model_stable6","V10 ∩ reconstructed Stable★6"),("monitored_stable6","All monitored ∩ reconstructed Stable★6")]:
        s=t[k]; lines.append(f"|{label}|{s['n']}|{pct(s['avg'])}|{pct(s['median'])}|{pct(s['robust_avg'])}|{pct(s['wr'])}|{s['hits']} ({pct(s['target_rate'])})|")
    lines += ["","- Positive = actual BOTTOM from weekly-report alerts_raw + signals_archive.","- Negative = actually monitored watchlist session with no saved BOTTOM.","- July selects threshold; August is untouched.","- No production writes; historical TV is teacher only; generation is Yahoo-only."]
    return "\n".join(lines)


def run(args):
    teacher=load_teacher(args.teacher); wl,_,wl_stats=load_exact_watchlists(args.watchlist_repo,TRAIN_START,TEST_END)
    monitor_keys=set(); union=set()
    for d,symbols in wl.items():
        if TRAIN_START<=d<=TEST_END:
            union.update(symbols); monitor_keys.update(f"{d}|{s}" for s in symbols)
    teacher["monitor_key"]=teacher.signal_date+"|"+teacher.symbol_code
    teacher_mon=teacher[teacher.monitor_key.isin(monitor_keys)&(teacher.signal_date>=TRAIN_START)&(teacher.signal_date<=TEST_END)].copy(); positive_keys=set(teacher_mon.key)
    if args.max_symbols:
        freq={s:0 for s in union}
        for symbols in wl.values():
            for s in symbols:
                if s in freq: freq[s]+=1
        must=set(teacher_mon.loc[(teacher_mon.signal_date>=TEST_START)&(teacher_mon.signal_date<=TEST_END),"symbol_code"])
        ordered=sorted(union,key=lambda s:(s not in must,-freq[s],s))[:args.max_symbols]; union=set(ordered)
        monitor_keys={k for k in monitor_keys if k.split("|",1)[1] in union}; positive_keys={k for k in positive_keys if k.split("|",1)[0] in union}
    frames=[]; errors={}; ok=0; codes=sorted(union)
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        fut={ex.submit(fetch_one,c,TRAIN_START,FETCH_END):c for c in codes}
        for n,f in enumerate(as_completed(fut),1):
            try: fr,err=f.result()
            except Exception as exc: fr,err=None,type(exc).__name__
            if fr is not None:
                ok+=1
                if not fr.empty: frames.append(fr)
            elif err: errors[err]=errors.get(err,0)+1
            if n%100==0: print(f"progress {n}/{len(codes)} frames={len(frames)}",flush=True)
    if not frames: raise RuntimeError("no candidate rows")
    data=pd.concat(frames,ignore_index=True); data["monitor_key"]=data.date.astype(str)+"|"+data.symbol.astype(str); data=data[data.monitor_key.isin(monitor_keys)&(data.date>=TRAIN_START)&(data.date<=TEST_END)].copy()
    data["key"]=data.symbol.astype(str)+"|"+data.date.astype(str)+"|"+data.session.astype(int).astype(str); data["label"]=data.key.isin(positive_keys).astype(int)
    train=data[(data.date>=TRAIN_START)&(data.date<=TRAIN_END)].copy(); valid=data[(data.date>=VALID_START)&(data.date<=VALID_END)].copy(); test=data[(data.date>=TEST_START)&(data.date<=TEST_END)].copy()
    print(f"split train={len(train)}/{train.label.sum()} valid={len(valid)}/{valid.label.sum()} test={len(test)}/{test.label.sum()}",flush=True)
    if min(train.label.sum(),valid.label.sum(),test.label.sum())<10: raise RuntimeError("too few positives in one split")
    model=HistGradientBoostingClassifier(learning_rate=.05,max_iter=260,max_leaf_nodes=31,min_samples_leaf=35,l2_regularization=1.5,random_state=42)
    ytr=train.label.to_numpy(int); model.fit(train[FEATURES].astype(float),ytr,sample_weight=balanced_weights(ytr)); pv=model.predict_proba(valid[FEATURES].astype(float))[:,1]; th=choose_threshold(valid.label.to_numpy(int),pv)
    pt=model.predict_proba(test[FEATURES].astype(float))[:,1]; test["prob"]=pt; pred=test[test.prob>=th["threshold"]].copy(); matched=set(data.loc[data.label==1,"key"])
    return {"generated_at_jst":now_jst().isoformat(timespec="seconds"),"teacher":{"rows":int(len(teacher)),"symbols":int(teacher.symbol_code.nunique()),"date_min":teacher.signal_date.min(),"date_max":teacher.signal_date.max(),"monitored_keys":len(positive_keys),"matched_candidate_keys":len(matched),"unmatched_monitored_keys":len(positive_keys-matched)},
      "watchlists":{**wl_stats,"union_symbols":len(union)},"yahoo":{"requested":len(codes),"ok":ok,"errors":errors},"candidate_rows":int(len(data)),
      "split":{"train":{"n":len(train),"pos":int(train.label.sum())},"valid":{"n":len(valid),"pos":int(valid.label.sum())},"test":{"n":len(test),"pos":int(test.label.sum())}},"features":FEATURES,"threshold":th,
      "classification":{"validation":class_stats(valid,pv,th["threshold"]),"test":class_stats(test,pt,th["threshold"])},"current_champion":CHAMPION,
      "trading_test":{"teacher_all":trade_stats(test[test.label==1]),"model_all":trade_stats(pred),"model_top30":trade_stats(top_per_day(test,30)),"model_stable6":trade_stats(pred[pred.stable_score==6]),"monitored_stable6":trade_stats(test[test.stable_score==6])},
      "top_predictions":test.sort_values("prob",ascending=False)[["date","session","symbol","prob","label","stable_score","perf_5bd"]].head(200).to_dict("records")}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--teacher",required=True); ap.add_argument("--watchlist-repo",required=True); ap.add_argument("--max-symbols",type=int); ap.add_argument("--max-workers",type=int,default=20); ap.add_argument("--output-dir",default="research_artifacts/v10_standalone")
    a=ap.parse_args(); r=run(a); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True); (out/"comparison_v10.json").write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str),encoding="utf-8"); (out/"comparison_v10.md").write_text(make_report(r),encoding="utf-8"); print(json.dumps({"teacher":r["teacher"],"watchlists":r["watchlists"],"split":r["split"],"threshold":r["threshold"],"classification":r["classification"],"trading_test":r["trading_test"]},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
