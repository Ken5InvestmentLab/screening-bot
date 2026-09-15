#!/usr/bin/env python3
"""Capture exact official JPX PIT source bytes and emit a SHA-256 receipt.
Research-only; no strategy/performance logic.
"""
from __future__ import annotations
import hashlib, json, pathlib, time, urllib.request
from datetime import datetime, timezone

SOURCES = {
    "new_current": "https://www.jpx.co.jp/english/listing/stocks/new/index.html",
    "new_2025": "https://www.jpx.co.jp/english/listing/stocks/new/00-archives-01.html",
    "new_2024": "https://www.jpx.co.jp/english/listing/stocks/new/00-archives-02.html",
    "delisted_current": "https://www.jpx.co.jp/english/listing/stocks/delisted/index.html",
    "delisted_2025": "https://www.jpx.co.jp/english/listing/stocks/delisted/archives-01.html",
    "delisted_2024": "https://www.jpx.co.jp/english/listing/stocks/delisted/archives-02.html",
    # Official JPX page that publishes the previous-month-end TSE-listed-issues workbook.
    # Capture the page bytes first so the workbook href itself is provenance-pinned;
    # a later deterministic step may capture the discovered workbook bytes.
    "listed_issues_page": "https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html",
}
OUT = pathlib.Path("research/tentei_cloud/artifacts/jpx_pit_source_capture")
OUT.mkdir(parents=True, exist_ok=True)
rows=[]
for name,url in SOURCES.items():
    req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 research provenance capture"})
    last=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body=r.read(); final_url=r.geturl(); status=getattr(r,"status",200)
            break
        except Exception as e:
            last=e
            if attempt==2: raise
            time.sleep(2**attempt)
    suffix = ".html"
    path=OUT/f"{name}{suffix}"
    path.write_bytes(body)
    rows.append({"name":name,"source_url":url,"final_url":final_url,"http_status":status,"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest(),"captured_at_utc":datetime.now(timezone.utc).isoformat()})
receipt={"contract":"official JPX listing/delisting plus listed-issues anchor-page byte capture; research-only","sources":rows}
(OUT/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,ensure_ascii=False,indent=2))
