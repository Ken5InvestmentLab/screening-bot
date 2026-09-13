from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class MaturityPolicy:
    min_resolved: int = 40
    min_distinct_signal_dates: int = 20
    min_calendar_span_days: int = 35
    min_distinct_months: int = 2


def _as_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def evaluate_maturity(rows: Iterable[dict], policy: MaturityPolicy | None = None) -> dict:
    policy = policy or MaturityPolicy()
    rows = list(rows)
    resolved = [r for r in rows if str(r.get("status", "")).upper() == "RESOLVED"]

    signal_dates = sorted({_as_date(r["signal_date"]) for r in resolved if r.get("signal_date")})
    months = sorted({d.strftime("%Y-%m") for d in signal_dates})
    span_days = (signal_dates[-1] - signal_dates[0]).days if len(signal_dates) >= 2 else 0

    checks = {
        "resolved_count": len(resolved) >= policy.min_resolved,
        "distinct_signal_dates": len(signal_dates) >= policy.min_distinct_signal_dates,
        "calendar_span_days": span_days >= policy.min_calendar_span_days,
        "distinct_months": len(months) >= policy.min_distinct_months,
    }
    mature = all(checks.values())

    return {
        "mature": mature,
        "decision": "EVIDENCE_MATURE_FOR_REVIEW" if mature else "KEEP_COLLECTING_PROSPECTIVE_EVIDENCE",
        "counts": {
            "total_rows": len(rows),
            "resolved_rows": len(resolved),
            "distinct_signal_dates": len(signal_dates),
            "distinct_months": len(months),
            "calendar_span_days": span_days,
        },
        "thresholds": {
            "min_resolved": policy.min_resolved,
            "min_distinct_signal_dates": policy.min_distinct_signal_dates,
            "min_calendar_span_days": policy.min_calendar_span_days,
            "min_distinct_months": policy.min_distinct_months,
        },
        "checks": checks,
        "integrity": {
            "uses_return_values": False,
            "uses_model_scores": False,
            "changes_model_or_thresholds": False,
            "promotion_authorized": False,
            "note": "Passing this gate only permits evidence review; it never promotes a model automatically.",
        },
    }


def _load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Outcome-free prospective shadow evidence maturity gate")
    ap.add_argument("--shadow-jsonl", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--min-resolved", type=int, default=40)
    ap.add_argument("--min-distinct-signal-dates", type=int, default=20)
    ap.add_argument("--min-calendar-span-days", type=int, default=35)
    ap.add_argument("--min-distinct-months", type=int, default=2)
    args = ap.parse_args()

    policy = MaturityPolicy(
        min_resolved=args.min_resolved,
        min_distinct_signal_dates=args.min_distinct_signal_dates,
        min_calendar_span_days=args.min_calendar_span_days,
        min_distinct_months=args.min_distinct_months,
    )
    result = evaluate_maturity(_load_jsonl(args.shadow_jsonl), policy)
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
