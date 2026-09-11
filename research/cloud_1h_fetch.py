#!/usr/bin/env python3
"""Research-only Yahoo Finance JPX 1h downloader for 天底極致 Cloud.

- Keeps genuine 1h bars; does NOT aggregate into the production 09:00/13:00 session bars.
- Writes no production Sheets/Discord data.
- Intended for research/tentei-cloud-1h only.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
UA = "Mozilla/5.0 (compatible; TenteiCloudResearch/1.0)"


def yahoo_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.startswith("TYO:"):
        s = s.split(":", 1)[1]
    if s.endswith(".T"):
        return s
    return f"{s}.T"


def epoch_jst(date_text: str, end: bool = False) -> int:
    d = dt.date.fromisoformat(date_text)
    t = dt.time(23, 59, 59) if end else dt.time(0, 0, 0)
    return int(dt.datetime.combine(d, t, JST).timestamp())


def fetch_chunk(symbol: str, start: dt.datetime, end: dt.datetime) -> list[dict]:
    ys = yahoo_symbol(symbol)
    qs = urllib.parse.urlencode({
        "interval": "1h",
        "period1": int(start.timestamp()),
        "period2": int(end.timestamp()),
        "includePrePost": "false",
        "events": "div,splits",
    })
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ys)}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))

    result = (data.get("chart") or {}).get("result")
    if not result:
        return []
    r = result[0]
    ts = r.get("timestamp") or []
    quote = (((r.get("indicators") or {}).get("quote") or [{}])[0])
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    rows = []
    for i, sec in enumerate(ts):
        vals = [opens[i] if i < len(opens) else None,
                highs[i] if i < len(highs) else None,
                lows[i] if i < len(lows) else None,
                closes[i] if i < len(closes) else None]
        if any(v is None for v in vals):
            continue
        stamp = dt.datetime.fromtimestamp(sec, JST)
        # JPX regular-session data only. Keep 15:30/16:00 flat snapshots flagged,
        # so research code can decide whether to use or ignore them.
        if stamp.hour < 9 or stamp.hour > 16:
            continue
        vol = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
        o, h, l, c = map(float, vals)
        flat = (o == h == l == c)
        snapshot = bool(vol == 0 and flat and ((stamp.hour == 15 and stamp.minute >= 30) or stamp.hour == 16))
        rows.append({
            "symbol": symbol,
            "timestamp": stamp.isoformat(),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": int(vol or 0),
            "is_closing_snapshot": int(snapshot),
        })
    return rows


def fetch_symbol(symbol: str, start_date: str, end_date: str, chunk_days: int = 30) -> list[dict]:
    start = dt.datetime.combine(dt.date.fromisoformat(start_date), dt.time(), JST)
    stop = dt.datetime.combine(dt.date.fromisoformat(end_date) + dt.timedelta(days=1), dt.time(), JST)
    out = []
    cur = start
    while cur < stop:
        nxt = min(cur + dt.timedelta(days=chunk_days), stop)
        out.extend(fetch_chunk(symbol, cur, nxt))
        cur = nxt
        time.sleep(0.25)

    # Deterministic de-duplication: one row per symbol/timestamp.
    uniq = {(r["symbol"], r["timestamp"]): r for r in out}
    return [uniq[k] for k in sorted(uniq, key=lambda x: (x[0], x[1]))]


def parse_symbols(args) -> list[str]:
    values = []
    if args.symbols:
        values.extend(x.strip() for x in args.symbols.split(",") if x.strip())
    if args.symbol_file:
        for line in Path(args.symbol_file).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                values.append(s)
    # preserve order
    return list(dict.fromkeys(values))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default="")
    p.add_argument("--symbol-file")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", default="cloud_1h_raw.csv")
    p.add_argument("--chunk-days", type=int, default=30)
    args = p.parse_args()

    symbols = parse_symbols(args)
    if not symbols:
        raise SystemExit("No symbols supplied")

    rows = []
    failures = []
    for idx, symbol in enumerate(symbols, 1):
        try:
            got = fetch_symbol(symbol, args.start, args.end, args.chunk_days)
            rows.extend(got)
            print(f"[{idx}/{len(symbols)}] {symbol}: {len(got)} rows")
        except Exception as exc:
            failures.append((symbol, repr(exc)))
            print(f"[{idx}/{len(symbols)}] {symbol}: ERROR {exc}")
        time.sleep(0.25)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["symbol","timestamp","open","high","low","close","volume","is_closing_snapshot"]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out}")
    if failures:
        print("Failures:")
        for symbol, err in failures:
            print(f"  {symbol}: {err}")


if __name__ == "__main__":
    main()
