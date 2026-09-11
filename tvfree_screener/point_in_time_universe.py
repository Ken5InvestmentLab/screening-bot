#!/usr/bin/env python3
"""Reconstruct point-in-time TSE stock membership from official JPX events.

TEST ONLY. This module does not alter production or model semantics.

Method:
- anchor on the current JPX domestic-common-stock snapshot,
- collect official JPX new-listing and delisting archive rows from 2022 onward,
- walk those events backwards to answer membership as of a historical date.

This removes the specific mistake of applying today's survivor set to every
historical date. It is intentionally fail-closed: ambiguous same-day code events
or rows whose market cannot be classified are reported rather than guessed.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

OUT = Path("tvfree_screener/out")
NEW_URL = "https://www.jpx.co.jp/listing/stocks/new/"
DELIST_URL = "https://www.jpx.co.jp/listing/stocks/delisted/"
DATE_RE = re.compile(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})")
CODE_RE = re.compile(r"^[0-9A-Z]{4}$")
DOMESTIC_MARKET_RE = re.compile(
    r"プライム|スタンダード|グロース|市場第一部|市場第二部|第一部|第二部|マザーズ|JQ|JASDAQ",
    re.I,
)
EXCLUDED_MARKET_RE = re.compile(r"外国|TOKYO\s*PRO|PRO\s*Market", re.I)


@dataclass(frozen=True)
class Event:
    event_date: pd.Timestamp
    code: str
    event: str  # listing | delisting
    market: str
    source_url: str


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }


def _get(url: str) -> str:
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.text


def discover_archive_pages(base_url: str) -> list[str]:
    """Return current page plus all discoverable year archive pages."""
    html = _get(base_url)
    hrefs = re.findall(r'href=["\']([^"\']*archives-\d+\.html)["\']', html, flags=re.I)
    urls = {base_url}
    urls.update(urljoin(base_url, h) for h in hrefs)
    return sorted(urls)


def _row_cells(row: pd.Series) -> list[str]:
    vals: list[str] = []
    for value in row.tolist():
        text = "" if pd.isna(value) else str(value).strip()
        if text and text.lower() != "nan":
            vals.append(re.sub(r"\s+", " ", text))
    return vals


def _first_date(cells: list[str]) -> pd.Timestamp | None:
    for cell in cells:
        m = DATE_RE.search(cell)
        if m:
            try:
                return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
            except ValueError:
                pass
    return None


def _first_code(cells: list[str]) -> str | None:
    for cell in cells:
        token = cell.replace(" ", "").upper()
        if CODE_RE.fullmatch(token):
            return token
    return None


def _market_text(cells: list[str]) -> str:
    hits = [c for c in cells if DOMESTIC_MARKET_RE.search(c) or EXCLUDED_MARKET_RE.search(c)]
    return " | ".join(hits)


def parse_event_page(url: str, event: str, start_year: int, end_date: pd.Timestamp) -> tuple[list[Event], list[dict]]:
    """Parse code/date/market from JPX HTML tables without relying on fragile headers."""
    html = _get(url)
    events: list[Event] = []
    unknown: list[dict] = []
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return events, unknown

    seen: set[tuple[pd.Timestamp, str, str]] = set()
    for table in tables:
        for _, row in table.iterrows():
            cells = _row_cells(row)
            date = _first_date(cells)
            code = _first_code(cells)
            if date is None or code is None or date.year < start_year or date > end_date:
                continue
            market = _market_text(cells)
            key = (date, code, event)
            if key in seen:
                continue
            seen.add(key)
            if EXCLUDED_MARKET_RE.search(market):
                continue
            if not DOMESTIC_MARKET_RE.search(market):
                unknown.append({
                    "event_date": date.strftime("%Y-%m-%d"),
                    "code": code,
                    "event": event,
                    "market": market,
                    "source_url": url,
                })
                continue
            events.append(Event(date, code, event, market, url))
    return events, unknown


def collect_events(start_year: int, anchor_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_events: list[Event] = []
    unknown: list[dict] = []
    for base, event in [(NEW_URL, "listing"), (DELIST_URL, "delisting")]:
        for url in discover_archive_pages(base):
            ev, un = parse_event_page(url, event, start_year, anchor_date)
            all_events.extend(ev)
            unknown.extend(un)

    # De-duplicate archive/current overlap by semantic event key.
    uniq: dict[tuple[pd.Timestamp, str, str], Event] = {}
    for e in all_events:
        uniq[(e.event_date, e.code, e.event)] = e
    events = pd.DataFrame([
        {
            "event_date": e.event_date,
            "code": e.code,
            "event": e.event,
            "market": e.market,
            "source_url": e.source_url,
        }
        for e in uniq.values()
    ])
    if events.empty:
        raise RuntimeError("no JPX listing/delisting events parsed")
    events = events.sort_values(["event_date", "code", "event"], kind="mergesort").reset_index(drop=True)
    unknown_df = pd.DataFrame(unknown).drop_duplicates() if unknown else pd.DataFrame(
        columns=["event_date", "code", "event", "market", "source_url"]
    )
    return events, unknown_df


def temporal_code_reuse_codes(events: pd.DataFrame) -> list[str]:
    """Return codes that delist and later list again within the event history.

    Membership state can still be reversed by date, but a reused four-character
    code cannot safely be assumed to represent one Yahoo ticker identity across
    both episodes.
    """
    reused: list[str] = []
    for code, g in events.groupby("code", sort=True):
        dels = pd.to_datetime(g.loc[g["event"] == "delisting", "event_date"]).tolist()
        lists = pd.to_datetime(g.loc[g["event"] == "listing", "event_date"]).tolist()
        if any(listed > delisted for delisted in dels for listed in lists):
            reused.append(str(code))
    return sorted(set(reused))


def validate_events(events: pd.DataFrame, unknown: pd.DataFrame) -> dict:
    collisions = (
        events.groupby(["event_date", "code"])["event"].nunique().reset_index(name="event_types")
    )
    collisions = collisions[collisions["event_types"] > 1]
    reused = temporal_code_reuse_codes(events)
    return {
        "event_rows": int(len(events)),
        "unknown_market_rows": int(len(unknown)),
        "same_day_code_collisions": int(len(collisions)),
        "temporal_code_reuse_count": int(len(reused)),
        "temporal_code_reuse_codes": reused,
        "valid_for_membership_reconstruction": bool(len(unknown) == 0 and len(collisions) == 0),
        "yahoo_price_identity_safe_without_quarantine": bool(len(reused) == 0),
    }


def members_as_of(current_codes: set[str], events: pd.DataFrame, as_of: pd.Timestamp, anchor_date: pd.Timestamp) -> set[str]:
    """Reverse official listing state changes from anchor_date back to as_of."""
    if as_of > anchor_date:
        raise ValueError("as_of must not be after anchor_date")
    members = set(current_codes)
    z = events[(events["event_date"] > as_of) & (events["event_date"] <= anchor_date)]
    # Reverse chronological. A later listing is undone by removal; a later
    # delisting is undone by restoring the code.
    for _, row in z.sort_values(["event_date", "code"], ascending=[False, True], kind="mergesort").iterrows():
        code = str(row["code"])
        if row["event"] == "listing":
            members.discard(code)
        elif row["event"] == "delisting":
            members.add(code)
        else:
            raise RuntimeError(f"unknown event type: {row['event']}")
    return members


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current-snapshot", default="tvfree_screener/out/jpx_universe_snapshot.csv")
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--anchor-date", default=None, help="JPX snapshot date; defaults to today in Asia/Tokyo")
    args = ap.parse_args()

    snapshot = pd.read_csv(args.current_snapshot, dtype={"code": str})
    if "code" not in snapshot.columns:
        raise RuntimeError("current universe snapshot lacks code column")
    current_codes = set(snapshot["code"].astype(str).str.strip())
    start = pd.Timestamp(args.start).normalize()
    anchor = (
        pd.Timestamp(args.anchor_date).normalize()
        if args.anchor_date
        else pd.Timestamp.now(tz="Asia/Tokyo").tz_localize(None).normalize()
    )

    events, unknown = collect_events(start.year, anchor)
    validation = validate_events(events, unknown)
    OUT.mkdir(parents=True, exist_ok=True)
    events.to_csv(OUT / "jpx_membership_events.csv", index=False)
    unknown.to_csv(OUT / "jpx_membership_unknown_rows.csv", index=False)

    # Produce compact checkpoint counts rather than millions of date/code rows.
    checkpoints = []
    for date in pd.date_range(start, anchor, freq="MS"):
        members = members_as_of(current_codes, events, date, anchor)
        checkpoints.append({"date": date.strftime("%Y-%m-%d"), "members": len(members)})
    pd.DataFrame(checkpoints).to_csv(OUT / "jpx_membership_monthly_counts.csv", index=False)

    report = {
        "status": "research_only_no_production_writes",
        "method": "reverse current JPX domestic-common membership using official JPX listing/delisting events",
        "start": start.strftime("%Y-%m-%d"),
        "anchor_date": anchor.strftime("%Y-%m-%d"),
        "current_members": len(current_codes),
        "validation": validation,
        "outputs": [
            "jpx_membership_events.csv",
            "jpx_membership_unknown_rows.csv",
            "jpx_membership_monthly_counts.csv",
        ],
        "acceptance_rule": (
            "membership state may be used only when unknown_market_rows=0 and "
            "same_day_code_collisions=0; temporal code reuse must be quarantined "
            "before mapping historical members to Yahoo ticker identity"
        ),
        "limitation": (
            "membership reconstruction does not guarantee Yahoo retains OHLCV for every "
            "delisted code, and a reused four-character code may represent multiple issuer "
            "episodes; price coverage/identity must be measured separately"
        ),
    }
    with open(OUT / "jpx_point_in_time_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
