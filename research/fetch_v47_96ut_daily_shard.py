from __future__ import annotations

import argparse
import json
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"
YEARS=(2024,2025,2026)


def clean(x: object) -> str:
    s=str(x).strip()
    return s[:-2] if s.endswith(".0") else s


def shard_symbols(symbols: list[str], shard_index: int, shard_count: int) -> list[str]:
    ordered=sorted(set(clean(x) for x in symbols if str(x).strip()))
    return [s for i,s in enumerate(ordered) if i % shard_count == shard_index]


def parse_num(x):
    s=str(x).replace(",","").replace("―","").replace("-","").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def fetch_year(code: str, year: int) -> tuple[pd.DataFrame,str|None]:
    try:
        r=requests.get(
            "https://96ut.com/stock/jikei.php",
            params={"code":code,"year":year},
            headers={"User-Agent":UA},
            timeout=30,
        )
    except Exception as e:
        return pd.DataFrame(),f"{type(e).__name__}: {e}"
    if r.status_code!=200:
        return pd.DataFrame(),f"http_{r.status_code}"
    try:
        tables=pd.read_html(StringIO(r.text))
    except Exception as e:
        return pd.DataFrame(),f"parse_{type(e).__name__}"

    target=None
    for t in tables:
        cols=[str(c).strip() for c in t.columns]
        if all(k in cols for k in ["日付","始値","高値","安値","終値","出来高"]):
            target=t.copy()
            break
    if target is None or target.empty:
        return pd.DataFrame(),"no_price_table"

    out=pd.DataFrame({
        "date":pd.to_datetime(target["日付"],errors="coerce"),
        "open":[parse_num(x) for x in target["始値"]],
        "high":[parse_num(x) for x in target["高値"]],
        "low":[parse_num(x) for x in target["安値"]],
        "close":[parse_num(x) for x in target["終値"]],
        "volume":[parse_num(x) for x in target["出来高"]],
    })
    out["symbol"]=code
    out=out.dropna(subset=["date","open","high","low","close","volume"])
    out=out[
        (out["close"]>0)&(out["high"]>0)&(out["low"]>0)&
        (out["high"]>=out["low"])&(out["volume"]>=0)
    ].copy()
    out["date"]=out["date"].dt.strftime("%Y-%m-%d")
    out=out.drop_duplicates(["symbol","date"]).sort_values("date")
    return out,None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily-receipt",required=True,type=Path)
    ap.add_argument("--shard-index",required=True,type=int)
    ap.add_argument("--shard-count",required=True,type=int)
    ap.add_argument("--output-dir",required=True,type=Path)
    a=ap.parse_args()

    receipt=json.loads(a.daily_receipt.read_text(encoding="utf-8"))
    all_missing=[
        clean(x)
        for x in receipt["restored_daily_fetch"]["missing_symbols"]
    ]
    symbols=shard_symbols(all_missing,a.shard_index,a.shard_count)

    frames=[]
    recs=[]
    for i,code in enumerate(symbols,1):
        code_frames=[]
        errs=[]
        for year in YEARS:
            fr,err=fetch_year(code,year)
            if not fr.empty:
                code_frames.append(fr)
            if err:
                errs.append({"year":year,"error":err})
            time.sleep(1.0)
        if code_frames:
            z=pd.concat(code_frames,ignore_index=True)
            z=z.drop_duplicates(["symbol","date"]).sort_values("date")
            frames.append(z)
            recs.append({
                "symbol":code,"status":"ok","rows":int(len(z)),
                "first_date":str(z["date"].min()),
                "last_date":str(z["date"].max()),
                "errors":json.dumps(errs,ensure_ascii=False),
            })
        else:
            recs.append({
                "symbol":code,"status":"no_data","rows":0,
                "first_date":"","last_date":"",
                "errors":json.dumps(errs,ensure_ascii=False),
            })
        print(
            f"shard {a.shard_index}/{a.shard_count} {i}/{len(symbols)} "
            f"{code} {recs[-1]['status']} rows={recs[-1]['rows']}",
            flush=True,
        )

    out=a.output_dir
    out.mkdir(parents=True,exist_ok=True)
    daily=(
        pd.concat(frames,ignore_index=True)
        if frames else
        pd.DataFrame(columns=["date","open","high","low","close","volume","symbol"])
    )
    daily.to_csv(out/f"v47_96ut_daily_shard_{a.shard_index:02d}.csv.gz",index=False,compression="gzip")
    pd.DataFrame(recs).to_csv(out/f"v47_96ut_receipt_shard_{a.shard_index:02d}.csv",index=False)

    ok=sum(1 for x in recs if x["status"]=="ok")
    summary={
        "scope":"outcome-free restored/delisted nominal daily OHLCV from 96ut",
        "shard_index":a.shard_index,
        "shard_count":a.shard_count,
        "requested_symbols":len(symbols),
        "ok_symbols":ok,
        "missing_symbols":[x["symbol"] for x in recs if x["status"]!="ok"],
        "rows":int(len(daily)),
        "years":list(YEARS),
        "basis":"point-in-time nominal OHLCV as displayed by 96ut; no future split normalization applied here",
        "strategy_returns_opened":False,
        "model_scores_opened":False,
        "production_writes":False,
    }
    (out/f"v47_96ut_summary_shard_{a.shard_index:02d}.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
