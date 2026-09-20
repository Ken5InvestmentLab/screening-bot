"""Causal JPX tradability gate for the isolated Cloud beta."""

from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
JPX_RESTRICTIONS_URL = "https://www.jpx.co.jp/listing/market-alerts/supervision/01.html"
DEFAULT_RESTRICTION_SNAPSHOT = ROOT / "weak_early_beta" / "state" / "jpx_restricted_symbols_latest.json"
DEFAULT_EXCLUDED_LEDGER = ROOT / "weak_early_beta" / "state" / "excluded_detections.csv"


class _TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._row is not None and self._cell is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def parse_jpx_restricted_symbols(document: bytes, as_of: Any) -> list[dict[str, str]]:
    """Extract only securities whose delisting has been decided by the as-of date."""
    parser = _TableRows()
    parser.feed(document.decode("utf-8"))
    cutoff = pd.Timestamp(as_of).normalize()
    rows: list[dict[str, str]] = []
    for cells in parser.rows:
        if len(cells) < 6:
            continue
        code = cells[2].strip()
        content = cells[5].strip()
        designated = pd.to_datetime(cells[0], errors="coerce")
        if not re.fullmatch(r"[0-9A-Z]{4}", code) or pd.isna(designated):
            continue
        if designated.normalize() > cutoff:
            continue
        if "上場廃止の決定" not in content or "整理銘柄指定" not in content:
            continue
        rows.append({
            "code": code,
            "company_name": cells[1].strip(),
            "designation_date": f"{designated:%Y-%m-%d}",
            "designation": content,
            "source_url": JPX_RESTRICTIONS_URL,
        })
    return sorted(rows, key=lambda row: (row["designation_date"], row["code"]))


def fetch_jpx_restricted_symbols(
    as_of: Any,
    snapshot_path: Path = DEFAULT_RESTRICTION_SNAPSHOT,
) -> list[dict[str, str]]:
    response = requests.get(JPX_RESTRICTIONS_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    rows = parse_jpx_restricted_symbols(response.content, as_of)
    payload = {
        "version": 1,
        "as_of": f"{pd.Timestamp(as_of):%Y-%m-%d}",
        "fetched_at": pd.Timestamp.now(tz="Asia/Tokyo").isoformat(),
        "source_url": JPX_RESTRICTIONS_URL,
        "source_sha256": hashlib.sha256(response.content).hexdigest(),
        "rule": "exclude only JPX rows marked 上場廃止の決定・整理銘柄指定 on or before signal date",
        "symbols": rows,
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def restricted_mask(frame: pd.DataFrame, restrictions: list[dict[str, str]]) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    if frame.empty:
        return mask
    date_column = "signal_date" if "signal_date" in frame else "date"
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    symbols = frame["symbol"].astype(str)
    for restriction in restrictions:
        mask |= symbols.eq(restriction["code"]) & dates.ge(pd.Timestamp(restriction["designation_date"]))
    return mask


def quarantine_restricted_detections(
    ledger: pd.DataFrame,
    restrictions: list[dict[str, str]],
    excluded_path: Path = DEFAULT_EXCLUDED_LEDGER,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = ledger["source_scope"].eq("FORWARD_CAUSAL") & restricted_mask(ledger, restrictions)
    excluded = ledger[mask].copy()
    active = ledger[~mask].copy()
    if excluded.empty:
        return active, excluded
    lookup = {row["code"]: row for row in restrictions}
    excluded["exclusion_reason"] = "JPX 上場廃止決定・整理銘柄指定"
    excluded["restriction_designation_date"] = excluded["symbol"].map(
        lambda symbol: lookup[str(symbol)]["designation_date"]
    )
    excluded["restriction_source_url"] = JPX_RESTRICTIONS_URL
    excluded["excluded_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    if excluded_path.exists():
        prior = pd.read_csv(excluded_path, dtype={"symbol": str})
        excluded = pd.concat([prior, excluded], ignore_index=True)
    excluded = excluded.drop_duplicates("detection_id", keep="last")
    excluded_path.parent.mkdir(parents=True, exist_ok=True)
    excluded.to_csv(excluded_path, index=False, encoding="utf-8", lineterminator="\n")
    return active, excluded
