from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v13_official_daily as v13
import no_tv_v18_rank_rolling as v18
import no_tv_v29_purged_rolling as v29

DATA_START = "2024-10-01"
EVAL_START = "2025-01-06"
EVAL_END = "2025-12-30"

THRESHOLDS = [0.90, 0.95, 0.97, 0.98, 0.99]
POLICIES = {
    f"fixed_min{int(th*100):02d}_both": {
        "type": "consensus",
        "mode": "min",
        "threshold": th,
        "guard": {"id": "none"},
        "sessions": "both",
        "cooldown_days": 0,
    }
    for th in THRESHOLDS
}


def load_frozen(path: str):
    use = ["date", "open", "high", "low", "close", "volume", "symbol"]
    d = pd.read_csv(path, usecols=use, dtype={"symbol": str})
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d[d["date"].notna()].copy()
    d["symbol"] = d["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    d = d.sort_values(["symbol", "date"]).reset_index(drop=True)
    d["prev_close"] = d.groupby("symbol", sort=False)["close"].shift(1)
    d["prev_volume"] = d.groupby("symbol", sort=False)["volume"].shift(1)

    window = d[d["date"].between(DATA_START, EVAL_END)].copy()
    elig = window[
        (window["prev_close"] <= 1000)
        & (window["prev_volume"] >= 10000)
    ].copy()
    elig["date_s"] = elig["date"].dt.strftime("%Y-%m-%d")

    monitor_dates = {
        str(sym): set(g["date_s"])
        for sym, g in elig.groupby("symbol", sort=False)
    }
    codes = sorted(monitor_dates)

    eval_elig = elig[pd.to_datetime(elig["date_s"]).between(EVAL_START, EVAL_END)]
    daily_counts = eval_elig.groupby("date_s")["symbol"].nunique()
    prefilter = {
        "data_start": DATA_START,
        "eval_start": EVAL_START,
        "eval_end": EVAL_END,
        "eligible_rows_all": int(len(elig)),
        "unique_symbols_all": int(len(codes)),
        "eval_days": int(len(daily_counts)),
        "eval_daily_min": int(daily_counts.min()) if len(daily_counts) else 0,
        "eval_daily_median": float(daily_counts.median()) if len(daily_counts) else 0.0,
        "eval_daily_mean": float(daily_counts.mean()) if len(daily_counts) else 0.0,
        "eval_daily_max": int(daily_counts.max()) if len(daily_counts) else 0,
        "eval_days_over_1000": int((daily_counts > 1000).sum()),
    }

    keep = d["symbol"].isin(codes)
    slim = d.loc[keep, use].copy()
    slim["date"] = slim["date"].dt.strftime("%Y-%m-%d")
    daily_by_symbol = {
        str(sym): g[["date", "open", "high", "low", "close", "volume"]]
        .sort_values("date")
        .reset_index(drop=True)
        for sym, g in slim.groupby("symbol", sort=False)
    }
    return daily_by_symbol, monitor_dates, codes, prefilter


def build_one(code: str, daily: pd.DataFrame, monitor_dates: set[str]):
    chart, err = base.fetch_chart(code)
    if err:
        return None, err
    hourly = base.parse_1h_chart(chart or {})
    if hourly is None or hourly.empty or len(daily) < 90:
        return None, "parse_failed"
    sessions = base.synthetic_sessions(hourly).reset_index(drop=True)
    if len(sessions) < 120:
        return None, "too_few_sessions"

    dd = daily.copy()
    dd["day_index"] = np.arange(len(dd))
    dd["future_close_5"] = dd["close"].shift(-5)
    dd["exit_date_5bd"] = dd["date"].shift(-5)
    daymap = dd.set_index("date")
    svolume = sessions["volume"].to_numpy(float)

    rows = []
    for i, row in sessions.iterrows():
        dt = str(row.date)
        if dt < DATA_START or dt > EVAL_END:
            continue
        if dt not in monitor_dates or dt not in daymap.index:
            continue
        if int(row.session) not in (9, 13) or float(row.volume) < 5000:
            continue
        asof = v13.build_asof_official(daily, sessions, i)
        if asof is None:
            continue
        tf = base.technical_features(asof)
        if tf is None:
            continue
        prev20 = svolume[max(0, i - 20):i]
        svr = (
            float(row.volume / np.mean(prev20))
            if len(prev20) >= 5 and np.mean(prev20) > 0
            else np.nan
        )
        rng = float(row.high - row.low)
        rec = {
            "date": dt,
            "session": int(row.session),
            "symbol": str(code),
            "entry": float(row.close),
            "session_volume": float(row.volume),
            "session13": int(row.session == 13),
            "log_price": float(np.log(max(float(row.close), 1e-9))),
            "session_ret": float(row.close / row.open - 1) if row.open else np.nan,
            "session_range_pct": float(rng / row.open) if row.open else np.nan,
            "session_body_pct": float((row.close - row.open) / row.open) if row.open else np.nan,
            "session_close_loc": float((row.close - row.low) / rng) if rng > 0 else .5,
            "session_vol_ratio20": svr,
            **tf,
        }
        fc = daymap.loc[dt, "future_close_5"]
        ex = daymap.loc[dt, "exit_date_5bd"]
        rec["perf_5bd"] = float(fc / row.close - 1) if pd.notna(fc) and row.close else np.nan
        rec["exit_date_5bd"] = str(ex) if pd.notna(ex) else ""
        rows.append(rec)
    return pd.DataFrame(rows), None


def build_dataset(path: str, workers: int):
    daily_by_symbol, monitor_dates, codes, prefilter = load_frozen(path)
    frames, errors, ok = [], {}, 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {
            ex.submit(build_one, code, daily_by_symbol[code], monitor_dates[code]): code
            for code in codes
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
                print(f"V43 hourly {i}/{len(codes)} ok={ok} frames={len(frames)}", flush=True)
    if not frames:
        raise RuntimeError(f"no V43 rows; errors={errors}")
    data = pd.concat(frames, ignore_index=True)
    data = data[data["date"].between(DATA_START, EVAL_END)].copy()
    data = v11.enrich_cross_sectional(data)
    return data, prefilter, {
        "requested_symbols": len(codes),
        "ok_symbols": ok,
        "errors": errors,
        "candidate_rows": int(len(data)),
        "candidate_symbols": int(data["symbol"].nunique()),
    }


def blocks(data: pd.DataFrame):
    dates = sorted(data.loc[data["date"].between(EVAL_START, EVAL_END), "date"].unique())
    return [dates[i:i+5] for i in range(0, len(dates), 5) if dates[i:i+5]]


def available_before(data: pd.DataFrame, block_start: str):
    x = data[(data["date"] < block_start) & data["perf_5bd"].notna()].copy()
    x = v29.known_by_test_start(x, block_start)
    if not x.empty and not (x["exit_date_norm"] < block_start).all():
        raise RuntimeError("V43 purge invariant failed")
    return x


def month_stats(parts):
    x = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if x.empty:
        return {}
    return {
        str(m): risk.risk_stats(g)
        for m, g in x.groupby(x["date"].astype(str).str[:7])
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-daily", required=True)
    ap.add_argument("--max-workers", type=int, default=20)
    ap.add_argument("--output-dir", default="research_artifacts/v43_2025_uncapped")
    a = ap.parse_args()

    data, prefilter, fetch = build_dataset(a.frozen_daily, a.max_workers)
    parts = {k: [] for k in POLICIES}
    block_rows = []

    for dates in blocks(data):
        block_start = dates[0]
        available = available_before(data, block_start)
        block = data[data["date"].isin(dates) & data["perf_5bd"].notna()].copy()
        if available.empty or block.empty:
            continue
        if len(available) < 1000:
            raise RuntimeError(f"too little training data before {block_start}: {len(available)}")

        models = v11.fit_models(available, v11.features())
        scored = v11.attach(block, models, v11.features())
        fixed = {}
        for name, policy in POLICIES.items():
            sel = v18.apply_consensus(scored, policy).assign(block_start=block_start)
            parts[name].append(sel)
            fixed[name] = risk.risk_stats(sel)

        block_rows.append({
            "block_start": block_start,
            "block_end": dates[-1],
            "known_rows": int(len(available)),
            "test_rows": int(len(block)),
            "latest_known_exit": str(available["exit_date_norm"].max()),
            "fixed": fixed,
        })
        print(
            f"V43 {block_start}..{dates[-1]} "
            + " ".join(f"{k}={fixed[k]['n']}" for k in POLICIES),
            flush=True,
        )

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    combined, monthly = {}, {}
    for name, frames in parts.items():
        cat = pd.concat(frames, ignore_index=True) if frames else data.iloc[0:0]
        combined[name] = risk.risk_stats(cat)
        monthly[name] = month_stats(frames)
        if len(cat):
            cat.to_csv(out / f"v43_{name}_selected.csv", index=False)

    result = {
        "scope": (
            "Backward-period uncapped prequential audit. Initial history is "
            "2024-10 through 2024-12; evaluation is all of 2025 in 5-signal-day "
            "blocks. Fixed consensus thresholds are not selected from 2025 outcomes."
        ),
        "warning": (
            "This is reverse-time robustness evidence, not prospective blind OOS. "
            "Frozen universe contains current JPX survivors, so survivorship bias remains."
        ),
        "prefilter": prefilter,
        "hourly_fetch": fetch,
        "policies": POLICIES,
        "blocks": block_rows,
        "combined_test": combined,
        "monthly_test": monthly,
        "production_writes": False,
    }
    (out / "v43_2025_uncapped.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
