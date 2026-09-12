"""Generate the complete pre-cooldown First Reversal pool from preserved OHLCV."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .artifact_store import read_verified_parquet, sha256_file, write_parquet_artifact
from .first_reversal import (
    FIRST_REVERSAL_SPEC,
    FIRST_REVERSAL_SPEC_SHA256,
    build_first_reversal_candidate_pool,
)
from .session_calendar import SessionCalendar


BATCH_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = BATCH_DIR / ".cache" / "artifacts" / "tse_daily.csv"
DEFAULT_CALENDAR = BATCH_DIR / "reference" / "xtks_sessions.csv"
DEFAULT_CALENDAR_MANIFEST = BATCH_DIR / "reference" / "xtks_sessions.manifest.json"
DEFAULT_PRESERVATION_MANIFEST = BATCH_DIR / "PRESERVATION_MANIFEST.json"
DEFAULT_OUTPUT = BATCH_DIR / ".cache" / "first_reversal_candidate_pool.parquet"
DEFAULT_MARKET_TABLE = BATCH_DIR / ".cache" / "market_returns.parquet"


def generate(
    *,
    source_path: Path,
    calendar_path: Path,
    calendar_manifest_path: Path,
    preservation_manifest_path: Path,
    market_table_path: Path,
    output_path: Path,
    start: str,
    through: str,
) -> dict[str, object]:
    calendar_meta = json.loads(calendar_manifest_path.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(calendar_path, expected_sha256=str(calendar_meta["csv_sha256"]))
    preservation = json.loads(preservation_manifest_path.read_text(encoding="utf-8"))
    expected_source_sha = next(
        item["member_sha256"]
        for item in preservation["artifacts"]
        if item["member"] == source_path.name
    )
    actual_source_sha = sha256_file(source_path)
    if actual_source_sha != expected_source_sha:
        raise ValueError("OHLCV source hash differs from the preserved-artifact manifest")

    first = pd.Timestamp(start).normalize()
    last = pd.Timestamp(through).normalize()
    if first > last:
        raise ValueError("start must not be after through")
    bars = pd.read_csv(
        source_path,
        usecols=["date", "symbol", "open", "high", "low", "close", "volume"],
        dtype={
            "symbol": "string", "open": "float64", "high": "float64",
            "low": "float64", "close": "float64", "volume": "float64",
        },
        parse_dates=["date"],
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="raise").dt.normalize()
    bars = bars.loc[bars["date"].between(first, last)].copy()
    if bars.empty:
        raise ValueError("requested candidate-pool range contains no OHLCV rows")
    market_table, market_receipt = read_verified_parquet(market_table_path)
    if market_receipt.get("schema_version") != "tvfree-market-returns-v1":
        raise ValueError("market-return artifact schema is not the registered version")
    if market_receipt.get("source_sha256") != actual_source_sha:
        raise ValueError("market-return artifact was generated from a different OHLCV source")
    if market_receipt.get("calendar_sha256") != calendar.sha256:
        raise ValueError("market-return artifact uses a different official session calendar")

    pool = build_first_reversal_candidate_pool(
        bars,
        sessions=calendar.sessions,
        market_table=market_table,
        progress=lambda done, total: print(f"candidate generation: {done}/{total} symbols", flush=True),
    )
    receipt = write_parquet_artifact(
        pool,
        output_path,
        metadata={
            "schema_version": "tvfree-candidate-pool-v1",
            "family": FIRST_REVERSAL_SPEC["spec_id"],
            "spec_sha256": FIRST_REVERSAL_SPEC_SHA256,
            "spec": FIRST_REVERSAL_SPEC,
            "source_sha256": actual_source_sha,
            "source_member": source_path.name,
            "calendar_sha256": calendar.sha256,
            "market_table_sha256": market_receipt["sha256"],
            "start": first.date().isoformat(),
            "through": last.date().isoformat(),
            "rows": len(pool),
            "symbols": int(pool["symbol"].nunique()),
            "decision_time_only": True,
            "labels_included": False,
            "pool_cut_before_cooldown": False,
            "survivorship_limit": "source is current JPX membership Yahoo history; not full point-in-time listing universe",
        },
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--calendar", type=Path, default=DEFAULT_CALENDAR)
    parser.add_argument("--calendar-manifest", type=Path, default=DEFAULT_CALENDAR_MANIFEST)
    parser.add_argument("--preservation-manifest", type=Path, default=DEFAULT_PRESERVATION_MANIFEST)
    parser.add_argument("--market-table", type=Path, default=DEFAULT_MARKET_TABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start", default="2022-01-04")
    parser.add_argument("--through", default="2025-12-31")
    args = parser.parse_args()
    result = generate(
        source_path=args.source,
        calendar_path=args.calendar,
        calendar_manifest_path=args.calendar_manifest,
        preservation_manifest_path=args.preservation_manifest,
        market_table_path=args.market_table,
        output_path=args.output,
        start=args.start,
        through=args.through,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
