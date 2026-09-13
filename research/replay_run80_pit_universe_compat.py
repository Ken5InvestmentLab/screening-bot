from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import requests


NEW_ARCHIVES = [
    "https://www.jpx.co.jp/listing/stocks/new/",
    "https://www.jpx.co.jp/listing/stocks/new/00-archives-01.html",  # 2025
    "https://www.jpx.co.jp/listing/stocks/new/00-archives-02.html",  # 2024
    "https://www.jpx.co.jp/listing/stocks/new/00-archives-03.html",  # 2023
    "https://www.jpx.co.jp/listing/stocks/new/00-archives-04.html",  # 2022
]
DELIST_ARCHIVES = [
    "https://www.jpx.co.jp/listing/stocks/delisted/",
    "https://www.jpx.co.jp/listing/stocks/delisted/archives-01.html",  # 2025
    "https://www.jpx.co.jp/listing/stocks/delisted/archives-02.html",  # 2024
    "https://www.jpx.co.jp/listing/stocks/delisted/archives-03.html",  # 2023
    "https://www.jpx.co.jp/listing/stocks/delisted/archives-04.html",  # 2022
]


def load_exact_module(path: Path):
    spec = importlib.util.spec_from_file_location("run80_pit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import exact source module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def explicit_discovery(base_url: str) -> list[str]:
    if "/stocks/new/" in base_url:
        return NEW_ARCHIVES
    if "/stocks/delisted/" in base_url:
        return DELIST_ARCHIVES
    raise RuntimeError(f"unexpected JPX base URL: {base_url}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-module", required=True, type=Path)
    ap.add_argument("--current-snapshot", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--anchor-date", default="2026-09-11")
    a = ap.parse_args()

    pit = load_exact_module(a.source_module)

    # Compatibility layer ONLY: current JPX pages are UTF-8, while requests'
    # guessed encoding can decode Japanese market labels as mojibake. The exact
    # source parser/regex then rejects otherwise valid rows as unknown-market.
    def get_utf8(url: str) -> str:
        r = requests.get(url, headers=pit._headers(), timeout=60)
        r.raise_for_status()
        return r.content.decode("utf-8")

    pit._get = get_utf8

    # Compatibility layer ONLY: current JPX archive selector no longer exposes
    # the old href shape expected by the 2026-09-11 source discovery regex.
    pit.discover_archive_pages = explicit_discovery

    snapshot = pd.read_csv(a.current_snapshot, dtype={"code": str})
    if "code" not in snapshot.columns:
        raise RuntimeError("current universe snapshot lacks code column")
    current_codes = set(snapshot["code"].astype(str).str.strip())

    start = pd.Timestamp(a.start).normalize()
    anchor = pd.Timestamp(a.anchor_date).normalize()
    events, unknown = pit.collect_events(start.year, anchor)
    validation = pit.validate_events(events, unknown)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    events.to_csv(out / "jpx_membership_events.csv", index=False)
    unknown.to_csv(out / "jpx_membership_unknown_rows.csv", index=False)

    checkpoints = []
    detail = []
    for date in pd.date_range(start, anchor, freq="MS"):
        members = pit.members_as_of(current_codes, events, date, anchor)
        checkpoints.append({
            "date": date.strftime("%Y-%m-%d"),
            "members": len(members),
            "delta_vs_anchor": len(members) - len(current_codes),
        })
        if date.year >= 2024:
            later_listed = sorted(current_codes - members)
            restored_delisted = sorted(members - current_codes)
            detail.append({
                "date": date.strftime("%Y-%m-%d"),
                "members": len(members),
                "later_listed_count": len(later_listed),
                "restored_delisted_count": len(restored_delisted),
                "later_listed_sample": later_listed[:30],
                "restored_delisted_sample": restored_delisted[:30],
            })

    counts = pd.DataFrame(checkpoints)
    counts.to_csv(out / "jpx_membership_monthly_counts.csv", index=False)
    (out / "jpx_membership_monthly_detail.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "status": "research_only_no_production_writes",
        "method": (
            "exact run80 source membership parser/reversal logic; archive discovery "
            "compatibility only uses explicit current JPX 2022-2025 archive URLs"
        ),
        "source_module": str(a.source_module),
        "start": start.strftime("%Y-%m-%d"),
        "anchor_date": anchor.strftime("%Y-%m-%d"),
        "current_members": len(current_codes),
        "validation": validation,
        "event_counts": {
            str(k): int(v)
            for k, v in events["event"].value_counts().to_dict().items()
        },
        "event_year_counts": {
            str(int(k)): int(v)
            for k, v in events.groupby(events["event_date"].dt.year).size().to_dict().items()
        },
        "selected_checkpoints": {
            row["date"]: {
                "members": int(row["members"]),
                "delta_vs_anchor": int(row["delta_vs_anchor"]),
            }
            for row in checkpoints
            if row["date"] in {
                "2024-10-01", "2025-01-01", "2025-07-01", "2026-01-01", "2026-09-01"
            }
        },
        "strategy_returns_opened": False,
        "model_scores_opened": False,
        "production_writes": False,
        "acceptance_rule": (
            "unknown_market_rows=0 AND same_day_code_collisions=0 AND "
            "valid_for_membership_reconstruction=true"
        ),
        "limitation": (
            "Membership reconstruction alone does not provide historical OHLCV "
            "for restored delisted names. Coverage must be audited before clean backtest."
        ),
    }
    (out / "jpx_point_in_time_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
