from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Iterable, Mapping


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def metrics(rows: Iterable[Mapping], cost: float = 0.005) -> dict:
    rows = list(rows)
    status_counts = Counter(str(r.get("status", "MISSING_STATUS")) for r in rows)
    resolved = []
    for r in rows:
        if str(r.get("status")) != "RESOLVED":
            continue
        gross = _float(r.get("ret5bd_gross"))
        if gross is None:
            raise ValueError("RESOLVED row missing numeric ret5bd_gross")
        resolved.append(gross)

    out = {
        "rows": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "resolved": len(resolved),
        "unresolved_or_pending": len(rows) - len(resolved),
        "cost_assumption": cost,
    }
    if not resolved:
        return out

    net = [x - cost for x in resolved]
    desc = sorted(net, reverse=True)
    out.update(
        net_mean=mean(net),
        net_median=median(net),
        net_win_rate=sum(x > 0 for x in net) / len(net),
        gross_ge10_rate=sum(x >= 0.10 for x in resolved) / len(resolved),
        gross_ge20_rate=sum(x >= 0.20 for x in resolved) / len(resolved),
        gross_ge50_rate=sum(x >= 0.50 for x in resolved) / len(resolved),
        gross_le10_rate=sum(x <= -0.10 for x in resolved) / len(resolved),
        gross_le20_rate=sum(x <= -0.20 for x in resolved) / len(resolved),
        top1_removed_net_mean=mean(desc[1:]) if len(desc) > 1 else None,
        top3_removed_net_mean=mean(desc[3:]) if len(desc) > 3 else None,
    )
    return out


def build_report(rows: Iterable[Mapping], cost: float = 0.005) -> dict:
    rows = list(rows)
    by_model = defaultdict(list)
    by_month = defaultdict(list)
    for r in rows:
        key = f"{r.get('experiment_id','')}|{r.get('model_freeze_id','')}"
        by_model[key].append(r)
        signal_date = str(r.get("signal_date", ""))
        month = signal_date[:7] if len(signal_date) >= 7 else "UNKNOWN"
        by_month[month].append(r)

    return {
        "scope": "PROSPECTIVE_SHADOW_ONLY",
        "selection_or_threshold_tuning_allowed": False,
        "overall": metrics(rows, cost),
        "by_model_freeze": {k: metrics(v, cost) for k, v in sorted(by_model.items())},
        "by_signal_month": {k: metrics(v, cost) for k, v in sorted(by_month.items())},
    }


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"line {i}: expected object")
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize resolved prospective shadow evidence without tuning models")
    ap.add_argument("--resolved-jsonl", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cost", type=float, default=0.005)
    args = ap.parse_args()
    if args.cost < 0:
        raise ValueError("cost must be nonnegative")
    report = build_report(read_jsonl(args.resolved_jsonl), args.cost)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
