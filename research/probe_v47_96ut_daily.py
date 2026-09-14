from __future__ import annotations

import json
import time
from io import StringIO

import pandas as pd
import requests

SYMBOLS=["1439","5595","7205","8515","8940"]
YEARS=[2024,2025]
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"


def fetch(code: str, year: int):
    url="https://96ut.com/stock/jikei.php"
    r=requests.get(url,params={"code":code,"year":year},headers={"User-Agent":UA},timeout=30)
    out={"status":r.status_code,"bytes":len(r.content),"rows":0}
    if r.status_code!=200:
        return out
    try:
        tables=pd.read_html(StringIO(r.text))
    except Exception as e:
        out["parse_error"]=type(e).__name__
        return out
    for t in tables:
        cols=[str(c).strip() for c in t.columns]
        if all(x in cols for x in ["日付","始値","高値","安値","終値","出来高"]):
            out["rows"]=int(len(t))
            out["first"]=str(t["日付"].iloc[-1]) if len(t) else None
            out["last"]=str(t["日付"].iloc[0]) if len(t) else None
            return out
    out["tables"]=len(tables)
    return out


def main():
    result={}
    for code in SYMBOLS:
        result[code]={}
        for year in YEARS:
            result[code][str(year)]=fetch(code,year)
            print(code,year,result[code][str(year)],flush=True)
            time.sleep(1.0)
    print("FINAL_JSON")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
