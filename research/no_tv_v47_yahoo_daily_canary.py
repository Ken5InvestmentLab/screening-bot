from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
CONTROL = "7203"
SAMPLE_N = 8
TERMINAL = {400, 404, 410, 422}
RETRYABLE = {429, 502, 503, 504}


def classify(host: str, code: str) -> dict:
    url = f"https://{host}/v8/finance/chart/{code}.T"
    try:
        r = requests.get(
            url,
            params={
                "period1": 1714521600,
                "period2": 1768867200,
                "interval": "1d",
                "events": "div,splits",
                "includePrePost": "false",
            },
            headers={
                "User-Agent": "Mozilla/5.0 V47OutcomeBlindCanary/1.0",
                "Accept": "application/json,text/plain,*/*",
            },
            timeout=30,
        )
        status = int(r.status_code)
        out = {"host": host, "symbol": code, "http_status": status}
        if status in TERMINAL:
            out["classification"] = "terminal_http"
            return out
        if status in RETRYABLE:
            out["classification"] = "retryable_http"
            return out
        r.raise_for_status()
        payload = r.json()
        err = (payload.get("chart") or {}).get("error")
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if err:
            out["classification"] = "chart_error"
            out["chart_error_code"] = err.get("code")
            return out
        timestamps = (result or {}).get("timestamp") or []
        out["classification"] = "usable" if timestamps else "no_result"
        out["timestamp_count"] = len(timestamps)
        return out
    except Exception as exc:
        return {
            "host": host,
            "symbol": code,
            "classification": "exception",
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v6-receipt", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--sleep-seconds", type=float, default=6.0)
    args = ap.parse_args()

    receipt = json.loads(args.v6_receipt.read_text(encoding="utf-8"))
    missing = list(receipt["restored_daily_fetch"]["missing_symbols"])
    if len(missing) != 251:
        raise RuntimeError(f"expected exact v6 missing population 251, got {len(missing)}")

    # Deterministic spread across the exact frozen 251-symbol population.
    if SAMPLE_N == 1:
        sample = [missing[0]]
    else:
        idx = [round(i * (len(missing) - 1) / (SAMPLE_N - 1)) for i in range(SAMPLE_N)]
        sample = [missing[i] for i in idx]

    rows = []
    for host in HOSTS:
        for code in [CONTROL] + sample:
            rows.append(classify(host, code))
            time.sleep(args.sleep_seconds)

    control_rows = [r for r in rows if r["symbol"] == CONTROL]
    sample_rows = [r for r in rows if r["symbol"] != CONTROL]
    control_available = any(r["classification"] == "usable" for r in control_rows)
    any_non_429 = any(
        not (r.get("http_status") == 429 or r.get("classification") == "exception")
        for r in rows
    )
    query2_better = any(
        r["host"] == "query2.finance.yahoo.com"
        and r["classification"] in {"usable", "terminal_http", "no_result", "chart_error"}
        for r in sample_rows
    ) and not any(
        r["host"] == "query1.finance.yahoo.com"
        and r["classification"] in {"usable", "terminal_http", "no_result", "chart_error"}
        for r in sample_rows
    )

    out = {
        "scope": "outcome-blind direct Yahoo daily provider canary",
        "source_v6_run": 34788533946,
        "frozen_missing_population_count": len(missing),
        "sample_symbols": sample,
        "control_symbol": CONTROL,
        "sleep_seconds": args.sleep_seconds,
        "strategy_outcomes_read": False,
        "model_scores_read": False,
        "control_available": control_available,
        "any_non_429_or_terminal_response": any_non_429,
        "query2_fallback_looks_viable": query2_better,
        "requests": rows,
        "decision": (
            "DIRECT_YAHOO_REACHABLE_STAGE_RATE_SAFE_251_RETRY"
            if control_available
            else "DIRECT_YAHOO_STILL_PROVIDER_BLOCKED_DO_NOT_RUN_251"
        ),
        "production_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
