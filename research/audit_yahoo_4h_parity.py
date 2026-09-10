from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base

RULES = {
    "clock_lt_13": lambda x: np.where((x.ts.dt.hour * 60 + x.ts.dt.minute) < 13 * 60, 9, 13),
    "clock_lt_1230": lambda x: np.where((x.ts.dt.hour * 60 + x.ts.dt.minute) < 12 * 60 + 30, 9, 13),
    "clock_lt_12": lambda x: np.where((x.ts.dt.hour * 60 + x.ts.dt.minute) < 12 * 60, 9, 13),
}


def aggregate_rule(hourly, rule):
    x = hourly.copy()
    if rule.startswith("first_"):
        n = int(rule.split("_")[1])
        x["slot"] = x.groupby("date").cumcount()
        x["session"] = np.where(x.slot < n, 9, 13)
    else:
        x["session"] = RULES[rule](x)
    return x.groupby(["date", "session"], sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), bars=("close", "size")
    ).reset_index()


def clean_prod(path, start, end):
    p = pd.read_csv(path, dtype={"symbol": str})
    p["symbol"] = p.symbol.astype(str).str.replace(r"\.0$", "", regex=True)
    ts = pd.to_datetime(p.timestamp, errors="coerce")
    p["date"] = ts.dt.strftime("%Y-%m-%d")
    p["session"] = ts.dt.hour
    for c in ["open", "high", "low", "close", "volume"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p[p.session.isin([9, 13]) & p.date.between(start, end)].dropna(subset=["open","high","low","close","volume"])
    p = p.sort_values(["date", "session", "symbol"]).drop_duplicates(["date", "session", "symbol"], keep="last")
    return p


def metrics(merged):
    if merged.empty:
        return {"n": 0}
    out = {"n": int(len(merged)), "symbols": int(merged.symbol.nunique()), "dates": int(merged.date.nunique())}
    for c in ["open", "high", "low", "close"]:
        a = merged[f"{c}_prod"].to_numpy(float)
        b = merged[f"{c}_yahoo"].to_numpy(float)
        den = np.maximum(np.abs(a), 1e-9)
        ape = np.abs(b-a)/den
        out[f"{c}_mape"] = float(np.mean(ape))
        out[f"{c}_median_ape"] = float(np.median(ape))
        out[f"{c}_exact_1bp"] = float(np.mean(ape <= 0.0001))
    av = merged.volume_prod.to_numpy(float); bv = merged.volume_yahoo.to_numpy(float)
    vden = np.maximum(np.abs(av), 1.0); vape = np.abs(bv-av)/vden
    out["volume_mape"] = float(np.mean(vape)); out["volume_median_ape"] = float(np.median(vape))
    out["ohlc_mean_mape"] = float(np.mean([out[f"{c}_mape"] for c in ["open","high","low","close"]]))
    out["close_corr"] = float(np.corrcoef(merged.close_prod, merged.close_yahoo)[0,1]) if len(merged)>2 else None
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--production-4h", required=True); ap.add_argument("--start", default="2026-03-05"); ap.add_argument("--end", default="2026-08-31")
    ap.add_argument("--max-symbols", type=int, default=100); ap.add_argument("--max-workers", type=int, default=16); ap.add_argument("--output-dir", default="research_artifacts/4h_parity")
    a=ap.parse_args(); prod=clean_prod(a.production_4h,a.start,a.end)
    freq=prod.groupby("symbol").size().sort_values(ascending=False); codes=freq.head(a.max_symbols).index.astype(str).tolist()
    prod=prod[prod.symbol.isin(codes)].copy(); rules=list(RULES)+["first_3","first_4"]
    frames={r:[] for r in rules}; errors={}
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(base.fetch_chart,c):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            code=fut[f]
            try: chart,err=f.result()
            except Exception as e: chart,err=None,type(e).__name__
            if chart is None:
                errors[err or "fetch_failed"]=errors.get(err or "fetch_failed",0)+1; continue
            h=base.parse_1h_chart(chart)
            if h is None or h.empty: errors["parse_failed"]=errors.get("parse_failed",0)+1; continue
            h=h[h.date.between(a.start,a.end)].copy()
            for rule in rules:
                g=aggregate_rule(h,rule); g["symbol"]=code; frames[rule].append(g)
            if i%25==0: print(f"progress {i}/{len(codes)}",flush=True)
    results={}
    for rule in rules:
        if not frames[rule]: results[rule]={"n":0}; continue
        y=pd.concat(frames[rule],ignore_index=True)
        m=prod.merge(y,on=["date","session","symbol"],how="inner",suffixes=("_prod","_yahoo"))
        results[rule]=metrics(m)
    ranked=sorted(results.items(),key=lambda kv:(kv[1].get("ohlc_mean_mape",999),kv[1].get("volume_mape",999)))
    out={"production_rows":int(len(prod)),"production_symbols":int(prod.symbol.nunique()),"requested_symbols":len(codes),"errors":errors,"rules":results,"ranking":[r for r,_ in ranked],"best_rule":ranked[0][0] if ranked else None}
    od=Path(a.output_dir);od.mkdir(parents=True,exist_ok=True);(od/"parity_4h.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
