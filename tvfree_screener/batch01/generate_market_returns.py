"""Build and cache PIT market-median returns from all preserved OHLCV names."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .artifact_store import sha256_file, write_parquet_artifact
from .feature_panel import build_market_return_table
from .session_calendar import SessionCalendar


BATCH_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = BATCH_DIR / ".cache" / "artifacts" / "tse_daily.csv"
DEFAULT_CALENDAR = BATCH_DIR / "reference" / "xtks_sessions.csv"
DEFAULT_CALENDAR_MANIFEST = BATCH_DIR / "reference" / "xtks_sessions.manifest.json"
DEFAULT_PRESERVATION_MANIFEST = BATCH_DIR / "PRESERVATION_MANIFEST.json"
DEFAULT_OUTPUT = BATCH_DIR / ".cache" / "market_returns.parquet"


def generate(
    *,
    source_path: Path,
    calendar_path: Path,
    calendar_manifest_path: Path,
    preservation_manifest_path: Path,
    output_path: Path,
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

    bars = pd.read_csv(
        source_path,
        usecols=["date", "symbol", "close"],
        dtype={"symbol": "string", "close": "float64"},
        parse_dates=["date"],
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="raise").dt.normalize()
    market = build_market_return_table(
        bars,
        sessions=calendar.sessions,
        progress=lambda done, total: print(f"market return matrix complete: {done}/{total} symbols", flush=True),
    )
    if len(market) != len(calendar.sessions) or market["date"].duplicated().any():
        raise RuntimeError("market return table does not cover each official session exactly once")
    latest_data_date = bars["date"].max()
    observed = market.loc[market["date"].le(latest_data_date)]
    for column, warmup_sessions in (("market_median_ret1", 1), ("market_median_ret5", 5)):
        if observed.loc[observed["date"].ge(calendar.sessions[warmup_sessions]), column].isna().any():
            raise RuntimeError(f"observed market session has no cross-sectional values for {column}")

    return write_parquet_artifact(
        market,
        output_path,
        metadata={
            "schema_version": "tvfree-market-returns-v1",
            "source_sha256": actual_source_sha,
            "source_member": source_path.name,
            "calendar_sha256": calendar.sha256,
            "latest_data_date": latest_data_date.date().isoformat(),
            "rows": len(market),
            "symbols": int(bars["symbol"].nunique()),
            "market_definition": "cross-sectional median of exact official-session close-to-close returns over 1 and 5 sessions",
            "lagged_features": "previous official session, never same-day for preregistered lag1 families",
            "decision_time_only": True,
            "labels_included": False,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--calendar", type=Path, default=DEFAULT_CALENDAR)
    parser.add_argument("--calendar-manifest", type=Path, default=DEFAULT_CALENDAR_MANIFEST)
    parser.add_argument("--preservation-manifest", type=Path, default=DEFAULT_PRESERVATION_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = generate(
        source_path=args.source,
        calendar_path=args.calendar,
        calendar_manifest_path=args.calendar_manifest,
        preservation_manifest_path=args.preservation_manifest,
        output_path=args.output,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
