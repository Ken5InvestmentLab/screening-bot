from __future__ import annotations

import json
import time
from urllib.parse import quote

import requests

SYMBOLS=["1439","5595","7205","8515","8940"]
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"


def fetch_query2_with_crumb(code: str) -> dict:
    s=requests.Session()
    s.headers.update({"User-Agent":UA,"Accept":"application/json,text/plain,*/*"})
    crumb=None
    bootstrap={}
    try:
        r0=s.get("https://fc.yahoo.com",timeout=15,allow_redirects=True)
        bootstrap["fc_status"]=r0.status_code
    except Exception as e:
        bootstrap["fc_error"]=type(e).__name__

    try:
        rc=s.get("https://query2.finance.yahoo.com/v1/test/getcrumb",timeout=15)
        bootstrap["crumb_status"]=rc.status_code
        if rc.status_code==200 and rc.text and "Too Many Requests" not in rc.text:
            crumb=rc.text.strip()
    except Exception as e:
        bootstrap["crumb_error"]=type(e).__name__

    params={
        "period1":1725148800,
        "period2":1767225600,
        "interval":"1d",
        "events":"div,splits",
        "includePrePost":"false",
    }
    if crumb:
        params["crumb"]=crumb
    try:
        r=s.get(
            f"https://query2.finance.yahoo.com/v8/finance/chart/{quote(code+'.T',safe='')}",
            params=params,
            timeout=20,
        )
        out={
            **bootstrap,
            "chart_status":r.status_code,
            "has_crumb":bool(crumb),
            "content_type":r.headers.get("content-type"),
            "body_prefix":r.text[:200],
        }
        if r.status_code==200:
            try:
                p=r.json()
                result=(p.get("chart",{}).get("result") or [None])[0]
                out["rows"]=len(result.get("timestamp") or []) if result else 0
                out["chart_error"]=p.get("chart",{}).get("error")
            except Exception as e:
                out["json_error"]=type(e).__name__
        return out
    except Exception as e:
        return {**bootstrap,"request_error":f"{type(e).__name__}: {e}"}


def main():
    result={}
    for code in SYMBOLS:
        result[code]=fetch_query2_with_crumb(code)
        print(code,json.dumps(result[code],ensure_ascii=False),flush=True)
        time.sleep(5)
    print("FINAL_JSON")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
