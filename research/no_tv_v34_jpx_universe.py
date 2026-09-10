from __future__ import annotations

import argparse
import json
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

JPX_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
MARKET_COLS = ["市場・商品区分", "市場商品区分", "市場区分"]
CODE_COLS = ["コード", "銘柄コード"]
NAME_COLS = ["銘柄名", "会社名"]
TARGET_MARKETS = ["プライム", "スタンダード", "グロース"]
MARKET_EXCLUDE = ["ETF", "ETN", "REIT", "インフラファンド", "出資証券", "優先出資証券", "外国株式"]
NAME_EXCLUDE = ["優先株", "優先出資", "種類株"]


def pick(cols, names):
    for n in names:
        if n in cols:
            return n
    raise RuntimeError(f"column not found: {names}; actual={cols}")


def normalize_code(v):
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def resolve_excel_url():
    r = requests.get(JPX_PAGE, headers={"User-Agent": UA}, timeout=45)
    r.raise_for_status()
    html = r.text.replace("\\/", "/").replace("&amp;", "&")
    hrefs = re.findall(r'["\']([^"\']+\.(?:xls|xlsx)(?:\?[^"\']*)?)["\']', html, re.I)
    urls = []
    for h in hrefs:
        u = urljoin(JPX_PAGE, h)
        if u not in urls:
            urls.append(u)
    if not urls:
        raise RuntimeError("JPX listed-issues Excel link not found")
    urls.sort(key=lambda u: ("data_j" not in u.lower(), u))
    return urls[0]


def load_universe():
    url = resolve_excel_url()
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    df = pd.read_excel(BytesIO(r.content))
    df.columns = [str(c).strip() for c in df.columns]
    market_col = pick(list(df.columns), MARKET_COLS)
    code_col = pick(list(df.columns), CODE_COLS)
    name_col = pick(list(df.columns), NAME_COLS)

    rows = []
    excluded = {"non_target_market": 0, "market_keyword": 0, "name_keyword": 0, "bad_code": 0}
    for _, row in df.iterrows():
        market = str(row.get(market_col, "")).strip()
        code = normalize_code(row.get(code_col, ""))
        name = str(row.get(name_col, "")).strip()
        if not any(k in market for k in TARGET_MARKETS):
            excluded["non_target_market"] += 1
            continue
        if any(k in market for k in MARKET_EXCLUDE):
            excluded["market_keyword"] += 1
            continue
        if any(k in name for k in NAME_EXCLUDE):
            excluded["name_keyword"] += 1
            continue
        if not re.fullmatch(r"[0-9A-Z]{4}", code):
            excluded["bad_code"] += 1
            continue
        rows.append({"code": code, "name": name, "market": market, "yahoo_symbol": f"{code}.T"})

    out = pd.DataFrame(rows).drop_duplicates("code").sort_values("code").reset_index(drop=True)
    if out.empty:
        raise RuntimeError("JPX ordinary-stock universe is empty")
    market_counts = out.market.value_counts().to_dict()
    return url, out, excluded, market_counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="research_artifacts/v34_jpx_universe")
    a = ap.parse_args()
    url, universe, excluded, market_counts = load_universe()
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    universe.to_csv(out / "jpx_ordinary_universe.csv", index=False, encoding="utf-8-sig")
    result = {
        "scope": "Current JPX Prime/Standard/Growth domestic ordinary-stock universe. No TradingView, no Google Sheet, no teacher data.",
        "jpx_page": JPX_PAGE,
        "resolved_excel": url,
        "universe_count": len(universe),
        "market_counts": market_counts,
        "excluded_counts": excluded,
        "sample": universe.head(20).to_dict("records"),
    }
    (out / "v34_jpx_universe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
