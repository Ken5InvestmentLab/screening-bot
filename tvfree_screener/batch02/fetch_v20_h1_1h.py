#!/usr/bin/env python3
"""Fetch Yahoo 1H for the frozen V20 H1 universe. Research-only."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

JST=ZoneInfo("Asia/Tokyo")
BASE="https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
UA="Mozilla/5.0 TenteiV20Research/1.0"

def epoch_jst(d,end=False):
    t=dt.time(23,59,59) if end else dt.time(0,0,0)
    return int(dt.datetime.combine(d,t,tzinfo=JST).timestamp())

def load_symbols(path,shard_index,shard_count):
    items=[x.strip().upper() for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    items=sorted(dict.fromkeys(items))
    if shard_count<1 or not (0<=shard_index<shard_count):
        raise ValueError("invalid shard")
    return [s for i,s in enumerate(items) if i%shard_count==shard_index]

def chunks(start,end,days):
    cur=start
    while cur<=end:
        ce=min(end,cur+dt.timedelta(days=days-1))
        yield cur,ce
        cur=ce+dt.timedelta(days=1)

def request_json(code,start,end,retries=6):
    symbol=urllib.parse.quote(code if code.endswith(".T") else f"{code}.T")
    params=urllib.parse.urlencode({
        "period1":epoch_jst(start),
        "period2":epoch_jst(end+dt.timedelta(days=1)),
        "interval":"1h",
        "includePrePost":"false",
        "events":"div,splits",
    })
    url=BASE.format(symbol=symbol)+"?"+params
    last=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}"
            if e.code not in (429,500,502,503,504):
                break
        except Exception as e:
            last=repr(e)
        time.sleep(min(45.0,(2**attempt)+random.random()))
    raise RuntimeError(last or "request failed")

def extract_rows(code,payload,start,end):
    chart=payload.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(str(chart["error"]))
    result=(chart.get("result") or [None])[0]
    if not result:
        return []
    ts=result.get("timestamp") or []
    quote=(((result.get("indicators") or {}).get("quote") or [{}])[0])
    cols=[quote.get(k) or [] for k in ("open","high","low","close","volume")]
    rows=[]
    for i,t in enumerate(ts):
        stamp=dt.datetime.fromtimestamp(int(t),tz=dt.timezone.utc).astimezone(JST)
        if stamp.date()<start or stamp.date()>end or stamp.hour<9 or stamp.hour>16:
            continue
        vals=[a[i] if i<len(a) else None for a in cols]
        o,h,l,c,v=vals
        if None in (o,h,l,c):
            continue
        rows.append((stamp.strftime("%Y-%m-%d %H:%M:%S%z"),code,float(o),float(h),float(l),float(c),0.0 if v is None else float(v)))
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",required=True)
    ap.add_argument("--start",required=True)
    ap.add_argument("--end",required=True)
    ap.add_argument("--shard-index",type=int,required=True)
    ap.add_argument("--shard-count",type=int,required=True)
    ap.add_argument("--chunk-days",type=int,default=110)
    ap.add_argument("--output",required=True)
    ap.add_argument("--failures",required=True)
    a=ap.parse_args()
    start=dt.date.fromisoformat(a.start); end=dt.date.fromisoformat(a.end)
    syms=load_symbols(a.symbols,a.shard_index,a.shard_count)
    rows_by_key={}; failures=[]
    for pos,code in enumerate(syms,1):
        n=0
        for cs,ce in chunks(start,end,a.chunk_days):
            try:
                rows=extract_rows(code,request_json(code,cs,ce),cs,ce)
                for row in rows:
                    rows_by_key[(row[1],row[0])]=row
                n+=len(rows)
            except Exception as e:
                failures.append({"symbol":code,"start":str(cs),"end":str(ce),"error":str(e)})
        if pos%20==0 or pos==len(syms):
            print(f"{pos}/{len(syms)} {code}: rows={n} failures={len(failures)}",flush=True)
        time.sleep(0.10+random.random()*0.10)
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["timestamp","symbol","open","high","low","close","volume"])
        for key in sorted(rows_by_key,key=lambda k:(k[0],k[1])):
            w.writerow(rows_by_key[key])
    Path(a.failures).write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"wrote {len(rows_by_key)} rows; failures={len(failures)}",flush=True)

if __name__=="__main__":
    main()
