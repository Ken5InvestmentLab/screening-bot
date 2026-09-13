from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.T"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
KEEP_START = pd.Timestamp("2024-09-01", tz="Asia/Tokyo")
KEEP_END = pd.Timestamp("2025-12-31", tz="Asia/Tokyo")
SHARD_COUNT_DEFAULT = 12


def clean_symbol(x: object) -> str:
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def shard_symbols(symbols: list[str], shard_index: int, shard_count: int) -> list[str]:
    ordered = sorted(set(clean_symbol(x) for x in symbols if str(x).strip()))
    if not 0 <= shard_index < shard_count:
        raise ValueError("invalid shard index")
    return [s for i, s in enumerate(ordered) if i % shard_count == shard_index]


def fetch_chart(code: str) -> tuple[dict | None, str | None]:
    last = None
    for attempt in range(5):
        try:
            r = requests.get(
                YAHOO.format(symbol=quote(code, safe="")),
                params={"range": "730d", "interval": "1h"},
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json,text/plain,*/*",
                },
                timeout=30,
            )
            if r.status_code in {429, 502, 503, 504}:
                last = f"http_{r.status_code}"
                time.sleep(1.0 * (attempt + 1))
                continue
            r.raise_for_status()
            payload = r.json()
            err = payload.get("chart", {}).get("error")
            if err:
                return None, err.get("description") or "chart_error"
            result = (payload.get("chart", {}).get("result") or [None])[0]
            if not result:
                return None, "no_result"
            q = result.get("indicators", {}).get("quote", [{}])[0]
            ts = result.get("timestamp") or []
            if not ts or not q:
                return None, "empty_chart"
            return {
                "timestamp": ts,
                "open": q.get("open") or [],
                "high": q.get("high") or [],
                "low": q.get("low") or [],
                "close": q.get("close") or [],
                "volume": q.get("volume") or [],
            }, None
        except Exception as exc:
            last = type(exc).__name__
            time.sleep(0.8 * (attempt + 1))
    return None, last or "fetch_failed"


def parse_rows(code: str, chart: dict) -> pd.DataFrame:
    keys = ("timestamp", "open", "high", "low", "close", "volume")
    try:
        n = min(len(chart.get(k, [])) for k in keys)
    except Exception:
        return pd.DataFrame()
    rows = []
    for i in range(n):
        vals = [
            chart["open"][i],
            chart["high"][i],
            chart["low"][i],
            chart["close"][i],
            chart["volume"][i],
        ]
        if any(x is None for x in vals):
            continue
        o, h, l, c, v = map(float, vals)
        if c <= 0 or h <= 0 or l <= 0 or h < l or v < 0:
            continue
        ts = pd.to_datetime(
            int(chart["timestamp"][i]),
            unit="s",
            utc=True,
        ).tz_convert("Asia/Tokyo")
        if ts < KEEP_START or ts >= KEEP_END:
            continue
        rows.append({
            "symbol": code,
            "ts_jst": ts.isoformat(),
            "date": ts.strftime("%Y-%m-%d"),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
        })
    return pd.DataFrame(rows)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols-file", required=True, type=Path)
    ap.add_argument("--shard-index", required=True, type=int)
    ap.add_argument("--shard-count", type=int, default=SHARD_COUNT_DEFAULT)
    ap.add_argument("--output-dir", required=True, type=Path)
    a = ap.parse_args()

    all_symbols = [
        clean_symbol(x)
        for x in a.symbols_file.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    symbols = shard_symbols(all_symbols, a.shard_index, a.shard_count)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    raw_path = out / f"v47_raw1h_shard_{a.shard_index:02d}.csv.gz"

    receipts = []
    total_rows = 0
    with gzip.open(raw_path, "wt", encoding="utf-8", newline="") as gz:
        wrote_header = False
        for i, code in enumerate(symbols, 1):
            chart, err = fetch_chart(code)
            if chart is None:
                receipts.append({
                    "symbol": code,
                    "status": "fetch_error",
                    "error": err,
                    "rows": 0,
                })
                continue

            fr = parse_rows(code, chart)
            if fr.empty:
                receipts.append({
                    "symbol": code,
                    "status": "no_rows_in_window",
                    "error": None,
                    "rows": 0,
                })
                continue

            fr.to_csv(gz, index=False, header=not wrote_header)
            wrote_header = True
            total_rows += len(fr)
            receipts.append({
                "symbol": code,
                "status": "ok",
                "error": None,
                "rows": int(len(fr)),
                "first_date": str(fr["date"].min()),
                "last_date": str(fr["date"].max()),
            })
            if i % 25 == 0:
                print(
                    f"shard {a.shard_index}/{a.shard_count} "
                    f"{i}/{len(symbols)} rows={total_rows}",
                    flush=True,
                )
            time.sleep(0.02)

    r = pd.DataFrame(receipts)
    receipt_csv = out / f"v47_raw1h_shard_{a.shard_index:02d}_receipt.csv"
    r.to_csv(receipt_csv, index=False)

    ok = r[r["status"] == "ok"] if len(r) else r
    summary = {
        "scope": "outcome-blind V47 raw Yahoo 1H freeze",
        "shard_index": a.shard_index,
        "shard_count": a.shard_count,
        "all_required_symbols": len(set(all_symbols)),
        "requested_symbols": len(symbols),
        "ok_symbols": int(len(ok)),
        "non_ok_symbols": int(len(r) - len(ok)),
        "total_rows": int(total_rows),
        "date_window": ["2024-09-01", "2025-12-30"],
        "source": "Yahoo chart range=730d interval=1h",
        "strategy_returns_opened": False,
        "model_scores_opened": False,
        "production_writes": False,
        "files": {
            raw_path.name: sha256_file(raw_path),
            receipt_csv.name: sha256_file(receipt_csv),
        },
    }
    (out / f"v47_raw1h_shard_{a.shard_index:02d}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
