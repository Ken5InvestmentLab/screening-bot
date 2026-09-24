#!/usr/bin/env python3
"""Fail-closed daily Cloud detection gate and independent 5BD close settlement.

Research-only policy. A daily Yahoo 1H acquisition failure blocks all new
signals for that date. Previously detected signals may settle from real Yahoo
Chart 1D closes; daily data never becomes synthetic intraday data.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from fetch_1h import UA, yahoo_symbol

JST = ZoneInfo("Asia/Tokyo")
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def detection_gate(targets: set[str], seen_on_day: set[str], failed_on_day: set[str]) -> dict:
    missing = sorted(targets - seen_on_day)
    failed = sorted(targets & failed_on_day)
    return {"new_detection_allowed": bool(targets) and not missing and not failed,
            "target_symbols": len(targets), "seen_on_day": len(targets & seen_on_day),
            "missing_symbols": missing, "failed_symbols": failed,
            "reason": "complete_1h" if targets and not missing and not failed else "incomplete_1h"}


def daily_close_from_payload(code: str, date: dt.date, payload: dict) -> float:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"Yahoo daily error: {chart['error']}")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise ValueError("Yahoo daily result missing")
    stamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    for i, stamp in enumerate(stamps):
        local_date = dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).astimezone(JST).date()
        if local_date == date and i < len(closes) and closes[i] is not None:
            price = float(closes[i])
            if price <= 0:
                raise ValueError(f"invalid daily close for {code} {date}")
            return price
    raise ValueError(f"actual daily close missing for {code} {date}; no fill permitted")


def fetch_daily_close(code: str, date: dt.date, retries: int = 5) -> float:
    ticker = urllib.parse.quote(yahoo_symbol(code))
    start = int(dt.datetime.combine(date, dt.time(), tzinfo=JST).timestamp())
    end = int(dt.datetime.combine(date + dt.timedelta(days=1), dt.time(), tzinfo=JST).timestamp())
    params = urllib.parse.urlencode({"period1": start, "period2": end, "interval": "1d",
                                     "includePrePost": "false", "events": "div,splits"})
    url = BASE.format(symbol=ticker) + "?" + params
    last = "request failed"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return daily_close_from_payload(code, date, payload)
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except (OSError, ValueError, KeyError, TypeError) as exc:
            last = str(exc)
        if attempt + 1 < retries:
            time.sleep(min(30, 2 ** attempt + random.random()))
    raise RuntimeError(last)


def settle_due_positions(positions: list[dict], date: dt.date, price_lookup=fetch_daily_close) -> list[dict]:
    cache: dict[tuple[str, dt.date], float | Exception] = {}
    out = []
    for position in positions:
        row = dict(position)
        exit_date = dt.date.fromisoformat(row["exit_date"])
        row.update({"exit_close": "", "return_5bd": "", "price_source": "", "status": "not_due"})
        if exit_date > date:
            out.append(row)
            continue
        code = row["symbol"].upper().removesuffix(".T")
        key = (code, exit_date)
        if key not in cache:
            try:
                cache[key] = price_lookup(code, exit_date)
            except Exception as exc:
                cache[key] = exc
        close = cache[key]
        if isinstance(close, Exception):
            row["status"] = "unresolved"
            row["error"] = str(close)
        else:
            entry = float(row["entry_price"])
            if entry <= 0:
                raise ValueError(f"invalid entry_price for {row.get('signal_id', code)}")
            row.update({"exit_close": close, "return_5bd": close / entry - 1,
                        "price_source": "Yahoo Chart API 1d actual close", "status": "settled"})
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--symbols", required=True, help="current JPX symbols.txt")
    ap.add_argument("--intraday", required=True, help="glob for the completed daily 1H CSV shards")
    ap.add_argument("--failures", required=True, help="glob for the completed daily 1H failure JSON shards")
    ap.add_argument("--positions", required=True, help="existing signals with signal_id,symbol,exit_date,entry_price")
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    day = dt.date.fromisoformat(a.date)
    targets = {s.strip() for s in Path(a.symbols).read_text(encoding="utf-8").splitlines() if s.strip()}
    seen = set()
    for path in sorted(glob.glob(a.intraday, recursive=True)):
        with Path(path).open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                stamp = dt.datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S%z").astimezone(JST)
                if stamp.date() == day:
                    seen.add(row["symbol"])
    failed = set()
    for path in sorted(glob.glob(a.failures, recursive=True)):
        for item in json.loads(Path(path).read_text(encoding="utf-8")):
            if dt.date.fromisoformat(item["start"]) <= day <= dt.date.fromisoformat(item["end"]):
                failed.add(item["symbol"])
    gate = detection_gate(targets, seen, failed)
    with Path(a.positions).open(encoding="utf-8", newline="") as f:
        positions = list(csv.DictReader(f))
    settled = settle_due_positions(positions, day)
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "detection_gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = list(dict.fromkeys(["signal_id", "symbol", "exit_date", "entry_price", "exit_close",
                                "return_5bd", "price_source", "status", "error"] +
                               [key for row in settled for key in row]))
    with (out / "exit_settlements.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(settled)
    print(json.dumps({"gate": gate, "settled": sum(r["status"] == "settled" for r in settled),
                      "unresolved": sum(r["status"] == "unresolved" for r in settled)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
