"""Append-safe beta detection ledger and exact historical bootstrap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .config import SELECTOR_ORDER, selector_info


ROOT = Path(__file__).resolve().parents[1]
PACK_OUTPUT = ROOT / "research" / "repro_packs" / "weak_early_exact_v1" / "output"
DEFAULT_LEDGER = ROOT / "weak_early_beta" / "state" / "detections.csv"
DEFAULT_QUEUE = ROOT / "weak_early_beta" / "state" / "fundamental_queue.json"

LEDGER_COLUMNS = [
    "detection_id", "signal_date", "symbol", "company_name", "selector_id",
    "selector_name", "model_period", "status", "entry_date", "entry_open",
    "fifth_xtks_exit_date", "fifth_xtks_exit_close", "gross_return",
    "one_hundred_shares_pl_yen", "med_ret5", "med_ret1", "ret10",
    "volr20", "body_pct", "rank_volr20", "rank_body_pct", "mean_rank",
    "tail_cdf", "tail_p", "source_scope", "source_sha256",
    "signal_discord_url", "notified_at", "fundamental_status",
    "fundamental_discord_url", "fundamental_html", "created_at", "updated_at",
]


def _empty_ledger() -> pd.DataFrame:
    return pd.DataFrame(columns=LEDGER_COLUMNS)


def read_ledger(path: Path = DEFAULT_LEDGER) -> pd.DataFrame:
    if not path.exists():
        return _empty_ledger()
    frame = pd.read_csv(path, dtype={"symbol": str})
    for column in ("signal_date", "entry_date", "fifth_xtks_exit_date"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame.reindex(columns=LEDGER_COLUMNS)


def write_ledger(frame: pd.DataFrame, path: Path = DEFAULT_LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = frame.reindex(columns=LEDGER_COLUMNS).copy()
    ordered = ordered.sort_values(
        ["signal_date", "selector_id", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
    ordered.to_csv(
        path, index=False, encoding="utf-8", lineterminator="\n",
        date_format="%Y-%m-%d", float_format="%.12g",
    )


def _canonical_paths(selector_id: str) -> list[Path]:
    return [
        PACK_OUTPUT / f"canonical_trade_rows_{selector_id}.csv",
        PACK_OUTPUT / "full_period_2026" / f"canonical_trade_rows_{selector_id}_2026.csv",
    ]


def bootstrap_historical() -> pd.DataFrame:
    """Import the frozen exact 2023-2026 canonical rows without recomputation."""
    parts: list[pd.DataFrame] = []
    now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    for selector_id in SELECTOR_ORDER:
        info = selector_info(selector_id)
        for path in _canonical_paths(selector_id):
            if not path.exists():
                raise FileNotFoundError(f"missing canonical input: {path}")
            frame = pd.read_csv(path, dtype={"symbol": str})
            frame = frame.rename(columns={"candidate_id": "legacy_candidate_id"})
            frame["signal_date"] = pd.to_datetime(frame["signal_date"])
            frame["selector_id"] = selector_id
            frame["selector_name"] = info.display_name
            frame["company_name"] = ""
            frame["detection_id"] = (
                frame["signal_date"].dt.strftime("%Y-%m-%d")
                + "|" + frame["symbol"].astype(str) + "|" + selector_id
            )
            frame["status"] = "mature"
            frame["source_scope"] = "EXACT_CANONICAL_2023_2026"
            frame["source_sha256"] = ""
            frame["signal_discord_url"] = ""
            frame["notified_at"] = ""
            frame["fundamental_status"] = "not_requested_historical"
            frame["fundamental_discord_url"] = ""
            frame["fundamental_html"] = ""
            frame["created_at"] = now
            frame["updated_at"] = now
            parts.append(frame)
    result = pd.concat(parts, ignore_index=True).reindex(columns=LEDGER_COLUMNS)
    if result["detection_id"].duplicated().any():
        dupes = result.loc[result["detection_id"].duplicated(), "detection_id"].tolist()
        raise RuntimeError(f"duplicate historical detection identities: {dupes[:5]}")
    return result


def merge_detections(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Upsert calculated fields while preserving external notification receipts."""
    if incoming.empty:
        return existing.copy()
    if incoming["detection_id"].duplicated().any():
        raise RuntimeError("incoming detections contain duplicate detection_id")
    protected = [
        "signal_discord_url", "notified_at", "fundamental_status",
        "fundamental_discord_url", "fundamental_html", "created_at",
    ]
    old = existing.set_index("detection_id", drop=False)
    new = incoming.set_index("detection_id", drop=False)
    for detection_id in new.index.intersection(old.index):
        for column in protected:
            value = old.at[detection_id, column]
            if pd.notna(value) and str(value).strip():
                new.at[detection_id, column] = value
    untouched = old.loc[~old.index.isin(new.index)]
    result = pd.concat([untouched, new], ignore_index=True)
    return result.reindex(columns=LEDGER_COLUMNS)


def build_fundamental_queue(frame: pd.DataFrame) -> list[dict]:
    """One future-analysis claim per signal-date/symbol, even across five lanes."""
    future = frame[
        frame["source_scope"].eq("FORWARD_CAUSAL")
        & frame["fundamental_status"].isin(["queued", "retry"])
    ].copy()
    claims = []
    for (signal_date, symbol), group in future.groupby(["signal_date", "symbol"], sort=True):
        claims.append({
            "claim_id": f"{pd.Timestamp(signal_date):%Y-%m-%d}|{symbol}",
            "signal_date": f"{pd.Timestamp(signal_date):%Y-%m-%d}",
            "symbol": str(symbol),
            "company_name": next((str(x) for x in group["company_name"] if str(x).strip()), ""),
            "selectors": sorted(group["selector_id"].tolist()),
            "selector_names": sorted(group["selector_name"].tolist()),
            "status": "queued",
        })
    return claims


def write_fundamental_queue(frame: pd.DataFrame, path: Path = DEFAULT_QUEUE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_fundamental_queue(frame), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_fundamental_receipts(frame: pd.DataFrame, receipts: Iterable[dict]) -> pd.DataFrame:
    result = frame.copy()
    for receipt in receipts:
        signal_date = pd.Timestamp(receipt["signal_date"]).strftime("%Y-%m-%d")
        symbol = str(receipt["symbol"])
        mask = (
            pd.to_datetime(result["signal_date"]).dt.strftime("%Y-%m-%d").eq(signal_date)
            & result["symbol"].astype(str).eq(symbol)
        )
        if not mask.any():
            raise ValueError(f"fundamental receipt has no matching detection: {signal_date}|{symbol}")
        result.loc[mask, "fundamental_status"] = receipt.get("status", "complete")
        result.loc[mask, "fundamental_discord_url"] = receipt.get("discord_url", "")
        result.loc[mask, "fundamental_html"] = receipt.get("html", "")
        result.loc[mask, "updated_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    return result
