#!/usr/bin/env python3
"""Fetch JPX 1-hour OHLCV from Yahoo Finance for Tentei Cloud research.

Research-only. Does not write to production Sheets/Discord.
The symbol universe is sharded so GitHub Actions can fetch in parallel.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
UA = "Mozilla/5.0 TenteiCloudResearch/1.0"
CODE = re.compile(r"^[0-9A-Z]{4}$")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--shard-index", type=int, default=0)
    p.add_argument("--shard-count", type=int, default=1)
    p.add_argument("--chunk-days", type=int, default=110)
    p.add_argument("--output", required=True)
    p.add_argument("--failures", default="")
    return p.parse_args()

def epoch_jst(d, end=False):
    t = dt.time(23, 59, 59) if end else dt.time(0, 0, 0)
    return int(dt.datetime.combine(d, t, tzinfo=JST).timestamp())

def load_symbols(path, shard_index, shard_count):
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip().upper()
        if s and not s.startswith("#"):
            items.append(s)
    items = sorted(dict.fromkeys(items))
    bad = [s for s in items if not CODE.fullmatch(s)]
    if bad:
        raise ValueError(f"invalid JPX symbols: {bad[:10]}")
    if shard_count < 1 or not (0 <= shard_index < shard_count):
        raise ValueError("invalid shard")
    return [s for i, s in enumerate(items) if i % shard_count == shard_index]

def chunks(start, end, days):
    cur = start
    while cur <= end:
        chunk_end = min(end, cur + dt.timedelta(days=days - 1))
        yield cur, chunk_end
        cur = chunk_end + dt.timedelta(days=1)

def yahoo_symbol(code):
    code = code.upper()
    base = code[:-2] if code.endswith(".T") else code
    if not CODE.fullmatch(base):
        raise ValueError(f"invalid Yahoo JPX symbol: {code}")
    return base + ".T"


def deduplicate_rows(rows):
    return {(row[1], row[0]): row for row in rows}

def request_json(code, start, end, retries=5):
    symbol = urllib.parse.quote(yahoo_symbol(code))
    p1 = epoch_jst(start)
    p2 = epoch_jst(end + dt.timedelta(days=1))
    params = urllib.parse.urlencode({
        "period1": p1,
        "period2": p2,
        "interval": "1h",
        "includePrePost": "false",
        "events": "div,splits",
    })
    url = BASE.format(symbol=symbol) + "?" + params
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:
            last = repr(e)
        time.sleep(min(30.0, (2 ** attempt) + random.random()))
    raise RuntimeError(last or "request failed")

def extract_rows(code, payload, start, end):
    chart = payload.get("chart") or {}
    err = chart.get("error")
    if err:
        raise RuntimeError(str(err))
    result = (chart.get("result") or [None])[0]
    if not result:
        return []
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    rows = []
    for i, ts in enumerate(timestamps):
        stamp = dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc).astimezone(JST)
        if stamp.date() < start or stamp.date() > end:
            continue
        if stamp.hour < 9 or stamp.hour > 16:
            continue
        vals = []
        for arr in (opens, highs, lows, closes, volumes):
            vals.append(arr[i] if i < len(arr) else None)
        o, h, l, c, v = vals
        if c is None or o is None or h is None or l is None:
            continue
        rows.append((
            stamp.strftime("%Y-%m-%d %H:%M:%S%z"),
            code,
            float(o), float(h), float(l), float(c),
            0.0 if v is None else float(v),
        ))
    return rows

def main():
    a = parse_args()
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end)
    if end < start:
        raise SystemExit("end must be >= start")
    syms = load_symbols(a.symbols, a.shard_index, a.shard_count)
    print(f"shard {a.shard_index}/{a.shard_count}: {len(syms)} symbols")
    all_rows = {}
    failures = []
    total = len(syms)
    for pos, code in enumerate(syms, 1):
        symbol_rows = 0
        for cstart, cend in chunks(start, end, a.chunk_days):
            try:
                payload = request_json(code, cstart, cend)
                rows = extract_rows(code, payload, cstart, cend)
                if not rows:
                    failures.append({"symbol": code, "start": str(cstart), "end": str(cend), "error": "no_usable_rows"})
                all_rows.update(deduplicate_rows(rows))
                symbol_rows += len(rows)
            except Exception as e:
                failures.append({"symbol": code, "start": str(cstart), "end": str(cend), "error": str(e)})
        if pos % 20 == 0 or pos == total:
            print(f"{pos}/{total} {code}: rows={symbol_rows}, failures={len(failures)}")
        time.sleep(0.08 + random.random() * 0.08)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "symbol", "open", "high", "low", "close", "volume"])
        for key in sorted(all_rows, key=lambda k: (k[0], k[1])):
            w.writerow(all_rows[key])
    failure_path = Path(a.failures) if a.failures else out.with_suffix(".failures.json")
    failure_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(all_rows)} rows -> {out}; failures={len(failures)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
