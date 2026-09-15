#!/usr/bin/env python3
"""Capture exact official JPX PIT source bytes and emit a SHA-256 receipt.
Research-only; no strategy/performance logic.
"""
from __future__ import annotations
import hashlib, html, json, pathlib, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone

SOURCES = {
    "new_current": "https://www.jpx.co.jp/english/listing/stocks/new/index.html",
    "new_2025": "https://www.jpx.co.jp/english/listing/stocks/new/00-archives-01.html",
    "new_2024": "https://www.jpx.co.jp/english/listing/stocks/new/00-archives-02.html",
    "delisted_current": "https://www.jpx.co.jp/english/listing/stocks/delisted/index.html",
    "delisted_2025": "https://www.jpx.co.jp/english/listing/stocks/delisted/archives-01.html",
    "delisted_2024": "https://www.jpx.co.jp/english/listing/stocks/delisted/archives-02.html",
    "transfer_current": "https://www.jpx.co.jp/english/listing/stocks/transfers/index.html",
    "transfer_2025": "https://www.jpx.co.jp/english/listing/stocks/transfers/00-archives-01.html",
    "transfer_2024": "https://www.jpx.co.jp/english/listing/stocks/transfers/00-archives-02.html",
    "listed_issues_page": "https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html",
}
OUT = pathlib.Path("research/tentei_cloud/artifacts/jpx_pit_source_capture")
OUT.mkdir(parents=True, exist_ok=True)

def fetch_bytes(name: str, url: str, suffix: str):
    req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 research provenance capture"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body=r.read(); final_url=r.geturl(); status=getattr(r,"status",200)
            break
        except Exception:
            if attempt==2: raise
            time.sleep(2**attempt)
    (OUT/f"{name}{suffix}").write_bytes(body)
    row={"name":name,"source_url":url,"final_url":final_url,"http_status":status,"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest(),"captured_at_utc":datetime.now(timezone.utc).isoformat()}
    return body,row

rows=[]; bodies={}
for name,url in SOURCES.items():
    body,row=fetch_bytes(name,url,".html")
    bodies[name]=body; rows.append(row)

# Discover only from the exact captured JPX publication-page bytes. The page also
# links a historical correction workbook (jyoujyou(updated)_e.xlsx); that object
# is explicitly NOT the current listed-issues universe and must never be selected.
page=bodies["listed_issues_page"].decode("utf-8","ignore")
hrefs=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',page,re.I)]
books=[x for x in hrefs if x.lower().endswith((".xlsx",".xls"))]
current=[x for x in books if x.lower().endswith("/data_e.xlsx")]
if len(current)!=1:
    raise RuntimeError(f"fail-closed: expected exactly one current listed-issues data_e workbook, got all={books}, current={current}")
book_url=urllib.parse.urljoin(SOURCES["listed_issues_page"],current[0])
_,book_row=fetch_bytes("listed_issues_workbook",book_url,".xlsx" if book_url.lower().endswith(".xlsx") else ".xls")
book_row["discovered_from_page_sha256"]=next(r["sha256"] for r in rows if r["name"]=="listed_issues_page")
book_row["excluded_correction_workbooks"]=[x for x in books if x not in current]
rows.append(book_row)

receipt={"contract":"official JPX listing/delisting/segment-transfer plus listed-issues anchor page/current workbook byte capture; correction workbook excluded; research-only","sources":rows}
(OUT/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,ensure_ascii=False,indent=2))
