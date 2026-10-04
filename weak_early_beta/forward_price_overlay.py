"""Replay a reviewed provider snapshot into missing forward signal-price views.

Only presentation copies are enriched. Canonical rows, frozen trade economics,
and D6 release receipts are untouched. Future daily runs capture these prices
normally through model.attach_forward_rows/refresh_forward_endpoints.
"""
from pathlib import Path
import hashlib
import json

import pandas as pd

from .corporate_actions import action_table, normalize_daily
from .endpoint_receipts import SIGNAL_ACTUAL_COLUMNS, build_endpoint_receipts, signal_actual_close_verified


CSV_SHA = "7baa3a8e025bd1b196de894cbc5c136c85921020fb791f207423e6efe5117b89"
MANIFEST_SHA = "01093003d13e71c005bc6692c49fccb56c39d76015e9373c4f252da03870f647"


def apply_reviewed_forward_close(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    target = (result["source_scope"].eq("FORWARD_CAUSAL")
              & result["symbol"].astype(str).eq("4052")
              & pd.to_datetime(result["signal_date"]).eq(pd.Timestamp("2026-09-30")))
    if not target.any():
        return result
    root = Path(__file__).parent / "state"
    source = root / "reviewed_forward_4052_20260930.csv"
    manifest_path = source.with_suffix(".json")
    if hashlib.sha256(source.read_bytes()).hexdigest() != CSV_SHA or hashlib.sha256(manifest_path.read_bytes()).hexdigest() != MANIFEST_SHA:
        raise ValueError("reviewed forward price snapshot changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = pd.read_csv(source).rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "Stock Splits": "split_ratio", "Repaired?": "provider_repaired"})
    raw["date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None).dt.normalize()
    raw["symbol"] = "4052"
    normalized = normalize_daily(raw[["symbol", "date", "open", "high", "low", "close", "volume", "split_ratio", "provider_repaired"]], basis_asof=raw["date"].max())
    if len(normalized) != 4 or manifest["source_sha256"] != CSV_SHA:
        raise ValueError("invalid reviewed forward snapshot")
    prices = normalized.set_index(["symbol", "date"])
    actions = action_table(normalized)
    for column in SIGNAL_ACTUAL_COLUMNS:
        if column != "signal_actual_close":
            result[column] = result.get(column, pd.Series("", index=result.index)).astype(object)
    for index, row in result.loc[target].iterrows():
        # Never overwrite even a malformed claimed verified price silently.
        if row.get("signal_actual_close_status") == "verified":
            if not signal_actual_close_verified(row):
                raise ValueError("invalid existing forward signal close")
            continue
        receipt = build_endpoint_receipts(row, prices, actions, digest=CSV_SHA, observed_at=manifest["observed_at"])
        if not signal_actual_close_verified({**dict(row), **receipt}):
            raise ValueError("reviewed forward signal close failed validation")
        for column in SIGNAL_ACTUAL_COLUMNS:
            result.at[index, column] = receipt[column]
    return result
