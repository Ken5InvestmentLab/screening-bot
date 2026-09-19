"""Attach the canonical next-open to fifth-XTKS-close endpoint to exact rows."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd


RAW_SHA256 = "f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2"
UNION_SHA256 = "91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62"
IDENTITY = "CLOUD_MONSTER_CANONICAL_NEXT_OPEN_FIFTH_CLOSE_V1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metric_row(group: pd.DataFrame, period: str) -> dict:
    x = group["gross_return"].to_numpy(float)
    ordered = np.sort(x)[::-1]
    return {
        "period": period,
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "win": float(np.mean(x > 0)),
        "plus10": float(np.mean(x >= 0.10)),
        "plus20": float(np.mean(x >= 0.20)),
        "minus10": float(np.mean(x <= -0.10)),
        "minus20": float(np.mean(x <= -0.20)),
        "max_up": float(np.max(x)),
        "max_down": float(np.min(x)),
        "top3_excluded_mean": float(np.mean(ordered[3:])) if len(x) > 3 else np.nan,
        "pl_100_shares_yen": float(
            ((group["exit_close"] - group["entry_open"]) * 100).sum()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-csv", type=Path, required=True)
    parser.add_argument("--union-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    raw_path = args.raw_csv.resolve()
    union_path = args.union_csv.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if sha256(raw_path) != RAW_SHA256:
        raise RuntimeError("raw OHLCV SHA-256 drift")
    if sha256(union_path) != UNION_SHA256:
        raise RuntimeError("recovered union SHA-256 drift")

    signals = pd.read_csv(union_path, dtype={"symbol": str})
    signals = signals[signals["lane"].eq("Monster")].copy()
    signals["signal_date"] = pd.to_datetime(signals["date"]).dt.normalize()
    signals["signal_timestamp"] = pd.to_datetime(signals["timestamp"])
    signals.rename(
        columns={"close": "signal_close", "ret5": "legacy_gross_return"},
        inplace=True,
    )
    signals["candidate_identity"] = (
        signals["symbol"].astype(str)
        + "|"
        + signals["signal_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    raw = pd.read_csv(raw_path, dtype={"symbol": str})
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], format="mixed")
    raw["date"] = raw["timestamp"].dt.normalize()
    for column in ["open", "high", "low", "close", "volume"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    alert_id = raw["alert_id"].astype(str)
    raw["_priority"] = np.where(
        alert_id.str.contains("REPAIR|MIDDAY", case=False, regex=True), 2, 1
    )
    raw["_volume_priority"] = raw["volume"].fillna(-1)
    raw = (
        raw.sort_values(["symbol", "timestamp", "_priority", "_volume_priority"])
        .drop_duplicates(["symbol", "timestamp"], keep="last")
        .drop(columns=["_priority", "_volume_priority"])
        .dropna(subset=["open", "close"])
    )
    daily = (
        raw.groupby(["symbol", "date"], as_index=False)
        .agg(open=("open", "first"), close=("close", "last"))
        .sort_values(["symbol", "date"])
    )

    calendar = xc.get_calendar("JPX")
    sessions = calendar.sessions_in_range("2026-02-01", "2026-10-01")
    sessions = pd.DatetimeIndex(sessions).tz_localize(None).normalize()
    position = {date: index for index, date in enumerate(sessions)}
    if not signals["signal_date"].isin(position).all():
        raise RuntimeError("one or more signal dates are not official JPX sessions")
    signals["entry_date"] = signals["signal_date"].map(
        lambda date: sessions[position[date] + 1]
    )
    signals["exit_date"] = signals["signal_date"].map(
        lambda date: sessions[position[date] + 5]
    )

    entries = daily.rename(columns={"date": "entry_date", "open": "entry_open"})[
        ["symbol", "entry_date", "entry_open"]
    ]
    exits = daily.rename(columns={"date": "exit_date", "close": "exit_close"})[
        ["symbol", "exit_date", "exit_close"]
    ]
    rows = signals.merge(entries, on=["symbol", "entry_date"], how="left", validate="many_to_one")
    rows = rows.merge(exits, on=["symbol", "exit_date"], how="left", validate="many_to_one")
    if rows[["entry_open", "exit_close"]].isna().any().any():
        missing = rows[rows[["entry_open", "exit_close"]].isna().any(axis=1)]
        raise RuntimeError(f"missing canonical endpoint prices for {len(missing)} rows")
    rows["gross_return"] = rows["exit_close"] / rows["entry_open"] - 1
    rows["legacy_exit_consistent"] = np.isclose(
        rows["exit_close"] / rows["signal_close"] - 1,
        rows["legacy_gross_return"],
        rtol=0,
        atol=1e-15,
    )
    if not rows["legacy_exit_consistent"].all():
        raise RuntimeError("raw daily exit price does not reproduce one or more legacy returns")

    columns = [
        "signal_date",
        "signal_timestamp",
        "symbol",
        "candidate_identity",
        "entry_date",
        "entry_open",
        "exit_date",
        "exit_close",
        "gross_return",
        "signal_close",
        "legacy_gross_return",
    ]
    rows = rows[columns].sort_values(["signal_date", "symbol", "signal_timestamp"])
    rows_path = output_dir / "canonical_trade_rows_next_open_fifth_close.csv"
    rows_for_output = rows.copy()
    for column in ["signal_date", "entry_date", "exit_date"]:
        rows_for_output[column] = rows_for_output[column].dt.strftime("%Y-%m-%d")
    rows_for_output["signal_timestamp"] = rows_for_output["signal_timestamp"].dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    rows_for_output.to_csv(rows_path, index=False)

    metric_rows = [
        metric_row(group, str(year))
        for year, group in rows.groupby(rows["signal_date"].dt.year, sort=True)
    ]
    metric_rows.append(metric_row(rows, "TOTAL"))
    metrics = pd.DataFrame(metric_rows)
    metrics_path = output_dir / "canonical_metrics_by_year_and_total.csv"
    metrics.to_csv(metrics_path, index=False)

    receipt = {
        "identity": IDENTITY,
        "status": "EXACT_ENDPOINT_BRIDGE",
        "selection_identity": "CLOUD_MONSTER_LEGACY_EXACT_V1",
        "selection_changed": False,
        "endpoint": "signal T -> next official XTKS session open -> fifth official XTKS session close",
        "cost": 0.0,
        "win_definition": "gross_return > 0",
        "inputs": {
            "raw_csv": {"artifact_id": "10266329903", "sha256": sha256(raw_path)},
            "union_csv": {"sha256": sha256(union_path)},
        },
        "outputs": {
            rows_path.name: {"rows": int(len(rows)), "sha256": sha256(rows_path)},
            metrics_path.name: {"rows": int(len(metrics)), "sha256": sha256(metrics_path)},
        },
        "legacy_exit_consistency": {
            "rows_checked": int(len(rows)),
            "all_equal_with_atol_1e-15": True,
        },
        "metrics": metric_rows,
    }
    receipt_path = output_dir / "canonical_bridge_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
