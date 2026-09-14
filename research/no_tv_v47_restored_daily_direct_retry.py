from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import requests

HOST = "query1.finance.yahoo.com"
CONTROL = "7203"
TERMINAL = {400, 404, 410, 422}
RETRYABLE = {429, 502, 503, 504}
PERIOD1 = 1714521600
PERIOD2 = 1768867200


def request_symbol(code: str, max_attempts: int = 4) -> tuple[dict, list[dict]]:
    url = f"https://{HOST}/v8/finance/chart/{code}.T"
    last = None
    for attempt in range(max_attempts):
        try:
            r = requests.get(
                url,
                params={
                    "period1": PERIOD1,
                    "period2": PERIOD2,
                    "interval": "1d",
                    "events": "div,splits",
                    "includePrePost": "false",
                },
                headers={
                    "User-Agent": "Mozilla/5.0 V47OutcomeBlindDirectRetry/1.0",
                    "Accept": "application/json,text/plain,*/*",
                },
                timeout=30,
            )
            status = int(r.status_code)
            if status in TERMINAL:
                return {"symbol": code, "http_status": status, "classification": "terminal_http"}, []
            if status in RETRYABLE:
                last = {"symbol": code, "http_status": status, "classification": "retryable_http"}
                time.sleep(20.0 * (attempt + 1))
                continue
            r.raise_for_status()
            payload = r.json()
            chart = payload.get("chart") or {}
            err = chart.get("error")
            result = (chart.get("result") or [None])[0]
            if err:
                return {
                    "symbol": code,
                    "http_status": status,
                    "classification": "chart_error",
                    "chart_error_code": err.get("code"),
                    "chart_error_description": err.get("description"),
                }, []
            if not result:
                return {"symbol": code, "http_status": status, "classification": "no_result"}, []
            ts = result.get("timestamp") or []
            q = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            rows = []
            for i, t in enumerate(ts):
                vals = []
                ok = True
                for key in ("open", "high", "low", "close", "volume"):
                    a = q.get(key) or []
                    v = a[i] if i < len(a) else None
                    if v is None:
                        ok = False
                        break
                    vals.append(v)
                if not ok:
                    continue
                rows.append({
                    "timestamp": int(t),
                    "symbol": code,
                    "open": float(vals[0]),
                    "high": float(vals[1]),
                    "low": float(vals[2]),
                    "close": float(vals[3]),
                    "volume": float(vals[4]),
                })
            return {
                "symbol": code,
                "http_status": status,
                "classification": "usable" if rows else "no_daily_rows",
                "daily_rows": len(rows),
            }, rows
        except Exception as exc:
            last = {
                "symbol": code,
                "classification": "exception",
                "error_type": type(exc).__name__,
                "error": str(exc)[:300],
            }
            time.sleep(10.0 * (attempt + 1))
    return last or {"symbol": code, "classification": "unknown_failure"}, []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v6-receipt", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--sleep-seconds", type=float, default=3.5)
    args = ap.parse_args()

    v6 = json.loads(args.v6_receipt.read_text(encoding="utf-8"))
    symbols = list(v6["restored_daily_fetch"]["missing_symbols"])
    if len(symbols) != 251:
        raise RuntimeError(f"exact frozen direct-retry population must be 251, got {len(symbols)}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    control_start, _ = request_symbol(CONTROL)
    if control_start.get("classification") != "usable":
        raise RuntimeError(f"provider control unavailable before retry: {control_start}")

    statuses = []
    all_rows = []
    for i, code in enumerate(symbols, 1):
        st, rows = request_symbol(code)
        statuses.append(st)
        all_rows.extend(rows)
        if i % 25 == 0 or i == len(symbols):
            usable = sum(x.get("classification") == "usable" for x in statuses)
            terminal = sum(x.get("classification") == "terminal_http" for x in statuses)
            retryable = sum(x.get("classification") == "retryable_http" for x in statuses)
            print(f"direct retry {i}/{len(symbols)} usable={usable} terminal={terminal} retryable={retryable}", flush=True)
        time.sleep(args.sleep_seconds)

    control_end, _ = request_symbol(CONTROL)

    counts = {}
    for st in statuses:
        k = st.get("classification", "unknown")
        counts[k] = counts.get(k, 0) + 1

    receipt = {
        "scope": "outcome-blind V47 exact-251 direct Yahoo daily retry",
        "source_v6_run": 34788533946,
        "requested_symbols": 251,
        "host": HOST,
        "sleep_seconds": args.sleep_seconds,
        "strategy_outcomes_read": False,
        "model_scores_read": False,
        "control_start": control_start,
        "control_end": control_end,
        "classification_counts": counts,
        "usable_symbols": sorted(st["symbol"] for st in statuses if st.get("classification") == "usable"),
        "terminal_symbols": sorted(st["symbol"] for st in statuses if st.get("classification") == "terminal_http"),
        "unresolved_symbols": sorted(st["symbol"] for st in statuses if st.get("classification") not in {"usable", "terminal_http", "no_result", "no_daily_rows", "chart_error"}),
        "statuses": statuses,
        "next_rule": "Only terminal/unavailable historical codes may advance to official JPX/company identity-continuity verification. Retryable/provider failures remain direct-Yahoo step and must not be aliased.",
        "production_modified": False,
    }
    (args.output_dir / "v47_restored_daily_direct_retry_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (args.output_dir / "v47_restored_daily_direct_rows.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "symbol", "open", "high", "low", "close", "volume"])
        w.writeheader()
        w.writerows(all_rows)
    print(json.dumps({k: receipt[k] for k in ["requested_symbols", "classification_counts", "control_start", "control_end"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
