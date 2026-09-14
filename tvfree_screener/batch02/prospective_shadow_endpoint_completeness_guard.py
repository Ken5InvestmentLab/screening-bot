from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Mapping, Sequence


def _normalize_symbol(value: object) -> str:
    return str(value or "").strip().replace(".0", "").upper()


def _load_shadow(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"shadow_line_{line_number}_not_object")
        rows.append(item)
    return rows


def _load_daily(path: Path) -> dict[tuple[str, str], Mapping]:
    out: dict[tuple[str, str], Mapping] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"symbol", "date", "open", "close"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError("daily_required_columns_missing:" + ",".join(missing))
        for row_number, row in enumerate(reader, start=2):
            symbol = _normalize_symbol(row.get("symbol"))
            date = str(row.get("date", ""))[:10]
            key = (symbol, date)
            if key in out:
                raise ValueError(f"daily_duplicate_symbol_date:{symbol}|{date}|row={row_number}")
            out[key] = row
    return out


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def audit_endpoint_completeness(
    shadow_rows: Sequence[Mapping],
    daily_by_key: Mapping[tuple[str, str], Mapping],
    sessions: Sequence[str],
) -> dict:
    errors: list[str] = []
    session_list = [str(x) for x in sessions]
    if len(session_list) != len(set(session_list)):
        errors.append("session_calendar_contains_duplicates")
    session_index = {date: i for i, date in enumerate(session_list)}

    required_pairs: set[tuple[str, str, str]] = set()
    mature_candidates = 0
    pending_candidates = 0
    candidate_symbols: set[str] = set()

    for row_number, row in enumerate(shadow_rows, start=1):
        symbol = _normalize_symbol(row.get("symbol"))
        signal_date = str(row.get("signal_date", ""))[:10]
        if not symbol:
            errors.append(f"shadow_row_{row_number}:empty_symbol")
            continue
        candidate_symbols.add(symbol)
        if signal_date not in session_index:
            errors.append(f"shadow_row_{row_number}:signal_date_not_in_calendar:{signal_date}")
            continue
        i = session_index[signal_date]
        if i + 5 >= len(session_list):
            pending_candidates += 1
            continue
        mature_candidates += 1
        required_pairs.add((symbol, session_list[i + 1], "open"))
        required_pairs.add((symbol, session_list[i + 5], "close"))

    missing_pairs: list[str] = []
    invalid_price_pairs: list[str] = []
    endpoint_symbols: set[str] = set()
    for symbol, date, field in sorted(required_pairs):
        row = daily_by_key.get((symbol, date))
        if row is None:
            missing_pairs.append(f"{symbol}|{date}|{field}")
            continue
        endpoint_symbols.add(symbol)
        if not _finite_positive(row.get(field)):
            invalid_price_pairs.append(f"{symbol}|{date}|{field}")

    required_symbols = {symbol for symbol, _, _ in required_pairs}
    missing_symbols = sorted(required_symbols - endpoint_symbols)
    if missing_pairs:
        errors.append(f"missing_required_endpoint_pairs:{len(missing_pairs)}")
    if invalid_price_pairs:
        errors.append(f"invalid_required_endpoint_prices:{len(invalid_price_pairs)}")
    if missing_symbols:
        errors.append(f"missing_required_endpoint_symbols:{len(missing_symbols)}")

    valid = not errors
    return {
        "endpoint_completeness_valid": valid,
        "decision": "ALLOW_SHADOW_ENDPOINT_RESOLUTION" if valid else "BLOCK_SHADOW_ENDPOINT_RESOLUTION",
        "shadow_rows": len(shadow_rows),
        "candidate_symbol_count": len(candidate_symbols),
        "mature_candidate_count": mature_candidates,
        "pending_candidate_count": pending_candidates,
        "required_endpoint_pair_count": len(required_pairs),
        "required_endpoint_symbol_count": len(required_symbols),
        "missing_required_endpoint_pair_count": len(missing_pairs),
        "invalid_required_endpoint_price_count": len(invalid_price_pairs),
        "missing_required_endpoint_symbol_count": len(missing_symbols),
        "missing_required_endpoint_pairs": missing_pairs,
        "invalid_required_endpoint_prices": invalid_price_pairs,
        "missing_required_endpoint_symbols": missing_symbols,
        "errors": errors,
        "integrity": {
            "strategy_outcomes_opened": False,
            "gross_returns_computed": False,
            "thresholds_or_rankers_modified": False,
            "requires_exact_next_xtks_open": True,
            "requires_exact_fifth_xtks_close": True,
            "pending_not_yet_mature_candidates_are_not_failures": True,
            "production_modified": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Fail-closed prospective-shadow symbol/date endpoint completeness audit")
    ap.add_argument("--shadow", type=Path, required=True)
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--sessions", type=Path, required=True)
    args = ap.parse_args()

    shadow = _load_shadow(args.shadow)
    daily = _load_daily(args.daily)
    with args.sessions.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if "date" not in fields:
            raise SystemExit("session calendar requires date column")
        sessions = [str(row["date"])[:10] for row in reader]
    result = audit_endpoint_completeness(shadow, daily, sessions)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["endpoint_completeness_valid"] else 2)


if __name__ == "__main__":
    main()
