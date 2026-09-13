from __future__ import annotations

import argparse, csv, glob, hashlib, json, math, os
from array import array
from collections import Counter, defaultdict, deque
from datetime import date, datetime
from pathlib import Path

CHANGE_DATE = date(2024, 11, 5)

def valid_bar(row):
    try: o,h,l,c,v = map(float, [row['open'],row['high'],row['low'],row['close'],row['volume']])
    except Exception: return False
    return o>0 and h>=max(o,c) and l<=min(o,c) and h>=l and v>=0 and all(math.isfinite(x) for x in (o,h,l,c,v))

def required(day, bin_name):
    if bin_name=='AM_09_13': return (9,10,11,12)
    return (13,14) if day<CHANGE_DATE else (13,14,15)

def regime(day, bin_name):
    if bin_name=='AM_09_13': return 'AM_STABLE'
    return 'PM_PRE_20241105' if day<CHANGE_DATE else 'PM_POST_20241105'

def quant(values, p):
    if not values: return None
    xs=sorted(values); pos=(len(xs)-1)*p; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    return xs[lo] if lo==hi else xs[lo]+(xs[hi]-xs[lo])*(pos-lo)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--raw-dir',required=True); ap.add_argument('--output',required=True); args=ap.parse_args()
    counts=Counter(); vals=array('d'); logs=array('d'); monthly=defaultdict(lambda:array('d')); by_regime=defaultdict(lambda:array('d')); shas={}
    def process_symbol(rows):
        history=defaultdict(lambda:deque(maxlen=20)); current=None; day_rows=[]
        def flush(day, drs):
            if day is None: return
            byh=defaultdict(list)
            for r in drs:
                dt=r['_dt']
                if dt.minute==0 and dt.second==0: byh[dt.hour].append(r)
            for bn in ('AM_09_13','PM_13_CLOSE'):
                selected=[]
                for hour in required(day,bn):
                    candidates=byh.get(hour,[])
                    if len(candidates)!=1 or not valid_bar(candidates[0]): selected=[]; break
                    selected.append(candidates[0])
                if not selected: continue
                volume=sum(float(x['volume']) for x in selected); counts['complete_bins']+=1
                key=(bn,regime(day,bn)); q=history[key]
                if len(q)==20:
                    counts['history20_bins']+=1; s=sorted(q); med=(s[9]+s[10])/2
                    if med>0:
                        ratio=volume/med
                        if math.isfinite(ratio):
                            logv=math.log1p(ratio); vals.append(ratio); logs.append(logv); monthly[day.strftime('%Y-%m')].append(logv); by_regime[key[1]].append(logv); counts['feature_bins']+=1
                q.append(volume)
        for r in rows:
            day=r['_dt'].date()
            if current is None: current=day
            if day!=current: flush(current,day_rows); day_rows=[]; current=day
            day_rows.append(r)
        flush(current,day_rows)
    for fp in sorted(glob.glob(str(Path(args.raw_dir)/'ohlcv_1h_shard_*.csv'))):
        h=hashlib.sha256(Path(fp).read_bytes()).hexdigest(); shas[os.path.basename(fp)]=h
        cur=None; rows=[]
        with open(fp,encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                counts['raw_rows']+=1
                try: row['_dt']=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
                except Exception: continue
                sym=row['symbol']
                if cur is None: cur=sym
                if sym!=cur: process_symbol(rows); rows=[]; cur=sym
                rows.append(row)
        if rows: process_symbol(rows)
    out={
      'audit_id':'CAUSAL-INTRADAY-RELATIVE-VOLUME-QUALITY-20260913-01',
      'strategy_outcomes_opened':False,
      'counts':dict(counts),
      'coverage_of_complete':counts['feature_bins']/counts['complete_bins'],
      'ratio':{k:quant(vals,p) for k,p in [('p01',.01),('p50',.5),('p95',.95),('p99',.99),('p999',.999)]},
      'log1p_ratio':{k:quant(logs,p) for k,p in [('p01',.01),('p50',.5),('p95',.95),('p99',.99),('p999',.999)]},
      'regime_medians':{k:quant(v,.5) for k,v in by_regime.items()},
      'monthly_medians':{k:quant(v,.5) for k,v in sorted(monthly.items())}
    }
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')

if __name__=='__main__': main()
