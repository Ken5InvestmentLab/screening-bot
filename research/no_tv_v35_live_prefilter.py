from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import no_tv_v34_jpx_universe as v34

JST = ZoneInfo("Asia/Tokyo")
UA = v34.UA
ENDPOINTS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
]


def fetch_daily_row(symbol: str, decision_date: str):
    last = None
    for endpoint in ENDPOINTS:
        for attempt in range(3):
            try:
                r = requests.get(
                    endpoint.format(symbol=symbol),
                    params={"range": "1mo", "interval": "1d", "events": "div,splits"},
                    headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"},
                    timeout=20,
                )
                if r.status_code in {429, 502, 503, 504}:
                    last = f"http_{r.status_code}"
                    time.sleep(.4 * (attempt + 1))
                    continue
                r.raise_for_status()
                p = r.json()
                err = p.get("chart", {}).get("error")
                if err:
                    last = err.get("description") or "chart_error"
                    break
                res = p.get("chart", {}).get("result", [None])[0]
                if not res:
                    last = "empty_result"
                    break
                ts = res.get("timestamp") or []
                q = res.get("indicators", {}).get("quote", [{}])[0]
                closes = q.get("close") or []
                vols = q.get("volume") or []
                rows = []
                n = min(len(ts), len(closes), len(vols))
                for i in range(n):
                    if closes[i] is None or vols[i] is None:
                        continue
                    dt = pd.to_datetime(int(ts[i]), unit="s", utc=True).tz_convert("Asia/Tokyo").date().isoformat()
                    if dt >= decision_date:
                        continue
                    c = float(closes[i]); v = float(vols[i])
                    if c > 0 and v >= 0:
                        rows.append((dt, c, v))
                if not rows:
                    return None, "no_completed_prior_bar"
                dt, c, v = rows[-1]
                return {"prior_date": dt, "previous_close": c, "previous_volume": v}, None
            except Exception as e:
                last = type(e).__name__
                time.sleep(.3 * (attempt + 1))
    return None, last or "fetch_failed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision-date", default=datetime.now(JST).date().isoformat())
    ap.add_argument("--max-workers", type=int, default=32)
    ap.add_argument("--max-symbols", type=int)
    ap.add_argument("--price-max", type=float, default=1000.0)
    ap.add_argument("--volume-min", type=float, default=10000.0)
    ap.add_argument("--output-dir", default="research_artifacts/v35_live_prefilter")
    a = ap.parse_args()

    excel_url, universe, excluded, market_counts = v34.load_universe()
    if a.max_symbols:
        universe = universe.head(a.max_symbols).copy()

    rows, errors, failed = [], {}, []
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut = {ex.submit(fetch_daily_row, r.yahoo_symbol, a.decision_date): r for r in universe.itertuples(index=False)}
        for i, f in enumerate(as_completed(fut), 1):
            issue = fut[f]
            try:
                m, err = f.result()
            except Exception as e:
                m, err = None, type(e).__name__
            if m is not None:
                rows.append({"code": issue.code, "name": issue.name, "market": issue.market, "yahoo_symbol": issue.yahoo_symbol, **m})
            else:
                errors[err or "unknown"] = errors.get(err or "unknown", 0) + 1
                failed.append({"code": issue.code, "symbol": issue.yahoo_symbol, "error": err or "unknown"})
            if i % 250 == 0:
                print(f"V35 daily progress {i}/{len(universe)} ok={len(rows)} errors={len(failed)}", flush=True)

    daily = pd.DataFrame(rows)
    if daily.empty:
        raise RuntimeError("Yahoo daily prefilter produced no data")
    eligible = daily[(daily.previous_close <= a.price_max) & (daily.previous_volume >= a.volume_min)].copy()
    eligible = eligible.sort_values(["previous_volume", "code"], ascending=[False, True]).reset_index(drop=True)

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out / "daily_snapshot.csv", index=False, encoding="utf-8-sig")
    eligible.to_csv(out / "eligible_watchlist.csv", index=False, encoding="utf-8-sig")
    success_rate = len(daily) / len(universe) if len(universe) else 0.0
    result = {
        "scope": "Standalone live prefilter from current JPX ordinary stocks + Yahoo daily chart only. No TradingView, no Google Sheet, no teacher data.",
        "decision_date": a.decision_date,
        "filters": {"previous_close_max": a.price_max, "previous_volume_min": a.volume_min},
        "jpx_excel": excel_url,
        "universe_count": len(universe),
        "yahoo_ok": len(daily),
        "yahoo_failed": len(failed),
        "success_rate": success_rate,
        "eligible_count": len(eligible),
        "eligible_prior_date_distribution": eligible.prior_date.value_counts().to_dict(),
        "market_counts_eligible": eligible.market.value_counts().to_dict(),
        "error_counts": errors,
        "failed_examples": failed[:50],
        "top_by_volume": eligible.head(30).to_dict("records"),
        "jpx_excluded_counts": excluded,
        "jpx_market_counts": market_counts,
    }
    (out / "v35_live_prefilter.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
