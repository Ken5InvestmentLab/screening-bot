"""Acquire frozen-period EDINET daily metadata without reading parser or strategy outcomes.

The EDINET v2 documents-list API requires date, type, and Subscription-Key query
parameters. This helper writes one raw JSON response per requested calendar day
and is deliberately separated from snapshot freezing/selection.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"


def _dates(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def acquire_day(day: date, *, api_key: str, timeout: float = 60.0) -> bytes:
    if not api_key:
        raise ValueError("EDINET API key is required")
    query = urllib.parse.urlencode(
        {"date": day.isoformat(), "type": "2", "Subscription-Key": api_key}
    )
    req = urllib.request.Request(f"{BASE_URL}?{query}", headers={"User-Agent": "screening-bot-research/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if getattr(resp, "status", 200) != 200:
            raise RuntimeError(f"EDINET HTTP status {getattr(resp, 'status', None)} for {day}")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError(f"{day}: malformed EDINET response")
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("status") is not None and str(metadata.get("status")) != "200":
        raise ValueError(f"{day}: EDINET metadata status is not 200")
    return raw


def acquire_range(
    output_dir: str | Path,
    *,
    start: str,
    end: str,
    api_key: str,
    sleep_seconds: float = 0.25,
    overwrite: bool = False,
) -> dict[str, int]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if start_date > end_date:
        raise ValueError("start must be <= end")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    fetched = skipped = 0
    for day in _dates(start_date, end_date):
        path = root / f"{day.isoformat()}.json"
        if path.exists() and not overwrite:
            skipped += 1
            continue
        raw = acquire_day(day, api_key=api_key)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_bytes(raw)
        tmp.replace(path)
        fetched += 1
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return {"fetched": fetched, "skipped": skipped}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--api-key-env", default="EDINET_API_KEY")
    p.add_argument("--sleep-seconds", type=float, default=0.25)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args()
    api_key = os.environ.get(a.api_key_env, "").strip()
    if not api_key:
        raise SystemExit(f"missing required environment variable: {a.api_key_env}")
    print(
        json.dumps(
            acquire_range(
                a.output_dir,
                start=a.start,
                end=a.end,
                api_key=api_key,
                sleep_seconds=a.sleep_seconds,
                overwrite=a.overwrite,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
