from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ATR_CAP = 2.8640659721217943
H2_START = "2025-07-01"


def load_selected(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype={"symbol": str})
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["symbol"] = d["symbol"].astype(str).str.replace(r"\.0$", "", regex=True)
    return d[d["date"].notna()].copy()


def load_daily(path: Path, symbols: set[str]) -> pd.DataFrame:
    parts = []
    for chunk in pd.read_csv(
        path,
        usecols=["date", "open", "close", "symbol"],
        dtype={"symbol": str},
        chunksize=500_000,
    ):
        chunk["symbol"] = chunk["symbol"].astype(str).str.replace(r"\.0$", "", regex=True)
        x = chunk[chunk["symbol"].isin(symbols)].copy()
        if len(x):
            parts.append(x)
    if not parts:
        raise RuntimeError("no matching daily rows")
    d = pd.concat(parts, ignore_index=True)
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d[d["date"].notna()].sort_values(["symbol", "date"]).reset_index(drop=True)
    g = d.groupby("symbol", sort=False)
    d["next_open"] = g["open"].shift(-1)
    d["next_close"] = g["close"].shift(-1)
    d["d5_close"] = g["close"].shift(-5)
    return d[["symbol", "date", "next_open", "next_close", "d5_close"]]


def attach_execution(d: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    x = d.merge(daily, on=["symbol", "date"], how="left", validate="many_to_one")
    x["ret_signalclose_to_d5"] = x["d5_close"] / x["entry"] - 1
    x["ret_nextopen_to_d5"] = x["d5_close"] / x["next_open"] - 1
    x["ret_nextclose_to_d5"] = x["d5_close"] / x["next_close"] - 1
    err = (x["ret_signalclose_to_d5"] - x["perf_5bd"]).abs().max()
    if pd.isna(err) or err > 1e-10:
        raise RuntimeError(f"stored perf mismatch: {err}")
    return x


def stats(d: pd.DataFrame, col: str) -> dict:
    r = pd.to_numeric(d[col], errors="coerce").dropna().to_numpy(float)
    if not len(r):
        return {"n": 0}
    s = np.sort(r)
    return {
        "n": int(len(r)),
        "mean_pct": float(np.mean(r) * 100),
        "median_pct": float(np.median(r) * 100),
        "win_pct": float(np.mean(r > 0) * 100),
        "hit10_pct": float(np.mean(r >= 0.10) * 100),
        "hit20_pct": float(np.mean(r >= 0.20) * 100),
        "loss10_pct": float(np.mean(r <= -0.10) * 100),
        "loss20_pct": float(np.mean(r <= -0.20) * 100),
        "top3_ex_mean_pct": float(np.mean(s[:-3]) * 100) if len(s) > 3 else None,
    }


def summarize(d: pd.DataFrame) -> dict:
    return {
        "signalclose_to_d5": stats(d, "ret_signalclose_to_d5"),
        "nextopen_to_d5": stats(d, "ret_nextopen_to_d5"),
        "nextclose_to_d5": stats(d, "ret_nextclose_to_d5"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v43-min95", type=Path, required=True)
    ap.add_argument("--v42-min95", type=Path, required=True)
    ap.add_argument("--frozen-daily", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()

    y2025 = load_selected(a.v43_min95)
    y2026 = load_selected(a.v42_min95)
    symbols = set(y2025["symbol"]) | set(y2026["symbol"])
    daily = load_daily(a.frozen_daily, symbols)
    y2025 = attach_execution(y2025, daily)
    y2026 = attach_execution(y2026, daily)

    h2 = y2025[y2025["date"] >= H2_START].copy()
    h2_gate = h2[h2["market_median_atr"] <= ATR_CAP].copy()

    result = {
        "scope": "research-only execution-delay audit",
        "return_definition": {
            "original": "signal-session close -> D+5 daily close",
            "next_open": "D+1 daily open -> D+5 daily close",
            "next_close": "D+1 daily close -> D+5 daily close",
        },
        "atr_cap": ATR_CAP,
        "2025_all": summarize(y2025),
        "2025_h2": summarize(h2),
        "2025_h2_frozen_atr_gate": summarize(h2_gate),
        "2026_descriptive": summarize(y2026),
        "session_split_2025": {
            str(int(session)): summarize(g)
            for session, g in y2025.groupby("session", sort=True)
        },
        "session_split_2025_h2": {
            str(int(session)): summarize(g)
            for session, g in h2.groupby("session", sort=True)
        },
        "production_writes": False,
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
