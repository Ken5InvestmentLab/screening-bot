"""Causal JPX tradability gate for the isolated Cloud beta."""

from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from .network import retry_get


ROOT = Path(__file__).resolve().parents[1]
JPX_RESTRICTIONS_URL = "https://www.jpx.co.jp/listing/market-alerts/supervision/01.html"
JPX_DELISTINGS_URL = "https://www.jpx.co.jp/listing/stocks/delisted/index.html"
JPX_NEW_LISTINGS_URL = "https://www.jpx.co.jp/listing/stocks/new/index.html"
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
    response = retry_get(requests.get, JPX_RESTRICTIONS_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    supervision = _TableRows()
    supervision.feed(response.content.decode("utf-8"))
    if not any(len(row) >= 6 and row[:3] == ["指定年月日", "銘柄名", "コード"] and row[5] == "内容"
               for row in supervision.rows):
        raise ValueError("missing or malformed JPX supervision header")
    rows = parse_jpx_restricted_symbols(response.content, as_of)
    current = _get_jpx_page(JPX_DELISTINGS_URL)
    pages = _DelistingPage()
    pages.feed(current.decode("utf-8"))
    cutoff = _cutoff(as_of)
    required_years = range(cutoff.year - 5, cutoff.year + 1)
    if any(year not in pages.year_urls for year in required_years):
        raise ValueError("JPX delisting archives do not cover the required five-year history")
    delisted = []
    evidence = []
    for year in required_years:
        url = pages.year_urls[year]
        document = current if url == JPX_DELISTINGS_URL else _get_jpx_page(url)
        parsed = parse_jpx_delisted_symbols(document, cutoff, source_url=url)
        if any(int(row["delisting_date"][:4]) != year for row in parsed):
            raise ValueError(f"JPX delisting archive year mismatch: {year}")
        delisted.extend(parsed)
        evidence.append({"year": year, "source_url": url,
                         "source_sha256": hashlib.sha256(document).hexdigest(),
                         "delisted_symbol_count": len(parsed)})
    listing_document = _get_jpx_page(JPX_NEW_LISTINGS_URL)
    listing_page = _DelistingPage(new_listings=True)
    listing_page.feed(listing_document.decode("utf-8"))
    listing_years = sorted(year for year in listing_page.year_urls if year <= cutoff.year)
    if not listing_years or listing_years[-1] != cutoff.year:
        raise ValueError("JPX new-listing archives do not cover the as-of year")
    listings = []
    listing_evidence = []
    for year in listing_years:
        url = listing_page.year_urls[year]
        document = listing_document if url == JPX_NEW_LISTINGS_URL else _get_jpx_page(url)
        parsed = parse_jpx_new_listings(document, cutoff, source_url=url)
        if any(int(row["listing_date"][:4]) != year for row in parsed):
            raise ValueError(f"JPX new-listing archive year mismatch: {year}")
        listings.extend(parsed)
        listing_evidence.append({"year": year, "source_url": url,
                                 "source_sha256": hashlib.sha256(document).hexdigest(),
                                 "listed_symbol_count": len(parsed)})
    combined_rows = []
    pending = [row.copy() for row in rows]
    relisted = []
    for row in delisted:
        later = sorted((item for item in listings if item["code"] == row["code"]
                        and item["listing_date"] > row["delisting_date"]), key=lambda item: item["listing_date"])
        existing = {"code": row["code"], "company_name": row["company_name"],
                    "designation_date": row["delisting_date"],
                    "designation": "上場廃止済み", "source_url": row["delisting_source_url"]}
        candidates = [item for item in pending if item["code"] == row["code"]
                      and item["designation_date"] <= row["delisting_date"]]
        if candidates:
            designation = max(candidates, key=lambda item: item["designation_date"])
            existing.update(designation)
            pending.remove(designation)
        existing.update(delisting_date=row["delisting_date"],
                        delisting_source_url=row["delisting_source_url"],
                        relisting_coverage_start_year=listing_years[0])
        if later:
            existing.update(relisting_date=later[0]["listing_date"],
                            relisting_source_url=later[0]["listing_source_url"])
            relisted.append({**row, "relisting_date": later[0]["listing_date"],
                             "relisting_source_url": later[0]["listing_source_url"]})
        combined_rows.append(existing)
    rows = sorted(combined_rows + pending, key=lambda row: (row["designation_date"], row["code"]))
    payload = {
        "version": 2,
        "announced_delistings": parse_jpx_delisted_symbols(current, '2262-01-01'),
        "as_of": f"{pd.Timestamp(as_of):%Y-%m-%d}",
        "fetched_at": pd.Timestamp.now(tz="Asia/Tokyo").isoformat(),
        "source_url": JPX_RESTRICTIONS_URL,
        "source_sha256": hashlib.sha256(response.content).hexdigest(),
        "rule": "causal designation-date gate; exclude acquisition only on or after the official delisting date",
        "delisting_sources": evidence,
        "delisted_symbols": sorted(_delisted_lookup(rows, cutoff).values(), key=lambda row: (row["delisting_date"], row["code"])),
        "delisting_history": sorted(delisted, key=lambda row: (row["delisting_date"], row["code"])),
        "relisting_sources": listing_evidence,
        "relisting_coverage_start_year": listing_years[0],
        "relisted_symbols": relisted,
        "symbols": rows,
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def _cutoff(value: Any) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError("missing JPX as-of date")
    if result.tzinfo is not None:
        result = result.tz_convert("Asia/Tokyo").tz_localize(None)
    return result.normalize()


def _archive_url(value: str, *, new_listings: bool = False) -> str:
    url = urljoin(JPX_NEW_LISTINGS_URL if new_listings else JPX_DELISTINGS_URL, value)
    parsed = urlparse(url)
    pattern = (r"/listing/stocks/new/(?:index|00-archives-[0-9]{2})\.html" if new_listings
               else r"/listing/stocks/delisted/(?:index|archives-[0-9]{2})\.html")
    if (parsed.scheme != "https" or parsed.netloc != "www.jpx.co.jp"
            or parsed.query or parsed.fragment
            or not re.fullmatch(pattern, parsed.path)):
        raise ValueError("unsafe JPX delisting archive URL")
    return url


def _get_jpx_page(url: str) -> bytes:
    new_listings = "/listing/stocks/new/" in url
    _archive_url(url, new_listings=new_listings)
    response = retry_get(requests.get, url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    if getattr(response, "url", url) != url:
        _archive_url(response.url, new_listings=new_listings)
    return response.content


class _DelistingPage(_TableRows):
    def __init__(self, *, new_listings: bool = False) -> None:
        super().__init__()
        self.new_listings = new_listings
        self.tables: list[list[list[str]]] = []
        self.year_urls: dict[int, str] = {}
        self._table_start: int | None = None
        self._backnumber = False
        self._option_url: str | None = None
        self._option_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "table":
            if self._table_start is not None:
                raise ValueError("nested JPX delisting table")
            self._table_start = len(self.rows)
        if tag == "select":
            self._backnumber = "backnumber" in values.get("class", "").split()
        if tag == "option" and self._backnumber:
            self._option_url = values.get("value", "")
            self._option_text = []
        super().handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._option_url is not None:
            self._option_text.append(data)
        super().handle_data(data)

    def handle_endtag(self, tag: str) -> None:
        super().handle_endtag(tag)
        if tag == "table" and self._table_start is not None:
            self.tables.append(self.rows[self._table_start:])
            self._table_start = None
        if tag == "option" and self._option_url is not None:
            label = "".join(self._option_text).strip()
            if not re.fullmatch(r"[0-9]{4}年", label):
                raise ValueError("malformed JPX archive year")
            year = int(label[:4])
            url = _archive_url(self._option_url, new_listings=self.new_listings)
            if year in self.year_urls:
                raise ValueError("duplicate JPX archive year")
            self.year_urls[year] = url
            self._option_url = None
        if tag == "select":
            self._backnumber = False


def parse_jpx_delisted_symbols(
    document: bytes, as_of: Any, *, source_url: str = JPX_DELISTINGS_URL,
) -> list[dict[str, str]]:
    """Require the official table structure, including valid future rows."""
    parser = _DelistingPage()
    parser.feed(document.decode("utf-8"))
    header = ["上場廃止日", "銘柄名", "コード", "市場区分", "上場廃止理由"]
    tables = [table for table in parser.tables if table and table[0] == header]
    if len(tables) != 1 or len(tables[0]) < 2 or parser._table_start is not None:
        raise ValueError("missing or malformed JPX delisting table")
    cutoff = _cutoff(as_of)
    result = []
    seen: set[str] = set()
    for cells in tables[0][1:]:
        if len(cells) != 5 or not re.fullmatch(r"[0-9]{4}/[0-9]{2}/[0-9]{2}", cells[0]):
            raise ValueError("malformed JPX delisting row")
        code = cells[2].strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{4}", code) or not all(cells[index] for index in (1, 3, 4)):
            raise ValueError("invalid JPX delisting security")
        date = pd.to_datetime(cells[0], format="%Y/%m/%d", errors="raise").normalize()
        if code in seen:
            raise ValueError(f"duplicate JPX delisting security: {code}")
        seen.add(code)
        if date <= cutoff:
            result.append({"code": code, "company_name": cells[1],
                           "delisting_date": f"{date:%Y-%m-%d}",
                           "delisting_source_url": source_url})
    return sorted(result, key=lambda row: (row["delisting_date"], row["code"]))


def _delisted_lookup(restrictions: list[dict[str, str]], as_of: Any) -> dict[str, dict[str, str]]:
    cutoff = _cutoff(as_of)
    return {row["code"]: row for row in restrictions
            if row.get("delisting_date") and _cutoff(row["delisting_date"]) <= cutoff
            and (not row.get("relisting_date") or cutoff < _cutoff(row["relisting_date"]))}


def parse_jpx_new_listings(
    document: bytes, as_of: Any, *, source_url: str = JPX_NEW_LISTINGS_URL,
) -> list[dict[str, str]]:
    parser = _DelistingPage(new_listings=True)
    parser.feed(document.decode("utf-8"))
    tables = [table for table in parser.tables if table and len(table[0]) == 8
              and table[0][0] == "上場日（上場承認日）" and table[0][2] == "コード"]
    if (len(tables) != 1 or len(tables[0]) < 4 or parser._table_start is not None
            or len(tables[0][1]) != 6 or tables[0][1][0] != "市場区分"
            or len(tables[0]) % 2):
        raise ValueError("missing or malformed JPX new-listing table")
    cutoff = _cutoff(as_of)
    result = []
    seen = set()
    for offset in range(2, len(tables[0]), 2):
        cells, secondary = tables[0][offset:offset + 2]
        if (len(cells) != 8 or len(secondary) != 6 or not secondary[0]
                or not re.fullmatch(r"[0-9]{4}/[0-9]{2}/[0-9]{2}(?:\s*[（(][0-9]{4}/[0-9]{2}/[0-9]{2}[）)])?", cells[0])):
            raise ValueError("malformed JPX new-listing row")
        code = cells[2].strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{4}", code) or not cells[1]:
            raise ValueError("invalid JPX new-listing security")
        date = pd.to_datetime(cells[0][:10], format="%Y/%m/%d", errors="raise").normalize()
        identity = (code, date)
        if identity in seen:
            raise ValueError("duplicate JPX new-listing event")
        seen.add(identity)
        if date <= cutoff:
            result.append({"code": code, "company_name": cells[1], "listing_date": f"{date:%Y-%m-%d}",
                           "listing_source_url": source_url})
    return result


def exclude_delisted_universe(
    universe: pd.DataFrame, restrictions: list[dict[str, str]], as_of: Any,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    lookup = _delisted_lookup(restrictions, as_of)
    codes = universe["code"].astype(str).str.strip().str.upper()
    mask = codes.isin(lookup)
    for code in codes[mask]:
        coverage = lookup[code].get("relisting_coverage_start_year")
        if coverage is not None and int(lookup[code]["delisting_date"][:4]) < int(coverage):
            raise ValueError(f"JPX relisting coverage cannot verify current universe identity: {code}")
    excluded = universe[mask].copy()
    excluded["delisting_date"] = codes[mask].map(lambda code: lookup[code]["delisting_date"])
    excluded["delisting_source_url"] = codes[mask].map(lambda code: lookup[code]["delisting_source_url"])
    return universe[~mask].copy(), excluded


def preserve_delisted_history(
    previous: pd.DataFrame | None, current: pd.DataFrame,
    restrictions: list[dict[str, str]], as_of: Any, previous_source_sha256: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Retain verified historical units without treating old quotes as fresh data.

    The caller must first verify the source-quality sidecar against the complete
    prior file SHA. Validation here checks the action-aware rows, not that sidecar.
    """
    from .corporate_actions import normalize_daily

    lookup = _delisted_lookup(restrictions, as_of)
    if current["symbol"].astype(str).str.strip().str.upper().isin(lookup).any():
        raise ValueError("current acquisition contains an officially delisted security")
    receipt: dict[str, Any] = {"identity": "CLOUD_DELISTED_HISTORY_V1", "excluded_codes": sorted(lookup),
                               "retained_rows": 0, "retained_symbols": []}
    if previous is None or previous.empty:
        return current, receipt
    mask = previous["symbol"].astype(str).isin(lookup)
    if not mask.any():
        return current, receipt
    if not re.fullmatch(r"[0-9a-f]{64}", previous_source_sha256 or ""):
        raise ValueError("delisted history requires a verified complete-cache SHA-256")
    declared = previous.attrs.get("source_sha256")
    if declared is not None and declared != previous_source_sha256:
        raise ValueError("delisted history source SHA-256 mismatch")
    if "corporate_actions_version" not in previous:
        raise ValueError("delisted history requires an action-aware verified cache")
    retained = previous[mask].copy()
    retained["basis_asof"] = pd.to_datetime(retained["basis_asof"], errors="raise")
    current_start = pd.to_datetime(current["date"], errors="raise").min()
    if pd.notna(current_start):
        within_window = pd.to_datetime(retained["date"], errors="raise").ge(current_start)
        receipt["outside_current_window_rows"] = int((~within_window).sum())
        receipt["current_window_start"] = f"{current_start:%Y-%m-%d}"
        retained = retained[within_window].copy()
    if retained.empty:
        return current, receipt
    normalize_daily(retained)
    for code, group in retained.groupby("symbol", sort=True):
        dates = pd.to_datetime(group["date"], errors="raise")
        if dates.ge(_cutoff(lookup[code]["delisting_date"])).any():
            raise ValueError(f"cached price on or after official delisting: {code}")
        digest = hashlib.sha256(group.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()
        receipt["retained_symbols"].append({"code": str(code), "rows": len(group),
                                            "latest_session": f"{dates.max():%Y-%m-%d}",
                                            "delisting_date": lookup[code]["delisting_date"],
                                            "rows_sha256": digest})
    attrs = current.attrs.copy()
    combined = pd.concat([current, retained], ignore_index=True)
    combined = combined.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    combined.attrs = attrs
    receipt.update(previous_source_sha256=previous_source_sha256, retained_rows=len(retained))
    return combined, receipt


def restricted_mask(frame: pd.DataFrame, restrictions: list[dict[str, str]]) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    if frame.empty:
        return mask
    date_column = "signal_date" if "signal_date" in frame else "date"
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    symbols = frame["symbol"].astype(str)
    for restriction in restrictions:
        restricted = symbols.eq(restriction["code"]) & dates.ge(pd.Timestamp(restriction["designation_date"]))
        if restriction.get("relisting_date"):
            restricted &= dates.lt(pd.Timestamp(restriction["relisting_date"]))
        mask |= restricted
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
    def matched_restriction(record):
        signal = pd.Timestamp(record["signal_date"])
        matches = [row for row in restrictions if row["code"] == str(record["symbol"])
                   and pd.Timestamp(row["designation_date"]) <= signal
                   and (not row.get("relisting_date") or signal < pd.Timestamp(row["relisting_date"]))]
        return max(matches, key=lambda row: row["designation_date"])

    matched = excluded.apply(matched_restriction, axis=1)
    excluded["exclusion_reason"] = matched.map(
        lambda row: "JPX 上場廃止済み" if row.get("designation") == "上場廃止済み"
        else "JPX 上場廃止決定・整理銘柄指定"
    )
    excluded["restriction_designation_date"] = matched.map(
        lambda row: row["designation_date"]
    )
    excluded["restriction_source_url"] = matched.map(
        lambda row: row.get("source_url", JPX_RESTRICTIONS_URL)
    )
    excluded["excluded_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    if excluded_path.exists():
        prior = pd.read_csv(excluded_path, dtype={"symbol": str})
        excluded = pd.concat([prior, excluded], ignore_index=True)
    excluded = excluded.drop_duplicates("detection_id", keep="last")
    excluded_path.parent.mkdir(parents=True, exist_ok=True)
    excluded.to_csv(excluded_path, index=False, encoding="utf-8", lineterminator="\n")
    return active, excluded
