"""Display-only latest nominal closes; never feed prices into frozen scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "weak_early_beta/state/latest_prices.json"
IDENTITY = "CLOUD_LATEST_PRICES_V1"


def write_snapshot(daily: pd.DataFrame, symbols, source_sha256: str,
                   path: Path = DEFAULT_SNAPSHOT) -> dict:
    """Called only after the daily pipeline's source-quality/revision gates."""
    if len(source_sha256) != 64:
        raise ValueError("latest prices require the verified source SHA-256")
    data = daily.loc[daily["symbol"].astype(str).isin(set(map(str, symbols))),
                     ["symbol", "date", "actual_close", "source_usable"]].copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise")
    data = data.sort_values(["symbol", "date"], kind="stable").drop_duplicates("symbol", keep="last")
    prices = {}
    for row in data.itertuples(index=False):
        price = pd.to_numeric(row.actual_close, errors="coerce")
        usable = str(row.source_usable).lower() == "true"
        prices[str(row.symbol)] = {
            "date": row.date.strftime("%Y-%m-%d"),
            "close": float(price) if usable and pd.notna(price) and math.isfinite(price) and price > 0 else None,
        }
    result = {"identity": IDENTITY, "price_basis": "actual_close", "source_sha256": source_sha256,
              "prices": prices}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return result


def read_snapshot(path: Path = DEFAULT_SNAPSHOT) -> dict:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("identity") != IDENTITY or payload.get("price_basis") != "actual_close":
        raise ValueError("unverified latest-price snapshot")
    return payload["prices"]


def quote_for(prices: dict, symbol: str, *, before: date | None = None) -> tuple[str, str]:
    """Morning messages must never read that day's later closing price."""
    quote = prices.get(str(symbol), {})
    stamp, value = quote.get("date", ""), quote.get("close")
    if not stamp or (before is not None and date.fromisoformat(stamp) >= before):
        return "未取得", ""
    if value is None or not math.isfinite(float(value)) or float(value) <= 0:
        return "未取得", f"{stamp} 終値未確認"
    return f"{float(value):,.2f}".rstrip("0").rstrip(".") + "円", f"{stamp} 終値"


def refresh_from_cache(corpus: Path, path: Path = DEFAULT_SNAPSHOT) -> dict:
    """One-off display refresh from an unchanged SHA/quality-verified cache."""
    from .ledger import read_ledger

    def digest():
        with corpus.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    quality = json.loads(corpus.with_suffix(".source-quality.json").read_text(encoding="utf-8"))
    source_sha = digest()
    if quality.get("identity") != "CLOUD_SOURCE_QUALITY_V1" or quality.get("daily_sha256") != source_sha:
        raise ValueError("latest-price cache requires a matching source-quality receipt")
    data = pd.read_csv(corpus, usecols=["symbol", "date", "actual_close", "source_usable"], dtype={"symbol": str})
    if len(data) != quality.get("sourceRows") or digest() != source_sha:
        raise ValueError("latest-price source changed or row count mismatched")
    return write_snapshot(data, read_ledger()["symbol"], source_sha, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()
    result = refresh_from_cache(args.daily_corpus, args.output)
    print(json.dumps({"identity": result["identity"], "symbols": len(result["prices"]),
                      "source_sha256": result["source_sha256"]}))
