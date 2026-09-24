#!/usr/bin/env python3
"""Audit the exact JPX target set against sharded Yahoo 1H artifacts."""
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import Counter
from pathlib import Path


def coverage(universe_rows: list[dict], ohlcv_paths: list[Path], failure_paths: list[Path]) -> tuple[dict, list[dict]]:
    target = {r["code"]: r for r in universe_rows}
    if len(target) != len(universe_rows) or not target:
        raise ValueError("empty or duplicated JPX universe")
    seen: set[str] = set()
    keys: set[tuple[str, str]] = set()
    first = last = None
    duplicates = total_rows = 0
    for path in ohlcv_paths:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not {"timestamp", "symbol", "open", "high", "low", "close", "volume"} <= set(reader.fieldnames or []):
                raise ValueError(f"bad OHLCV header: {path}")
            for row in reader:
                symbol, stamp = row["symbol"], row["timestamp"]
                if symbol not in target:
                    raise ValueError(f"OHLCV symbol outside JPX universe: {symbol}")
                total_rows += 1
                seen.add(symbol)
                key = (symbol, stamp)
                if key in keys:
                    duplicates += 1
                else:
                    keys.add(key)
                first = stamp if first is None or stamp < first else first
                last = stamp if last is None or stamp > last else last
    failures = []
    for path in failure_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"bad failure JSON: {path}")
        failures.extend(data)
    missing = [target[s] for s in sorted(target.keys() - seen)]
    markets = ("Prime", "Standard", "Growth")
    report = {
        "target_symbols": len(target), "seen_symbols": len(seen),
        "missing_symbols": len(missing), "coverage_rate": len(seen) / len(target),
        "total_rows": total_rows, "unique_rows": len(keys), "duplicate_rows": duplicates,
        "failed_chunks": len(failures), "failure_symbols": len({f["symbol"] for f in failures}),
        "first_timestamp": first, "last_timestamp": last,
        "market_counts": {m: sum(r["market"] == m for r in universe_rows) for m in markets},
        "seen_by_market": {m: sum(target[s]["market"] == m for s in seen) for m in markets},
        "missing_by_market": {m: sum(r["market"] == m for r in missing) for m in markets},
        "failure_reasons": dict(Counter(f.get("error", "unknown") for f in failures)),
    }
    return report, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True)
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--failures", required=True)
    ap.add_argument("--expected-shards", type=int, required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    paths = [list(map(Path, sorted(glob.glob(p, recursive=True)))) for p in (a.inputs, a.failures)]
    if any(len(p) != a.expected_shards for p in paths):
        raise SystemExit(f"expected {a.expected_shards} OHLCV and failure files, found {[len(p) for p in paths]}")
    with Path(a.universe).open(encoding="utf-8", newline="") as f:
        universe = list(csv.DictReader(f))
    report, missing = coverage(universe, *paths)
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "missing_symbols.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "name", "market", "ticker"])
        writer.writeheader()
        writer.writerows(missing)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
