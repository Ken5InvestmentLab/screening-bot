from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v13_official_daily as v13
import no_tv_v34_jpx_universe as v34
import no_tv_v35_live_prefilter as v35


def eligible_universe(decision_date: str, workers: int):
    excel_url, universe, excluded, markets = v34.load_universe()
    rows, errors = [], {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {ex.submit(v35.fetch_daily_row, r.yahoo_symbol, decision_date): r for r in universe.itertuples(index=False)}
        for i, f in enumerate(as_completed(fut), 1):
            issue = fut[f]
            try:
                m, err = f.result()
            except Exception as e:
                m, err = None, type(e).__name__
            if m is not None:
                if m["previous_close"] <= 1000 and m["previous_volume"] >= 10000:
                    rows.append({"code": issue.code, "name": issue.name, "market": issue.market, "yahoo_symbol": issue.yahoo_symbol, **m})
            else:
                errors[err or "unknown"] = errors.get(err or "unknown", 0) + 1
            if i % 500 == 0:
                print(f"V36 prefilter {i}/{len(universe)} eligible={len(rows)}", flush=True)
    return excel_url, pd.DataFrame(rows), excluded, markets, errors


def build_current_rows(code: str, yahoo_symbol: str, name: str, market: str, decision_date: str):
    # Yahoo Japan equities require the exchange suffix (normally .T). Keep the
    # canonical JPX code separately for output/model identity.
    with ThreadPoolExecutor(max_workers=2) as ex:
        fh = ex.submit(v13.fetch_interval, code, "1h", "1mo")
        fd = ex.submit(v13.fetch_interval, code, "1d", "1y")
        hc, he = fh.result(); dc, de = fd.result()
    if he:
        return None, "1h_" + str(he)
    if de:
        return None, "1d_" + str(de)
    hourly = base.parse_1h_chart(hc or {})
    daily = v13.parse_daily(dc or {})
    if hourly is None or daily is None or hourly.empty or daily.empty:
        return None, "parse_failed"
    sessions = base.synthetic_sessions(hourly).reset_index(drop=True)
    if sessions.empty:
        return None, "no_sessions"
    svol = sessions.volume.to_numpy(float)
    out = []
    for i, row in sessions.iterrows():
        if str(row.date) != decision_date or int(row.session) not in (9, 13):
            continue
        if float(row.volume) < 5000:
            continue
        asof = v13.build_asof_official(daily, sessions, i)
        if asof is None:
            continue
        tf = base.technical_features(asof)
        if tf is None:
            continue
        prev20 = svol[max(0, i-20):i]
        svr = float(row.volume / np.mean(prev20)) if len(prev20) >= 5 and np.mean(prev20) > 0 else np.nan
        rng = float(row.high - row.low)
        stable_score = int(sum(int(bool(tf.get(c, False))) for c in ["ema25", "macdpos", "stoch75", "bb80", "pre_down3", "gap_up"]))
        out.append({
            "date": decision_date, "session": int(row.session), "symbol": code, "yahoo_symbol": yahoo_symbol,
            "name": name, "market": market,
            "entry": float(row.close), "session_volume": float(row.volume),
            "session13": int(row.session == 13), "log_price": float(np.log(max(float(row.close), 1e-9))),
            "session_ret": float(row.close / row.open - 1) if row.open else np.nan,
            "session_range_pct": float(rng / row.open) if row.open else np.nan,
            "session_body_pct": float((row.close - row.open) / row.open) if row.open else np.nan,
            "session_close_loc": float((row.close - row.low) / rng) if rng > 0 else .5,
            "session_vol_ratio20": svr, "stable_score": stable_score, **tf,
        })
    return pd.DataFrame(out), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision-date", required=True)
    ap.add_argument("--max-workers", type=int, default=24)
    ap.add_argument("--max-symbols", type=int)
    ap.add_argument("--output-dir", default="research_artifacts/v36_live_features")
    a = ap.parse_args()

    excel_url, eligible, excluded, markets, prefilter_errors = eligible_universe(a.decision_date, a.max_workers)
    if eligible.empty:
        raise RuntimeError("no eligible symbols")
    if a.max_symbols:
        eligible = eligible.sort_values("previous_volume", ascending=False).head(a.max_symbols).copy()

    frames, errors, ok = [], {}, 0
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut = {
            ex.submit(build_current_rows, str(r.code), str(r.yahoo_symbol), str(r.name), str(r.market), a.decision_date): str(r.code)
            for r in eligible.itertuples(index=False)
        }
        for i, f in enumerate(as_completed(fut), 1):
            try:
                fr, err = f.result()
            except Exception as e:
                fr, err = None, type(e).__name__
            if fr is not None:
                ok += 1
                if not fr.empty:
                    frames.append(fr)
            elif err:
                errors[err] = errors.get(err, 0) + 1
            if i % 100 == 0:
                print(f"V36 features {i}/{len(eligible)} ok={ok} frames={len(frames)}", flush=True)
    if not frames:
        raise RuntimeError(f"no live feature rows; fetch_errors={errors}")

    data = pd.concat(frames, ignore_index=True)
    data = v11.enrich_cross_sectional(data)
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    data.to_csv(out / "live_features.csv", index=False, encoding="utf-8-sig")

    sessions = {}
    for sess, g in data.groupby("session"):
        top = g.sort_values(["stable_score", "session_vol_ratio20", "session_volume"], ascending=[False, False, False])
        sessions[str(int(sess))] = {
            "rows": len(g),
            "stable_score_counts": {str(k): int(v) for k, v in g.stable_score.value_counts().sort_index().items()},
            "stable6": int((g.stable_score == 6).sum()),
            "top_stable": top[["symbol", "name", "entry", "stable_score", "session_volume", "session_vol_ratio20", "rsi14", "stoch14", "bb_pct"]].head(30).to_dict("records"),
        }
    result = {
        "scope": "Standalone current-session feature snapshot from JPX + Yahoo only. No TradingView, no Google Sheet, no teacher data.",
        "decision_date": a.decision_date,
        "jpx_excel": excel_url,
        "eligible_count": len(eligible),
        "feature_fetch_ok": ok,
        "feature_rows": len(data),
        "sessions": sessions,
        "prefilter_errors": prefilter_errors,
        "feature_errors": errors,
        "jpx_excluded_counts": excluded,
        "jpx_market_counts": markets,
    }
    (out / "v36_live_features.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
