#!/usr/bin/env python3
"""Bootstrap the test screener with a dynamically discovered JPX universe file.

TEST ONLY. The optional TVFREE_START_DATE environment variable switches Yahoo
history acquisition from a rolling ``period`` window to a fixed start date.
That keeps historical training rows stable as calendar time advances while
preserving ``run.py``'s normal period-based behavior outside this bootstrap.
"""
import io
import os
import re
import time
from urllib.parse import urljoin

import pandas as pd
import requests
import yfinance as yf

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


def fixed_start_fetch_daily(universe: pd.DataFrame, period: str, batch: int = 80) -> pd.DataFrame:
    """Download daily OHLCV from a fixed date when TVFREE_START_DATE is set.

    The ``period`` argument remains in the signature because ``run.py`` calls
    ``fetch_daily(universe, period)``. If no fixed start is configured, defer
    unchanged to the original implementation.
    """
    start_date = os.environ.get("TVFREE_START_DATE", "").strip()
    if not start_date:
        return _original_fetch_daily(universe, period, batch)

    # Validate once and normalize the representation used by yfinance.
    start_date = pd.Timestamp(start_date).strftime("%Y-%m-%d")
    print(f"Yahoo history mode: fixed start {start_date} -> current")

    rows = []
    tickers = universe["ticker"].tolist()
    for no, part in enumerate(core._chunk(tickers, batch), 1):
        data = None
        err = None
        for attempt in range(3):
            try:
                data = yf.download(
                    part,
                    start=start_date,
                    interval="1d",
                    group_by="ticker",
                    auto_adjust=False,
                    actions=False,
                    threads=True,
                    progress=False,
                    timeout=30,
                )
                if data is not None and not data.empty:
                    break
            except Exception as exc:
                err = exc
            time.sleep(2 ** attempt)
        if data is None or data.empty:
            print(f"WARN batch {no}: no data ({err})")
            continue

        for ticker in part:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if ticker not in data.columns.get_level_values(0):
                        continue
                    z = data[ticker].copy()
                else:
                    z = data.copy()
                z = z.rename(columns={c: str(c).lower() for c in z.columns})
                need = ["open", "high", "low", "close", "volume"]
                if not all(c in z.columns for c in need):
                    continue
                z = z[need].dropna(subset=["close"]).reset_index()
                z = z.rename(columns={z.columns[0]: "date"})
                z["symbol"] = ticker[:-2]
                rows.append(z)
            except Exception as exc:
                print(f"WARN {ticker}: {exc}")
        print(f"downloaded batch {no}/{(len(tickers) + batch - 1) // batch}")

    if not rows:
        raise RuntimeError("Yahoo Finance returned no usable rows")
    d = pd.concat(rows, ignore_index=True)
    d["date"] = pd.to_datetime(d["date"]).dt.tz_localize(None).dt.normalize()
    for c in ["open", "high", "low", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")


_original_fetch_daily = core.fetch_daily
core.jpx_universe = dynamic_jpx_universe
core.fetch_daily = fixed_start_fetch_daily

if __name__ == "__main__":
    core.main()
