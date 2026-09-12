"""Build the canonical signal-time panel from the preserved Yahoo OHLCV artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .artifact_store import sha256_file, write_parquet_artifact
from .feature_panel import FEATURE_COLUMNS, build_feature_panel
from .session_calendar import SessionCalendar


BATCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = BATCH_DIR.parents[1]
DEFAULT_SOURCE = BATCH_DIR / ".cache" / "artifacts" / "tse_daily.csv"
DEFAULT_CALENDAR = BATCH_DIR / "reference" / "xtks_sessions.csv"
DEFAULT_CALENDAR_MANIFEST = BATCH_DIR / "reference" / "xtks_sessions.manifest.json"
DEFAULT_PRESERVATION_MANIFEST = BATCH_DIR / "PRESERVATION_MANIFEST.json"
DEFAULT_OUTPUT = BATCH_DIR / ".cache" / "feature_panel_2022_2025.parquet"


def generate(
    *,
    source_path: Path,
    calendar_path: Path,
    calendar_manifest_path: Path,
    preservation_manifest_path: Path,
    output_path: Path,
    start: str,
    through: str,
) -> dict[str, object]:
    calendar_meta = json.loads(calendar_manifest_path.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(
        calendar_path,
        expected_sha256=str(calendar_meta["csv_sha256"]),
    )
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
    frame = pd.read_csv(
        source_path,
        usecols=["date", "symbol", "open", "high", "low", "close", "volume"],
        dtype={
            "symbol": "string", "open": "float64", "high": "float64",
            "low": "float64", "close": "float64", "volume": "float64",
        },
        parse_dates=["date"],
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame = frame.loc[frame["date"].between(first, last)].copy()
    if frame.empty:
        raise ValueError("requested feature-panel date range contains no OHLCV rows")
    panel = build_feature_panel(
        frame,
        sessions=calendar.sessions,
        progress=lambda done, total: print(
            f"feature panel: {done}/{total} symbols", flush=True,
        ),
    )
    if len(panel) != len(frame):
        raise RuntimeError("feature generation changed source date/symbol row coverage")
    if panel.duplicated(["date", "symbol"]).any():
        raise RuntimeError("feature panel has duplicate date/symbol rows")
    if not set(FEATURE_COLUMNS).issubset(panel.columns):
        raise RuntimeError("feature panel is missing a registered feature column")
    if any(any(token in str(column).lower() for token in ("future", "target", "label", "realized")) for column in panel.columns):
        raise RuntimeError("feature panel unexpectedly contains an outcome-like column")

    receipt = write_parquet_artifact(
        panel,
        output_path,
        metadata={
            "schema_version": "tvfree-feature-panel-v1",
            "source_sha256": actual_source_sha,
            "source_member": source_path.name,
            "calendar_sha256": calendar.sha256,
            "feature_columns": list(FEATURE_COLUMNS),
            "feature_timestamp": "official session close; same-day market fields are separate from lag1 fields",
            "start": first.date().isoformat(),
            "through": last.date().isoformat(),
            "rows": len(panel),
            "symbols": int(panel["symbol"].nunique()),
            "decision_time_only": True,
            "labels_included": False,
        },
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--calendar", type=Path, default=DEFAULT_CALENDAR)
    parser.add_argument("--calendar-manifest", type=Path, default=DEFAULT_CALENDAR_MANIFEST)
    parser.add_argument("--preservation-manifest", type=Path, default=DEFAULT_PRESERVATION_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start", default="2022-01-04")
    parser.add_argument("--through", default="2025-12-31")
    args = parser.parse_args()
    receipt = generate(
        source_path=args.source,
        calendar_path=args.calendar,
        calendar_manifest_path=args.calendar_manifest,
        preservation_manifest_path=args.preservation_manifest,
        output_path=args.output,
        start=args.start,
        through=args.through,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
