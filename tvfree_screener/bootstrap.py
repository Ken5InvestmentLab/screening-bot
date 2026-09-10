#!/usr/bin/env python3
"""Bootstrap the test screener with a dynamically discovered JPX universe file."""
import io
import re
from urllib.parse import urljoin

import pandas as pd
import requests

import run as core

JPX_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"


def dynamic_jpx_universe() -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
    page = requests.get(JPX_PAGE, timeout=60, headers=headers)
    page.raise_for_status()
    hrefs = re.findall(r'href=["\']([^"\']+\.(?:xls|xlsx)(?:\?[^"\']*)?)["\']', page.text, flags=re.I)
    if not hrefs:
        raise RuntimeError("JPX listed-issues Excel link was not found on the official page")
    # Prefer the listed-issues attachment when multiple spreadsheets exist.
    href = next((h for h in hrefs if "data_j" in h.lower()), hrefs[0])
    excel_url = urljoin(JPX_PAGE, href)
    print(f"JPX universe source: {excel_url}")
    r = requests.get(excel_url, timeout=60, headers={**headers, "Referer": JPX_PAGE})
    r.raise_for_status()
    x = pd.read_excel(io.BytesIO(r.content), dtype={"コード": str})
    market_col = next(c for c in x.columns if "市場" in str(c) and "区分" in str(c))
    code_col = next(c for c in x.columns if str(c).strip() == "コード")
    name_col = next(c for c in x.columns if "銘柄名" in str(c))
    market = x[market_col].astype(str)
    keep = market.str.contains("プライム|スタンダード|グロース", regex=True)
    keep &= market.str.contains("内国株式", regex=False)
    out = x.loc[keep, [code_col, name_col, market_col]].copy()
    out.columns = ["code", "name", "market"]
    out["code"] = out["code"].astype(str).str.strip()
    out = out[out["code"].str.match(r"^[0-9A-Z]{4}$", na=False)].drop_duplicates("code")
    out["ticker"] = out["code"] + ".T"
    print(f"JPX domestic common-stock universe: {len(out)}")
    return out.reset_index(drop=True)


core.jpx_universe = dynamic_jpx_universe

if __name__ == "__main__":
    core.main()
