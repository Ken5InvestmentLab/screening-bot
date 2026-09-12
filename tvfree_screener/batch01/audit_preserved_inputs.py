"""Recheck and document exact hashes and coverage of preserved research inputs."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

from .artifact_store import sha256_file
from .session_calendar import SessionCalendar
from tvfree_screener.reproducibility_manifest import cache_manifest


ARTIFACTS = [
    {
        "artifact_id": "10148332198",
        "name": "no-tv-tenchi-v29-purged-rolling",
        "zip_sha256": "55af5133975e4ab3dfb444a661ba4c74c5cfe077403d8a00d0a1bf6a7db0379a",
        "zip_bytes": 5854,
        "created_at": "2026-09-10T10:49:06Z",
        "expires_at": "2026-09-24T10:49:05Z",
        "artifact_run_id": "34466986752",
        "artifact_run_sha": "a6ccb4e8db6dc8dc39598b7e1694593b32647675",
        "source_run_id": "34466986752",
        "member": "v29_purged_rolling.json",
    },
    {
        "artifact_id": "10264205130",
        "name": "tvfree-frozen-dataset-run80-preserved",
        "zip_sha256": "095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0",
        "zip_bytes": 49866286,
        "created_at": "2026-09-11T12:39:18Z",
        "expires_at": "2026-12-10T12:38:23Z",
        "artifact_run_id": "34599959356",
        "artifact_run_sha": "d03cdff1f27628f44f78d3787b0cc55bfa4bd271",
        "source_run_id": "34545440155",
        "source_run_sha": "5461eef6f35ea2cea2b4bc38ca7177c681681783",
        "member": "tse_daily.csv",
    },
    {
        "artifact_id": "10264251140",
        "name": "tvfree-v7-causal-tail-cache-2023-2025",
        "zip_sha256": "2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198",
        "zip_bytes": 443579,
        "created_at": "2026-09-11T12:45:55Z",
        "expires_at": "2026-12-10T12:39:53Z",
        "artifact_run_id": "34600083474",
        "artifact_run_sha": "ef8754d835ccb39faf783092f969417a3ea74ce9",
        "source_run_id": "34600083474",
        "source_run_sha": "ef8754d835ccb39faf783092f969417a3ea74ce9",
        "member": "v7_causal_tail_cache_2023_2025.csv",
    },
]


def _hash(path: Path) -> str:
    return sha256_file(path)


def _audit_ohlcv(path: Path, calendar: SessionCalendar, member_sha256: str) -> dict[str, object]:
    row_count = 0
    sessions: set[str] = set()
    symbols: set[str] = set()
    by_session: Counter[str] = Counter()
    anomalies: Counter[str] = Counter()
    anomaly_sessions: Counter[str] = Counter()
    examples: dict[str, list[dict[str, object]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = ["date", "open", "high", "low", "close", "volume", "symbol"]
        if reader.fieldnames != expected:
            raise ValueError(f"unexpected OHLCV member schema: {reader.fieldnames}")
        for line_number, row in enumerate(reader, start=2):
            row_count += 1
            date = row["date"]
            symbol = row["symbol"]
            sessions.add(date)
            symbols.add(symbol)
            by_session[date] += 1
            try:
                open_, high, low, close, volume = (
                    float(row[key]) for key in ("open", "high", "low", "close", "volume")
                )
            except (TypeError, ValueError):
                anomalies["non_numeric"] += 1
                continue
            flags = []
            if min(open_, high, low, close) <= 0:
                flags.append("nonpositive_price")
            if volume < 0:
                flags.append("negative_volume")
            if low > min(open_, close):
                flags.append("low_above_open_or_close")
            if high < max(open_, close):
                flags.append("high_below_open_or_close")
            if high < low:
                flags.append("high_below_low")
            for flag in flags:
                anomalies[flag] += 1
                anomaly_sessions[f"{flag}|{date}"] += 1
                sample = examples.setdefault(flag, [])
                if len(sample) < 8:
                    sample.append({
                        "line": line_number, "date": date, "symbol": symbol,
                        "open": open_, "high": high, "low": low, "close": close,
                        "volume": volume,
                    })

    data_first = min(sessions) if sessions else None
    data_last = max(sessions) if sessions else None
    calendar_slice = calendar.slice(data_first, data_last) if data_first is not None else pd.DatetimeIndex([])
    calendar_dates = set(calendar_slice.strftime("%Y-%m-%d"))
    missing_sessions = sorted(calendar_dates - sessions)
    extra_sessions = sorted(sessions - calendar_dates)
    if sessions and (min(sessions) != str(calendar_slice[0].date()) or max(sessions) != str(calendar_slice[-1].date())):
        raise ValueError("OHLCV range endpoints differ from the frozen calendar")
    if missing_sessions or extra_sessions:
        raise ValueError("OHLCV trading dates do not exactly match the frozen XTKS calendar")
    per_day = list(by_session.values())
    return {
        "member": path.name,
        "sha256": member_sha256,
        "bytes": path.stat().st_size,
        "rows": row_count,
        "columns": ["date", "open", "high", "low", "close", "volume", "symbol"],
        "date_range": [min(sessions), max(sessions)],
        "xtks_sessions": len(sessions),
        "calendar_sessions_within_dataset_range": len(calendar_slice),
        "calendar_total_sessions": len(calendar.sessions),
        "calendar_session_match": True,
        "unique_symbols": len(symbols),
        "rows_per_session_min_median_max": [
            min(per_day), sorted(per_day)[len(per_day) // 2], max(per_day)
        ],
        "ohlc_or_volume_anomalies": dict(sorted(anomalies.items())),
        "anomalous_session_counts": {
            key: value for key, value in sorted(anomaly_sessions.items())
        },
        "anomaly_examples": examples,
        "limits": [
            "Yahoo-derived current-survivor coverage is not full historical TSE membership.",
            "OHLCV auto-adjustment and corporate-action reconstruction are not proven by this file.",
            "Daily bars cannot establish queue priority, price-limit fills, or actual execution costs.",
            "A CSV row is not proof that the security was listed or tradable on that date.",
        ],
    }


def audit(base: Path, manifest_path: Path) -> dict[str, object]:
    artifact_dir = base / ".cache" / "artifacts"
    calendar_dir = base / "reference"
    calendar_manifest = json.loads(
        (calendar_dir / "xtks_sessions.manifest.json").read_text(encoding="utf-8")
    )
    calendar = SessionCalendar.from_csv(
        calendar_dir / "xtks_sessions.csv",
        expected_sha256=calendar_manifest["csv_sha256"],
    )

    report: dict[str, object] = {
        "schema_version": 1,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_api_checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": "Ken5InvestmentLab/screening-bot",
        "artifacts": [],
    }
    baseline_path = base.parent / "fixed_baseline_run80.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_sha256 = _hash(baseline_path)
    old = {}
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        old = {item["artifact_id"]: item for item in previous.get("artifacts", [])}
        report["retrieved_at_utc"] = previous.get("retrieved_at_utc", report["retrieved_at_utc"])

    for record in ARTIFACTS:
        member = artifact_dir / str(record["member"])
        if not member.exists():
            raise FileNotFoundError(member)
        item = {
            **record,
            "downloaded_at_utc": old.get(record["artifact_id"], {}).get(
                "downloaded_at_utc", report["retrieved_at_utc"]
            ),
            "member_sha256": _hash(member),
            "member_bytes": member.stat().st_size,
        }
        if record["artifact_id"] == "10264205130":
            expected_sha = (artifact_dir / "tse_daily.sha256").read_text(encoding="utf-8").split()[0]
            if expected_sha != item["member_sha256"]:
                raise ValueError("preserved OHLCV checksum sidecar does not match the data member")
            item["dataset_audit"] = _audit_ohlcv(member, calendar, item["member_sha256"])
            lines = int((artifact_dir / "tse_daily.lines.txt").read_text(encoding="utf-8").split()[0])
            if lines != item["dataset_audit"]["rows"] + 1:
                raise ValueError("preserved OHLCV line-count sidecar does not match parsed rows plus header")
            expected = baseline["hashes"]
            previous_item = old.get(record["artifact_id"], {})
            previous_comparison = previous_item.get("run80_normalized_baseline_comparison", {})
            if (
                previous_item.get("member_sha256") == item["member_sha256"]
                and previous_comparison.get("baseline_json_sha256") == baseline_sha256
                and previous_comparison.get("status") == "MATCH"
            ):
                item["run80_normalized_baseline_comparison"] = {
                    **previous_comparison,
                    "verification_reused_after_member_and_baseline_sha256_match": True,
                }
            else:
                frozen_semantics = cache_manifest(member)
                comparisons = {
                    "historical_rows": frozen_semantics["historical_rows"] == baseline["historical_rows"],
                    "historical_date_symbol_sha256": frozen_semantics["historical_date_symbol_sha256"] == expected["historical_date_symbol_sha256"],
                    "historical_ohlcv_sha256": frozen_semantics["historical_ohlcv_sha256"] == expected["historical_ohlcv_sha256"],
                }
                item["run80_normalized_baseline_comparison"] = {
                    "baseline_json_sha256": baseline_sha256,
                    "historical_cutoff": frozen_semantics["historical_cutoff"],
                    "recomputed": frozen_semantics,
                    "expected": {
                        "historical_rows": baseline["historical_rows"],
                        "historical_date_symbol_sha256": expected["historical_date_symbol_sha256"],
                        "historical_ohlcv_sha256": expected["historical_ohlcv_sha256"],
                    },
                    "checks": comparisons,
                    "status": "MATCH" if all(comparisons.values()) else "MISMATCH",
                    "verification_reused_after_member_and_baseline_sha256_match": False,
                }
                if not all(comparisons.values()):
                    raise ValueError("preserved dataset does not reproduce the frozen run80 source fingerprints")
        elif record["artifact_id"] == "10264251140":
            with member.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                counts: Counter[str] = Counter()
                row_count = 0
                for row in reader:
                    row_count += 1
                    counts[row["date"][:4]] += 1
                item["table_audit"] = {
                    "rows": row_count,
                    "columns": len(reader.fieldnames or []),
                    "rows_by_year": dict(sorted(counts.items())),
                }
            item["source_metadata_sha256"] = _hash(artifact_dir / "v7_causal_tail_cache_meta.json")
        elif record["artifact_id"] == "10148332198":
            payload = json.loads(member.read_text(encoding="utf-8"))
            item["json_top_level_type"] = type(payload).__name__
            item["json_top_level_keys"] = sorted(payload) if isinstance(payload, dict) else []
        report["artifacts"].append(item)
    manifest_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    base = Path(__file__).resolve().parent
    output = base / "PRESERVATION_MANIFEST.json"
    report = audit(base, output)
    print(json.dumps({
        "output": str(output),
        "downloaded_at_utc": report["retrieved_at_utc"],
        "artifacts": len(report["artifacts"]),
        "daily_rows": report["artifacts"][1]["dataset_audit"]["rows"],
        "ohlc_anomalies": report["artifacts"][1]["dataset_audit"]["ohlc_or_volume_anomalies"],
    }, indent=2))


if __name__ == "__main__":
    main()
