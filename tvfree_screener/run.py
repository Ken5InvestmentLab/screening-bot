#!/usr/bin/env python3
"""TradingView-free TSE screener prototype. TEST ONLY."""
from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from xgboost import XGBClassifier

JPX_LIST_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
FEATURES = [
    "ret1","ret2","ret3","ret5","ret10","ret20","ret40",
    "ma5_gap","ma10_gap","ma20_gap","ma40_gap",
    "volr5","volr10","volr20","volr40","rsi14","atr14p",
    "body_pct","lower_wick","upper_wick","range_pct","gap",
    "pos10","pos20","pos40","pos60","dd10","dd20","dd40","dd60",
    "bounce10","bounce20","bounce40","bounce60","stoch14","bbpct","bbwidth",
    "volz20","log_dv","down3","down5",
    "breadth_ret1_pos","med_ret1","med_ret5","breadth_ma20",
]


def jpx_universe() -> pd.DataFrame:
    r = requests.get(JPX_LIST_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    x = pd.read_excel(io.BytesIO(r.content), dtype={"コード": str})
    market_col = next(c for c in x.columns if "市場" in str(c) and "区分" in str(c))
    code_col = next(c for c in x.columns if str(c).strip() == "コード")
    name_col = next(c for c in x.columns if "銘柄名" in str(c))
    # TSE domestic common shares only: Prime / Standard / Growth.
    keep = x[market_col].astype(str).str.contains("プライム|スタンダード|グロース", regex=True)
    keep &= x[market_col].astype(str).str.contains("内国株式", regex=False)
    out = x.loc[keep, [code_col, name_col, market_col]].copy()
    out.columns = ["code", "name", "market"]
    out["code"] = out["code"].astype(str).str.strip()
    out = out[out["code"].str.match(r"^[0-9A-Z]{4}$", na=False)].drop_duplicates("code")
    out["ticker"] = out["code"] + ".T"
    return out.reset_index(drop=True)


def _chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def fetch_daily(universe: pd.DataFrame, period: str, batch: int = 80) -> pd.DataFrame:
    rows = []
    tickers = universe["ticker"].tolist()
    for no, part in enumerate(_chunk(tickers, batch), 1):
        data = None
        err = None
        for attempt in range(3):
            try:
                data = yf.download(
                    part, period=period, interval="1d", group_by="ticker",
                    auto_adjust=False, actions=False, threads=True,
                    progress=False, timeout=30,
                )
                if data is not None and not data.empty:
                    break
            except Exception as e:
                err = e
            time.sleep(2 ** attempt)
        if data is None or data.empty:
            print(f"WARN batch {no}: no data ({err})")
            continue
        for ticker in part:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if ticker not in data.columns.get_level_values(0):
                        continue
                    z = data[ticker].copy()
                else:
                    z = data.copy()
                z = z.rename(columns={c: str(c).lower() for c in z.columns})
                need = ["open","high","low","close","volume"]
                if not all(c in z.columns for c in need):
                    continue
                z = z[need].dropna(subset=["close"]).reset_index()
                z = z.rename(columns={z.columns[0]: "date"})
                z["symbol"] = ticker[:-2]
                rows.append(z)
            except Exception as e:
                print(f"WARN {ticker}: {e}")
        print(f"downloaded batch {no}/{(len(tickers)+batch-1)//batch}")
    if not rows:
        raise RuntimeError("Yahoo Finance returned no usable rows")
    d = pd.concat(rows, ignore_index=True)
    d["date"] = pd.to_datetime(d["date"]).dt.tz_localize(None).dt.normalize()
    for c in ["open","high","low","close","volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"], keep="last")


def build_features(d: pd.DataFrame) -> pd.DataFrame:
    d = d.sort_values(["symbol","date"]).copy()
    g = d.groupby("symbol", group_keys=False)
    for n in [1,2,3,5,10,20,40]:
        d[f"ret{n}"] = g["close"].pct_change(n, fill_method=None)
    for n in [5,10,20,40]:
        ma = g["close"].transform(lambda s: s.rolling(n, min_periods=n).mean())
        va = g["volume"].transform(lambda s: s.rolling(n, min_periods=n).mean())
        d[f"ma{n}_gap"] = d["close"] / ma - 1
        d[f"volr{n}"] = d["volume"] / va.replace(0, np.nan)
    delta = g["close"].diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    ag = gain.groupby(d["symbol"]).transform(lambda s:s.rolling(14,min_periods=14).mean())
    al = loss.groupby(d["symbol"]).transform(lambda s:s.rolling(14,min_periods=14).mean())
    rs = ag / al.replace(0, np.nan)
    d["rsi14"] = 100 - 100/(1+rs)
    d.loc[(al == 0) & (ag > 0), "rsi14"] = 100
    prev = g["close"].shift(1)
    tr = pd.concat([(d.high-d.low),(d.high-prev).abs(),(d.low-prev).abs()], axis=1).max(axis=1)
    d["atr14p"] = tr.groupby(d["symbol"]).transform(lambda s:s.rolling(14,min_periods=14).mean()) / d.close
    rng = (d.high-d.low).replace(0,np.nan)
    d["body_pct"] = (d.close-d.open)/rng
    d["lower_wick"] = (np.minimum(d.open,d.close)-d.low)/rng
    d["upper_wick"] = (d.high-np.maximum(d.open,d.close))/rng
    d["range_pct"] = (d.high-d.low)/d.close
    d["gap"] = d.open/prev-1
    for n in [10,20,40,60]:
        hi = g["high"].transform(lambda s:s.rolling(n,min_periods=n).max())
        lo = g["low"].transform(lambda s:s.rolling(n,min_periods=n).min())
        d[f"pos{n}"] = (d.close-lo)/(hi-lo).replace(0,np.nan)
        d[f"dd{n}"] = d.close/hi-1
        d[f"bounce{n}"] = d.close/lo-1
    lo14 = g["low"].transform(lambda s:s.rolling(14,min_periods=14).min())
    hi14 = g["high"].transform(lambda s:s.rolling(14,min_periods=14).max())
    d["stoch14"] = 100*(d.close-lo14)/(hi14-lo14).replace(0,np.nan)
    ma20 = g["close"].transform(lambda s:s.rolling(20,min_periods=20).mean())
    sd20 = g["close"].transform(lambda s:s.rolling(20,min_periods=20).std(ddof=0))
    d["bbpct"] = (d.close-(ma20-2*sd20))/(4*sd20).replace(0,np.nan)
    d["bbwidth"] = 4*sd20/ma20
    vm = g["volume"].transform(lambda s:s.rolling(20,min_periods=20).mean())
    vs = g["volume"].transform(lambda s:s.rolling(20,min_periods=20).std(ddof=0))
    d["volz20"] = (d.volume-vm)/vs.replace(0,np.nan)
    d["log_dv"] = np.log1p(d.close*d.volume)
    d["down3"] = g["close"].transform(lambda s:(s.diff()<0).rolling(3,min_periods=3).sum()).astype(float)
    d["down5"] = g["close"].transform(lambda s:(s.diff()<0).rolling(5,min_periods=5).sum()).astype(float)
    d["target5_cc"] = g["close"].shift(-5)/d.close-1
    d["next_open"] = g["open"].shift(-1)
    d["target5_no"] = g["close"].shift(-5)/d.next_open-1
    d["target_end_date"] = g["date"].shift(-5)
    d["prev_close"] = g["close"].shift(1)
    d["prev_volume"] = g["volume"].shift(1)
    bd = d.groupby("date")
    m = pd.DataFrame({
        "breadth_ret1_pos": bd["ret1"].apply(lambda s:(s>0).mean()),
        "med_ret1": bd["ret1"].median(),
        "med_ret5": bd["ret5"].median(),
        "breadth_ma20": bd["ma20_gap"].apply(lambda s:(s>0).mean()),
    }).reset_index()
    d = d.merge(m, on="date", how="left")
    return d.replace([np.inf,-np.inf],np.nan)


def model(seed=42):
    return XGBClassifier(
        n_estimators=180, max_depth=3, learning_rate=.04,
        subsample=.8, colsample_bytree=.8, min_child_weight=25,
        reg_lambda=5, reg_alpha=.2, objective="binary:logistic",
        eval_metric="logloss", n_jobs=4, random_state=seed,
    )


def eligible_rows(f: pd.DataFrame, price_cap: float = 0) -> pd.DataFrame:
    q = f[(f.prev_volume >= 10000) & (f.volume >= 5000) & (f.close >= 20)].copy()
    if price_cap > 0:
        q = q[q.prev_close <= price_cap]
    return q.dropna(subset=FEATURES)


def fit_probabilities(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    out = pred.copy()
    for name, y in {
        "big5": (train.target5_cc >= .05).astype(int),
        "loss10": (train.target5_cc <= -.10).astype(int),
    }.items():
        m = model()
        m.fit(train[FEATURES], y, verbose=False)
        out[f"p_{name}"] = m.predict_proba(out[FEATURES])[:,1]
    return out


def summarize(x: pd.Series) -> dict:
    x = x.dropna()
    if x.empty:
        return {"n":0}
    return {
        "n": int(len(x)), "mean": float(x.mean()), "median": float(x.median()),
        "win_rate": float((x>0).mean()), "hit10_rate": float((x>=.10).mean()),
        "loss10_rate": float((x<=-.10).mean()),
    }


def walk_forward(f: pd.DataFrame, price_cap: float, loss_penalty: float, topk: int) -> tuple[pd.DataFrame, dict]:
    f = eligible_rows(f, price_cap)
    labeled = f.dropna(subset=["target5_cc","target_end_date"]).copy()
    months = pd.period_range(labeled.date.min().to_period("M")+4, labeled.date.max().to_period("M"), freq="M")
    picks = []
    for p in months:
        start, end = p.start_time, p.end_time.normalize()
        train = labeled[labeled.target_end_date < start]
        pred = labeled[(labeled.date >= start) & (labeled.date <= end)]
        if len(train) < 10000 or pred.empty:
            continue
        scored = fit_probabilities(train, pred)
        scored["score"] = scored.p_big5 - loss_penalty*scored.p_loss10
        picks.append(scored.sort_values(["date","score"], ascending=[True,False]).groupby("date").head(topk))
    if not picks:
        return pd.DataFrame(), {"n":0}
    p = pd.concat(picks, ignore_index=True)
    report = {"close_to_5bd": summarize(p.target5_cc), "next_open_to_5bd": summarize(p.target5_no)}
    report["monthly"] = {}
    for month, z in p.groupby(p.date.dt.to_period("M")):
        report["monthly"][str(month)] = summarize(z.target5_cc)
    return p, report


def latest_score(f: pd.DataFrame, price_cap: float, loss_penalty: float, topn: int) -> pd.DataFrame:
    q = eligible_rows(f, price_cap)
    latest = q.date.max()
    pred = q[q.date == latest].copy()
    train = q[(q.target_end_date < latest) & q.target5_cc.notna()].copy()
    if len(train) < 10000:
        raise RuntimeError(f"insufficient training rows: {len(train)}")
    scored = fit_probabilities(train, pred)
    scored["score"] = scored.p_big5 - loss_penalty*scored.p_loss10
    cols = ["date","symbol","close","volume","p_big5","p_loss10","score","rsi14","ret5","ret20","breadth_ma20"]
    return scored.sort_values("score", ascending=False)[cols].head(topn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["backtest","score"], default="backtest")
    ap.add_argument("--period", default="3y")
    ap.add_argument("--price-cap", type=float, default=1000.0, help="0 disables price cap")
    ap.add_argument("--loss-penalty", type=float, default=6.0)
    ap.add_argument("--topk", type=int, default=1)
    ap.add_argument("--topn", type=int, default=20)
    ap.add_argument("--cache", default="tvfree_screener/out/tse_daily.csv")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    outdir = Path("tvfree_screener/out")
    outdir.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache)
    if cache.exists() and not args.refresh:
        daily = pd.read_csv(cache, parse_dates=["date"])
    else:
        u = jpx_universe()
        print(f"JPX domestic common-stock universe: {len(u)}")
        daily = fetch_daily(u, args.period)
        cache.parent.mkdir(parents=True, exist_ok=True)
        daily.to_csv(cache, index=False)
    f = build_features(daily)
    if args.mode == "backtest":
        picks, report = walk_forward(f, args.price_cap, args.loss_penalty, args.topk)
        picks.to_csv(outdir/"walk_forward_picks.csv", index=False)
        with open(outdir/"walk_forward_report.json", "w", encoding="utf-8") as fp:
            json.dump(report, fp, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = latest_score(f, args.price_cap, args.loss_penalty, args.topn)
        s.to_csv(outdir/"latest_candidates.csv", index=False)
        print(s.to_string(index=False))


if __name__ == "__main__":
    main()
